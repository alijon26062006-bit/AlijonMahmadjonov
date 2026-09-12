// Package cryptox holds the cryptographic primitives the product relies on:
// password hashing, opaque session tokens, single-use token hashing, envelope
// encryption for third-party credentials and HMAC signing for webhooks.
package cryptox

import (
	"crypto/aes"
	"crypto/cipher"
	"crypto/hmac"
	"crypto/rand"
	"crypto/sha256"
	"crypto/sha512"
	"crypto/subtle"
	"encoding/base64"
	"encoding/hex"
	"errors"
	"fmt"
	"io"
	"strings"

	"golang.org/x/crypto/bcrypt"
	"golang.org/x/crypto/hkdf"
)

// ── Passwords ───────────────────────────────────────────────────────────────

// HashPassword hashes with bcrypt at the configured cost.
//
// bcrypt caps its input at 72 bytes, and silently truncating a long
// passphrase would make the tail meaningless. Pre-hashing with SHA-512 keeps
// the full entropy of any length of input.
func HashPassword(password string, cost int) (string, error) {
	if cost <= 0 {
		cost = bcrypt.DefaultCost
	}
	digest := sha512.Sum512([]byte(password))
	hash, err := bcrypt.GenerateFromPassword(digest[:], cost)
	if err != nil {
		return "", fmt.Errorf("hash password: %w", err)
	}
	return string(hash), nil
}

// VerifyPassword compares a candidate against a stored hash in constant time.
func VerifyPassword(hash, password string) bool {
	if hash == "" {
		return false
	}
	digest := sha512.Sum512([]byte(password))
	return bcrypt.CompareHashAndPassword([]byte(hash), digest[:]) == nil
}

// NeedsRehash reports whether a stored hash was made at a weaker cost, so a
// successful login can transparently upgrade it.
func NeedsRehash(hash string, wantCost int) bool {
	cost, err := bcrypt.Cost([]byte(hash))
	return err == nil && cost < wantCost
}

// ── Random values ───────────────────────────────────────────────────────────

// RandomToken returns a URL-safe random string carrying n bytes of entropy.
func RandomToken(n int) (string, error) {
	if n < 16 {
		n = 16
	}
	b := make([]byte, n)
	if _, err := io.ReadFull(rand.Reader, b); err != nil {
		return "", fmt.Errorf("read random bytes: %w", err)
	}
	return base64.RawURLEncoding.EncodeToString(b), nil
}

// RandomHex returns a random lowercase hex string, used for storage keys.
func RandomHex(n int) (string, error) {
	b := make([]byte, n)
	if _, err := io.ReadFull(rand.Reader, b); err != nil {
		return "", fmt.Errorf("read random bytes: %w", err)
	}
	return hex.EncodeToString(b), nil
}

// ── Session tokens ──────────────────────────────────────────────────────────

// SessionToken is a selector/verifier pair. The cookie carries both; the
// database stores the selector in the clear (so the lookup is an index hit) and
// only a hash of the verifier. A database leak therefore yields no usable
// session, and the comparison is constant-time regardless.
type SessionToken struct {
	Selector string
	Verifier string
}

func (t SessionToken) String() string { return t.Selector + "." + t.Verifier }

func NewSessionToken() (SessionToken, error) {
	selector, err := RandomToken(16)
	if err != nil {
		return SessionToken{}, err
	}
	verifier, err := RandomToken(32)
	if err != nil {
		return SessionToken{}, err
	}
	return SessionToken{Selector: selector, Verifier: verifier}, nil
}

var ErrMalformedToken = errors.New("malformed session token")

func ParseSessionToken(raw string) (SessionToken, error) {
	selector, verifier, ok := strings.Cut(raw, ".")
	if !ok || selector == "" || verifier == "" {
		return SessionToken{}, ErrMalformedToken
	}
	return SessionToken{Selector: selector, Verifier: verifier}, nil
}

// HashVerifier hashes a verifier for storage. SHA-256 is correct here rather
// than bcrypt: the verifier is 32 random bytes, so there is nothing to brute
// force, and session lookup happens on every request.
func HashVerifier(verifier string) []byte {
	sum := sha256.Sum256([]byte(verifier))
	return sum[:]
}

func VerifierMatches(stored []byte, verifier string) bool {
	want := HashVerifier(verifier)
	return subtle.ConstantTimeCompare(stored, want) == 1
}

// HashToken hashes a single-use token (email verification, password reset) the
// same way and for the same reason.
func HashToken(token string) []byte {
	sum := sha256.Sum256([]byte(token))
	return sum[:]
}

// ── Envelope encryption ─────────────────────────────────────────────────────

// Sealer encrypts values that must be stored but never read by anyone but the
// service: GitHub access tokens, above all.
type Sealer struct {
	aead cipher.AEAD
}

// NewSealer derives a purpose-specific key from the master data key, so the same
// secret can protect different kinds of value without one context's ciphertext
// being valid in another.
func NewSealer(masterKey []byte, purpose string) (*Sealer, error) {
	if len(masterKey) < 32 {
		return nil, fmt.Errorf("data key must be at least 32 bytes, got %d", len(masterKey))
	}
	key := make([]byte, 32)
	kdf := hkdf.New(sha256.New, masterKey, nil, []byte("averix:"+purpose))
	if _, err := io.ReadFull(kdf, key); err != nil {
		return nil, fmt.Errorf("derive key: %w", err)
	}
	block, err := aes.NewCipher(key)
	if err != nil {
		return nil, fmt.Errorf("create cipher: %w", err)
	}
	aead, err := cipher.NewGCM(block)
	if err != nil {
		return nil, fmt.Errorf("create GCM: %w", err)
	}
	return &Sealer{aead: aead}, nil
}

// Seal encrypts plaintext, returning nonce||ciphertext.
func (s *Sealer) Seal(plaintext []byte) ([]byte, error) {
	if len(plaintext) == 0 {
		return nil, nil
	}
	nonce := make([]byte, s.aead.NonceSize())
	if _, err := io.ReadFull(rand.Reader, nonce); err != nil {
		return nil, fmt.Errorf("read nonce: %w", err)
	}
	return s.aead.Seal(nonce, nonce, plaintext, nil), nil
}

func (s *Sealer) SealString(plaintext string) ([]byte, error) {
	return s.Seal([]byte(plaintext))
}

var ErrDecrypt = errors.New("could not decrypt value")

func (s *Sealer) Open(sealed []byte) ([]byte, error) {
	if len(sealed) == 0 {
		return nil, nil
	}
	ns := s.aead.NonceSize()
	if len(sealed) < ns+s.aead.Overhead() {
		return nil, ErrDecrypt
	}
	plaintext, err := s.aead.Open(nil, sealed[:ns], sealed[ns:], nil)
	if err != nil {
		return nil, ErrDecrypt
	}
	return plaintext, nil
}

func (s *Sealer) OpenString(sealed []byte) (string, error) {
	b, err := s.Open(sealed)
	return string(b), err
}

// ── HMAC ────────────────────────────────────────────────────────────────────

// SignHMAC returns a hex HMAC-SHA256, used for webhook verification and signed
// URLs to private objects.
func SignHMAC(secret, message []byte) string {
	mac := hmac.New(sha256.New, secret)
	mac.Write(message)
	return hex.EncodeToString(mac.Sum(nil))
}

// VerifyHMAC compares a provided signature in constant time. Accepts a bare hex
// digest or one prefixed with an algorithm name, which is how Stripe and GitHub
// both format theirs.
func VerifyHMAC(secret, message []byte, signature string) bool {
	if signature == "" {
		return false
	}
	if _, after, found := strings.Cut(signature, "="); found {
		signature = after
	}
	want := SignHMAC(secret, message)
	return subtle.ConstantTimeCompare([]byte(want), []byte(strings.TrimSpace(signature))) == 1
}

// ConstantTimeEquals compares two strings without leaking their contents
// through timing.
func ConstantTimeEquals(a, b string) bool {
	return subtle.ConstantTimeCompare([]byte(a), []byte(b)) == 1
}
