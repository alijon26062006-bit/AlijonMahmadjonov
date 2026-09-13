package search

import (
	"context"
	"errors"
	"strings"

	"github.com/google/uuid"

	"github.com/averix/api/internal/audit"
	"github.com/averix/api/internal/platform/httpx"
	"github.com/averix/api/internal/security"
	"github.com/averix/api/internal/services"
)

type Service struct {
	store    *Store
	services *services.Store
	audit    *audit.Recorder
}

func NewService(store *Store, serviceStore *services.Store, rec *audit.Recorder) *Service {
	return &Service{store: store, services: serviceStore, audit: rec}
}

func (s *Service) Freelancers(ctx context.Context, q FreelancerQuery) ([]FreelancerCard, map[string]any, error) {
	cards, total, err := s.store.Freelancers(ctx, q)
	if err != nil {
		return nil, nil, httpx.Internalf(err, "list freelancers")
	}
	limit := q.Limit
	if limit <= 0 || limit > 48 {
		limit = 24
	}
	meta := map[string]any{"total": total, "offset": q.Offset, "limit": limit}
	if q.Offset+len(cards) < total {
		meta["next_offset"] = q.Offset + limit
	}
	return cards, meta, nil
}

// Everything answers one box. Each group is capped so the page is a
// summary; the totals say how much more there is.
func (s *Service) Everything(ctx context.Context, id *security.Identity, text string) (*Results, error) {
	text = strings.TrimSpace(text)
	if len([]rune(text)) < 2 {
		return nil, httpx.Validation(map[string]string{"q": "Введите хотя бы два символа."})
	}
	if len([]rune(text)) > 100 {
		text = string([]rune(text)[:100])
	}
	var viewer *uuid.UUID
	if id.Authenticated() {
		viewer = &id.UserID
	}

	freelancers, freelancerTotal, err := s.store.Freelancers(ctx, FreelancerQuery{Text: text, Limit: 5, ViewerID: viewer})
	if err != nil {
		return nil, httpx.Internalf(err, "search freelancers")
	}
	serviceCards, serviceTotal, err := s.services.Catalogue(ctx, services.Query{Text: text, Sort: "relevance", Limit: 5})
	if err != nil {
		return nil, httpx.Internalf(err, "search services")
	}
	projects, projectTotal, err := s.store.Projects(ctx, text, 5)
	if err != nil {
		return nil, httpx.Internalf(err, "search projects")
	}
	return &Results{
		Query:       text,
		Freelancers: freelancers,
		Services:    serviceCards,
		Projects:    projects,
		Totals:      map[string]int{"freelancers": freelancerTotal, "services": serviceTotal, "projects": projectTotal},
	}, nil
}

// ── Favourites ──────────────────────────────────────────────────────────────

func (s *Service) SaveFreelancer(ctx context.Context, id *security.Identity, username, note string) error {
	if err := security.RequireRole(id, security.RoleClient); err != nil {
		return httpx.Forbiddenf("switch to your client profile to save a freelancer")
	}
	developerID, err := s.store.userIDByUsername(ctx, username)
	if err != nil {
		return httpx.NotFoundf("user %s does not exist", username)
	}
	if developerID == id.UserID {
		return httpx.Forbiddenf("you cannot save yourself")
	}
	note = strings.TrimSpace(note)
	if len([]rune(note)) > 300 {
		return httpx.Validation(map[string]string{"note": "Заметка — не длиннее 300 символов."})
	}
	if err := s.store.SaveFreelancer(ctx, id.UserID, developerID, note); err != nil {
		return httpx.Internalf(err, "save freelancer")
	}
	return nil
}

func (s *Service) UnsaveFreelancer(ctx context.Context, id *security.Identity, username string) error {
	if err := security.RequireRole(id, security.RoleClient); err != nil {
		return httpx.Forbiddenf("switch to your client profile to manage saved freelancers")
	}
	developerID, err := s.store.userIDByUsername(ctx, username)
	if err != nil {
		return httpx.NotFoundf("user %s does not exist", username)
	}
	if err := s.store.UnsaveFreelancer(ctx, id.UserID, developerID); err != nil {
		return httpx.Internalf(err, "unsave freelancer")
	}
	return nil
}

func (s *Service) SavedFreelancers(ctx context.Context, id *security.Identity) ([]SavedFreelancer, error) {
	if err := security.RequireRole(id, security.RoleClient); err != nil {
		return nil, httpx.Forbiddenf("switch to your client profile to see saved freelancers")
	}
	out, err := s.store.SavedFreelancers(ctx, id.UserID)
	if err != nil {
		return nil, httpx.Internalf(err, "list saved freelancers")
	}
	return out, nil
}

func (s *Service) SaveProject(ctx context.Context, id *security.Identity, projectID uuid.UUID) error {
	if err := security.RequireRole(id, security.RoleDeveloper); err != nil {
		return httpx.Forbiddenf("switch to your freelancer profile to save a project")
	}
	err := s.store.SaveProject(ctx, id.UserID, projectID)
	switch {
	case errors.Is(err, ErrNotFound):
		return httpx.NotFoundf("project %s does not exist", projectID)
	case err != nil:
		return httpx.Internalf(err, "save project")
	}
	return nil
}

func (s *Service) UnsaveProject(ctx context.Context, id *security.Identity, projectID uuid.UUID) error {
	if err := security.RequireRole(id, security.RoleDeveloper); err != nil {
		return httpx.Forbiddenf("switch to your freelancer profile to manage saved projects")
	}
	if err := s.store.UnsaveProject(ctx, id.UserID, projectID); err != nil {
		return httpx.Internalf(err, "unsave project")
	}
	return nil
}
