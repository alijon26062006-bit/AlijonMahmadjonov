package settings

import (
	"net/http"

	"github.com/averix/api/internal/platform/httpx"
)

// Handlers serve the settings the web app is allowed to know about.
//
// There is exactly one endpoint and it is public, because the things it
// carries — the platform fee, upload limits, how long a client has to accept
// delivered work — are printed on screens a visitor can see before signing in.
// Everything else about the configuration stays inside the API.
type Handlers struct{ store *Store }

func NewHandlers(store *Store) *Handlers { return &Handlers{store: store} }

func (h *Handlers) Register(r *httpx.Router) {
	r.GET("/platform/settings", h.public)
}

func (h *Handlers) public(w http.ResponseWriter, r *http.Request) error {
	values, err := h.store.Public(r.Context())
	if err != nil {
		return httpx.Internalf(err, "read public settings")
	}
	return httpx.JSON(w, http.StatusOK, values)
}
