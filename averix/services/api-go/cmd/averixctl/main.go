// Command averixctl performs the operational tasks a deployment needs:
// migrations, the first administrator, and development seed data.
//
// It is a separate binary from the API so a migration can run as a job that
// must succeed before the new API containers start taking traffic.
package main

import (
	"context"
	"errors"
	"fmt"
	"net/http"
	"os"
	"strings"
	"time"

	"github.com/averix/api/internal/config"
	"github.com/averix/api/internal/platform/database"
)

const usage = `averixctl — AVERIX operations

Usage:
  averixctl healthcheck        probe the local API over HTTP (used by Docker)
  averixctl migrate            apply every pending migration
  averixctl migrate status     list migrations and whether they are applied
  averixctl migrate rollback   revert the most recent migration
  averixctl create-admin       create or promote an administrator (interactive)
  averixctl verify-email       confirm an address when mail is not configured yet
  averixctl chat-test          send a test line to the staff chat and say why not
  averixctl seed               load development demo data (refused in production)
  averixctl health             check that every dependency is reachable

Every command reads its configuration from the environment, the same way the
API does, so there is no second place for a connection string to drift.
`

func main() {
	if err := run(os.Args[1:]); err != nil {
		fmt.Fprintf(os.Stderr, "averixctl: %v\n", err)
		os.Exit(1)
	}
}

func run(args []string) error {
	if len(args) == 0 {
		fmt.Print(usage)
		return nil
	}

	ctx := context.Background()
	switch args[0] {
	case "migrate":
		return migrateCmd(ctx, args[1:])
	case "verify-email":
		return verifyEmailCmd(ctx, args[1:])
	case "create-admin":
		return createAdminCmd(ctx, args[1:])
	case "chat-test":
		return chatTestCmd(ctx, args[1:])
	case "seed":
		return seedCmd(ctx, args[1:])
	case "healthcheck":
		return healthcheckCmd(ctx)
	case "health":
		return healthCmd(ctx)
	case "help", "-h", "--help":
		fmt.Print(usage)
		return nil
	default:
		return fmt.Errorf("unknown command %q\n\n%s", args[0], usage)
	}
}

func connect(ctx context.Context) (*config.Config, *database.DB, error) {
	cfg, err := config.Load()
	if err != nil {
		return nil, nil, err
	}
	db, err := database.Connect(ctx, cfg.Database)
	if err != nil {
		return nil, nil, err
	}
	return cfg, db, nil
}

func migrateCmd(ctx context.Context, args []string) error {
	cfg, db, err := connect(ctx)
	if err != nil {
		return err
	}
	defer db.Close()

	sub := "up"
	if len(args) > 0 {
		sub = args[0]
	}

	switch sub {
	case "up":
		applied, err := db.Migrate(ctx)
		if err != nil {
			return err
		}
		if len(applied) == 0 {
			fmt.Println("database is already up to date")
			return nil
		}
		for _, v := range applied {
			fmt.Printf("applied migration %04d\n", v)
		}
		fmt.Printf("%d migration(s) applied\n", len(applied))
		return nil

	case "status":
		rows, err := db.MigrationStatus(ctx)
		if err != nil {
			return err
		}
		pending := 0
		for _, row := range rows {
			mark := "  pending"
			if row["applied"] == true {
				mark = "  applied"
			} else {
				pending++
			}
			fmt.Printf("%s  %04d_%s\n", mark, row["version"], row["name"])
		}
		fmt.Printf("\n%d migration(s), %d pending\n", len(rows), pending)
		return nil

	case "rollback":
		if cfg.Env.IsProduction() && os.Getenv("AVERIX_CONFIRM_ROLLBACK") != "yes" {
			return errors.New("rolling back in production requires AVERIX_CONFIRM_ROLLBACK=yes")
		}
		version, err := db.Rollback(ctx)
		if err != nil {
			return err
		}
		fmt.Printf("rolled back migration %04d\n", version)
		return nil

	default:
		return fmt.Errorf("unknown migrate subcommand %q (want up, status or rollback)", sub)
	}
}

func healthCmd(ctx context.Context) error {
	cfg, db, err := connect(ctx)
	if err != nil {
		return err
	}
	defer db.Close()

	fmt.Printf("environment   %s\n", cfg.Env)
	if err := db.Ping(ctx); err != nil {
		return fmt.Errorf("database unreachable: %w", err)
	}
	fmt.Println("database      ok")

	var applied, total int
	rows, err := db.MigrationStatus(ctx)
	if err != nil {
		return err
	}
	for _, row := range rows {
		total++
		if row["applied"] == true {
			applied++
		}
	}
	fmt.Printf("migrations    %d/%d applied\n", applied, total)
	if applied < total {
		fmt.Println("              run `averixctl migrate` before serving traffic")
	}

	fmt.Printf("github        %s\n", configured(cfg.GitHub.Configured()))
	fmt.Printf("ai service    %s\n", configured(cfg.AI.Configured()))
	fmt.Printf("mail          %s\n", configured(cfg.Mail.Enabled))
	fmt.Printf("storage       %s\n", cfg.Storage.Driver)
	return nil
}

func configured(ok bool) string {
	if ok {
		return "configured"
	}
	return "not configured"
}

func prompt(label string) (string, error) {
	fmt.Print(label)
	var line string
	if _, err := fmt.Scanln(&line); err != nil {
		return "", fmt.Errorf("read %s: %w", strings.TrimSpace(label), err)
	}
	return strings.TrimSpace(line), nil
}

// healthcheckCmd probes the API over its own HTTP port.
//
// This is what the container health check runs. It exists as a subcommand
// because the runtime image is distroless: there is no curl and no shell in
// it, which is the point — but a container still has to be able to say
// whether it is alive.
func healthcheckCmd(ctx context.Context) error {
	port := os.Getenv("PORT")
	if port == "" {
		port = "8080"
	}

	probeCtx, cancel := context.WithTimeout(ctx, 4*time.Second)
	defer cancel()

	request, err := http.NewRequestWithContext(probeCtx, http.MethodGet,
		"http://127.0.0.1:"+port+"/health", nil)
	if err != nil {
		return err
	}
	response, err := http.DefaultClient.Do(request)
	if err != nil {
		return fmt.Errorf("api is not answering on port %s: %w", port, err)
	}
	defer response.Body.Close()
	if response.StatusCode != http.StatusOK {
		return fmt.Errorf("api answered %d", response.StatusCode)
	}
	return nil
}
