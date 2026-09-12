package main

import (
	"context"
	"errors"
	"fmt"
	"os"
	"strings"
	"syscall"

	"golang.org/x/term"

	"github.com/averix/api/internal/audit"
	"github.com/averix/api/internal/auth"
	"github.com/averix/api/internal/platform/cryptox"
	"github.com/averix/api/internal/platform/validate"
	"github.com/averix/api/internal/security"
)

// createAdminCmd creates the first administrator, or promotes an existing
// account.
//
// There is no self-service route to the admin role and no default admin
// account with a known password: the only way in is someone with shell access
// on the server running this command.
func createAdminCmd(ctx context.Context, args []string) error {
	cfg, db, err := connect(ctx)
	if err != nil {
		return err
	}
	defer db.Close()

	store := auth.NewStore(db)
	recorder := audit.New(db)

	email := flagValue(args, "--email")
	fullName := flagValue(args, "--name")
	username := flagValue(args, "--username")
	password := os.Getenv("AVERIX_ADMIN_PASSWORD")

	if email == "" {
		if email, err = prompt("Email: "); err != nil {
			return err
		}
	}
	v := validate.New()
	email = v.Email("email", email)
	if v.Any() {
		return errors.New(v.Fields()["email"])
	}

	// Promote rather than duplicate when the address already has an account.
	if existing, err := store.AccountByEmail(ctx, email); err == nil {
		for _, r := range existing.Roles {
			if r == security.RoleAdmin {
				fmt.Printf("%s is already an administrator\n", email)
				return nil
			}
		}
		if err := store.AddRole(ctx, existing.ID, security.RoleAdmin); err != nil {
			return fmt.Errorf("grant admin role: %w", err)
		}
		recorder.Record(ctx, audit.Entry{
			Action: audit.ActionRoleGranted, SubjectType: "user", SubjectID: &existing.ID,
			After:  map[string]any{"role": "admin"},
			Detail: "granted by averixctl create-admin",
		})
		fmt.Printf("granted the admin role to the existing account %s\n", email)
		return nil
	} else if !errors.Is(err, auth.ErrNotFound) {
		return fmt.Errorf("look up account: %w", err)
	}

	if fullName == "" {
		if fullName, err = prompt("Full name: "); err != nil {
			return err
		}
	}
	if username == "" {
		if username, err = prompt("Username: "); err != nil {
			return err
		}
	}
	username = v.Username("username", username)
	fullName = v.Required("full_name", "Full name", fullName)
	if v.Any() {
		for field, msg := range v.Fields() {
			fmt.Fprintf(os.Stderr, "  %s: %s\n", field, msg)
		}
		return errors.New("please correct the values above")
	}

	if password == "" {
		// Read without echo, and never from a command-line flag: a password in
		// argv is visible in the process list and the shell history.
		fmt.Print("Password (not shown): ")
		raw, err := term.ReadPassword(int(syscall.Stdin))
		fmt.Println()
		if err != nil {
			return fmt.Errorf("read password: %w", err)
		}
		password = string(raw)

		fmt.Print("Confirm password: ")
		confirm, err := term.ReadPassword(int(syscall.Stdin))
		fmt.Println()
		if err != nil {
			return fmt.Errorf("read confirmation: %w", err)
		}
		if password != string(confirm) {
			return errors.New("the two passwords do not match")
		}
	}

	// Administrators get a higher floor than the product default: this account
	// can release money and suspend users.
	minLen := cfg.Auth.PasswordMinLen
	if minLen < 14 {
		minLen = 14
	}
	pv := validate.New()
	pv.Password("password", password, minLen)
	if pv.Any() {
		return errors.New(pv.Fields()["password"])
	}

	hash, err := cryptox.HashPassword(password, cfg.Auth.BcryptCost)
	if err != nil {
		return fmt.Errorf("hash password: %w", err)
	}

	// Created as a client first, because CreateAccount only supports the two
	// self-service roles and every account needs a profile row; the admin role
	// is then added.
	account, err := store.CreateAccount(ctx, auth.NewAccount{
		Email:        email,
		Username:     username,
		PasswordHash: hash,
		FullName:     fullName,
		Role:         security.RoleClient,
	})
	if err != nil {
		return fmt.Errorf("create account: %w", err)
	}
	if err := store.AddRole(ctx, account.ID, security.RoleAdmin); err != nil {
		return fmt.Errorf("grant admin role: %w", err)
	}
	// The administrator's own address is trusted: they proved control of the
	// server, which is a stronger signal than clicking a link in an email.
	if err := store.MarkEmailVerified(ctx, account.ID); err != nil {
		return fmt.Errorf("mark email verified: %w", err)
	}

	recorder.Record(ctx, audit.Entry{
		ActorID: &account.ID, ActorRole: "admin",
		Action: audit.ActionRegister, SubjectType: "user", SubjectID: &account.ID,
		After:  map[string]any{"role": "admin", "username": username},
		Detail: "created by averixctl create-admin",
	})

	fmt.Printf("\nadministrator created\n  email    %s\n  username %s\n\n", email, username)
	fmt.Printf("Sign in at %s/login and open %s/admin\n", cfg.AppURL, cfg.AppURL)
	return nil
}

func flagValue(args []string, name string) string {
	for i, a := range args {
		if a == name && i+1 < len(args) {
			return strings.TrimSpace(args[i+1])
		}
		if strings.HasPrefix(a, name+"=") {
			return strings.TrimSpace(strings.TrimPrefix(a, name+"="))
		}
	}
	return ""
}
