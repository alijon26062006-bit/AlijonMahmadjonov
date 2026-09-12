// Package config loads and validates the application's environment.
//
// Everything the service needs is read once at start-up and validated together,
// so a misconfigured deployment fails immediately with a list of what is wrong
// rather than at the first request that happens to need a missing value.
package config

import (
	"errors"
	"fmt"
	"net/url"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"time"
)

type Environment string

const (
	EnvDevelopment Environment = "development"
	EnvStaging     Environment = "staging"
	EnvProduction  Environment = "production"
	EnvTest        Environment = "test"
)

func (e Environment) IsProduction() bool  { return e == EnvProduction }
func (e Environment) IsDevelopment() bool { return e == EnvDevelopment || e == EnvTest }

type Config struct {
	Env       Environment
	AppURL    string
	APIURL    string
	Port      int
	LogLevel  string
	LogFormat string

	Database Database
	Redis    Redis
	Storage  Storage
	Auth     Auth
	GitHub   GitHub
	AI       AI
	Mail     Mail
	Payments Payments
	Limits   Limits
}

type Database struct {
	URL              string
	MaxConns         int32
	MinConns         int32
	MaxConnLifetime  time.Duration
	MaxConnIdleTime  time.Duration
	StatementTimeout time.Duration
}

type Redis struct {
	URL       string
	KeyPrefix string
}

type Storage struct {
	// "s3" for any S3-compatible endpoint, "filesystem" for local development.
	Driver        string
	Endpoint      string
	Region        string
	Bucket        string
	PublicBucket  string
	AccessKey     string
	SecretKey     string
	UseSSL        bool
	PublicBaseURL string
	// Local filesystem root, used only by the filesystem driver.
	Root string
	// Lifetime of a signed URL for a private object.
	SignedURLTTL time.Duration
}

type Auth struct {
	// Signs and encrypts session cookies and the at-rest encryption of third
	// party tokens. Both must be at least 32 bytes.
	CookieSecret []byte
	DataKey      []byte
	CookieDomain string
	CookieName   string
	// Sessions are server-side; this is how long one stays valid without use.
	SessionTTL        time.Duration
	SessionIdleTTL    time.Duration
	PasswordMinLen    int
	BcryptCost        int
	MaxFailedLogins   int
	LockoutDuration   time.Duration
	TrustProxyHeaders bool
}

type GitHub struct {
	ClientID     string
	ClientSecret string
	CallbackURL  string
	APIBaseURL   string
	// The OAuth endpoints. Configurable because GitHub Enterprise serves them
	// from the installation's own host, and because a hard-coded host cannot
	// be tested against a fake.
	AuthorizeURL string
	TokenURL     string
	// Scopes requested for a normal connection. Private repository access asks
	// for "repo" separately, on an explicit second consent.
	Scopes []string
}

func (g GitHub) Configured() bool { return g.ClientID != "" && g.ClientSecret != "" }

type AI struct {
	ServiceURL string
	// Shared secret for service-to-service calls between Go and Python.
	ServiceToken string
	Timeout      time.Duration
}

func (a AI) Configured() bool { return a.ServiceURL != "" }

type Mail struct {
	Host        string
	Port        int
	Username    string
	Password    string
	FromAddress string
	FromName    string
	// When false, mail is written to the log and the email_log table instead of
	// being sent — the delivery record still exists, so nothing is faked.
	Enabled bool
}

type Payments struct {
	StripeSecretKey     string
	StripeWebhookSecret string
	PaddleAPIKey        string
	PaddleWebhookSecret string
	// Falls back to "manual" (an administrator records the transfer) when no
	// gateway is configured.
	DefaultProvider string
}

type Limits struct {
	MaxImageBytes     int64
	MaxFileBytes      int64
	MaxRequestBytes   int64
	RequestTimeout    time.Duration
	ShutdownGrace     time.Duration
	RateLimitWindow   time.Duration
	AnonRatePerWindow int
	AuthRatePerWindow int
}

// Load reads the environment, applies defaults and validates the result.
func Load() (*Config, error) {
	var problems []string
	note := func(format string, args ...any) { problems = append(problems, fmt.Sprintf(format, args...)) }

	env := Environment(strDefault("APP_ENV", "development"))
	switch env {
	case EnvDevelopment, EnvStaging, EnvProduction, EnvTest:
	default:
		note("APP_ENV must be development, staging, production or test (got %q)", env)
	}

	cfg := &Config{
		Env:       env,
		AppURL:    strings.TrimRight(strDefault("APP_URL", "http://localhost:3000"), "/"),
		APIURL:    strings.TrimRight(strDefault("API_URL", "http://localhost:8080"), "/"),
		Port:      intDefault("PORT", 8080),
		LogLevel:  strDefault("LOG_LEVEL", "info"),
		LogFormat: strDefault("LOG_FORMAT", map[bool]string{true: "text", false: "json"}[env.IsDevelopment()]),

		Database: Database{
			URL:              os.Getenv("DATABASE_URL"),
			MaxConns:         int32(intDefault("DATABASE_MAX_CONNS", 20)),
			MinConns:         int32(intDefault("DATABASE_MIN_CONNS", 2)),
			MaxConnLifetime:  durDefault("DATABASE_CONN_LIFETIME", time.Hour),
			MaxConnIdleTime:  durDefault("DATABASE_CONN_IDLE", 30*time.Minute),
			StatementTimeout: durDefault("DATABASE_STATEMENT_TIMEOUT", 15*time.Second),
		},
		Redis: Redis{
			URL:       strDefault("REDIS_URL", "redis://localhost:6379/0"),
			KeyPrefix: strDefault("REDIS_PREFIX", "averix"),
		},
		Storage: Storage{
			Driver:        strDefault("S3_DRIVER", "filesystem"),
			Endpoint:      os.Getenv("S3_ENDPOINT"),
			Region:        strDefault("S3_REGION", "us-east-1"),
			Bucket:        strDefault("S3_BUCKET", "averix-private"),
			PublicBucket:  strDefault("S3_PUBLIC_BUCKET", "averix-public"),
			AccessKey:     os.Getenv("S3_ACCESS_KEY"),
			SecretKey:     os.Getenv("S3_SECRET_KEY"),
			UseSSL:        boolDefault("S3_USE_SSL", true),
			PublicBaseURL: strings.TrimRight(os.Getenv("S3_PUBLIC_BASE_URL"), "/"),
			Root:          strDefault("STORAGE_ROOT", "./.storage"),
			SignedURLTTL:  durDefault("S3_SIGNED_URL_TTL", 10*time.Minute),
		},
		Auth: Auth{
			CookieSecret:      []byte(os.Getenv("COOKIE_SECRET")),
			DataKey:           []byte(os.Getenv("DATA_ENCRYPTION_KEY")),
			CookieDomain:      os.Getenv("COOKIE_DOMAIN"),
			CookieName:        strDefault("COOKIE_NAME", "averix_session"),
			SessionTTL:        durDefault("SESSION_TTL", 30*24*time.Hour),
			SessionIdleTTL:    durDefault("SESSION_IDLE_TTL", 14*24*time.Hour),
			PasswordMinLen:    intDefault("PASSWORD_MIN_LENGTH", 10),
			BcryptCost:        intDefault("BCRYPT_COST", 12),
			MaxFailedLogins:   intDefault("MAX_FAILED_LOGINS", 8),
			LockoutDuration:   durDefault("LOCKOUT_DURATION", 15*time.Minute),
			TrustProxyHeaders: boolDefault("TRUST_PROXY_HEADERS", !env.IsDevelopment()),
		},
		GitHub: GitHub{
			ClientID:     os.Getenv("GITHUB_CLIENT_ID"),
			ClientSecret: os.Getenv("GITHUB_CLIENT_SECRET"),
			CallbackURL:  os.Getenv("GITHUB_CALLBACK_URL"),
			APIBaseURL:   strDefault("GITHUB_API_BASE_URL", "https://api.github.com"),
			AuthorizeURL: strDefault("GITHUB_AUTHORIZE_URL", "https://github.com/login/oauth/authorize"),
			TokenURL:     strDefault("GITHUB_TOKEN_URL", "https://github.com/login/oauth/access_token"),
			Scopes:       splitList(strDefault("GITHUB_SCOPES", "read:user,user:email")),
		},
		AI: AI{
			ServiceURL:   strings.TrimRight(os.Getenv("AI_SERVICE_URL"), "/"),
			ServiceToken: os.Getenv("AI_SERVICE_TOKEN"),
			Timeout:      durDefault("AI_SERVICE_TIMEOUT", 30*time.Second),
		},
		Mail: Mail{
			Host:        os.Getenv("SMTP_HOST"),
			Port:        intDefault("SMTP_PORT", 587),
			Username:    os.Getenv("SMTP_USERNAME"),
			Password:    os.Getenv("SMTP_PASSWORD"),
			FromAddress: strDefault("MAIL_FROM_ADDRESS", "no-reply@averix.local"),
			FromName:    strDefault("MAIL_FROM_NAME", "AVERIX"),
		},
		Payments: Payments{
			StripeSecretKey:     os.Getenv("STRIPE_SECRET_KEY"),
			StripeWebhookSecret: os.Getenv("STRIPE_WEBHOOK_SECRET"),
			PaddleAPIKey:        os.Getenv("PADDLE_API_KEY"),
			PaddleWebhookSecret: os.Getenv("PADDLE_WEBHOOK_SECRET"),
			DefaultProvider:     strDefault("PAYMENTS_DEFAULT_PROVIDER", "manual"),
		},
		Limits: Limits{
			MaxImageBytes:     int64(intDefault("MAX_IMAGE_BYTES", 10<<20)),
			MaxFileBytes:      int64(intDefault("MAX_FILE_BYTES", 50<<20)),
			MaxRequestBytes:   int64(intDefault("MAX_REQUEST_BYTES", 1<<20)),
			RequestTimeout:    durDefault("REQUEST_TIMEOUT", 30*time.Second),
			ShutdownGrace:     durDefault("SHUTDOWN_GRACE", 20*time.Second),
			RateLimitWindow:   durDefault("RATE_LIMIT_WINDOW", time.Minute),
			AnonRatePerWindow: intDefault("RATE_LIMIT_ANON", 60),
			AuthRatePerWindow: intDefault("RATE_LIMIT_AUTH", 240),
		},
	}
	cfg.Mail.Enabled = cfg.Mail.Host != ""

	if cfg.Database.URL == "" {
		note("DATABASE_URL is required")
	}
	if _, err := url.Parse(cfg.AppURL); err != nil {
		note("APP_URL is not a valid URL: %v", err)
	}
	if cfg.Port < 1 || cfg.Port > 65535 {
		note("PORT must be between 1 and 65535 (got %d)", cfg.Port)
	}
	if cfg.Database.MinConns > cfg.Database.MaxConns {
		note("DATABASE_MIN_CONNS (%d) exceeds DATABASE_MAX_CONNS (%d)",
			cfg.Database.MinConns, cfg.Database.MaxConns)
	}

	// Secrets: development gets deterministic stand-ins so a fresh checkout
	// runs, production gets no such courtesy.
	if len(cfg.Auth.CookieSecret) < 32 {
		if env.IsDevelopment() {
			cfg.Auth.CookieSecret = []byte("averix-development-cookie-secret-do-not-use-in-production")
		} else {
			note("COOKIE_SECRET must be at least 32 bytes (got %d)", len(cfg.Auth.CookieSecret))
		}
	}
	if len(cfg.Auth.DataKey) < 32 {
		if env.IsDevelopment() {
			cfg.Auth.DataKey = []byte("averix-development-data-key-do-not-use-in-production-either")
		} else {
			note("DATA_ENCRYPTION_KEY must be at least 32 bytes (got %d)", len(cfg.Auth.DataKey))
		}
	}
	if cfg.Auth.BcryptCost < 10 || cfg.Auth.BcryptCost > 15 {
		note("BCRYPT_COST must be between 10 and 15 (got %d)", cfg.Auth.BcryptCost)
	}

	switch cfg.Storage.Driver {
	case "filesystem":
		// A single server keeping uploads on a mounted volume is a legitimate
		// deployment, and it is what the production compose file does. What is
		// not legitimate is landing on the relative development default in
		// production: that writes inside the container, so every upload
		// disappears on the next deployment. Requiring an absolute path makes
		// the operator name a directory they can mount and back up.
		if env.IsProduction() && !filepath.IsAbs(cfg.Storage.Root) {
			note("STORAGE_ROOT must be an absolute path on persistent storage when S3_DRIVER=filesystem in production (got %q)", cfg.Storage.Root)
		}
	case "s3":
		if cfg.Storage.Endpoint == "" {
			note("S3_ENDPOINT is required when S3_DRIVER=s3")
		}
		if cfg.Storage.AccessKey == "" || cfg.Storage.SecretKey == "" {
			note("S3_ACCESS_KEY and S3_SECRET_KEY are required when S3_DRIVER=s3")
		}
	default:
		note("S3_DRIVER must be s3 or filesystem (got %q)", cfg.Storage.Driver)
	}

	// A partially configured integration is worse than an unconfigured one:
	// it looks available and then fails for a user.
	if (cfg.GitHub.ClientID == "") != (cfg.GitHub.ClientSecret == "") {
		note("GITHUB_CLIENT_ID and GITHUB_CLIENT_SECRET must both be set, or neither")
	}
	if cfg.GitHub.Configured() && cfg.GitHub.CallbackURL == "" {
		cfg.GitHub.CallbackURL = cfg.APIURL + "/api/v1/github/callback"
	}
	if cfg.AI.ServiceURL != "" && cfg.AI.ServiceToken == "" && env.IsProduction() {
		note("AI_SERVICE_TOKEN is required in production when AI_SERVICE_URL is set")
	}
	if env.IsProduction() && !strings.HasPrefix(cfg.AppURL, "https://") {
		note("APP_URL must use https in production (got %q)", cfg.AppURL)
	}

	if len(problems) > 0 {
		return nil, fmt.Errorf("invalid configuration:\n  - %s", strings.Join(problems, "\n  - "))
	}
	return cfg, nil
}

// SecureCookies reports whether cookies should carry the Secure attribute.
// Plain-HTTP localhost is the only case where they should not.
func (c *Config) SecureCookies() bool { return !strings.HasPrefix(c.AppURL, "http://") }

var ErrMissing = errors.New("missing configuration")

func strDefault(key, fallback string) string {
	if v := strings.TrimSpace(os.Getenv(key)); v != "" {
		return v
	}
	return fallback
}

func intDefault(key string, fallback int) int {
	if v := strings.TrimSpace(os.Getenv(key)); v != "" {
		if n, err := strconv.Atoi(v); err == nil {
			return n
		}
	}
	return fallback
}

func boolDefault(key string, fallback bool) bool {
	if v := strings.TrimSpace(os.Getenv(key)); v != "" {
		if b, err := strconv.ParseBool(v); err == nil {
			return b
		}
	}
	return fallback
}

func durDefault(key string, fallback time.Duration) time.Duration {
	if v := strings.TrimSpace(os.Getenv(key)); v != "" {
		if d, err := time.ParseDuration(v); err == nil {
			return d
		}
	}
	return fallback
}

func splitList(v string) []string {
	parts := strings.Split(v, ",")
	out := make([]string, 0, len(parts))
	for _, p := range parts {
		if p = strings.TrimSpace(p); p != "" {
			out = append(out, p)
		}
	}
	return out
}
