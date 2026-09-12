// Package httpx holds the HTTP plumbing shared by every module: the error
// vocabulary, response helpers, middleware and a small router.
package httpx

import (
	"errors"
	"fmt"
	"net/http"
)

// Error is the only thing handlers return. Message is written for a person and
// is safe to display; Detail never leaves the server logs.
//
// This split is why no endpoint can leak "pq: relation does not exist" to a
// user: an unwrapped error becomes a generic 500 with a human message, and the
// real cause goes to the log with the request id.
type Error struct {
	Status  int
	Code    string
	Message string
	// Field-level validation problems: {"email": "Enter a valid email address."}
	Fields map[string]string
	// Internal cause. Logged, never serialised.
	cause error
	// Retry hint for 429 and 503, in seconds.
	RetryAfter int
}

func (e *Error) Error() string {
	if e.cause != nil {
		return fmt.Sprintf("%s: %s: %v", e.Code, e.Message, e.cause)
	}
	return fmt.Sprintf("%s: %s", e.Code, e.Message)
}

func (e *Error) Unwrap() error { return e.cause }

// Wrap attaches an internal cause without changing what the user sees.
func (e *Error) Wrap(err error) *Error {
	clone := *e
	clone.cause = err
	return &clone
}

// WithField adds a field-level problem.
func (e *Error) WithField(field, message string) *Error {
	clone := *e
	clone.Fields = map[string]string{}
	for k, v := range e.Fields {
		clone.Fields[k] = v
	}
	clone.Fields[field] = message
	return &clone
}

func newError(status int, code, message string) *Error {
	return &Error{Status: status, Code: code, Message: message}
}

// The shared error vocabulary. Messages are deliberately plain: they explain
// what happened and what to do, and they never mention databases, caches or
// internal service names.
var (
	ErrBadRequest = newError(http.StatusBadRequest, "bad_request",
		"We couldn't process that request. Please check the details and try again.")
	ErrValidation = newError(http.StatusUnprocessableEntity, "validation_failed",
		"Some details need attention before we can continue.")
	ErrUnauthenticated = newError(http.StatusUnauthorized, "unauthenticated",
		"Please sign in to continue.")
	ErrInvalidCredentials = newError(http.StatusUnauthorized, "invalid_credentials",
		"That email and password don't match an account.")
	ErrSessionExpired = newError(http.StatusUnauthorized, "session_expired",
		"Your session has expired. Please sign in again.")
	ErrForbidden = newError(http.StatusForbidden, "forbidden",
		"You don't have access to this.")
	ErrCSRF = newError(http.StatusForbidden, "csrf_failed",
		"Your session couldn't be verified. Please refresh the page and try again.")
	ErrNotFound = newError(http.StatusNotFound, "not_found",
		"We couldn't find what you were looking for.")
	ErrConflict = newError(http.StatusConflict, "conflict",
		"That change conflicts with the current state. Please refresh and try again.")
	ErrEmailTaken = newError(http.StatusConflict, "email_taken",
		"An account with this email already exists.")
	ErrUsernameTaken = newError(http.StatusConflict, "username_taken",
		"That username is already taken.")
	ErrPayloadTooLarge = newError(http.StatusRequestEntityTooLarge, "payload_too_large",
		"That file is larger than we can accept.")
	ErrUnsupportedMedia = newError(http.StatusUnsupportedMediaType, "unsupported_media_type",
		"That file type isn't supported here.")
	ErrRateLimited = newError(http.StatusTooManyRequests, "rate_limited",
		"You're doing that a little too quickly. Please wait a moment and try again.")
	ErrAccountLocked = newError(http.StatusTooManyRequests, "account_locked",
		"Too many failed attempts. Please try again shortly or reset your password.")
	ErrInternal = newError(http.StatusInternalServerError, "internal_error",
		"Something went wrong on our end. Please try again.")
	ErrNotConfigured = newError(http.StatusServiceUnavailable, "not_configured",
		"This feature isn't configured on this environment yet.")
	ErrUnavailable = newError(http.StatusServiceUnavailable, "unavailable",
		"This service is temporarily unavailable. Please try again shortly.")
)

// Validation builds a 422 carrying per-field messages.
func Validation(fields map[string]string) *Error {
	e := *ErrValidation
	e.Fields = fields
	return &e
}

// NotFoundf keeps the generic message but records what was actually missing.
func NotFoundf(format string, args ...any) *Error {
	return ErrNotFound.Wrap(fmt.Errorf(format, args...))
}

// Forbiddenf records why access was denied without telling the caller.
func Forbiddenf(format string, args ...any) *Error {
	return ErrForbidden.Wrap(fmt.Errorf(format, args...))
}

// Internalf wraps an unexpected failure.
func Internalf(err error, format string, args ...any) *Error {
	return ErrInternal.Wrap(fmt.Errorf(format+": %w", append(args, err)...))
}

// AsError resolves any error into an *Error, so an unexpected failure becomes a
// safe 500 rather than an accidental disclosure.
func AsError(err error) *Error {
	if err == nil {
		return nil
	}
	var apiErr *Error
	if errors.As(err, &apiErr) {
		return apiErr
	}
	return ErrInternal.Wrap(err)
}
