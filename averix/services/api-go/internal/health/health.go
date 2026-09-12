// Package health exposes liveness and readiness.
//
// /health answers "is the process running" and must never touch a dependency,
// so a database hiccup does not make an orchestrator kill healthy containers.
// /ready answers "should this instance receive traffic" and does check them.
// Neither ever reveals a credential, a hostname or a connection string.
package health

import (
	"context"
	"net/http"
	"sync"
	"time"

	"github.com/averix/api/internal/config"
	"github.com/averix/api/internal/platform/cache"
	"github.com/averix/api/internal/platform/database"
	"github.com/averix/api/internal/platform/httpx"
	"github.com/averix/api/internal/platform/storage"
)

// Checker is one dependency's probe.
type Checker struct {
	Name string
	// Required dependencies failing make the instance not ready; optional ones
	// are reported as degraded so a mail outage does not take the API out of
	// the load balancer.
	Required bool
	Probe    func(context.Context) error
}

type Handlers struct {
	cfg      *config.Config
	checkers []Checker
	version  string
	started  time.Time
}

// Options carries the dependencies to probe. Any may be nil, which is how the
// worker reuses this with a smaller set.
type Options struct {
	DB      *database.DB
	Cache   *cache.Cache
	Storage storage.Store
	Version string
	// Extra probes contributed by modules, e.g. the AI service.
	Extra []Checker
}

func New(cfg *config.Config, opts Options) *Handlers {
	h := &Handlers{cfg: cfg, version: opts.Version, started: time.Now()}
	if h.version == "" {
		h.version = "dev"
	}

	if opts.DB != nil {
		h.checkers = append(h.checkers, Checker{
			Name: "database", Required: true,
			Probe: opts.DB.Ping,
		})
	}
	if opts.Cache != nil {
		// Redis carries the rate limiter and the WebSocket fan-out. The API
		// degrades rather than fails without it (the limiter fails open, the
		// socket falls back to per-instance delivery), so it is not required
		// for readiness.
		h.checkers = append(h.checkers, Checker{
			Name: "cache", Required: false,
			Probe: opts.Cache.Ping,
		})
	}
	if opts.Storage != nil {
		h.checkers = append(h.checkers, Checker{
			Name: "storage", Required: true,
			Probe: opts.Storage.Health,
		})
	}
	h.checkers = append(h.checkers, opts.Extra...)
	return h
}

func (h *Handlers) Register(r *httpx.Router) {
	r.GET("/health", h.live)
	r.GET("/ready", h.ready)
}

func (h *Handlers) live(w http.ResponseWriter, r *http.Request) error {
	return httpx.JSON(w, http.StatusOK, map[string]any{
		"status":     "ok",
		"service":    "averix-api",
		"version":    h.version,
		"uptime_sec": int(time.Since(h.started).Seconds()),
	})
}

type componentStatus struct {
	Status    string `json:"status"`
	LatencyMS int64  `json:"latency_ms"`
	Required  bool   `json:"required"`
	// A short, non-sensitive reason. The full error goes to the log.
	Detail string `json:"detail,omitempty"`
}

func (h *Handlers) ready(w http.ResponseWriter, r *http.Request) error {
	// A readiness probe that can hang is worse than one that fails.
	ctx, cancel := context.WithTimeout(r.Context(), 4*time.Second)
	defer cancel()

	type result struct {
		name   string
		status componentStatus
	}
	results := make([]result, len(h.checkers))
	var wg sync.WaitGroup
	for i, c := range h.checkers {
		wg.Add(1)
		go func(i int, c Checker) {
			defer wg.Done()
			start := time.Now()
			err := c.Probe(ctx)
			st := componentStatus{
				Status:    "ok",
				LatencyMS: time.Since(start).Milliseconds(),
				Required:  c.Required,
			}
			if err != nil {
				st.Status = "failing"
				// Deliberately generic: a readiness endpoint is usually
				// reachable from more places than the API itself, and a
				// connection string in its body would be a gift.
				st.Detail = "not reachable"
			}
			results[i] = result{name: c.Name, status: st}
		}(i, c)
	}
	wg.Wait()

	components := make(map[string]componentStatus, len(results))
	ready := true
	degraded := false
	for _, res := range results {
		components[res.name] = res.status
		if res.status.Status != "ok" {
			if res.status.Required {
				ready = false
			} else {
				degraded = true
			}
		}
	}

	status := "ready"
	code := http.StatusOK
	switch {
	case !ready:
		status, code = "not_ready", http.StatusServiceUnavailable
	case degraded:
		status = "degraded"
	}

	return httpx.JSON(w, code, map[string]any{
		"status":     status,
		"version":    h.version,
		"components": components,
	})
}
