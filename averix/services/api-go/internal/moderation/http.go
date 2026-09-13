package moderation

import (
	"net/http"
	"strconv"

	"github.com/google/uuid"

	"github.com/averix/api/internal/platform/httpx"
	"github.com/averix/api/internal/security"
)

type Handlers struct{ svc *Service }

func NewHandlers(svc *Service) *Handlers { return &Handlers{svc: svc} }

type Middleware struct {
	Require         httpx.Middleware
	CSRF            httpx.Middleware
	RequireStaff    httpx.Middleware
	RateLimitReport httpx.Middleware
}

func (h *Handlers) Register(r *httpx.Router, mw Middleware) {
	// Anyone signed in may report. The reasons list is public so the form
	// can render before the person decides.
	r.Group("/reports").GET("/reasons", h.reasons)
	user := r.Group("/reports", mw.Require, mw.CSRF)
	user.POST("", mw.RateLimitReport(h.report))

	staff := r.Group("/admin/moderation", mw.Require, mw.RequireStaff)
	staff.GET("/queue", h.queue)
	staff.GET("/reports", h.reports)

	write := r.Group("/admin/moderation", mw.Require, mw.RequireStaff, mw.CSRF)
	write.POST("/queue/{id}/decide", h.decide)
	write.POST("/reports/{id}/resolve", h.resolveReport)
}

func (h *Handlers) reasons(w http.ResponseWriter, r *http.Request) error {
	return httpx.JSON(w, http.StatusOK, ReportReasons())
}

func (h *Handlers) report(w http.ResponseWriter, r *http.Request) error {
	var body ReportRequest
	if err := httpx.DecodeJSON(w, r, &body, 16<<10); err != nil {
		return err
	}
	id, err := h.svc.Report(r.Context(), security.FromContext(r.Context()), body)
	if err != nil {
		return err
	}
	return httpx.JSON(w, http.StatusCreated, map[string]any{"id": id, "status": "open"})
}

func paging(r *http.Request) (int, int) {
	limit, _ := strconv.Atoi(r.URL.Query().Get("limit"))
	offset, _ := strconv.Atoi(r.URL.Query().Get("offset"))
	if offset < 0 {
		offset = 0
	}
	return limit, offset
}

func (h *Handlers) queue(w http.ResponseWriter, r *http.Request) error {
	limit, offset := paging(r)
	items, total, err := h.svc.Queue(r.Context(), security.FromContext(r.Context()), r.URL.Query().Get("status"), limit, offset)
	if err != nil {
		return err
	}
	return httpx.JSONMeta(w, http.StatusOK, items, map[string]any{"total": total, "offset": offset})
}

func (h *Handlers) decide(w http.ResponseWriter, r *http.Request) error {
	itemID, err := uuid.Parse(r.PathValue("id"))
	if err != nil {
		return httpx.ErrBadRequest.Wrap(err)
	}
	var body DecideRequest
	if err := httpx.DecodeJSON(w, r, &body, 8<<10); err != nil {
		return err
	}
	item, err := h.svc.Decide(r.Context(), security.FromContext(r.Context()), itemID, body)
	if err != nil {
		return err
	}
	return httpx.JSON(w, http.StatusOK, item)
}

func (h *Handlers) reports(w http.ResponseWriter, r *http.Request) error {
	limit, offset := paging(r)
	out, total, err := h.svc.Reports(r.Context(), security.FromContext(r.Context()), r.URL.Query().Get("status"), limit, offset)
	if err != nil {
		return err
	}
	return httpx.JSONMeta(w, http.StatusOK, out, map[string]any{"total": total, "offset": offset})
}

func (h *Handlers) resolveReport(w http.ResponseWriter, r *http.Request) error {
	reportID, err := uuid.Parse(r.PathValue("id"))
	if err != nil {
		return httpx.ErrBadRequest.Wrap(err)
	}
	var body struct {
		Status     string `json:"status"`
		Resolution string `json:"resolution"`
	}
	if err := httpx.DecodeJSON(w, r, &body, 8<<10); err != nil {
		return err
	}
	if err := h.svc.ResolveReport(r.Context(), security.FromContext(r.Context()), reportID, body.Status, body.Resolution); err != nil {
		return err
	}
	return httpx.JSON(w, http.StatusOK, map[string]any{"status": body.Status})
}
