package identity

import (
	"bytes"
	"context"
	"crypto/sha256"
	"encoding/hex"
	"errors"
	"fmt"
	"io"
	"time"

	"github.com/google/uuid"

	"github.com/averix/api/internal/platform/cryptox"
	"github.com/averix/api/internal/platform/database"
	"github.com/averix/api/internal/platform/imaging"
	"github.com/averix/api/internal/platform/storage"
)

var (
	ErrNotFound   = errors.New("verification case not found")
	ErrNoDocument = errors.New("document not found")
)

type Store struct {
	db    *database.DB
	blobs storage.Store
}

func NewStore(db *database.DB, blobs storage.Store) *Store {
	return &Store{db: db, blobs: blobs}
}

// storagePrefix keeps identity images in their own corner of the private
// bucket. Nothing else is ever written under it, so a bucket policy or a
// retention rule can be written against this prefix alone.
const storagePrefix = "identity"

// newKey builds an unguessable key that carries nothing about the person.
//
// Deliberately not sharded by user id, unlike every other upload in the
// product: a listing of this prefix must not reveal who has submitted
// documents, and a key that leaks must not name its owner.
func newKey(extension string) (string, error) {
	rnd, err := cryptox.RandomHex(24)
	if err != nil {
		return "", err
	}
	ext := "jpg"
	switch extension {
	case "png", "webp", "jpeg", "jpg":
		ext = extension
	}
	return fmt.Sprintf("%s/%s/%s.%s", storagePrefix, rnd[:2], rnd[2:], ext), nil
}

// ── Cases ───────────────────────────────────────────────────────────────────

type caseRow struct {
	ID, UserID     uuid.UUID
	Status         string
	DocumentType   *string
	CountryCode    *string
	SubmittedAt    *time.Time
	ReviewedAt     *time.Time
	ReviewedBy     *uuid.UUID
	ReviewerName   *string
	DecisionReason *string
	Resubmit       []string
	SelfieRequired bool
	SelfieWithDoc  bool
	Retention      *time.Time
	CreatedAt      time.Time
	UpdatedAt      time.Time
}

const caseSelect = `
	SELECT v.id, v.user_id, v.status, v.document_type, v.country_code,
	       v.submitted_at, v.reviewed_at, v.reviewed_by, r.full_name,
	       v.decision_reason, v.resubmit_reasons,
	       v.selfie_required, v.selfie_with_document, v.retention_expires_at,
	       v.created_at, v.updated_at
	FROM identity_verifications v
	LEFT JOIN users r ON r.id = v.reviewed_by`

func (s *Store) scanCase(row interface{ Scan(...any) error }) (*caseRow, error) {
	var c caseRow
	err := row.Scan(&c.ID, &c.UserID, &c.Status, &c.DocumentType, &c.CountryCode,
		&c.SubmittedAt, &c.ReviewedAt, &c.ReviewedBy, &c.ReviewerName,
		&c.DecisionReason, &c.Resubmit,
		&c.SelfieRequired, &c.SelfieWithDoc, &c.Retention,
		&c.CreatedAt, &c.UpdatedAt)
	if database.IsNoRows(err) {
		return nil, ErrNotFound
	}
	if err != nil {
		return nil, fmt.Errorf("scan verification case: %w", err)
	}
	return &c, nil
}

// Current returns the case a person is working on or waiting on, and falls
// back to their most recent decided one.
func (s *Store) Current(ctx context.Context, userID uuid.UUID) (*caseRow, error) {
	return s.scanCase(s.db.QueryRow(ctx, caseSelect+`
		WHERE v.user_id = $1
		ORDER BY (v.status IN ('draft','submitted','under_review','resubmit_requested')) DESC,
		         v.created_at DESC
		LIMIT 1`, userID))
}

func (s *Store) ByID(ctx context.Context, id uuid.UUID) (*caseRow, error) {
	return s.scanCase(s.db.QueryRow(ctx, caseSelect+` WHERE v.id = $1`, id))
}

// OpenOrCreate returns the case a person may still edit, creating one when
// there is none. The partial unique index is what makes "one open case" true
// under a double-click, not this check.
func (s *Store) OpenOrCreate(ctx context.Context, userID uuid.UUID, selfieWithDocument bool) (*caseRow, error) {
	existing, err := s.scanCase(s.db.QueryRow(ctx, caseSelect+`
		WHERE v.user_id = $1
		  AND v.status IN ('draft','resubmit_requested')
		ORDER BY v.created_at DESC LIMIT 1`, userID))
	if err == nil {
		return existing, nil
	}
	if !errors.Is(err, ErrNotFound) {
		return nil, err
	}

	var id uuid.UUID
	err = s.db.QueryRow(ctx, `
		INSERT INTO identity_verifications (user_id, status, selfie_with_document)
		VALUES ($1, 'draft', $2)
		RETURNING id`, userID, selfieWithDocument).Scan(&id)
	if database.IsUniqueViolation(err, "identity_verifications_open_per_user") {
		// Somebody's second tab won the race; theirs is the open case.
		return s.scanCase(s.db.QueryRow(ctx, caseSelect+`
			WHERE v.user_id = $1
			  AND v.status IN ('draft','submitted','under_review','resubmit_requested')
			LIMIT 1`, userID))
	}
	if err != nil {
		return nil, fmt.Errorf("open verification case: %w", err)
	}
	return s.ByID(ctx, id)
}

func (s *Store) SaveDetails(ctx context.Context, id uuid.UUID, documentType, country, name string, dob *time.Time) error {
	_, err := s.db.Exec(ctx, `
		UPDATE identity_verifications
		   SET document_type = $2, country_code = $3,
		       document_name = nullif($4, ''), date_of_birth = $5,
		       updated_at = now()
		 WHERE id = $1`, id, documentType, country, name, dob)
	if err != nil {
		return fmt.Errorf("save verification details: %w", err)
	}
	return nil
}

func (s *Store) SetStatus(ctx context.Context, id uuid.UUID, status string) error {
	_, err := s.db.Exec(ctx, `
		UPDATE identity_verifications SET status = $2, updated_at = now() WHERE id = $1`, id, status)
	if err != nil {
		return fmt.Errorf("set verification status: %w", err)
	}
	return nil
}

func (s *Store) Submit(ctx context.Context, id uuid.UUID) error {
	_, err := s.db.Exec(ctx, `
		UPDATE identity_verifications
		   SET status = 'submitted', submitted_at = now(),
		       resubmit_reasons = '{}', decision_reason = NULL, updated_at = now()
		 WHERE id = $1`, id)
	if err != nil {
		return fmt.Errorf("submit verification: %w", err)
	}
	return nil
}

// Decide records a reviewer's ruling and, for an approval, stamps the user's
// profile in the same transaction: a verified badge that outlived its case
// would be a lie nobody could trace.
func (s *Store) Decide(ctx context.Context, id, actorID uuid.UUID, status, reason string,
	resubmit []string, retention *time.Time) error {

	return s.db.InTx(ctx, func(q database.Querier) error {
		var userID uuid.UUID
		err := q.QueryRow(ctx, `
			UPDATE identity_verifications
			   SET status = $2,
			       reviewed_at = now(),
			       reviewed_by = $3,
			       decision_reason = nullif($4, ''),
			       resubmit_reasons = $5,
			       retention_expires_at = coalesce($6, retention_expires_at),
			       updated_at = now()
			 WHERE id = $1
			RETURNING user_id`, id, status, actorID, reason, database.Array(resubmit), retention).Scan(&userID)
		if database.IsNoRows(err) {
			return ErrNotFound
		}
		if err != nil {
			return fmt.Errorf("record decision: %w", err)
		}

		switch status {
		case StatusApproved:
			if _, err := q.Exec(ctx, `
				UPDATE users SET identity_verified_at = now(), updated_at = now()
				 WHERE id = $1`, userID); err != nil {
				return fmt.Errorf("mark identity verified: %w", err)
			}
			if _, err := q.Exec(ctx, `
				UPDATE identity_documents SET status = 'accepted'
				 WHERE verification_id = $1 AND status = 'pending'`, id); err != nil {
				return fmt.Errorf("accept documents: %w", err)
			}
			if retention != nil {
				if _, err := q.Exec(ctx, `
					UPDATE identity_documents SET retention_expires_at = $2
					 WHERE verification_id = $1 AND deleted_at IS NULL`, id, *retention); err != nil {
					return fmt.Errorf("set document retention: %w", err)
				}
			}
		case StatusRejected, StatusSuspended:
			// A rejected case must not leave a verified badge behind.
			if _, err := q.Exec(ctx, `
				UPDATE users SET identity_verified_at = NULL, updated_at = now()
				 WHERE id = $1`, userID); err != nil {
				return fmt.Errorf("clear identity verification: %w", err)
			}
			if retention != nil {
				if _, err := q.Exec(ctx, `
					UPDATE identity_documents SET retention_expires_at = $2
					 WHERE verification_id = $1 AND deleted_at IS NULL`, id, *retention); err != nil {
					return fmt.Errorf("set document retention: %w", err)
				}
			}
		}
		return nil
	})
}

// ── Documents ───────────────────────────────────────────────────────────────

type storedDocument struct {
	ID         uuid.UUID
	UserID     uuid.UUID
	CaseID     uuid.UUID
	Kind       string
	StorageKey string
	MIME       string
	ByteSize   int64
	Status     string
	DeletedAt  *time.Time
}

// SaveDocument writes one image to private storage and records it, replacing
// whatever was there for the same side.
//
// The bytes are inspected before they are written: what a browser calls the
// file decides nothing. Only real images pass.
func (s *Store) SaveDocument(ctx context.Context, caseID, userID uuid.UUID, kind string,
	r io.Reader, maxBytes int64) (*Document, error) {

	raw, err := io.ReadAll(io.LimitReader(r, maxBytes+1))
	if err != nil {
		return nil, fmt.Errorf("read document: %w", err)
	}
	if len(raw) == 0 {
		return nil, errors.New("файл пустой")
	}
	if int64(len(raw)) > maxBytes {
		return nil, fmt.Errorf("файл больше %d МБ", maxBytes>>20)
	}

	info, _, err := imaging.Inspect(bytes.NewReader(raw))
	if err != nil {
		return nil, errors.New("это не изображение")
	}
	if err := imaging.CheckBomb(info, int64(len(raw))); err != nil {
		return nil, errors.New("изображение не удалось обработать")
	}
	// The bytes decide the type. A file called passport.jpg that is really a
	// PDF, or an SVG that a browser would execute, stops here.
	switch info.Kind {
	case imaging.JPEG, imaging.PNG, imaging.WebP:
	default:
		return nil, errors.New("подойдут JPEG, PNG или WebP")
	}
	mime := string(info.Kind)
	if info.Width < 300 || info.Height < 300 {
		return nil, errors.New("снимок слишком мелкий: нужна сторона не меньше 300 пикселей")
	}

	key, err := newKey(info.Kind.Extension())
	if err != nil {
		return nil, fmt.Errorf("build storage key: %w", err)
	}
	sum := sha256.Sum256(raw)

	if _, err := s.blobs.Put(ctx, key, bytes.NewReader(raw), int64(len(raw)), storage.PutOptions{
		ContentType: mime,
		Visibility:  storage.Private,
		// No download name and no owner metadata: an object in this prefix
		// says nothing about whose document it is.
		CacheControl: "no-store",
	}); err != nil {
		return nil, fmt.Errorf("store document: %w", err)
	}

	var doc Document
	err = s.db.InTx(ctx, func(q database.Querier) error {
		if _, err := q.Exec(ctx, `
			UPDATE identity_documents SET status = 'replaced'
			 WHERE verification_id = $1 AND kind = $2 AND status IN ('pending','accepted')`,
			caseID, kind); err != nil {
			return fmt.Errorf("replace previous document: %w", err)
		}
		width, height := info.Width, info.Height
		return q.QueryRow(ctx, `
			INSERT INTO identity_documents
			  (verification_id, user_id, kind, storage_key, mime, byte_size,
			   checksum_sha256, width, height)
			VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9)
			RETURNING id, kind, mime, byte_size, width, height, status, created_at`,
			caseID, userID, kind, key, mime, int64(len(raw)),
			hex.EncodeToString(sum[:]), width, height).
			Scan(&doc.ID, &doc.Kind, &doc.MIME, &doc.ByteSize, &doc.Width, &doc.Height,
				&doc.Status, &doc.CreatedAt)
	})
	if err != nil {
		// The object is already written; leaving it unreferenced is worse than
		// removing it, because nothing would ever delete it.
		_ = s.blobs.Delete(context.WithoutCancel(ctx), key, storage.Private)
		return nil, err
	}
	doc.KindLabel = kindLabel(doc.Kind)
	return &doc, nil
}

func (s *Store) Documents(ctx context.Context, caseID uuid.UUID) ([]Document, error) {
	rows, err := s.db.Query(ctx, `
		SELECT id, kind, mime, byte_size, width, height, status, created_at, deleted_at
		FROM identity_documents
		WHERE verification_id = $1 AND status IN ('pending','accepted')
		ORDER BY array_position(ARRAY['front','back','selfie','selfie_with_document'], kind)`,
		caseID)
	if err != nil {
		return nil, fmt.Errorf("list documents: %w", err)
	}
	defer rows.Close()

	out := []Document{}
	for rows.Next() {
		var d Document
		if err := rows.Scan(&d.ID, &d.Kind, &d.MIME, &d.ByteSize, &d.Width, &d.Height,
			&d.Status, &d.CreatedAt, &d.DeletedAt); err != nil {
			return nil, err
		}
		d.KindLabel = kindLabel(d.Kind)
		out = append(out, d)
	}
	return out, rows.Err()
}

// Document loads one image's record, including where it is stored. The key is
// used to fetch the bytes and never leaves this package.
func (s *Store) Document(ctx context.Context, id uuid.UUID) (*storedDocument, error) {
	var d storedDocument
	err := s.db.QueryRow(ctx, `
		SELECT id, user_id, verification_id, kind, storage_key, mime, byte_size, status, deleted_at
		FROM identity_documents WHERE id = $1`, id).
		Scan(&d.ID, &d.UserID, &d.CaseID, &d.Kind, &d.StorageKey, &d.MIME,
			&d.ByteSize, &d.Status, &d.DeletedAt)
	if database.IsNoRows(err) {
		return nil, ErrNoDocument
	}
	if err != nil {
		return nil, fmt.Errorf("load document: %w", err)
	}
	return &d, nil
}

// Open streams a stored image.
func (s *Store) Open(ctx context.Context, doc *storedDocument) (io.ReadCloser, error) {
	body, _, err := s.blobs.Get(ctx, doc.StorageKey, storage.Private)
	if err != nil {
		return nil, fmt.Errorf("read document: %w", err)
	}
	return body, nil
}

// ── Retention ───────────────────────────────────────────────────────────────

// PurgeExpired deletes the images whose retention has run out and keeps the
// decision. Returns how many were removed.
//
// The row stays with status 'deleted' so the case still shows that a document
// was submitted and when it went — an empty gap would look like tampering.
func (s *Store) PurgeExpired(ctx context.Context, limit int) (int, error) {
	rows, err := s.db.Query(ctx, `
		SELECT id, storage_key FROM identity_documents
		WHERE deleted_at IS NULL
		  AND retention_expires_at IS NOT NULL
		  AND retention_expires_at <= now()
		LIMIT $1`, limit)
	if err != nil {
		return 0, fmt.Errorf("list expired documents: %w", err)
	}
	type expired struct {
		id  uuid.UUID
		key string
	}
	var batch []expired
	for rows.Next() {
		var e expired
		if err := rows.Scan(&e.id, &e.key); err != nil {
			rows.Close()
			return 0, err
		}
		batch = append(batch, e)
	}
	rows.Close()
	if err := rows.Err(); err != nil {
		return 0, err
	}

	removed := 0
	for _, e := range batch {
		if err := s.blobs.Delete(ctx, e.key, storage.Private); err != nil && !errors.Is(err, storage.ErrNotFound) {
			return removed, fmt.Errorf("delete expired document: %w", err)
		}
		if _, err := s.db.Exec(ctx, `
			UPDATE identity_documents
			   SET status = 'deleted', deleted_at = now(), storage_key = ''
			 WHERE id = $1`, e.id); err != nil {
			return removed, fmt.Errorf("mark document deleted: %w", err)
		}
		removed++
	}
	return removed, nil
}

// ── History ─────────────────────────────────────────────────────────────────

func (s *Store) RecordAction(ctx context.Context, caseID uuid.UUID, actorID *uuid.UUID,
	action, reason, detail string) error {

	_, err := s.db.Exec(ctx, `
		INSERT INTO identity_review_actions (verification_id, actor_id, action, reason, detail)
		VALUES ($1,$2,$3,nullif($4,''),nullif($5,''))`, caseID, actorID, action, reason, detail)
	if err != nil {
		return fmt.Errorf("record review action: %w", err)
	}
	return nil
}

func (s *Store) Actions(ctx context.Context, caseID uuid.UUID) ([]ReviewAction, error) {
	rows, err := s.db.Query(ctx, `
		SELECT a.id, a.actor_id, u.full_name, a.action, a.reason, a.detail, a.created_at
		FROM identity_review_actions a
		LEFT JOIN users u ON u.id = a.actor_id
		WHERE a.verification_id = $1
		ORDER BY a.created_at DESC`, caseID)
	if err != nil {
		return nil, fmt.Errorf("list review actions: %w", err)
	}
	defer rows.Close()

	out := []ReviewAction{}
	for rows.Next() {
		var a ReviewAction
		var name, reason, detail *string
		if err := rows.Scan(&a.ID, &a.ActorID, &name, &a.Action, &reason, &detail, &a.CreatedAt); err != nil {
			return nil, err
		}
		a.ActorName, a.Reason, a.Detail = deref(name), deref(reason), deref(detail)
		out = append(out, a)
	}
	return out, rows.Err()
}

func deref(v *string) string {
	if v == nil {
		return ""
	}
	return *v
}
