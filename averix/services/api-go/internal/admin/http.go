package admin

import (
	"net/http"
	"strconv"
	"strings"
	"time"

	"github.com/google/uuid"

	"github.com/averix/api/internal/contracts"
	"github.com/averix/api/internal/platform/httpx"
	"github.com/averix/api/internal/security"
)

type Handlers struct{ svc *Service }

func NewHandlers(svc *Service) *Handlers { return &Handlers{svc: svc} }

type Middleware struct {
	Require      httpx.Middleware
	CSRF         httpx.Middleware
	RequireStaff httpx.Middleware
}

func (h *Handlers) Register(r *httpx.Router, mw Middleware) {
	// Staff = admin or moderator at the door; each action checks its own
	// permission inside, so a moderator sees the dashboard and not the
	// settings.
	read := r.Group("/admin", mw.Require, mw.RequireStaff)
	read.GET("/overview", h.overview)
	read.GET("/users", h.users)
	read.GET("/users/{id}", h.user)
	read.GET("/users/{id}/projects", h.userProjects)
	read.GET("/users/{id}/payments", h.userPayments)
	read.GET("/users/{id}/security", h.userSecurity)
	read.GET("/users/{id}/history", h.userHistory)
	read.GET("/permissions", h.grantable)
	read.GET("/settings", h.settings)
	read.GET("/flags", h.flags)
	read.GET("/matching/weights", h.weights)
	read.GET("/disputes", h.disputes)
	read.GET("/audit", h.auditLog)

	write := r.Group("/admin", mw.Require, mw.RequireStaff, mw.CSRF)
	write.POST("/users/{id}/suspend", h.suspend)
	write.POST("/users/{id}/unsuspend", h.unsuspend)
	write.POST("/users/{id}/warn", h.warn)
	write.POST("/users/{id}/roles", h.grantRole)
	write.DELETE("/users/{id}/roles/{role}", h.revokeRole)
	write.PUT("/users/{id}/identity", h.verifyIdentity)
	write.POST("/users/{id}/block", h.block)
	write.POST("/users/{id}/unblock", h.unblock)
	write.POST("/users/{id}/permissions", h.grantPermission)
	write.DELETE("/users/{id}/permissions/{permission}", h.revokePermission)
	write.PUT("/settings/{key}", h.setSetting)
	write.PUT("/flags/{key}", h.setFlag)
	write.PUT("/matching/weights", h.setWeights)
	write.POST("/disputes/{id}/resolve", h.resolveDispute)
}

func caller(r *http.Request) *security.Identity { return security.FromContext(r.Context()) }

func pathID(r *http.Request, name string) (uuid.UUID, error) {
	id, err := uuid.Parse(r.PathValue(name))
	if err != nil {
		return uuid.Nil, httpx.ErrBadRequest.Wrap(err)
	}
	return id, nil
}

func (h *Handlers) overview(w http.ResponseWriter, r *http.Request) error {
	o, err := h.svc.Overview(r.Context(), caller(r))
	if err != nil {
		return err
	}
	return httpx.JSON(w, http.StatusOK, o)
}

func (h *Handlers) users(w http.ResponseWriter, r *http.Request) error {
	q := r.URL.Query()
	limit, _ := strconv.Atoi(q.Get("limit"))
	offset, _ := strconv.Atoi(q.Get("offset"))
	query := UserQuery{
		Text:           strings.TrimSpace(q.Get("q")),
		Status:         q.Get("status"),
		Role:           q.Get("role"),
		Identity:       strings.TrimSpace(q.Get("identity")),
		Country:        strings.TrimSpace(q.Get("country")),
		Specialisation: strings.TrimSpace(q.Get("specialisation")),
		Listed:         q.Get("listed") == "true",
		Reported:       q.Get("reported") == "true",
		Limit:          limit, Offset: offset,
	}
	for name, target := range map[string]**time.Time{
		"registered_from": &query.RegisteredFrom,
		"registered_to":   &query.RegisteredTo,
	} {
		raw := strings.TrimSpace(q.Get(name))
		if raw == "" {
			continue
		}
		parsed, err := time.Parse("2006-01-02", raw)
		if err != nil {
			return httpx.Validation(map[string]string{name: "Дата в формате ГГГГ-ММ-ДД."})
		}
		*target = &parsed
	}
	users, total, err := h.svc.Users(r.Context(), caller(r), query)
	if err != nil {
		return err
	}
	return httpx.JSONMeta(w, http.StatusOK, users, map[string]any{"total": total, "offset": offset})
}

func (h *Handlers) user(w http.ResponseWriter, r *http.Request) error {
	id, err := pathID(r, "id")
	if err != nil {
		return err
	}
	d, err := h.svc.User(r.Context(), caller(r), id)
	if err != nil {
		return err
	}
	return httpx.JSON(w, http.StatusOK, d)
}

func (h *Handlers) suspend(w http.ResponseWriter, r *http.Request) error {
	id, err := pathID(r, "id")
	if err != nil {
		return err
	}
	var body SuspendRequest
	if err := httpx.DecodeJSON(w, r, &body, 4<<10); err != nil {
		return err
	}
	if err := h.svc.Suspend(r.Context(), caller(r), id, body); err != nil {
		return err
	}
	return httpx.JSON(w, http.StatusOK, map[string]any{"status": "suspended"})
}

func (h *Handlers) unsuspend(w http.ResponseWriter, r *http.Request) error {
	id, err := pathID(r, "id")
	if err != nil {
		return err
	}
	if err := h.svc.Unsuspend(r.Context(), caller(r), id); err != nil {
		return err
	}
	return httpx.JSON(w, http.StatusOK, map[string]any{"status": "active"})
}

func (h *Handlers) warn(w http.ResponseWriter, r *http.Request) error {
	id, err := pathID(r, "id")
	if err != nil {
		return err
	}
	var body struct {
		Reason string `json:"reason"`
	}
	if err := httpx.DecodeJSON(w, r, &body, 4<<10); err != nil {
		return err
	}
	if err := h.svc.Warn(r.Context(), caller(r), id, body.Reason); err != nil {
		return err
	}
	return httpx.JSON(w, http.StatusOK, map[string]any{"warned": true})
}

func (h *Handlers) grantRole(w http.ResponseWriter, r *http.Request) error {
	id, err := pathID(r, "id")
	if err != nil {
		return err
	}
	var body struct {
		Role string `json:"role"`
	}
	if err := httpx.DecodeJSON(w, r, &body, 1<<10); err != nil {
		return err
	}
	if err := h.svc.GrantRole(r.Context(), caller(r), id, body.Role); err != nil {
		return err
	}
	return httpx.JSON(w, http.StatusOK, map[string]any{"granted": body.Role})
}

func (h *Handlers) revokeRole(w http.ResponseWriter, r *http.Request) error {
	id, err := pathID(r, "id")
	if err != nil {
		return err
	}
	if err := h.svc.RevokeRole(r.Context(), caller(r), id, r.PathValue("role")); err != nil {
		return err
	}
	return httpx.JSON(w, http.StatusOK, map[string]any{"revoked": r.PathValue("role")})
}

func (h *Handlers) verifyIdentity(w http.ResponseWriter, r *http.Request) error {
	id, err := pathID(r, "id")
	if err != nil {
		return err
	}
	var body struct {
		Verified bool `json:"verified"`
	}
	if err := httpx.DecodeJSON(w, r, &body, 1<<10); err != nil {
		return err
	}
	if err := h.svc.VerifyIdentity(r.Context(), caller(r), id, body.Verified); err != nil {
		return err
	}
	return httpx.JSON(w, http.StatusOK, map[string]any{"identity_verified": body.Verified})
}

func (h *Handlers) settings(w http.ResponseWriter, r *http.Request) error {
	rows, err := h.svc.Settings(r.Context(), caller(r))
	if err != nil {
		return err
	}
	return httpx.JSON(w, http.StatusOK, rows)
}

func (h *Handlers) setSetting(w http.ResponseWriter, r *http.Request) error {
	var body struct {
		Value any `json:"value"`
	}
	if err := httpx.DecodeJSON(w, r, &body, 8<<10); err != nil {
		return err
	}
	if err := h.svc.SetSetting(r.Context(), caller(r), r.PathValue("key"), body.Value); err != nil {
		return err
	}
	return httpx.JSON(w, http.StatusOK, map[string]any{"key": r.PathValue("key"), "value": body.Value})
}

func (h *Handlers) flags(w http.ResponseWriter, r *http.Request) error {
	flags, err := h.svc.Flags(r.Context(), caller(r))
	if err != nil {
		return err
	}
	return httpx.JSON(w, http.StatusOK, flags)
}

func (h *Handlers) setFlag(w http.ResponseWriter, r *http.Request) error {
	var body struct {
		Enabled        bool `json:"enabled"`
		RolloutPercent int  `json:"rollout_percent"`
	}
	if err := httpx.DecodeJSON(w, r, &body, 1<<10); err != nil {
		return err
	}
	if err := h.svc.SetFlag(r.Context(), caller(r), r.PathValue("key"), body.Enabled, body.RolloutPercent); err != nil {
		return err
	}
	return httpx.JSON(w, http.StatusOK, map[string]any{"key": r.PathValue("key"), "enabled": body.Enabled, "rollout_percent": body.RolloutPercent})
}

func (h *Handlers) weights(w http.ResponseWriter, r *http.Request) error {
	weights, history, err := h.svc.Weights(r.Context(), caller(r))
	if err != nil {
		return err
	}
	return httpx.JSONMeta(w, http.StatusOK, weights, map[string]any{"history": history})
}

func (h *Handlers) setWeights(w http.ResponseWriter, r *http.Request) error {
	var body WeightsRequest
	if err := httpx.DecodeJSON(w, r, &body, 4<<10); err != nil {
		return err
	}
	weights, err := h.svc.SetWeights(r.Context(), caller(r), body)
	if err != nil {
		return err
	}
	return httpx.JSON(w, http.StatusOK, weights)
}

func (h *Handlers) disputes(w http.ResponseWriter, r *http.Request) error {
	list, err := h.svc.Disputes(r.Context(), caller(r))
	if err != nil {
		return err
	}
	return httpx.JSONMeta(w, http.StatusOK, list, map[string]any{"count": len(list)})
}

func (h *Handlers) resolveDispute(w http.ResponseWriter, r *http.Request) error {
	id, err := pathID(r, "id")
	if err != nil {
		return err
	}
	var body contracts.DisputeOutcome
	if err := httpx.DecodeJSON(w, r, &body, 8<<10); err != nil {
		return err
	}
	m, err := h.svc.ResolveDispute(r.Context(), caller(r), id, body)
	if err != nil {
		return err
	}
	return httpx.JSON(w, http.StatusOK, m)
}

func (h *Handlers) auditLog(w http.ResponseWriter, r *http.Request) error {
	q := r.URL.Query()
	query := AuditQuery{Action: strings.TrimSpace(q.Get("action")), SubjectType: q.Get("subject_type"), Outcome: q.Get("outcome")}
	if raw := q.Get("actor_id"); raw != "" {
		id, err := uuid.Parse(raw)
		if err != nil {
			return httpx.Validation(map[string]string{"actor_id": "Неверный идентификатор."})
		}
		query.ActorID = &id
	}
	if raw := q.Get("subject_id"); raw != "" {
		id, err := uuid.Parse(raw)
		if err != nil {
			return httpx.Validation(map[string]string{"subject_id": "Неверный идентификатор."})
		}
		query.SubjectID = &id
	}
	query.Limit, _ = strconv.Atoi(q.Get("limit"))
	query.Offset, _ = strconv.Atoi(q.Get("offset"))
	rows, total, err := h.svc.Audit(r.Context(), caller(r), query)
	if err != nil {
		return err
	}
	return httpx.JSONMeta(w, http.StatusOK, rows, map[string]any{"total": total, "offset": query.Offset})
}

// ── The tabs of a user's page ───────────────────────────────────────────────

func (h *Handlers) userProjects(w http.ResponseWriter, r *http.Request) error {
	id, err := pathID(r, "id")
	if err != nil {
		return err
	}
	out, err := h.svc.Projects(r.Context(), caller(r), id)
	if err != nil {
		return err
	}
	return httpx.JSON(w, http.StatusOK, out)
}

func (h *Handlers) userPayments(w http.ResponseWriter, r *http.Request) error {
	id, err := pathID(r, "id")
	if err != nil {
		return err
	}
	out, err := h.svc.Payments(r.Context(), caller(r), id)
	if err != nil {
		return err
	}
	return httpx.JSON(w, http.StatusOK, out)
}

func (h *Handlers) userSecurity(w http.ResponseWriter, r *http.Request) error {
	id, err := pathID(r, "id")
	if err != nil {
		return err
	}
	out, err := h.svc.Security(r.Context(), caller(r), id)
	if err != nil {
		return err
	}
	return httpx.JSON(w, http.StatusOK, out)
}

func (h *Handlers) userHistory(w http.ResponseWriter, r *http.Request) error {
	id, err := pathID(r, "id")
	if err != nil {
		return err
	}
	out, err := h.svc.AdminHistory(r.Context(), caller(r), id)
	if err != nil {
		return err
	}
	return httpx.JSON(w, http.StatusOK, out)
}

// ── Blocking ────────────────────────────────────────────────────────────────

func (h *Handlers) block(w http.ResponseWriter, r *http.Request) error {
	id, err := pathID(r, "id")
	if err != nil {
		return err
	}
	var body struct {
		Reason string `json:"reason"`
	}
	if err := httpx.DecodeJSON(w, r, &body, 4<<10); err != nil {
		return err
	}
	if err := h.svc.Block(r.Context(), caller(r), id, body.Reason); err != nil {
		return err
	}
	return httpx.JSON(w, http.StatusOK, map[string]any{"status": "banned"})
}

func (h *Handlers) unblock(w http.ResponseWriter, r *http.Request) error {
	id, err := pathID(r, "id")
	if err != nil {
		return err
	}
	if err := h.svc.Unblock(r.Context(), caller(r), id); err != nil {
		return err
	}
	return httpx.JSON(w, http.StatusOK, map[string]any{"status": "active"})
}

// ── Permissions by name ─────────────────────────────────────────────────────

func (h *Handlers) grantable(w http.ResponseWriter, r *http.Request) error {
	out, err := h.svc.Grantable(r.Context(), caller(r))
	if err != nil {
		return err
	}
	return httpx.JSON(w, http.StatusOK, out)
}

func (h *Handlers) grantPermission(w http.ResponseWriter, r *http.Request) error {
	id, err := pathID(r, "id")
	if err != nil {
		return err
	}
	var body struct {
		Permission string `json:"permission"`
		Note       string `json:"note"`
	}
	if err := httpx.DecodeJSON(w, r, &body, 4<<10); err != nil {
		return err
	}
	out, err := h.svc.GrantPermission(r.Context(), caller(r), id, body.Permission, body.Note)
	if err != nil {
		return err
	}
	return httpx.JSON(w, http.StatusOK, out)
}

func (h *Handlers) revokePermission(w http.ResponseWriter, r *http.Request) error {
	id, err := pathID(r, "id")
	if err != nil {
		return err
	}
	out, err := h.svc.RevokePermission(r.Context(), caller(r), id, r.PathValue("permission"))
	if err != nil {
		return err
	}
	return httpx.JSON(w, http.StatusOK, out)
}
