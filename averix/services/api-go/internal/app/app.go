// Package app wires the modules together.
//
// Everything is constructed here in one place, so the dependency graph is
// readable and a module cannot quietly reach for a global.
package app

import (
	"context"
	"fmt"
	"net/http"
	"time"

	"github.com/averix/api/internal/audit"
	"github.com/averix/api/internal/auth"
	"github.com/averix/api/internal/config"
	"github.com/averix/api/internal/health"
	"github.com/averix/api/internal/platform/cache"
	"github.com/averix/api/internal/platform/cryptox"
	"github.com/averix/api/internal/platform/database"
	"github.com/averix/api/internal/platform/httpx"
	"github.com/averix/api/internal/platform/storage"
	"github.com/averix/api/internal/taxonomy"
)

// Version is set at build time with -ldflags.
var Version = "dev"

type App struct {
	Cfg     *config.Config
	DB      *database.DB
	Cache   *cache.Cache
	Storage storage.Store
	Audit   *audit.Recorder
	Sealer  *cryptox.Sealer

	AuthStore   *auth.Store
	AuthService *auth.Service
	AuthMW      *auth.Middleware
	Taxonomy    *taxonomy.Store

	redisStartupError error
}

// Build connects to every dependency and constructs the modules.
func Build(ctx context.Context, cfg *config.Config) (*App, error) {
	db, err := database.Connect(ctx, cfg.Database)
	if err != nil {
		return nil, fmt.Errorf("connect to database: %w", err)
	}

	// Redis is optional: the product degrades (see health.New) rather than
	// refusing to start, because a cache outage should not be an outage.
	redis, redisErr := cache.Connect(ctx, cfg.Redis)
	if redisErr != nil {
		redis = nil
	}

	store, err := storage.New(ctx, cfg.Storage)
	if err != nil {
		db.Close()
		return nil, fmt.Errorf("initialise storage: %w", err)
	}

	sealer, err := cryptox.NewSealer(cfg.Auth.DataKey, "third-party-tokens")
	if err != nil {
		db.Close()
		return nil, fmt.Errorf("initialise encryption: %w", err)
	}

	recorder := audit.New(db)
	authStore := auth.NewStore(db)

	a := &App{
		Cfg:         cfg,
		DB:          db,
		Cache:       redis,
		Storage:     store,
		Audit:       recorder,
		Sealer:      sealer,
		AuthStore:   authStore,
		AuthService: auth.NewService(authStore, redis, cfg, recorder, nil),
		AuthMW:      auth.NewMiddleware(authStore, cfg, redis, recorder),
		Taxonomy:    taxonomy.NewStore(db),
	}
	a.redisStartupError = redisErr
	return a, nil
}

// redisStartupError is reported once at start-up so a missing cache is visible
// in the logs rather than only in the readiness endpoint.
func (a *App) RedisStartupError() error { return a.redisStartupError }

func (a *App) Close() {
	if a.Cache != nil {
		_ = a.Cache.Close()
	}
	if a.DB != nil {
		a.DB.Close()
	}
}

// Handler builds the HTTP handler with the global middleware stack.
//
// Order matters: the request id comes first so everything downstream can log
// it, recovery wraps the handlers, and the identity is resolved before any
// endpoint that needs it.
func (a *App) Handler() http.Handler {
	r := httpx.NewRouter()
	r.Use(
		httpx.RequestID(),
		httpx.RealIP(a.Cfg.Auth.TrustProxyHeaders),
		httpx.Logger(),
		httpx.Errors(),
		httpx.Recover(),
		httpx.SecurityHeaders(),
		httpx.CORS([]string{a.Cfg.AppURL}),
		httpx.Timeout(a.Cfg.Limits.RequestTimeout),
	)

	// Health endpoints sit outside /api/v1 and outside authentication, because
	// an orchestrator probing them has no session.
	health.New(a.Cfg, health.Options{
		DB: a.DB, Cache: a.Cache, Storage: a.Storage, Version: Version,
	}).Register(r)

	v1 := r.Group("/api/v1",
		httpx.MaxBody(a.Cfg.Limits.MaxRequestBytes),
		a.AuthMW.Resolve(),
		a.AuthMW.RateLimit("api", a.Cfg.Limits.AnonRatePerWindow, a.Cfg.Limits.RateLimitWindow),
	)

	auth.NewHandlers(a.AuthService, a.AuthMW).Register(v1)
	taxonomy.NewHandlers(a.Taxonomy, a.Cache).Register(v1)

	return r
}

// Serve runs the HTTP server until the context is cancelled, then drains.
func (a *App) Serve(ctx context.Context) error {
	srv := &http.Server{
		Addr:    fmt.Sprintf(":%d", a.Cfg.Port),
		Handler: a.Handler(),
		// Generous enough for a slow mobile connection uploading a photo,
		// tight enough that a stalled client cannot hold a connection open.
		ReadHeaderTimeout: 10 * time.Second,
		ReadTimeout:       2 * time.Minute,
		WriteTimeout:      2 * time.Minute,
		IdleTimeout:       90 * time.Second,
		MaxHeaderBytes:    1 << 20,
	}

	errCh := make(chan error, 1)
	go func() {
		if err := srv.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			errCh <- err
		}
		close(errCh)
	}()

	select {
	case err := <-errCh:
		return err
	case <-ctx.Done():
	}

	// Drain in-flight requests before exiting, so a deployment does not cut a
	// proposal submission in half.
	shutdownCtx, cancel := context.WithTimeout(context.Background(), a.Cfg.Limits.ShutdownGrace)
	defer cancel()
	return srv.Shutdown(shutdownCtx)
}
