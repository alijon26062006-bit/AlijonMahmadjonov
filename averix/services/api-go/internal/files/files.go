// Package files owns uploads: validation, storage and authorised access.
//
// Three rules, each of which closes a classic upload hole:
//
//  1. The storage key is composed from the purpose, a date shard and random
//     bytes — never from the uploaded filename. An upload called
//     "../../etc/passwd" or "avatar.php.jpg" therefore cannot influence where
//     it is written or what it is served as.
//  2. The type is decided from the magic bytes. The browser-supplied
//     Content-Type and the extension are both recorded and both ignored.
//  3. A private file is served only after an authorisation check, through a
//     short-lived signed URL. There is no endpoint that streams a file by id
//     without asking who is entitled to it.
package files

import (
	"bytes"
	"context"
	"crypto/sha256"
	"errors"
	"fmt"
	"io"
	"path/filepath"
	"strings"
	"time"

	"github.com/google/uuid"

	"github.com/averix/api/internal/platform/database"
	"github.com/averix/api/internal/platform/imaging"
	"github.com/averix/api/internal/platform/storage"
)

// Purpose decides the bucket, the size limit and the accepted types.
type Purpose string

const (
	PurposeAvatar            Purpose = "avatar"
	PurposePortfolio         Purpose = "portfolio"
	PurposeProjectAttachment Purpose = "project_attachment"
	PurposeMessageAttachment Purpose = "message_attachment"
	PurposeDeliverable       Purpose = "deliverable"
	PurposeDisputeEvidence   Purpose = "dispute_evidence"
	PurposeServiceCover      Purpose = "service_cover"
)

// rules per purpose. Images are public because they appear in lists and on
// profiles; everything attached to a contract is private, because it is the
// work product and the parties' business.
var rules = map[Purpose]struct {
	MaxBytes   int64
	Visibility storage.Visibility
	// Accepted types. An empty set means "any of the document types below".
	Images    bool
	Documents bool
}{
	PurposeAvatar:            {MaxBytes: 10 << 20, Visibility: storage.Public, Images: true},
	PurposePortfolio:         {MaxBytes: 10 << 20, Visibility: storage.Public, Images: true},
	PurposeServiceCover:      {MaxBytes: 10 << 20, Visibility: storage.Public, Images: true},
	PurposeProjectAttachment: {MaxBytes: 25 << 20, Visibility: storage.Private, Images: true, Documents: true},
	PurposeMessageAttachment: {MaxBytes: 25 << 20, Visibility: storage.Private, Images: true, Documents: true},
	PurposeDeliverable:       {MaxBytes: 50 << 20, Visibility: storage.Private, Images: true, Documents: true},
	PurposeDisputeEvidence:   {MaxBytes: 25 << 20, Visibility: storage.Private, Images: true, Documents: true},
}

// documentTypes is the closed set of non-image uploads AVERIX accepts.
//
// Deliberately narrow. Anything executable, anything that can carry a macro,
// and anything a browser might render as HTML in our own origin is absent.
var documentTypes = map[string]string{
	"application/pdf":  "pdf",
	"application/zip":  "zip",
	"text/plain":       "txt",
	"text/markdown":    "md",
	"text/csv":         "csv",
	"application/json": "json",
	"application/vnd.openxmlformats-officedocument.wordprocessingml.document":   "docx",
	"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet":         "xlsx",
	"application/vnd.openxmlformats-officedocument.presentationml.presentation": "pptx",
}

type File struct {
	ID           uuid.UUID `json:"id"`
	OwnerID      uuid.UUID `json:"-"`
	OriginalName string    `json:"original_name"`
	ByteSize     int64     `json:"byte_size"`
	MIME         string    `json:"mime"`
	Width        *int      `json:"width,omitempty"`
	Height       *int      `json:"height,omitempty"`
	Purpose      Purpose   `json:"purpose"`
	Access       string    `json:"access"`
	// Present for a public file. A private one gets a signed URL instead, from
	// the endpoint that checked the caller's entitlement.
	URL       string    `json:"url,omitempty"`
	CreatedAt time.Time `json:"created_at"`
	// storageKey never leaves the server.
	storageKey string
}

func (f *File) StorageKey() string { return f.storageKey }

type Store struct {
	db        *database.DB
	blobs     storage.Store
	publicURL func(string) string
}

func NewStore(db *database.DB, blobs storage.Store) *Store {
	return &Store{db: db, blobs: blobs, publicURL: blobs.PublicURL}
}

var (
	ErrNotFound       = errors.New("file not found")
	ErrTooLarge       = errors.New("file exceeds the limit for this purpose")
	ErrTypeNotAllowed = errors.New("file type is not accepted for this purpose")
	ErrUnknownPurpose = errors.New("unknown upload purpose")
	ErrEmpty          = errors.New("file is empty")
)

// UploadInput is one upload in progress.
type UploadInput struct {
	OwnerID uuid.UUID
	Purpose Purpose
	// What the browser said. Recorded for the download filename and for
	// spotting an upload that lied about itself; never used to decide anything.
	DeclaredName string
	DeclaredMIME string
	Reader       io.Reader
}

// Save validates and stores an upload.
func (s *Store) Save(ctx context.Context, in UploadInput) (*File, error) {
	rule, ok := rules[in.Purpose]
	if !ok {
		return nil, fmt.Errorf("%w: %q", ErrUnknownPurpose, in.Purpose)
	}

	// Read with one byte of headroom so an over-size upload is detected rather
	// than silently truncated.
	raw, err := io.ReadAll(io.LimitReader(in.Reader, rule.MaxBytes+1))
	if err != nil {
		return nil, fmt.Errorf("read upload: %w", err)
	}
	if len(raw) == 0 {
		return nil, ErrEmpty
	}
	if int64(len(raw)) > rule.MaxBytes {
		return nil, fmt.Errorf("%w: %d bytes exceeds %d", ErrTooLarge, len(raw), rule.MaxBytes)
	}

	detected, extension, err := s.detect(raw, rule.Images, rule.Documents)
	if err != nil {
		return nil, err
	}

	var width, height *int
	if strings.HasPrefix(detected, "image/") {
		if info, _, inspectErr := imaging.Inspect(bytes.NewReader(raw)); inspectErr == nil {
			w, h := info.Width, info.Height
			width, height = &w, &h
			if err := imaging.CheckBomb(info, int64(len(raw))); err != nil {
				return nil, fmt.Errorf("%w: %v", ErrTypeNotAllowed, err)
			}
		}
	}

	key, err := storage.NewKey(string(in.Purpose), in.OwnerID.String(), extension)
	if err != nil {
		return nil, fmt.Errorf("build storage key: %w", err)
	}

	checksum := sha256.Sum256(raw)
	downloadName := safeDownloadName(in.DeclaredName, extension)

	if _, err := s.blobs.Put(ctx, key, bytes.NewReader(raw), int64(len(raw)), storage.PutOptions{
		ContentType:  detected,
		Visibility:   rule.Visibility,
		DownloadName: downloadName,
		Metadata:     map[string]string{"averix-owner": in.OwnerID.String()},
	}); err != nil {
		return nil, fmt.Errorf("store upload: %w", err)
	}

	file := &File{
		OwnerID:      in.OwnerID,
		OriginalName: downloadName,
		ByteSize:     int64(len(raw)),
		MIME:         detected,
		Width:        width,
		Height:       height,
		Purpose:      in.Purpose,
		Access:       string(rule.Visibility),
		storageKey:   key,
	}

	err = s.db.QueryRow(ctx, `
		INSERT INTO files
		  (owner_id, storage_key, bucket, original_name, byte_size,
		   declared_mime, detected_mime, checksum_sha256, width, height,
		   access, purpose, scan_state)
		VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,'skipped')
		RETURNING id, created_at`,
		in.OwnerID, key, string(rule.Visibility), downloadName, len(raw),
		nullIfBlank(in.DeclaredMIME), detected, checksum[:], width, height,
		string(rule.Visibility), string(in.Purpose)).
		Scan(&file.ID, &file.CreatedAt)
	if err != nil {
		// The object is orphaned rather than left with no row pointing at it.
		_ = s.blobs.Delete(context.WithoutCancel(ctx), key, rule.Visibility)
		return nil, fmt.Errorf("record upload: %w", err)
	}

	if rule.Visibility == storage.Public {
		file.URL = s.publicURL(key)
	}
	return file, nil
}

// detect identifies the upload from its bytes.
//
// The browser's Content-Type and the filename extension are both ignored here.
// "avatar.jpg" containing PHP is the oldest upload bug there is, and the only
// reliable answer is what the file actually starts with.
func (s *Store) detect(raw []byte, allowImages, allowDocuments bool) (mime, extension string, err error) {
	if allowImages {
		if info, _, inspectErr := imaging.Inspect(bytes.NewReader(raw)); inspectErr == nil {
			return string(info.Kind), info.Kind.Extension(), nil
		}
	}
	if !allowDocuments {
		return "", "", fmt.Errorf("%w: not a supported image", ErrTypeNotAllowed)
	}

	detected := sniffDocument(raw)
	extension, ok := documentTypes[detected]
	if !ok {
		return "", "", fmt.Errorf("%w: detected %s", ErrTypeNotAllowed, detected)
	}
	return detected, extension, nil
}

// sniffDocument identifies the accepted non-image types from their magic bytes.
//
// http.DetectContentType is not used: it reports text/html for anything that
// looks like markup, which would let an HTML file through as "text" and give
// an attacker a page in a bucket we serve.
func sniffDocument(raw []byte) string {
	switch {
	case bytes.HasPrefix(raw, []byte("%PDF-")):
		return "application/pdf"

	case bytes.HasPrefix(raw, []byte("PK\x03\x04")),
		bytes.HasPrefix(raw, []byte("PK\x05\x06")),
		bytes.HasPrefix(raw, []byte("PK\x07\x08")):
		// The Office formats are zip containers; the entry names distinguish
		// them. A plain zip is accepted as a zip.
		window := raw
		if len(window) > 4<<10 {
			window = window[:4<<10]
		}
		switch {
		case bytes.Contains(window, []byte("word/")):
			return "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
		case bytes.Contains(window, []byte("xl/")):
			return "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
		case bytes.Contains(window, []byte("ppt/")):
			return "application/vnd.openxmlformats-officedocument.presentationml.presentation"
		}
		return "application/zip"
	}

	// Text is accepted only when it really is text and does not look like
	// markup or a script.
	if looksLikeMarkupOrScript(raw) {
		return "text/html"
	}
	if isPlainText(raw) {
		if isJSON(raw) {
			return "application/json"
		}
		if isCSV(raw) {
			return "text/csv"
		}
		return "text/plain"
	}
	return "application/octet-stream"
}

func looksLikeMarkupOrScript(raw []byte) bool {
	window := raw
	if len(window) > 2<<10 {
		window = window[:2<<10]
	}
	lowered := bytes.ToLower(bytes.TrimSpace(window))
	for _, marker := range [][]byte{
		[]byte("<!doctype"), []byte("<html"), []byte("<script"), []byte("<?php"),
		[]byte("<%"), []byte("<svg"), []byte("<?xml"), []byte("#!"),
	} {
		if bytes.HasPrefix(lowered, marker) || bytes.Contains(lowered, marker) {
			return true
		}
	}
	return false
}

func isPlainText(raw []byte) bool {
	window := raw
	if len(window) > 8<<10 {
		window = window[:8<<10]
	}
	for _, b := range window {
		// Control characters other than tab, newline and carriage return mean
		// this is not text.
		if b < 0x09 || (b > 0x0d && b < 0x20) || b == 0x7f {
			return false
		}
	}
	return true
}

func isJSON(raw []byte) bool {
	trimmed := bytes.TrimSpace(raw)
	return len(trimmed) > 1 && (trimmed[0] == '{' || trimmed[0] == '[')
}

func isCSV(raw []byte) bool {
	window := raw
	if len(window) > 2<<10 {
		window = window[:2<<10]
	}
	lines := bytes.SplitN(window, []byte("\n"), 3)
	if len(lines) < 2 {
		return false
	}
	first := bytes.Count(lines[0], []byte(","))
	return first > 0 && first == bytes.Count(lines[1], []byte(","))
}

// safeDownloadName produces the filename a browser will be offered.
//
// The stored key is unrelated to this, so a hostile name cannot affect storage
// — but it would still be reflected in a Content-Disposition header, so the
// path components and control characters come out.
func safeDownloadName(declared, extension string) string {
	base := filepath.Base(strings.ReplaceAll(declared, "\\", "/"))
	base = strings.TrimSpace(base)

	cleaned := make([]rune, 0, len(base))
	for _, r := range base {
		switch {
		case r < 0x20, r == 0x7f, r == '/', r == '\\', r == ':', r == '"', r == ';':
			cleaned = append(cleaned, '_')
		default:
			cleaned = append(cleaned, r)
		}
	}
	name := strings.Trim(string(cleaned), "._ ")
	if name == "" || name == "." || name == ".." {
		name = "upload"
	}
	if len(name) > 120 {
		name = name[:120]
	}
	// The extension is the detected one, not the declared one: a PDF uploaded
	// as "invoice.exe" downloads as "invoice.pdf".
	if !strings.HasSuffix(strings.ToLower(name), "."+extension) {
		name = strings.TrimSuffix(name, filepath.Ext(name)) + "." + extension
	}
	return name
}

// ── Reads ───────────────────────────────────────────────────────────────────

const fileSelect = `
	SELECT id, owner_id, storage_key, original_name, byte_size, detected_mime,
	       width, height, access, purpose, created_at
	FROM files WHERE deleted_at IS NULL`

func (s *Store) scan(row interface{ Scan(...any) error }) (*File, error) {
	var f File
	var purpose string
	err := row.Scan(&f.ID, &f.OwnerID, &f.storageKey, &f.OriginalName, &f.ByteSize,
		&f.MIME, &f.Width, &f.Height, &f.Access, &purpose, &f.CreatedAt)
	if database.IsNoRows(err) {
		return nil, ErrNotFound
	}
	if err != nil {
		return nil, fmt.Errorf("scan file: %w", err)
	}
	f.Purpose = Purpose(purpose)
	if f.Access == string(storage.Public) {
		f.URL = s.publicURL(f.storageKey)
	}
	return &f, nil
}

func (s *Store) ByID(ctx context.Context, id uuid.UUID) (*File, error) {
	return s.scan(s.db.QueryRow(ctx, fileSelect+" AND id = $1", id))
}

// OwnedByID loads a file only if the caller owns it.
//
// Used by every path that attaches a file to something: a portfolio image, a
// service cover, a project attachment. Resolving ownership here rather than at
// each call site is why another user's file id cannot be attached to your own
// record.
func (s *Store) OwnedByID(ctx context.Context, id, ownerID uuid.UUID) (*File, error) {
	return s.scan(s.db.QueryRow(ctx, fileSelect+" AND id = $1 AND owner_id = $2", id, ownerID))
}

// SignedURL issues a short-lived URL for a private file. The caller must
// already have established that this user is entitled to it.
func (s *Store) SignedURL(ctx context.Context, f *File, ttl time.Duration) (string, error) {
	if f.Access == string(storage.Public) {
		return s.publicURL(f.storageKey), nil
	}
	return s.blobs.SignedURL(ctx, f.storageKey, ttl, f.OriginalName)
}

// Open streams a file's contents, for the endpoint that serves private files
// under the filesystem driver.
func (s *Store) Open(ctx context.Context, f *File) (io.ReadCloser, error) {
	visibility := storage.Private
	if f.Access == string(storage.Public) {
		visibility = storage.Public
	}
	reader, _, err := s.blobs.Get(ctx, f.storageKey, visibility)
	return reader, err
}

// Delete soft-deletes the row and removes the object.
func (s *Store) Delete(ctx context.Context, id, ownerID uuid.UUID) error {
	file, err := s.OwnedByID(ctx, id, ownerID)
	if err != nil {
		return err
	}
	if _, err := s.db.Exec(ctx,
		`UPDATE files SET deleted_at = now() WHERE id = $1 AND owner_id = $2`,
		id, ownerID); err != nil {
		return fmt.Errorf("mark file deleted: %w", err)
	}

	visibility := storage.Private
	if file.Access == string(storage.Public) {
		visibility = storage.Public
	}
	// On a detached context: the row is already gone, so a slow delete must
	// not fail the request.
	_ = s.blobs.Delete(context.WithoutCancel(ctx), file.storageKey, visibility)
	return nil
}

// PurgeOrphans removes files nothing references. Run by the worker: an upload
// that was never attached to anything is otherwise paid for forever.
func (s *Store) PurgeOrphans(ctx context.Context, olderThan time.Duration) (int, error) {
	rows, err := s.db.Query(ctx, `
		SELECT id, storage_key, access FROM files f
		WHERE f.deleted_at IS NULL
		  AND f.created_at < now() - $1::interval
		  AND NOT EXISTS (SELECT 1 FROM portfolio_images pi WHERE pi.file_id = f.id)
		  AND NOT EXISTS (SELECT 1 FROM portfolio_projects pp WHERE pp.cover_file_id = f.id)
		  AND NOT EXISTS (SELECT 1 FROM project_attachments pa WHERE pa.file_id = f.id)
		  AND NOT EXISTS (SELECT 1 FROM message_attachments ma WHERE ma.file_id = f.id)
		  AND NOT EXISTS (SELECT 1 FROM deliverables d WHERE d.file_id = f.id)
		  AND NOT EXISTS (SELECT 1 FROM services s WHERE s.cover_file_id = f.id)
		  AND NOT EXISTS (SELECT 1 FROM dispute_messages dm WHERE dm.file_id = f.id)
		LIMIT 500`, fmt.Sprintf("%d seconds", int(olderThan.Seconds())))
	if err != nil {
		return 0, fmt.Errorf("find orphaned files: %w", err)
	}

	type orphan struct {
		id     uuid.UUID
		key    string
		access string
	}
	var orphans []orphan
	for rows.Next() {
		var o orphan
		if err := rows.Scan(&o.id, &o.key, &o.access); err != nil {
			rows.Close()
			return 0, err
		}
		orphans = append(orphans, o)
	}
	rows.Close()
	if err := rows.Err(); err != nil {
		return 0, err
	}

	removed := 0
	for _, o := range orphans {
		visibility := storage.Private
		if o.access == string(storage.Public) {
			visibility = storage.Public
		}
		if err := s.blobs.Delete(ctx, o.key, visibility); err != nil {
			continue
		}
		if _, err := s.db.Exec(ctx, `UPDATE files SET deleted_at = now() WHERE id = $1`, o.id); err == nil {
			removed++
		}
	}
	return removed, nil
}

func nullIfBlank(s string) any {
	if strings.TrimSpace(s) == "" {
		return nil
	}
	return s
}
