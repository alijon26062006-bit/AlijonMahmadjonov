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
	// Field-level validation problems: {"email": "Проверьте адрес электронной почты."}
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
		"Не удалось обработать запрос. Проверьте данные и попробуйте ещё раз.")
	ErrValidation = newError(http.StatusUnprocessableEntity, "validation_failed",
		"Проверьте заполненные поля — что-то нужно поправить.")
	ErrUnauthenticated = newError(http.StatusUnauthorized, "unauthenticated",
		"Войдите, чтобы продолжить.")
	ErrInvalidCredentials = newError(http.StatusUnauthorized, "invalid_credentials",
		"Такой почты и пароля у нас нет.")
	ErrSessionExpired = newError(http.StatusUnauthorized, "session_expired",
		"Сеанс истёк. Войдите заново.")
	ErrForbidden = newError(http.StatusForbidden, "forbidden",
		"У вас нет доступа к этому разделу.")
	ErrCSRF = newError(http.StatusForbidden, "csrf_failed",
		"Не удалось проверить сеанс. Обновите страницу и попробуйте ещё раз.")
	ErrNotFound = newError(http.StatusNotFound, "not_found",
		"Мы не нашли то, что вы искали.")
	ErrConflict = newError(http.StatusConflict, "conflict",
		"Данные изменились с момента загрузки. Обновите страницу и повторите.")
	ErrEmailTaken = newError(http.StatusConflict, "email_taken",
		"Аккаунт с такой почтой уже есть.")
	ErrUsernameTaken = newError(http.StatusConflict, "username_taken",
		"Это имя пользователя уже занято.")
	ErrPayloadTooLarge = newError(http.StatusRequestEntityTooLarge, "payload_too_large",
		"Файл больше, чем мы можем принять.")
	ErrUnsupportedMedia = newError(http.StatusUnsupportedMediaType, "unsupported_media_type",
		"Такой тип файла здесь не поддерживается.")
	ErrRateLimited = newError(http.StatusTooManyRequests, "rate_limited",
		"Слишком часто. Подождите немного и попробуйте снова.")
	ErrAccountLocked = newError(http.StatusTooManyRequests, "account_locked",
		"Слишком много неудачных попыток. Подождите или восстановите пароль.")
	ErrInternal = newError(http.StatusInternalServerError, "internal_error",
		"Что-то пошло не так на нашей стороне. Попробуйте ещё раз.")
	ErrNotConfigured = newError(http.StatusServiceUnavailable, "not_configured",
		"Эта возможность пока не настроена на площадке.")
	ErrUnavailable = newError(http.StatusServiceUnavailable, "unavailable",
		"Сервис временно недоступен. Попробуйте чуть позже.")
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
