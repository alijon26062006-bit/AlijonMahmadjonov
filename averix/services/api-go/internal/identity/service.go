package identity

import (
	"context"
	"errors"
	"fmt"
	"io"
	"net"
	"strings"
	"time"

	"github.com/google/uuid"

	"github.com/averix/api/internal/audit"
	"github.com/averix/api/internal/platform/cache"
	"github.com/averix/api/internal/platform/cryptox"
	"github.com/averix/api/internal/platform/database"
	"github.com/averix/api/internal/platform/httpx"
	"github.com/averix/api/internal/platform/logx"
	"github.com/averix/api/internal/platform/validate"
	"github.com/averix/api/internal/security"
	"github.com/averix/api/internal/settings"
)

// Notifier is the part of notifications this package uses. Nothing it is
// given ever contains a document or a document number.
type Notifier interface {
	IdentitySubmitted(ctx context.Context, userID uuid.UUID)
	IdentityApproved(ctx context.Context, userID uuid.UUID)
	IdentityRejected(ctx context.Context, userID uuid.UUID, reason string)
	IdentityResubmitRequested(ctx context.Context, userID uuid.UUID, what string)
}

// Passwords is what re-authentication needs: the stored hash for an account.
type Passwords interface {
	PasswordHash(ctx context.Context, userID uuid.UUID) (string, error)
}

type Service struct {
	store    *Store
	db       *database.DB
	cache    *cache.Cache
	settings *settings.Store
	audit    *audit.Recorder
	notify   Notifier
	pass     Passwords
	chat     Chat
}

func NewService(store *Store, db *database.DB, c *cache.Cache, set *settings.Store,
	rec *audit.Recorder, notify Notifier, pass Passwords) *Service {
	return &Service{store: store, db: db, cache: c, settings: set, audit: rec, notify: notify, pass: pass}
}

// Chat is the staff chat, if the operator set one up.
//
// Look at the signature: a reference and a user id. It is not possible to hand
// this interface an image, a storage key or a document id, which is the whole
// design — a passport must not end up in a message history nobody on the
// platform can delete.
type Chat interface {
	Configured() bool
	IdentitySubmitted(ctx context.Context, reference string, userID fmt.Stringer) error
}

// AttachChat is optional. Without it the product behaves exactly as before:
// the notification in the panel is the only signal.
func (s *Service) AttachChat(c Chat) { s.chat = c }

// maxDocumentBytes is generous enough for a phone photograph and far below
// what would let someone use this endpoint as storage.
const maxDocumentBytes int64 = 12 << 20

// ── The owner's side ────────────────────────────────────────────────────────

// requireFreelancer is the first line of every owner-side call.
//
// Verification exists so that the person receiving money is who they say they
// are. A client receives nothing — they pay — so the platform has no reason to
// hold their passport, and does not ask for one. An account that holds both
// roles is a freelancer for this purpose.
func requireFreelancer(id *security.Identity) error {
	if !id.Authenticated() {
		return httpx.ErrUnauthenticated
	}
	if !id.HasRole(security.RoleDeveloper) {
		e := *httpx.ErrForbidden
		e.Code = "identity_not_applicable"
		e.Message = "Проверка личности нужна только исполнителям — тем, кто получает оплату. " +
			"Заказчику она не требуется, и документы у него не запрашиваются."
		return &e
	}
	return nil
}

// Mine returns the caller's own case. A person always sees their own
// documents' existence, never anybody else's.
func (s *Service) Mine(ctx context.Context, id *security.Identity) (*Case, error) {
	if err := requireFreelancer(id); err != nil {
		return nil, err
	}
	row, err := s.store.Current(ctx, id.UserID)
	if errors.Is(err, ErrNotFound) {
		return s.emptyCase(ctx, id.UserID), nil
	}
	if err != nil {
		return nil, httpx.Internalf(err, "load verification")
	}
	return s.present(ctx, row, false)
}

func (s *Service) emptyCase(ctx context.Context, userID uuid.UUID) *Case {
	withDoc := s.settings.Bool(ctx, "identity.selfie_with_document", false)
	required := []string{KindFront, KindSelfie}
	if withDoc {
		required = []string{KindFront, KindSelfieWithDocument}
	}
	return &Case{
		UserID: userID, Status: StatusDraft, StatusLabel: statusLabel(StatusDraft),
		Required: required, Missing: required, Documents: []Document{},
	}
}

type DetailsRequest struct {
	DocumentType string `json:"document_type"`
	CountryCode  string `json:"country_code"`
	DocumentName string `json:"document_name"`
	DateOfBirth  string `json:"date_of_birth"`
}

// SaveDetails starts a case, or updates the one the person is still filling in.
func (s *Service) SaveDetails(ctx context.Context, id *security.Identity, in DetailsRequest) (*Case, error) {
	if err := requireFreelancer(id); err != nil {
		return nil, err
	}

	v := validate.New()
	docType := v.OneOf("document_type", "Тип документа", in.DocumentType,
		"national_id", "passport", "driver_licence", "residence_permit")
	country := strings.ToUpper(strings.TrimSpace(in.CountryCode))
	if len(country) != 2 {
		v.Add("country_code", "Код страны — две латинские буквы.")
	}
	name := strings.TrimSpace(in.DocumentName)
	if name != "" {
		v.Length("document_name", "Имя в документе", name, 2, 200)
		v.NoControlChars("document_name", "Имя в документе", name)
	}
	var dob *time.Time
	if raw := strings.TrimSpace(in.DateOfBirth); raw != "" {
		parsed, err := time.Parse("2006-01-02", raw)
		if err != nil {
			v.Add("date_of_birth", "Дата в формате ГГГГ-ММ-ДД.")
		} else if parsed.After(time.Now()) {
			v.Add("date_of_birth", "Дата рождения не может быть в будущем.")
		} else {
			dob = &parsed
		}
	}
	if v.Any() {
		return nil, httpx.Validation(v.Fields())
	}

	row, err := s.openCase(ctx, id.UserID)
	if err != nil {
		return nil, err
	}
	if err := s.store.SaveDetails(ctx, row.ID, docType, country, name, dob); err != nil {
		return nil, httpx.Internalf(err, "save verification details")
	}
	return s.load(ctx, row.ID, false)
}

func (s *Service) openCase(ctx context.Context, userID uuid.UUID) (*caseRow, error) {
	withDoc := s.settings.Bool(ctx, "identity.selfie_with_document", false)
	row, err := s.store.OpenOrCreate(ctx, userID, withDoc)
	if err != nil {
		return nil, httpx.Internalf(err, "open verification case")
	}
	if row.Status == StatusSubmitted || row.Status == StatusUnderRev {
		e := *httpx.ErrConflict
		e.Code = "identity_under_review"
		e.Message = "Документы уже на проверке. Дождитесь решения — мы напишем."
		return nil, &e
	}
	return row, nil
}

// Upload stores one side of the document.
func (s *Service) Upload(ctx context.Context, id *security.Identity, kind string, r io.Reader) (*Case, error) {
	if err := requireFreelancer(id); err != nil {
		return nil, err
	}
	switch kind {
	case KindFront, KindBack, KindSelfie, KindSelfieWithDocument:
	default:
		return nil, httpx.Validation(map[string]string{"kind": "Неизвестный вид снимка."})
	}

	row, err := s.openCase(ctx, id.UserID)
	if err != nil {
		return nil, err
	}
	if _, err := s.store.SaveDocument(ctx, row.ID, id.UserID, kind, r, maxDocumentBytes); err != nil {
		if errors.Is(err, context.Canceled) {
			return nil, err
		}
		// The message here is written for the person holding the phone, and
		// says nothing about storage.
		return nil, httpx.Validation(map[string]string{"file": err.Error()})
	}

	// A person who was asked to retake one photograph has answered: the case
	// goes back to being theirs to submit.
	if row.Status == StatusResubmit {
		if err := s.store.SetStatus(ctx, row.ID, StatusDraft); err != nil {
			return nil, httpx.Internalf(err, "reopen verification")
		}
	}
	s.audit.RecordRequest(ctx, audit.Entry{
		Action: "identity.document_uploaded", SubjectType: "identity_verification",
		SubjectID: &row.ID, Detail: kind,
	})
	return s.load(ctx, row.ID, false)
}

// SubmitForReview closes the person's side of the case.
func (s *Service) SubmitForReview(ctx context.Context, id *security.Identity) (*Case, error) {
	if err := requireFreelancer(id); err != nil {
		return nil, err
	}
	row, err := s.openCase(ctx, id.UserID)
	if err != nil {
		return nil, err
	}
	view, err := s.present(ctx, row, false)
	if err != nil {
		return nil, err
	}
	if row.DocumentType == nil || *row.DocumentType == "" {
		return nil, httpx.Validation(map[string]string{"document_type": "Сначала выберите тип документа."})
	}
	if len(view.Missing) > 0 {
		labels := make([]string, 0, len(view.Missing))
		for _, kind := range view.Missing {
			labels = append(labels, kindLabel(kind))
		}
		return nil, httpx.Validation(map[string]string{
			"documents": "Не хватает снимков: " + strings.Join(labels, ", ") + ".",
		})
	}

	if err := s.store.Submit(ctx, row.ID); err != nil {
		return nil, httpx.Internalf(err, "submit verification")
	}
	_ = s.store.RecordAction(ctx, row.ID, &id.UserID, "submitted", "", "")
	s.audit.RecordRequest(ctx, audit.Entry{
		Action: "identity.submitted", SubjectType: "identity_verification", SubjectID: &row.ID,
	})
	if s.chat != nil && s.chat.Configured() {
		// Best effort and out of band: a chat that is down must not stop a
		// person from submitting their documents.
		reference := "AVX-" + strings.ToUpper(id.UserID.String()[:8])
		go func(ctx context.Context) {
			if err := s.chat.IdentitySubmitted(ctx, reference, id.UserID); err != nil {
				logx.From(ctx).Warn("identity: staff chat notice not delivered", "error", err)
			}
		}(context.WithoutCancel(ctx))
	}
	if s.notify != nil {
		s.notify.IdentitySubmitted(ctx, id.UserID)
	}
	return s.load(ctx, row.ID, false)
}

// ── Presentation ────────────────────────────────────────────────────────────

func (s *Service) load(ctx context.Context, id uuid.UUID, forReviewer bool) (*Case, error) {
	row, err := s.store.ByID(ctx, id)
	if err != nil {
		return nil, httpx.Internalf(err, "load verification")
	}
	return s.present(ctx, row, forReviewer)
}

func (s *Service) present(ctx context.Context, row *caseRow, forReviewer bool) (*Case, error) {
	docs, err := s.store.Documents(ctx, row.ID)
	if err != nil {
		return nil, httpx.Internalf(err, "list documents")
	}

	out := &Case{
		ID: row.ID, UserID: row.UserID,
		Status: row.Status, StatusLabel: statusLabel(row.Status),
		CountryCode:        deref(row.CountryCode),
		SubmittedAt:        row.SubmittedAt,
		ReviewedAt:         row.ReviewedAt,
		DecisionReason:     deref(row.DecisionReason),
		RetentionExpiresAt: row.Retention,
		CreatedAt:          row.CreatedAt,
		UpdatedAt:          row.UpdatedAt,
		Documents:          docs,
	}
	if row.DocumentType != nil {
		out.DocumentType = *row.DocumentType
		if label, _, ok := documentType(*row.DocumentType); ok {
			out.DocumentLabel = label
		}
	}
	// Who reviewed it is shown to the reviewer's colleagues, not to the
	// person under review: a name attached to a rejection invites pressure.
	if forReviewer {
		out.ReviewedBy = row.ReviewedBy
		out.ReviewerName = deref(row.ReviewerName)
	}
	for _, key := range row.Resubmit {
		if label, _, ok := resubmitReason(key); ok {
			out.Resubmit = append(out.Resubmit, ResubmitItem{Key: key, Label: label})
		}
	}

	out.Required = s.requiredKinds(row)
	have := map[string]bool{}
	for _, d := range docs {
		have[d.Kind] = true
	}
	for _, kind := range out.Required {
		if !have[kind] {
			out.Missing = append(out.Missing, kind)
		}
	}
	if out.Missing == nil {
		out.Missing = []string{}
	}
	return out, nil
}

// requiredKinds says which photographs this case needs, which depends on the
// document: a passport has no meaningful back side, an ID card does.
func (s *Service) requiredKinds(row *caseRow) []string {
	required := []string{KindFront}
	if row.DocumentType != nil {
		if _, needsBack, ok := documentType(*row.DocumentType); ok && needsBack {
			required = append(required, KindBack)
		}
	}
	if row.SelfieWithDoc {
		required = append(required, KindSelfieWithDocument)
	} else if row.SelfieRequired {
		required = append(required, KindSelfie)
	}
	return required
}

// ── Re-authentication ───────────────────────────────────────────────────────

// unlockTTL is how long a password check keeps the identity section open. Long
// enough to review a queue, short enough that an unattended laptop is not an
// open filing cabinet.
const unlockTTL = 10 * time.Minute

func unlockKey(sessionID uuid.UUID) string { return "identity:unlock:" + sessionID.String() }

// Unlock re-checks the reviewer's password before the sensitive section opens.
func (s *Service) Unlock(ctx context.Context, id *security.Identity, password string) (time.Time, error) {
	if err := s.requireView(id); err != nil {
		return time.Time{}, err
	}
	hash, err := s.pass.PasswordHash(ctx, id.UserID)
	if err != nil {
		return time.Time{}, httpx.Internalf(err, "load password hash")
	}
	if !cryptox.VerifyPassword(hash, password) {
		s.audit.Denial(ctx, "identity.unlock", nil, "wrong password")
		return time.Time{}, httpx.Validation(map[string]string{"password": "Пароль не подошёл."})
	}
	if s.cache == nil {
		e := *httpx.ErrUnavailable
		e.Code = "identity_unlock_unavailable"
		e.Message = "Подтверждение пароля сейчас недоступно. Попробуйте позже."
		return time.Time{}, &e
	}
	until := time.Now().Add(unlockTTL)
	if err := s.cache.SetJSON(ctx, unlockKey(id.SessionID), until, unlockTTL); err != nil {
		return time.Time{}, httpx.Internalf(err, "store identity unlock")
	}
	s.audit.RecordRequest(ctx, audit.Entry{Action: "identity.unlocked", SubjectType: "session"})
	return until, nil
}

// unlocked reports whether this session has re-authenticated recently.
//
// The ten-minute unlock lives in Redis. When Redis is not there — not
// configured, or down — nobody is unlocked and the documents stay shut. That
// is the direction this particular failure has to fall: a cache outage must
// not turn into "everyone can see passports", and it must not turn into a
// crash either.
func (s *Service) unlocked(ctx context.Context, id *security.Identity) bool {
	if s.cache == nil {
		return false
	}
	var until time.Time
	if err := s.cache.GetJSON(ctx, unlockKey(id.SessionID), &until); err != nil {
		return false
	}
	return time.Now().Before(until)
}

func (s *Service) requireView(id *security.Identity) error {
	if !id.Authenticated() {
		return httpx.ErrUnauthenticated
	}
	if err := security.RequirePermission(id, security.PermIdentityView); err != nil {
		return httpx.ErrForbidden.Wrap(err)
	}
	return nil
}

func (s *Service) requireReview(id *security.Identity) error {
	if err := s.requireView(id); err != nil {
		return err
	}
	if err := security.RequirePermission(id, security.PermIdentityReview); err != nil {
		return httpx.ErrForbidden.Wrap(err)
	}
	return nil
}

// requireUnlocked is the gate every sensitive read passes.
func (s *Service) requireUnlocked(ctx context.Context, id *security.Identity) error {
	if s.unlocked(ctx, id) {
		return nil
	}
	e := *httpx.ErrForbidden
	e.Code = "identity_locked"
	e.Message = "Подтвердите пароль, чтобы открыть раздел с документами."
	return &e
}

// ── The reviewer's side ─────────────────────────────────────────────────────

type QueueQuery struct {
	Status string
	Limit  int
	Offset int
}

func (s *Service) Queue(ctx context.Context, id *security.Identity, q QueueQuery) ([]QueueItem, int, error) {
	if err := s.requireView(id); err != nil {
		return nil, 0, err
	}
	if err := s.requireUnlocked(ctx, id); err != nil {
		return nil, 0, err
	}
	if q.Limit <= 0 || q.Limit > 100 {
		q.Limit = 50
	}
	status := q.Status
	if status == "" {
		status = "pending"
	}

	where := "v.status IN ('submitted','under_review')"
	args := []any{q.Limit, q.Offset}
	switch status {
	case "pending":
	case "all":
		where = "TRUE"
	case StatusApproved, StatusRejected, StatusResubmit, StatusSuspended, StatusDraft:
		where = "v.status = $3"
		args = append(args, status)
	default:
		return nil, 0, httpx.Validation(map[string]string{"status": "Неизвестный статус."})
	}

	rows, err := s.db.Query(ctx, `
		SELECT v.id, v.user_id, u.username, u.full_name, v.status,
		       v.document_type, v.country_code, v.submitted_at,
		       (SELECT count(*) FROM identity_documents d
		         WHERE d.verification_id = v.id AND d.status IN ('pending','accepted')),
		       count(*) OVER ()
		FROM identity_verifications v
		JOIN users u ON u.id = v.user_id
		WHERE `+where+`
		ORDER BY v.submitted_at NULLS LAST, v.created_at
		LIMIT $1 OFFSET $2`, args...)
	if err != nil {
		return nil, 0, httpx.Internalf(err, "list verification queue")
	}
	defer rows.Close()

	out := []QueueItem{}
	total := 0
	for rows.Next() {
		var item QueueItem
		var docType, country *string
		if err := rows.Scan(&item.ID, &item.UserID, &item.Username, &item.FullName, &item.Status,
			&docType, &country, &item.SubmittedAt, &item.Documents, &total); err != nil {
			return nil, 0, httpx.Internalf(err, "scan verification queue")
		}
		item.StatusLabel = statusLabel(item.Status)
		item.DocumentType, item.CountryCode = deref(docType), deref(country)
		if label, _, ok := documentType(item.DocumentType); ok {
			item.DocumentLabel = label
		}
		if item.SubmittedAt != nil {
			item.WaitingHours = int(time.Since(*item.SubmittedAt).Hours())
		}
		out = append(out, item)
	}
	if err := rows.Err(); err != nil {
		return nil, 0, httpx.Internalf(err, "read verification queue")
	}

	s.logAccess(ctx, id, nil, "identity_queue", "", "list", "")
	return out, total, nil
}

// ForUser opens one person's case for review. Opening it is itself an access
// worth recording, which is why the log entry is written here and not only
// when an image is fetched.
func (s *Service) ForUser(ctx context.Context, id *security.Identity, userID uuid.UUID) (*Case, error) {
	if err := s.requireView(id); err != nil {
		return nil, err
	}
	if err := s.requireUnlocked(ctx, id); err != nil {
		return nil, err
	}
	row, err := s.store.Current(ctx, userID)
	if errors.Is(err, ErrNotFound) {
		return nil, httpx.NotFoundf("user %s has no verification case", userID)
	}
	if err != nil {
		return nil, httpx.Internalf(err, "load verification")
	}
	// A case that arrives for review is being reviewed: the queue must show
	// that somebody has it.
	if row.Status == StatusSubmitted {
		if err := s.store.SetStatus(ctx, row.ID, StatusUnderRev); err == nil {
			row.Status = StatusUnderRev
		}
	}
	s.logAccess(ctx, id, &userID, "identity_case", row.ID.String(), "open", "")
	return s.present(ctx, row, true)
}

// ViewToken issues a short-lived ticket for one image, bound to one reviewer,
// one signed-in session and that one document.
//
// The image endpoint accepts nothing else. A URL copied out of the panel is
// useless within two minutes, and useless immediately to anyone but the
// reviewer it was issued to. It is not consumed on first use — a viewer that
// zooms or rotates re-requests the same bytes — but it dies with the session
// it was issued in, and every issue is written to the access log with the
// reason the reviewer gave.
type ViewToken struct {
	Token     string    `json:"token"`
	URL       string    `json:"url"`
	ExpiresAt time.Time `json:"expires_at"`
}

const viewTokenTTL = 2 * time.Minute

type viewTicket struct {
	AdminID    uuid.UUID `json:"admin_id"`
	DocumentID uuid.UUID `json:"document_id"`
	SessionID  uuid.UUID `json:"session_id"`
}

func (s *Service) ViewToken(ctx context.Context, id *security.Identity, docID uuid.UUID, reason string) (*ViewToken, error) {
	if err := s.requireView(id); err != nil {
		return nil, err
	}
	if err := s.requireUnlocked(ctx, id); err != nil {
		return nil, err
	}
	doc, err := s.store.Document(ctx, docID)
	if errors.Is(err, ErrNoDocument) {
		return nil, httpx.NotFoundf("identity document %s does not exist", docID)
	}
	if err != nil {
		return nil, httpx.Internalf(err, "load document")
	}
	if doc.DeletedAt != nil {
		e := *httpx.ErrConflict
		e.Code = "document_deleted"
		e.Message = "Изображение удалено по сроку хранения. Осталось только решение по проверке."
		return nil, &e
	}

	token, err := cryptox.RandomHex(32)
	if err != nil {
		return nil, httpx.Internalf(err, "generate view token")
	}
	ticket := viewTicket{AdminID: id.UserID, DocumentID: docID, SessionID: id.SessionID}
	if err := s.cache.SetJSON(ctx, "identity:view:"+token, ticket, viewTokenTTL); err != nil {
		return nil, httpx.Internalf(err, "store view token")
	}

	s.logAccess(ctx, id, &doc.UserID, "identity_document", docID.String(), "view:"+doc.Kind, reason)
	return &ViewToken{
		Token:     token,
		URL:       "/api/v1/admin/identity/documents/" + docID.String() + "/file?t=" + token,
		ExpiresAt: time.Now().Add(viewTokenTTL),
	}, nil
}

// Stream serves the bytes of one image, and only against a ticket that was
// issued to this caller for this document.
func (s *Service) Stream(ctx context.Context, id *security.Identity, docID uuid.UUID, token string) (io.ReadCloser, string, error) {
	if err := s.requireView(id); err != nil {
		return nil, "", err
	}
	if err := s.requireUnlocked(ctx, id); err != nil {
		return nil, "", err
	}
	if token == "" {
		return nil, "", httpx.ErrForbidden.Wrap(errors.New("missing view token"))
	}

	var ticket viewTicket
	if err := s.cache.GetJSON(ctx, "identity:view:"+token, &ticket); err != nil {
		return nil, "", httpx.ErrForbidden.Wrap(errors.New("view token expired or unknown"))
	}
	if ticket.AdminID != id.UserID || ticket.DocumentID != docID || ticket.SessionID != id.SessionID {
		s.audit.Denial(ctx, "identity.stream", &docID, "view token does not belong to this caller")
		return nil, "", httpx.ErrForbidden.Wrap(errors.New("view token belongs to another caller"))
	}

	doc, err := s.store.Document(ctx, docID)
	if err != nil {
		return nil, "", httpx.NotFoundf("identity document %s does not exist", docID)
	}
	if doc.DeletedAt != nil {
		return nil, "", httpx.NotFoundf("identity document %s has been deleted", docID)
	}
	body, err := s.store.Open(ctx, doc)
	if err != nil {
		return nil, "", httpx.Internalf(err, "open document")
	}
	return body, doc.MIME, nil
}

// ── Decisions ───────────────────────────────────────────────────────────────

type DecisionRequest struct {
	Action string `json:"action"`
	Reason string `json:"reason"`
	// For a resubmission request: which of the closed reasons apply.
	Reasons []string `json:"reasons"`
}

func (s *Service) Decide(ctx context.Context, id *security.Identity, caseID uuid.UUID, in DecisionRequest) (*Case, error) {
	if err := s.requireReview(id); err != nil {
		return nil, err
	}
	if err := s.requireUnlocked(ctx, id); err != nil {
		return nil, err
	}

	row, err := s.store.ByID(ctx, caseID)
	if errors.Is(err, ErrNotFound) {
		return nil, httpx.NotFoundf("verification %s does not exist", caseID)
	}
	if err != nil {
		return nil, httpx.Internalf(err, "load verification")
	}

	v := validate.New()
	action := v.OneOf("action", "Решение", in.Action,
		"approve", "reject", "request_resubmit", "suspend")
	reason := strings.TrimSpace(in.Reason)
	// Every decision is explained. An approval too: the next reviewer has to
	// be able to see what this one checked.
	v.Length("reason", "Обоснование", reason, 10, 2000)

	var keys []string
	if action == "request_resubmit" {
		for _, key := range in.Reasons {
			if _, _, ok := resubmitReason(strings.TrimSpace(key)); !ok {
				v.Addf("reasons", "Неизвестная причина: %s.", key)
				continue
			}
			keys = append(keys, strings.TrimSpace(key))
		}
		if len(keys) == 0 {
			v.Add("reasons", "Выберите хотя бы одну причину — человеку нужно знать, что переснять.")
		}
	}
	if v.Any() {
		return nil, httpx.Validation(v.Fields())
	}

	status := map[string]string{
		"approve":          StatusApproved,
		"reject":           StatusRejected,
		"request_resubmit": StatusResubmit,
		"suspend":          StatusSuspended,
	}[action]

	var retention *time.Time
	if status == StatusApproved || status == StatusRejected {
		if days := s.settings.Int(ctx, "identity.retention_days", 180); days > 0 {
			at := time.Now().AddDate(0, 0, days)
			retention = &at
		}
	}

	if err := s.store.Decide(ctx, caseID, id.UserID, status, reason, keys, retention); err != nil {
		return nil, httpx.Internalf(err, "record decision")
	}
	_ = s.store.RecordAction(ctx, caseID, &id.UserID, action, reason, strings.Join(keys, ", "))

	// The audit entry names the decision and never the document: a log that
	// quotes a passport number defeats the point of protecting the image.
	s.audit.RecordRequest(ctx, audit.Entry{
		Action: "identity." + action, SubjectType: "user", SubjectID: &row.UserID,
		After: map[string]any{"status": status}, Detail: reason,
	})
	s.logAccess(ctx, id, &row.UserID, "identity_case", caseID.String(), "decide:"+action, reason)

	if s.notify != nil {
		switch status {
		case StatusApproved:
			s.notify.IdentityApproved(ctx, row.UserID)
		case StatusRejected:
			s.notify.IdentityRejected(ctx, row.UserID, reason)
		case StatusResubmit:
			labels := make([]string, 0, len(keys))
			for _, key := range keys {
				if label, _, ok := resubmitReason(key); ok {
					labels = append(labels, label)
				}
			}
			s.notify.IdentityResubmitRequested(ctx, row.UserID, strings.Join(labels, ". ")+".")
		}
	}
	return s.load(ctx, caseID, true)
}

// History returns the decisions on a case.
func (s *Service) History(ctx context.Context, id *security.Identity, caseID uuid.UUID) ([]ReviewAction, error) {
	if err := s.requireView(id); err != nil {
		return nil, err
	}
	if err := s.requireUnlocked(ctx, id); err != nil {
		return nil, err
	}
	out, err := s.store.Actions(ctx, caseID)
	if err != nil {
		return nil, httpx.Internalf(err, "list review actions")
	}
	return out, nil
}

// AccessLog answers "who has looked at this person's documents".
//
// Reading it needs audit.read on top of identity access: the log of who read
// what is itself sensitive, and it is the record that would catch a reviewer
// browsing documents out of curiosity.
func (s *Service) AccessLog(ctx context.Context, id *security.Identity, userID uuid.UUID, limit int) ([]AccessEntry, error) {
	if err := s.requireView(id); err != nil {
		return nil, err
	}
	if err := security.RequirePermission(id, security.PermAuditRead); err != nil {
		return nil, httpx.ErrForbidden.Wrap(err)
	}
	if limit <= 0 || limit > 200 {
		limit = 100
	}
	rows, err := s.db.Query(ctx, `
		SELECT l.id, l.actor_id, u.full_name, l.subject_user_id, l.resource_type,
		       l.resource_id, l.action, l.reason, host(l.ip), l.created_at
		FROM admin_access_logs l
		LEFT JOIN users u ON u.id = l.actor_id
		WHERE l.subject_user_id = $1
		ORDER BY l.created_at DESC
		LIMIT $2`, userID, limit)
	if err != nil {
		return nil, httpx.Internalf(err, "list access log")
	}
	defer rows.Close()

	out := []AccessEntry{}
	for rows.Next() {
		var e AccessEntry
		var name, resourceID, reason, ip *string
		if err := rows.Scan(&e.ID, &e.ActorID, &name, &e.SubjectID, &e.Resource,
			&resourceID, &e.Action, &reason, &ip, &e.CreatedAt); err != nil {
			return nil, httpx.Internalf(err, "scan access log")
		}
		e.ActorName, e.ResourceID, e.Reason, e.IP = deref(name), deref(resourceID), deref(reason), deref(ip)
		out = append(out, e)
	}
	return out, rows.Err()
}

// logAccess writes the record of a read. It is deliberately best-effort in
// the sense that it never fails the request — but a failure is logged loudly,
// because an access nobody can account for is the thing this table exists to
// prevent.
func (s *Service) logAccess(ctx context.Context, id *security.Identity, subject *uuid.UUID,
	resourceType, resourceID, action, reason string) {

	_, err := s.db.Exec(context.WithoutCancel(ctx), `
		INSERT INTO admin_access_logs
		  (actor_id, subject_user_id, resource_type, resource_id, action, reason,
		   session_id, ip, user_agent)
		VALUES ($1,$2,$3,nullif($4,''),$5,nullif($6,''),$7,$8,nullif($9,''))`,
		id.UserID, subject, resourceType, resourceID, action, reason,
		id.SessionID, nullInet(httpx.ClientIP(ctx)), userAgent(ctx))
	if err != nil {
		logx.From(ctx).Error("failed to record identity access", "error", err,
			"actor", id.UserID, "resource", resourceType)
	}
}

func nullInet(ip string) any {
	if ip == "" || net.ParseIP(ip) == nil {
		return nil
	}
	return ip
}

// userAgent reads the browser the reviewer used, when the HTTP layer put it
// in context. Recorded because "the same admin from an unfamiliar client" is
// exactly the pattern this log exists to make visible.
func userAgent(ctx context.Context) string {
	if v, ok := ctx.Value(userAgentKey).(string); ok {
		return v
	}
	return ""
}

type ctxKey int

const userAgentKey ctxKey = iota

// WithUserAgent carries the caller's browser into the access log.
func WithUserAgent(ctx context.Context, agent string) context.Context {
	return context.WithValue(ctx, userAgentKey, agent)
}

// PurgeExpired is the retention job, run by the worker.
//
// The images go; the decision stays. A verification that was approved in
// March is still approved in September, but the photograph of the passport
// that proved it is not kept for as long as the account exists.
func (s *Service) PurgeExpired(ctx context.Context) (string, error) {
	removed, err := s.store.PurgeExpired(ctx, 200)
	if err != nil {
		return "", err
	}
	if removed == 0 {
		return "nothing past its retention", nil
	}
	logx.From(ctx).Info("deleted identity documents past their retention", "count", removed)
	s.audit.Record(ctx, audit.Entry{
		Action: "identity.documents_purged", SubjectType: "identity_document",
		Detail: fmt.Sprintf("%d document(s) removed after retention", removed),
	})
	return fmt.Sprintf("removed %d document(s)", removed), nil
}
