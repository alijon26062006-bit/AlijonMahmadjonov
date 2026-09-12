package main

import (
	"context"
	"errors"
	"fmt"
	"os"
	"path/filepath"
)

// seedCmd loads development demo data.
//
// Refused in production, and every row it writes is marked is_demo so demo
// content can be identified and removed. Reference data (the taxonomy) is a
// migration, not a seed, precisely so the two never get confused.
func seedCmd(ctx context.Context, args []string) error {
	cfg, db, err := connect(ctx)
	if err != nil {
		return err
	}
	defer db.Close()

	if cfg.Env.IsProduction() {
		return errors.New("seed data must never be loaded in production")
	}

	path := flagValue(args, "--file")
	if path == "" {
		// Looked up relative to the working directory so it works from the
		// repository root and from inside the service directory.
		for _, candidate := range []string{
			"scripts/seed-dev.sql",
			"../../scripts/seed-dev.sql",
			"/app/scripts/seed-dev.sql",
		} {
			if _, statErr := os.Stat(candidate); statErr == nil {
				path = candidate
				break
			}
		}
	}
	if path == "" {
		return errors.New("could not find scripts/seed-dev.sql; pass --file")
	}

	body, err := os.ReadFile(path)
	if err != nil {
		return fmt.Errorf("read %s: %w", path, err)
	}

	if _, err := db.Exec(ctx, string(body)); err != nil {
		return fmt.Errorf("apply %s: %w", filepath.Base(path), err)
	}

	var demoUsers, demoProjects int
	_ = db.QueryRow(ctx, `SELECT count(*) FROM users WHERE is_demo`).Scan(&demoUsers)
	_ = db.QueryRow(ctx, `SELECT count(*) FROM projects WHERE is_demo`).Scan(&demoProjects)

	fmt.Printf("seed data loaded from %s\n", path)
	fmt.Printf("  %d demo accounts, %d demo projects\n", demoUsers, demoProjects)
	fmt.Printf("  every demo account signs in with the password printed in %s\n", filepath.Base(path))
	return nil
}
