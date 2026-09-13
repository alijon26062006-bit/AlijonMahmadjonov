package reviews

import (
	"context"
	"errors"
	"fmt"
	"math"
	"strings"
	"time"

	"github.com/google/uuid"

	"github.com/averix/api/internal/audit"
	"github.com/averix/api/internal/platform/httpx"
	"github.com/averix/api/internal/platform/logx"
	"github.com/averix/api/internal/platform/validate"
	"github.com/averix/api/internal/security"
)

// Contracts is what this module asks of the contracts module: nothing but
// "is this caller a party, and which one".
type Contracts interface {
	EnsureParty(ctx context.Context, id *security.Identity, contractID uuid.UUID) (string, error)
}

type Settings interface {
	Int(ctx context.Context, key string, fallback int) int
}

// Notifier is the subset of notifications this module raises.
type Notifier interface {
	ContractCompleted(ctx context.Context, userID, contractID uuid.UUID)
	ReviewReceived(ctx context.Context, subjectID, authorID, contractID uuid.UUID)
	ReviewPublished(ctx context.Context, userID, contractID uuid.UUID)
}

type Service struct {
	store     *Store
	contracts Contracts
	settings  Settings
	notifier  Notifier
	audit     *audit.Recorder
}

func NewService(store *Store, contracts Contracts, settings Settings, notifier Notifier,
	rec *audit.Recorder) *Service {
	return &Service{store: store, contracts: contracts, settings: settings, notifier: notifier, audit: rec}
}

func (s *Service) Store() *Store { return s.store }

// window is how long after completion a review may be written, and how long
// a single-sided review waits before it is published alone.
func (s *Service) window(ctx context.Context) time.Duration {
	days := 14
	if s.settings != nil {
		days = s.settings.Int(ctx, "reviews.window_days", 14)
	}
	return time.Duration(days) * 24 * time.Hour
}

// ── The contracts hook ──────────────────────────────────────────────────────

// ContractCompleted records the verified history and tells both sides the
// review window is open. Called by contracts, never from a handler.
func (s *Service) ContractCompleted(ctx context.Context, contractID uuid.UUID) {
	if err := s.store.RecordCompletion(ctx, contractID); err != nil {
		logx.From(ctx).Error("reviews: could not record the completed contract", "contract_id", contractID, "error", err)
	}
	if s.notifier == nil {
		return
	}
	facts, err := s.store.contract(ctx, contractID)
	if err != nil {
		return
	}
	s.notifier.ContractCompleted(ctx, facts.ClientID, contractID)
	s.notifier.ContractCompleted(ctx, facts.DeveloperID, contractID)
}

// ── Writing ─────────────────────────────────────────────────────────────────

func (s *Service) Submit(ctx context.Context, id *security.Identity, contractID uuid.UUID,
	in SubmitRequest) (*Review, error) {

	role, err := s.contracts.EnsureParty(ctx, id, contractID)
	if err != nil {
		return nil, err
	}
	direction, subject, err := s.directionFor(ctx, contractID, id.UserID, role)
	if err != nil {
		return nil, err
	}
	facts, err := s.store.contract(ctx, contractID)
	if err != nil {
		return nil, httpx.NotFoundf("contract %s does not exist", contractID)
	}
	if facts.Status != "completed" || facts.CompletedAt == nil {
		e := *httpx.ErrConflict
		e.Code = "contract_not_completed"
		e.Message = "Отзыв можно оставить только по завершённому контракту."
		return nil, &e
	}
	if time.Since(*facts.CompletedAt) > s.window(ctx) {
		e := *httpx.ErrConflict
		e.Code = "review_window_closed"
		e.Message = fmt.Sprintf("Окно для отзыва закрылось: оно открыто %d дней после завершения контракта.",
			int(s.window(ctx).Hours()/24))
		return nil, &e
	}

	scores, overall, err := validateScores(direction, in)
	if err != nil {
		return nil, err
	}

	reviewID, err := s.store.Create(ctx, newReview{
		ContractID: contractID, AuthorID: id.UserID, SubjectID: subject, Direction: direction,
		Overall: overall, Scores: scores, Comment: strings.TrimSpace(in.Comment),
		WouldWorkAgain: in.WouldWorkAgain,
	})
	switch {
	case errors.Is(err, ErrAlreadyReviewed):
		e := *httpx.ErrConflict
		e.Code = "already_reviewed"
		e.Message = "Вы уже оставили отзыв по этому контракту. Отзыв нельзя изменить — только дополнить ответом, когда он будет опубликован."
		return nil, &e
	case err != nil:
		return nil, httpx.Internalf(err, "create review")
	}

	s.audit.RecordRequest(ctx, audit.Entry{
		Action: "review.submit", SubjectType: "review", SubjectID: &reviewID,
		Detail: fmt.Sprintf("%s on contract %s", direction, contractID),
	})

	published, err := s.store.PublishIfBothSubmitted(ctx, contractID)
	if err != nil {
		logx.From(ctx).Warn("reviews: could not publish", "contract_id", contractID, "error", err)
	}
	if s.notifier != nil {
		background := context.WithoutCancel(ctx)
		s.notifier.ReviewReceived(background, subject, id.UserID, contractID)
		if published {
			s.notifier.ReviewPublished(background, subject, contractID)
			s.notifier.ReviewPublished(background, id.UserID, contractID)
		}
	}

	review, err := s.store.ByID(ctx, reviewID)
	if err != nil {
		return nil, httpx.Internalf(err, "load review")
	}
	review.IsMine = true
	return review, nil
}

func (s *Service) directionFor(ctx context.Context, contractID, userID uuid.UUID, role string) (string, uuid.UUID, error) {
	facts, err := s.store.contract(ctx, contractID)
	if err != nil {
		return "", uuid.Nil, httpx.NotFoundf("contract %s does not exist", contractID)
	}
	switch {
	case role == "client" && userID == facts.ClientID:
		return DirectionOfDeveloper, facts.DeveloperID, nil
	case role == "developer" && userID == facts.DeveloperID:
		return DirectionOfClient, facts.ClientID, nil
	}
	// An observer is on the workspace to help, not to rate anyone.
	return "", uuid.Nil, httpx.Forbiddenf("only the client and the freelancer on a contract may review it")
}

// validateScores checks every category for the direction is present and in
// range, and computes the overall as their mean: an overall typed separately
// from its parts is a number nobody can explain.
func validateScores(direction string, in SubmitRequest) (map[string]float64, float64, error) {
	v := validate.New()
	scores := map[string]float64{}
	total := 0.0
	for _, cat := range categoriesFor(direction) {
		n, ok := in.Scores[cat.Key]
		switch {
		case !ok:
			v.Add("scores."+cat.Key, "Оцените «"+cat.Label+"» от 1 до 5.")
		case n < 1 || n > 5:
			v.Add("scores."+cat.Key, "Оценка должна быть от 1 до 5.")
		default:
			scores[cat.Key] = float64(n)
			total += float64(n)
		}
	}
	for key := range in.Scores {
		known := false
		for _, cat := range categoriesFor(direction) {
			if cat.Key == key {
				known = true
			}
		}
		if !known {
			v.Add("scores."+key, "Такой категории нет для этой стороны.")
		}
	}
	if comment := strings.TrimSpace(in.Comment); comment != "" {
		if len([]rune(comment)) < 20 {
			v.Add("comment", "Если пишете комментарий, напишите хотя бы 20 символов — или оставьте поле пустым.")
		}
		if len([]rune(comment)) > 2000 {
			v.Add("comment", "Комментарий — не больше 2000 символов.")
		}
		if found := validate.ContactDetails(comment); len(found) > 0 {
			v.Add("comment", "В отзыве не должно быть контактов: "+strings.Join(found, ", ")+".")
		}
	}
	if v.Any() {
		return nil, 0, httpx.Validation(v.Fields())
	}
	overall := math.Round(total/float64(len(scores))*100) / 100
	return scores, overall, nil
}

// ── Reading ─────────────────────────────────────────────────────────────────

// ForContract is the review panel: what each side has done, what the caller
// may do, and the content of whatever is published or their own.
func (s *Service) ForContract(ctx context.Context, id *security.Identity, contractID uuid.UUID) (*ContractReviews, error) {
	role, err := s.contracts.EnsureParty(ctx, id, contractID)
	if err != nil {
		return nil, err
	}
	facts, err := s.store.contract(ctx, contractID)
	if err != nil {
		return nil, httpx.NotFoundf("contract %s does not exist", contractID)
	}
	all, err := s.store.ForContract(ctx, contractID)
	if err != nil {
		return nil, httpx.Internalf(err, "load reviews")
	}

	out := &ContractReviews{
		ContractID:  contractID,
		OfDeveloper: Side{Direction: DirectionOfDeveloper, Categories: DeveloperCategories},
		OfClient:    Side{Direction: DirectionOfClient, Categories: ClientCategories},
	}
	if facts.CompletedAt != nil {
		closes := facts.CompletedAt.Add(s.window(ctx))
		out.WindowClosesAt = &closes
	}
	myDirection := ""
	switch {
	case role == "client" && id.UserID == facts.ClientID:
		myDirection = DirectionOfDeveloper
	case role == "developer" && id.UserID == facts.DeveloperID:
		myDirection = DirectionOfClient
	}
	out.MyDirection = myDirection

	for _, r := range all {
		side := &out.OfDeveloper
		if r.Direction == DirectionOfClient {
			side = &out.OfClient
		}
		side.Submitted = true
		side.Published = r.PublishedAt != nil
		r.IsMine = r.Author.UserID == id.UserID
		r.IsAboutMe = r.Subject.UserID == id.UserID
		r.CanRespond = r.IsAboutMe && r.PublishedAt != nil && r.Response == ""
		// Blind until published: the other side's content stays out of the
		// response entirely rather than being present-but-hidden.
		if r.PublishedAt != nil || r.IsMine {
			side.Review = r
		}
	}

	mine := &out.OfDeveloper
	if myDirection == DirectionOfClient {
		mine = &out.OfClient
	}
	switch {
	case myDirection == "":
		out.Reason = "Наблюдатели не оставляют отзывы."
	case facts.Status != "completed" || facts.CompletedAt == nil:
		out.Reason = "Отзыв можно оставить после завершения контракта."
	case mine.Submitted:
		out.Reason = "Вы уже оставили отзыв."
	case out.WindowClosesAt != nil && time.Now().After(*out.WindowClosesAt):
		out.Reason = "Окно для отзыва закрылось."
	default:
		out.CanReview = true
	}
	return out, nil
}

func (s *Service) Respond(ctx context.Context, id *security.Identity, reviewID uuid.UUID, text string) (*Review, error) {
	text = strings.TrimSpace(text)
	v := validate.New()
	if n := len([]rune(text)); n < 10 || n > 1000 {
		v.Add("response", "Ответ — от 10 до 1000 символов.")
	}
	if found := validate.ContactDetails(text); len(found) > 0 {
		v.Add("response", "В ответе не должно быть контактов.")
	}
	if v.Any() {
		return nil, httpx.Validation(v.Fields())
	}
	err := s.store.Respond(ctx, reviewID, id.UserID, text)
	switch {
	case errors.Is(err, ErrNotFound):
		// Not yours to answer, not published yet, or already answered: all
		// three read as not found, because saying which would confirm the
		// review exists to someone who should not know.
		return nil, httpx.NotFoundf("review %s cannot be answered", reviewID)
	case err != nil:
		return nil, httpx.Internalf(err, "respond to review")
	}
	s.audit.RecordRequest(ctx, audit.Entry{Action: "review.respond", SubjectType: "review", SubjectID: &reviewID})
	review, err := s.store.ByID(ctx, reviewID)
	if err != nil {
		return nil, httpx.Internalf(err, "load review")
	}
	review.IsAboutMe = true
	return review, nil
}

// PublicFor lists the published reviews about a person by username.
func (s *Service) PublicFor(ctx context.Context, username, direction string, before *time.Time,
	limit int) ([]*Review, Summary, error) {

	userID, err := s.store.userIDByUsername(ctx, username)
	if err != nil {
		return nil, Summary{}, httpx.NotFoundf("user %s does not exist", username)
	}
	list, err := s.store.Public(ctx, userID, direction, before, limit)
	if err != nil {
		return nil, Summary{}, httpx.Internalf(err, "list reviews")
	}
	summary, err := s.store.Summarise(ctx, userID, direction)
	if err != nil {
		return nil, Summary{}, httpx.Internalf(err, "summarise reviews")
	}
	return list, summary, nil
}

// HistoryFor lists a freelancer's verified contracts; the owner sees hidden
// entries too.
func (s *Service) HistoryFor(ctx context.Context, id *security.Identity, username string) ([]HistoryEntry, error) {
	userID, err := s.store.userIDByUsername(ctx, username)
	if err != nil {
		return nil, httpx.NotFoundf("user %s does not exist", username)
	}
	owner := id.Authenticated() && id.UserID == userID
	entries, err := s.store.History(ctx, userID, owner)
	if err != nil {
		return nil, httpx.Internalf(err, "list history")
	}
	return entries, nil
}

func (s *Service) SetHistoryVisibility(ctx context.Context, id *security.Identity, entryID uuid.UUID, visible bool) error {
	err := s.store.SetHistoryVisibility(ctx, id.UserID, entryID, visible)
	switch {
	case errors.Is(err, ErrNotFound):
		return httpx.NotFoundf("history entry %s does not exist", entryID)
	case err != nil:
		return httpx.Internalf(err, "update history visibility")
	}
	return nil
}

// ── Worker ──────────────────────────────────────────────────────────────────

// PublishExpired runs on a schedule: single-sided reviews whose window has
// closed are published, and both parties told.
func (s *Service) PublishExpired(ctx context.Context) (string, error) {
	contracts, err := s.store.PublishExpired(ctx, s.window(ctx))
	if err != nil {
		return "", err
	}
	if len(contracts) == 0 {
		return "", nil
	}
	if s.notifier != nil {
		for _, contractID := range contracts {
			facts, err := s.store.contract(ctx, contractID)
			if err != nil {
				continue
			}
			s.notifier.ReviewPublished(ctx, facts.ClientID, contractID)
			s.notifier.ReviewPublished(ctx, facts.DeveloperID, contractID)
		}
	}
	return fmt.Sprintf("published %d review(s) whose window closed", len(contracts)), nil
}
