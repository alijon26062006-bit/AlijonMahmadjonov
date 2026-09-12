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

	"github.com/google/uuid"

	"github.com/averix/api/internal/aiclient"
	"github.com/averix/api/internal/audit"
	"github.com/averix/api/internal/auth"
	"github.com/averix/api/internal/clients"
	"github.com/averix/api/internal/config"
	"github.com/averix/api/internal/contracts"
	"github.com/averix/api/internal/developers"
	"github.com/averix/api/internal/files"
	"github.com/averix/api/internal/githubint"
	"github.com/averix/api/internal/health"
	"github.com/averix/api/internal/matching"
	"github.com/averix/api/internal/messaging"
	"github.com/averix/api/internal/platform/cache"
	"github.com/averix/api/internal/platform/cryptox"
	"github.com/averix/api/internal/platform/database"
	"github.com/averix/api/internal/platform/httpx"
	"github.com/averix/api/internal/platform/storage"
	"github.com/averix/api/internal/portfolio"
	"github.com/averix/api/internal/preview"
	"github.com/averix/api/internal/projects"
	"github.com/averix/api/internal/proposals"
	"github.com/averix/api/internal/security"
	"github.com/averix/api/internal/settings"
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
	Developers  *developers.Service
	Photos      *developers.PhotoService
	Clients     *clients.Service
	Settings    *settings.Store
	Matching    *matching.Store
	Projects    *projects.Service
	Proposals   *proposals.Service
	Files       *files.Store
	Portfolio   *portfolio.Service
	Contracts   *contracts.Service
	Messaging   *messaging.Service
	AI          *aiclient.Client
	GitHub      *githubint.Service

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
	taxonomyStore := taxonomy.NewStore(db)
	developerStore := developers.NewStore(db, store.PublicURL)
	settingsStore := settings.NewStore(db)
	matchingStore := matching.NewStore(db)
	projectStore := projects.NewStore(db)
	proposalStore := proposals.NewStore(db, store.PublicURL)
	ai := aiclient.New(cfg.AI)
	githubStore := githubint.NewStore(db, sealer)
	githubOAuth := githubint.NewOAuth(cfg.GitHub, db)
	fileStore := files.NewStore(db, store)
	contractStore := contracts.NewStore(db, store.PublicURL)
	messageStore := messaging.NewStore(db, store.PublicURL)
	// One hub for the process. A deployment behind more than one API instance
	// needs the events relayed between them; that is a Redis pub/sub away and
	// is noted in the deployment docs rather than pretended here.
	hub := messaging.NewHub()
	messagingService := messaging.NewService(messageStore, fileStore, hub, settingsStore, nil, nil)
	portfolioStore := portfolio.NewStore(db, store.PublicURL)
	// The prober is the only thing in the product that fetches an address a
	// user supplied, and it does so through the SSRF-safe dialler. Development
	// is the only environment where a loopback preview is possible at all.
	prober := preview.NewProber(cfg.AppURL, cfg.Env.IsDevelopment())

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
		Taxonomy:    taxonomyStore,
		Developers:  developers.NewService(developerStore, taxonomyStore, recorder),
		Photos:      developers.NewPhotoService(developerStore, store, cfg.Limits.MaxImageBytes),
		Clients:     clients.NewService(clients.NewStore(db)),
		Settings:    settingsStore,
		Matching:    matchingStore,
		Projects: projects.NewService(projectStore, taxonomyStore, matchingStore,
			recorder, settingsStore),
		// Fees, moderation and notifications arrive in later phases; the
		// interfaces are nil until then, and every call site checks.
		Proposals: proposals.NewService(proposalStore, matchingStore, recorder,
			settingsStore, nil, nil, nil),
		Files: fileStore,
		Portfolio: portfolio.NewService(portfolioStore,
			portfolio.NewScreenshots(portfolioStore, fileStore, store, cfg.Limits.MaxImageBytes),
			taxonomyStore, prober, recorder, cfg.Env.IsDevelopment()),
		// The funder, the notifier and the workspace messenger arrive in the
		// next phases; until then every call site checks for nil and the
		// endpoints that need them say so plainly rather than pretending.
		Contracts: contracts.NewService(contractStore,
			proposalAcceptance{proposalStore}, projectStore, fileStore, recorder,
			settingsStore, nil, nil, messagingService, cfg.Env.IsDevelopment()),
		Messaging: messagingService,
		AI:        ai,
		GitHub: githubint.NewService(githubStore, githubOAuth, cfg, ai, recorder,
			redis, matchingStore, nil),
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
	//
	// The analysis service is an optional dependency: without it technologies
	// are still detected deterministically, so its absence is degraded rather
	// than not-ready.
	healthOptions := health.Options{
		DB: a.DB, Cache: a.Cache, Storage: a.Storage, Version: Version,
	}
	if a.AI.Configured() {
		healthOptions.Extra = append(healthOptions.Extra, health.Checker{
			Name: "analysis_service", Required: false, Probe: a.AI.Health,
		})
	}
	health.New(a.Cfg, healthOptions).Register(r)

	v1 := r.Group("/api/v1",
		httpx.MaxBody(a.Cfg.Limits.MaxRequestBytes),
		a.AuthMW.Resolve(),
		a.AuthMW.RateLimit("api", a.Cfg.Limits.AnonRatePerWindow, a.Cfg.Limits.RateLimitWindow),
	)

	auth.NewHandlers(a.AuthService, a.AuthMW).Register(v1)
	taxonomy.NewHandlers(a.Taxonomy, a.Cache).Register(v1)

	developers.NewHandlers(a.Developers, a.Photos, a.Cfg.Limits.MaxImageBytes).
		Register(v1, developers.Middleware{
			Require:         a.AuthMW.Require(),
			CSRF:            a.AuthMW.CSRF(),
			RequireDev:      a.AuthMW.RequireRole(security.RoleDeveloper),
			RateLimitUpload: a.AuthMW.RateLimit("upload", 30, time.Hour),
		})

	clients.NewHandlers(a.Clients).Register(v1, clients.Middleware{
		Require:       a.AuthMW.Require(),
		CSRF:          a.AuthMW.CSRF(),
		RequireClient: a.AuthMW.RequireRole(security.RoleClient),
	})

	projects.NewHandlers(a.Projects).Register(v1, projects.Middleware{
		Require:        a.AuthMW.Require(),
		CSRF:           a.AuthMW.CSRF(),
		RequireClient:  a.AuthMW.RequireRole(security.RoleClient),
		RequireDev:     a.AuthMW.RequireRole(security.RoleDeveloper),
		VerifiedEmail:  a.AuthMW.RequireVerifiedEmail(),
		RateLimitWrite: a.AuthMW.RateLimitOnSuccess("project_create", 20, time.Hour),
	})

	proposals.NewHandlers(a.Proposals, a.Projects.Store()).Register(v1, proposals.Middleware{
		Require:       a.AuthMW.Require(),
		CSRF:          a.AuthMW.CSRF(),
		RequireClient: a.AuthMW.RequireRole(security.RoleClient),
		RequireDev:    a.AuthMW.RequireRole(security.RoleDeveloper),
		VerifiedEmail: a.AuthMW.RequireVerifiedEmail(),
		// The durable per-day cap lives in the service; this is the burst
		// guard, which protects the endpoint rather than the marketplace.
		RateLimitWrite: a.AuthMW.RateLimitOnSuccess("proposal_submit", 20, time.Hour),
	})

	contracts.NewHandlers(a.Contracts).Register(v1, contracts.Middleware{
		Require:       a.AuthMW.Require(),
		CSRF:          a.AuthMW.CSRF(),
		RequireClient: a.AuthMW.RequireRole(security.RoleClient),
		VerifiedEmail: a.AuthMW.RequireVerifiedEmail(),
		// Hiring is rate limited on success only: a client fixing a validation
		// error should not burn their allowance.
		RateLimitHire: a.AuthMW.RateLimitOnSuccess("contract_sign", 20, time.Hour),
	})

	messaging.NewHandlers(a.Messaging, a.Files, a.Cfg.AppURL, a.Cfg.Limits.MaxFileBytes).
		Register(v1, messaging.Middleware{
			Require: a.AuthMW.Require(),
			CSRF:    a.AuthMW.CSRF(),
			// Generous: a working conversation is fast. The flood guard in the
			// service is what protects the other person's attention.
			RateLimitSend:   a.AuthMW.RateLimit("message_send", 300, time.Hour),
			RateLimitUpload: a.AuthMW.RateLimit("attachment_upload", 100, time.Hour),
		})

	portfolio.NewHandlers(a.Portfolio, a.Cfg.Limits.MaxImageBytes).
		Register(v1, portfolio.Middleware{
			Require:         a.AuthMW.Require(),
			CSRF:            a.AuthMW.CSRF(),
			RequireDev:      a.AuthMW.RequireRole(security.RoleDeveloper),
			RateLimitUpload: a.AuthMW.RateLimit("portfolio_upload", 60, time.Hour),
			// A probe is an outbound request on our address, so it is the
			// tightest allowance in the product.
			RateLimitProbe: a.AuthMW.RateLimit("portfolio_probe", 20, time.Hour),
		})

	// Object serving. Registered under /api/v1 because that is where the
	// filesystem driver's URLs point by default.
	files.NewHandlers(a.Storage).Register(v1)

	githubint.NewHandlers(a.GitHub).Register(v1, githubint.Middleware{
		Require:    a.AuthMW.Require(),
		CSRF:       a.AuthMW.CSRF(),
		RequireDev: a.AuthMW.RequireRole(security.RoleDeveloper),
		// A sync costs GitHub API quota and several seconds of work, so it is
		// limited well below the general write allowance.
		RateLimitSync: a.AuthMW.RateLimit("github_sync", 6, time.Hour),
	})

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

// proposalAcceptance adapts the proposals store to what contracts needs.
//
// The two modules stay independent this way: proposals knows nothing about
// contracts, contracts declares the shape it needs, and the translation
// between them lives here, where the graph is already visible.
type proposalAcceptance struct {
	store *proposals.Store
}

func (p proposalAcceptance) AcceptanceFacts(ctx context.Context,
	proposalID uuid.UUID) (contracts.Acceptance, error) {

	facts, err := p.store.AcceptanceFacts(ctx, proposalID)
	if err != nil {
		return contracts.Acceptance{}, err
	}
	out := contracts.Acceptance{
		ProposalID:    facts.ProposalID,
		ProjectID:     facts.ProjectID,
		ProjectTitle:  facts.ProjectTitle,
		ProjectStatus: facts.ProjectStatus,
		ClientID:      facts.ClientID,
		DeveloperID:   facts.DeveloperID,
		Status:        facts.Status,
		AmountMinor:   facts.AmountMinor,
		Currency:      facts.Currency,
		DeliveryDays:  facts.DeliveryDays,
	}
	for _, milestone := range facts.Milestones {
		var due *time.Time
		if milestone.Days != nil {
			when := time.Now().AddDate(0, 0, *milestone.Days)
			due = &when
		}
		out.Milestones = append(out.Milestones, contracts.NewMilestone{
			Position:    milestone.Position,
			Title:       milestone.Title,
			Detail:      milestone.Detail,
			AmountMinor: milestone.AmountMinor,
			DueOn:       due,
		})
	}
	return out, nil
}

func (p proposalAcceptance) MarkAccepted(ctx context.Context, proposalID, contractID uuid.UUID) error {
	return p.store.MarkAccepted(ctx, proposalID, contractID)
}

func (p proposalAcceptance) DeclineOthers(ctx context.Context, projectID, acceptedID uuid.UUID,
	reason string) (int, error) {

	return p.store.DeclineOthers(ctx, projectID, acceptedID, reason)
}
