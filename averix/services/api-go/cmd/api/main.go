// Command api serves the AVERIX HTTP API.
package main

import (
	"context"
	"fmt"
	"log/slog"
	"os"
	"os/signal"
	"syscall"

	"github.com/averix/api/internal/app"
	"github.com/averix/api/internal/config"
	"github.com/averix/api/internal/platform/logx"
)

func main() {
	if err := run(); err != nil {
		fmt.Fprintf(os.Stderr, "averix-api: %v\n", err)
		os.Exit(1)
	}
}

func run() error {
	cfg, err := config.Load()
	if err != nil {
		// Configuration problems are printed rather than logged: the logger
		// itself is configured from the values that just failed to validate.
		return err
	}

	log := logx.New(cfg.LogLevel, cfg.LogFormat)
	slog.SetDefault(log)

	// SIGTERM is what an orchestrator sends on a rolling deploy; SIGINT is
	// Ctrl-C in development. Both drain rather than drop connections.
	ctx, stop := signal.NotifyContext(context.Background(), syscall.SIGTERM, syscall.SIGINT)
	defer stop()

	application, err := app.Build(ctx, cfg)
	if err != nil {
		return err
	}
	defer application.Close()

	if redisErr := application.RedisStartupError(); redisErr != nil {
		log.Warn("running without Redis: rate limiting fails open and realtime delivery is per-instance",
			"error", redisErr)
	}

	log.Info("averix-api starting",
		"version", app.Version,
		"env", string(cfg.Env),
		"port", cfg.Port,
		"storage_driver", application.Storage.Driver(),
		"github_configured", cfg.GitHub.Configured(),
		"ai_configured", cfg.AI.Configured(),
		"mail_enabled", cfg.Mail.Enabled,
	)

	if err := application.Serve(ctx); err != nil {
		return fmt.Errorf("serve: %w", err)
	}
	log.Info("averix-api stopped cleanly")
	return nil
}
