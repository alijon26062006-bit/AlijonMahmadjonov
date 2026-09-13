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

	"github.com/averix/api/internal/account"
	"github.com/averix/api/internal/admin"
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
	"github.com/averix/api/internal/moderation"
	"github.com/averix/api/internal/notifications"
	"github.com/averix/api/internal/payments"
	"github.com/averix/api/internal/platform/cache"
	"github.com/averix/api/internal/platform/cryptox"
	"github.com/averix/api/internal/platform/database"
	"github.com/averix/api/internal/platform/httpx"
	"github.com/averix/api/internal/platform/storage"
	"github.com/averix/api/internal/portfolio"
	"github.com/averix/api/internal/preview"
	"github.com/averix/api/internal/projects"
	"github.com/averix/api/internal/proposals"
	"github.com/averix/api/internal/reviews"
	"github.com/averix/api/internal/search"
	"github.com/averix/api/internal/security"
	"github.com/averix/api/internal/services"
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
	Payments    *payments.Service
	AI          *aiclient.Client
	GitHub      *githubint.Service
	Notifier    *notifications.Service
	Mailer      *notifications.Mailer
	Reviews     *reviews.Service
	Services    *services.Svc
	Search      *search.Service
	Moderation  *moderation.Service
	Admin       *admin.Service
	Account     *account.Service

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

	// Notifications ride the chat socket for live delivery and the worker for
	// email. The mailer records every message in email_log whether or not
	// SMTP is configured, so "was this sent" always has an answer.
	notificationStore := notifications.NewStore(db, store.PublicURL)
	mailer := notifications.NewMailer(cfg.Mail, cfg.AppURL, cfg.Env.IsProduction(), notificationStore)
	notifier := notifications.NewService(notificationStore, mailer, hub, cfg.Push.Configured())

	// Moderation queues what other modules flag. It needs only the database
	// and the notifier, so it exists before the modules that flag into it.
	moderator := moderation.NewService(moderation.NewStore(db), recorder, notifier)

	messagingService := messaging.NewService(messageStore, fileStore, hub, settingsStore, notifier, moderator)
	portfolioStore := portfolio.NewStore(db, store.PublicURL)
	// The prober is the only thing in the product that fetches an address a
	// user supplied, and it does so through the SSRF-safe dialler. Development
	// is the only environment where a loopback preview is possible at all.
	prober := preview.NewProber(cfg.AppURL, cfg.Env.IsDevelopment())

	// Payments: the manual provider is always present, because an environment
	// with no gateway still has to be able to run a marketplace. Its transfer
	// details come from platform settings, which an administrator fills in
	// once; until they do, it reports itself unconfigured and the product
	// shows a configuration state rather than asking anyone to pay nowhere.
	manual := payments.NewManual(func(ctx context.Context) payments.ManualSettings {
		return manualSettings(ctx, settingsStore)
	})
	paymentRegistry := payments.NewRegistry(manual)
	paymentStore := payments.NewStore(db)

	a := &App{
		Cfg:         cfg,
		DB:          db,
		Cache:       redis,
		Storage:     store,
		Audit:       recorder,
		Sealer:      sealer,
		AuthStore:   authStore,
		AuthService: auth.NewService(authStore, redis, cfg, recorder, mailer),
		AuthMW:      auth.NewMiddleware(authStore, cfg, redis, recorder),
		Taxonomy:    taxonomyStore,
		Developers:  developers.NewService(developerStore, taxonomyStore, recorder),
		Photos:      developers.NewPhotoService(developerStore, store, cfg.Limits.MaxImageBytes),
		Clients:     clients.NewService(clients.NewStore(db)),
		Settings:    settingsStore,
		Matching:    matchingStore,
		Projects: projects.NewService(projectStore, taxonomyStore, matchingStore,
			recorder, settingsStore),
		// The fee resolver arrives with a gateway provider; nil until then,
		// and every call site checks.
		Proposals: proposals.NewService(proposalStore, matchingStore, recorder,
			settingsStore, nil, moderator, notifier),
		Files: fileStore,
		Portfolio: portfolio.NewService(portfolioStore,
			portfolio.NewScreenshots(portfolioStore, fileStore, store, cfg.Limits.MaxImageBytes),
			taxonomyStore, prober, recorder, cfg.Env.IsDevelopment()),
		// The funder is attached below, once payments exists.
		Contracts: contracts.NewService(contractStore,
			proposalAcceptance{proposalStore}, projectStore, fileStore, recorder,
			settingsStore, nil, notifier, messagingService, cfg.Env.IsDevelopment()),
		Messaging: messagingService,
		AI:        ai,
		GitHub: githubint.NewService(githubStore, githubOAuth, cfg, ai, recorder,
			redis, matchingStore, notifier),
		Notifier:   notifier,
		Mailer:     mailer,
		Moderation: moderator,
		Account:    account.NewService(db, authStore, mailer, recorder),
	}
	// Payments needs the contracts service, and contracts needs to know
	// whether money can move at all. Constructing payments second and handing
	// it back is what keeps that mutual need from being a construction cycle.
	a.Payments = payments.NewService(paymentStore, paymentRegistry, a.Contracts,
		recorder, settingsStore, notifier)
	a.Contracts.AttachFunder(a.Payments)
	a.Payments.SyncProviders(ctx)

	// Reviews need contracts to say who is a party; contracts need to tell
	// reviews when a contract finishes. Same shape as the funder.
	a.Reviews = reviews.NewService(reviews.NewStore(db, store.PublicURL), a.Contracts,
		settingsStore, notifier, recorder)
	a.Contracts.AttachCompletion(a.Reviews)

	// Fixed-price services order straight into a contract, so they come after
	// contracts. Moderation arrives with its module; nil until then.
	a.Services = services.NewSvc(services.NewStore(db, store.PublicURL), taxonomyStore,
		a.Contracts, projectStore, settingsStore, moderator, recorder)
	a.Search = search.NewService(search.NewStore(db, store.PublicURL), a.Services.Store(), recorder)
	a.Admin = admin.NewService(admin.NewStore(db), authStore, settingsStore, matchingStore,
		a.Contracts, notifier, recorder, cfg, Version)

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

	payments.NewHandlers(a.Payments).Register(v1, payments.Middleware{
		Require:       a.AuthMW.Require(),
		CSRF:          a.AuthMW.CSRF(),
		RequireClient: a.AuthMW.RequireRole(security.RoleClient),
		RequireAdmin:  a.AuthMW.RequireRole(security.RoleAdmin),
		VerifiedEmail: a.AuthMW.RequireVerifiedEmail(),
		RateLimitFund: a.AuthMW.RateLimitOnSuccess("milestone_fund", 60, time.Hour),
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

	services.NewHandlers(a.Services).Register(v1, services.Middleware{
		Require:       a.AuthMW.Require(),
		CSRF:          a.AuthMW.CSRF(),
		RequireDev:    a.AuthMW.RequireRole(security.RoleDeveloper),
		RequireClient: a.AuthMW.RequireRole(security.RoleClient),
		VerifiedEmail: a.AuthMW.RequireVerifiedEmail(),
		// An order creates a contract; the same allowance as hiring.
		RateLimitOrder: a.AuthMW.RateLimitOnSuccess("service_order", 20, time.Hour),
	})

	staff := a.AuthMW.RequireRole(security.RoleAdmin, security.RoleModerator)
	moderation.NewHandlers(a.Moderation).Register(v1, moderation.Middleware{
		Require:      a.AuthMW.Require(),
		CSRF:         a.AuthMW.CSRF(),
		RequireStaff: staff,
		// Reports are cheap to file and expensive to read; a person who files
		// thirty an hour is not helping.
		RateLimitReport: a.AuthMW.RateLimit("report", 30, time.Hour),
	})
	admin.NewHandlers(a.Admin).Register(v1, admin.Middleware{
		Require:      a.AuthMW.Require(),
		CSRF:         a.AuthMW.CSRF(),
		RequireStaff: staff,
	})
	account.NewHandlers(a.Account, a.AuthMW.ClearCookie).Register(v1, account.Middleware{
		Require:   a.AuthMW.Require(),
		CSRF:      a.AuthMW.CSRF(),
		RateLimit: a.AuthMW.RateLimit("account_sensitive", 10, time.Hour),
	})

	search.NewHandlers(a.Search).Register(v1, search.Middleware{
		Require:       a.AuthMW.Require(),
		CSRF:          a.AuthMW.CSRF(),
		RequireClient: a.AuthMW.RequireRole(security.RoleClient),
		RequireDev:    a.AuthMW.RequireRole(security.RoleDeveloper),
		// Public catalogues are the cheapest thing to scrape; the general
		// anonymous allowance still applies on top.
		RateLimit: a.AuthMW.RateLimit("catalogue", 120, time.Minute),
	})

	reviews.NewHandlers(a.Reviews).Register(v1, reviews.Middleware{
		Require:    a.AuthMW.Require(),
		CSRF:       a.AuthMW.CSRF(),
		RequireDev: a.AuthMW.RequireRole(security.RoleDeveloper),
	})

	notifications.NewHandlers(a.Notifier, a.Cfg.Push.Configured(), a.Cfg.Push.VAPIDPublicKey).
		Register(v1, notifications.Middleware{
			Require: a.AuthMW.Require(),
			CSRF:    a.AuthMW.CSRF(),
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

// manualSettings reads the manual provider's transfer details from platform
// settings, where an administrator enters them once.
//
// Deliberately not environment variables: these change when a bank account
// changes, which is an operational act by a person with an admin session, not
// a redeployment.
func manualSettings(ctx context.Context, store *settings.Store) payments.ManualSettings {
	return payments.ManualSettings{
		AccountName:   store.String(ctx, "payments.manual.account_name", ""),
		AccountNumber: store.String(ctx, "payments.manual.account_number", ""),
		BankName:      store.String(ctx, "payments.manual.bank_name", ""),
		ExtraLabel:    store.String(ctx, "payments.manual.extra_label", ""),
		ExtraValue:    store.String(ctx, "payments.manual.extra_value", ""),
		Note:          store.String(ctx, "payments.manual.note", ""),
	}
}
