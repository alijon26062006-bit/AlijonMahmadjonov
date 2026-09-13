package moderation

import (
	"context"
	"errors"
	"strings"

	"github.com/google/uuid"

	"github.com/averix/api/internal/audit"
	"github.com/averix/api/internal/platform/httpx"
	"github.com/averix/api/internal/platform/logx"
	"github.com/averix/api/internal/security"
)

// Notifier tells an owner their content was hidden or that they were warned.
type Notifier interface {
	AccountWarning(ctx context.Context, userID uuid.UUID, reason string)
}

type Service struct {
	store    *Store
	audit    *audit.Recorder
	notifier Notifier
}

func NewService(store *Store, rec *audit.Recorder, notifier Notifier) *Service {
	return &Service{store: store, audit: rec, notifier: notifier}
}

// Flag is what other modules call. It never fails the caller: a queue write
// that failed is logged, and the content stays visible until a person looks
// — which is the fail-safe direction for a marketplace, not the fail-closed.
func (s *Service) Flag(ctx context.Context, subjectType string, subjectID uuid.UUID, reason string) {
	if err := s.store.Flag(ctx, subjectType, subjectID, reason, "automatic", 50); err != nil {
		logx.From(ctx).Error("moderation: could not queue a flag", "subject", subjectType, "error", err)
	}
}

// Report files a user's report.
func (s *Service) Report(ctx context.Context, id *security.Identity, in ReportRequest) (uuid.UUID, error) {
	if _, ok := reportReasons[in.Reason]; !ok {
		return uuid.Nil, httpx.Validation(map[string]string{"reason": "Выберите причину из списка."})
	}
	subjectID, err := uuid.Parse(strings.TrimSpace(in.SubjectID))
	if err != nil {
		return uuid.Nil, httpx.Validation(map[string]string{"subject_id": "Неверная ссылка на объект жалобы."})
	}
	switch in.SubjectType {
	case SubjectUser, SubjectProject, SubjectProposal, SubjectPortfolioProject, SubjectService, SubjectReview, SubjectMessage:
	default:
		return uuid.Nil, httpx.Validation(map[string]string{"subject_type": "На это нельзя пожаловаться."})
	}
	if n := len([]rune(strings.TrimSpace(in.Detail))); n > 2000 {
		return uuid.Nil, httpx.Validation(map[string]string{"detail": "Не длиннее 2000 символов."})
	} else if in.Reason == "other" && n < 10 {
		return uuid.Nil, httpx.Validation(map[string]string{"detail": "Для причины «Другое» опишите, что не так."})
	}
	exists, err := s.store.SubjectExists(ctx, in.SubjectType, subjectID)
	if err != nil {
		return uuid.Nil, httpx.Internalf(err, "check report subject")
	}
	if !exists {
		return uuid.Nil, httpx.NotFoundf("%s %s does not exist", in.SubjectType, subjectID)
	}
	if in.SubjectType == SubjectUser && subjectID == id.UserID {
		return uuid.Nil, httpx.Validation(map[string]string{"subject_id": "Нельзя пожаловаться на себя."})
	}
	reportID, err := s.store.FileReport(ctx, id.UserID, in, subjectID)
	if err != nil {
		return uuid.Nil, httpx.Internalf(err, "file report")
	}
	s.audit.RecordRequest(ctx, audit.Entry{Action: "moderation.report_filed", SubjectType: in.SubjectType,
		SubjectID: &subjectID, Detail: in.Reason})
	return reportID, nil
}

// ── Moderator side ──────────────────────────────────────────────────────────

func (s *Service) Queue(ctx context.Context, id *security.Identity, status string, limit, offset int) ([]QueueItem, int, error) {
	if err := security.RequirePermission(id, security.PermModerationQueue); err != nil {
		return nil, 0, httpx.Forbiddenf("the moderation queue needs the moderation.queue permission")
	}
	switch status {
	case "", "pending", "escalated", "approved", "rejected":
	default:
		return nil, 0, httpx.Validation(map[string]string{"status": "Неизвестный статус."})
	}
	items, total, err := s.store.Queue(ctx, status, limit, offset)
	if err != nil {
		return nil, 0, httpx.Internalf(err, "load moderation queue")
	}
	return items, total, nil
}

func (s *Service) Decide(ctx context.Context, id *security.Identity, itemID uuid.UUID, in DecideRequest) (*QueueItem, error) {
	if err := security.RequirePermission(id, security.PermModerationDecide); err != nil {
		return nil, httpx.Forbiddenf("deciding needs the moderation.decide permission")
	}
	switch in.Outcome {
	case "approve", "reject", "escalate":
	default:
		return nil, httpx.Validation(map[string]string{"outcome": "Решение: approve, reject или escalate."})
	}
	note := strings.TrimSpace(in.Note)
	if in.Outcome == "reject" && len([]rune(note)) < 10 {
		return nil, httpx.Validation(map[string]string{"note": "Скрывая контент, объясните почему — владелец это увидит."})
	}
	item, err := s.store.Decide(ctx, itemID, id.UserID, in.Outcome, note)
	switch {
	case errors.Is(err, ErrNotFound):
		return nil, httpx.NotFoundf("queue item %s is not waiting for a decision", itemID)
	case err != nil:
		return nil, httpx.Internalf(err, "record moderation decision")
	}

	action := audit.ActionContentRestored
	if in.Outcome == "reject" {
		action = audit.ActionContentHidden
	}
	s.audit.RecordRequest(ctx, audit.Entry{Action: action, SubjectType: item.SubjectType,
		SubjectID: &item.SubjectID, Detail: note})

	if in.Outcome == "reject" && s.notifier != nil && item.Preview.OwnerID != uuid.Nil {
		msg := "Ваш контент «" + item.Preview.Title + "» скрыт модерацией. Причина: " + note
		if in.Warn {
			msg += " Это предупреждение: повторное нарушение приведёт к блокировке."
			s.audit.RecordRequest(ctx, audit.Entry{Action: audit.ActionUserWarned, SubjectType: "user",
				SubjectID: &item.Preview.OwnerID, Detail: note})
		}
		s.notifier.AccountWarning(context.WithoutCancel(ctx), item.Preview.OwnerID, msg)
	}
	return item, nil
}

func (s *Service) Reports(ctx context.Context, id *security.Identity, status string, limit, offset int) ([]Report, int, error) {
	if err := security.RequirePermission(id, security.PermReportReview); err != nil {
		return nil, 0, httpx.Forbiddenf("reports need the report.review permission")
	}
	out, total, err := s.store.Reports(ctx, status, limit, offset)
	if err != nil {
		return nil, 0, httpx.Internalf(err, "load reports")
	}
	return out, total, nil
}

func (s *Service) ResolveReport(ctx context.Context, id *security.Identity, reportID uuid.UUID, status, resolution string) error {
	if err := security.RequirePermission(id, security.PermReportReview); err != nil {
		return httpx.Forbiddenf("resolving reports needs the report.review permission")
	}
	if status != "actioned" && status != "dismissed" {
		return httpx.Validation(map[string]string{"status": "Итог: actioned или dismissed."})
	}
	err := s.store.ResolveReport(ctx, reportID, id.UserID, status, strings.TrimSpace(resolution))
	switch {
	case errors.Is(err, ErrNotFound):
		return httpx.NotFoundf("report %s is not open", reportID)
	case err != nil:
		return httpx.Internalf(err, "resolve report")
	}
	s.audit.RecordRequest(ctx, audit.Entry{Action: audit.ActionReportResolved, SubjectType: "report",
		SubjectID: &reportID, Detail: status})
	return nil
}

func (s *Service) Store() *Store { return s.store }
