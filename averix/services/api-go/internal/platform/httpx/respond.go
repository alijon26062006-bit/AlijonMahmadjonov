package httpx

import (
	"encoding/json"
	"errors"
	"io"
	"net/http"
	"strconv"
	"strings"

	"github.com/averix/api/internal/platform/logx"
)

// Handler is the signature every AVERIX endpoint uses. Returning an error is
// how a handler reports failure, so no handler has to remember to write a
// response and return on the error path.
type Handler func(http.ResponseWriter, *http.Request) error

// Envelope is the success shape: {"data": ...} with optional "meta".
type Envelope struct {
	Data any            `json:"data"`
	Meta map[string]any `json:"meta,omitempty"`
}

type errorBody struct {
	Error errorPayload `json:"error"`
}

type errorPayload struct {
	Code      string            `json:"code"`
	Message   string            `json:"message"`
	Fields    map[string]string `json:"fields,omitempty"`
	RequestID string            `json:"request_id,omitempty"`
}

// JSON writes a success response.
func JSON(w http.ResponseWriter, status int, data any) error {
	return write(w, status, Envelope{Data: data})
}

// JSONMeta writes a success response with metadata (pagination, counts).
func JSONMeta(w http.ResponseWriter, status int, data any, meta map[string]any) error {
	return write(w, status, Envelope{Data: data, Meta: meta})
}

// NoContent acknowledges a request that has nothing to return.
func NoContent(w http.ResponseWriter) error {
	w.WriteHeader(http.StatusNoContent)
	return nil
}

func write(w http.ResponseWriter, status int, body any) error {
	w.Header().Set("Content-Type", "application/json; charset=utf-8")
	w.WriteHeader(status)
	return json.NewEncoder(w).Encode(body)
}

// WriteError renders an error response and logs the internal cause.
func WriteError(w http.ResponseWriter, r *http.Request, err error) {
	apiErr := AsError(err)
	ctx := r.Context()
	log := logx.From(ctx)

	fields := []any{
		"code", apiErr.Code,
		"status", apiErr.Status,
		"method", r.Method,
		"path", r.URL.Path,
	}
	if cause := errors.Unwrap(apiErr); cause != nil {
		fields = append(fields, "cause", cause.Error())
	}
	switch {
	case apiErr.Status >= 500:
		log.Error("request failed", fields...)
	case apiErr.Status == http.StatusForbidden || apiErr.Status == http.StatusUnauthorized:
		// Denials are security-relevant even when they are routine.
		log.Warn("request denied", fields...)
	default:
		log.Info("request rejected", fields...)
	}

	if apiErr.RetryAfter > 0 {
		w.Header().Set("Retry-After", strconv.Itoa(apiErr.RetryAfter))
	}
	_ = write(w, apiErr.Status, errorBody{Error: errorPayload{
		Code:      apiErr.Code,
		Message:   apiErr.Message,
		Fields:    apiErr.Fields,
		RequestID: logx.RequestID(ctx),
	}})
}

// DecodeJSON reads and strictly decodes a JSON body into dst.
//
// Unknown fields are rejected: a client sending `is_admin: true` to a profile
// endpoint gets a 400 instead of silently having it ignored, which makes
// over-posting bugs impossible rather than merely unlikely.
func DecodeJSON(w http.ResponseWriter, r *http.Request, dst any, maxBytes int64) error {
	ct := r.Header.Get("Content-Type")
	if ct != "" && !strings.HasPrefix(ct, "application/json") {
		return ErrUnsupportedMedia.Wrap(errors.New("content-type " + ct))
	}
	if maxBytes <= 0 {
		maxBytes = 1 << 20
	}
	r.Body = http.MaxBytesReader(w, r.Body, maxBytes)

	dec := json.NewDecoder(r.Body)
	dec.DisallowUnknownFields()
	if err := dec.Decode(dst); err != nil {
		var maxErr *http.MaxBytesError
		switch {
		case errors.As(err, &maxErr):
			return ErrPayloadTooLarge.Wrap(err)
		case errors.Is(err, io.EOF):
			return ErrBadRequest.Wrap(errors.New("empty request body"))
		}
		var typeErr *json.UnmarshalTypeError
		if errors.As(err, &typeErr) {
			return Validation(map[string]string{
				typeErr.Field: "This value has the wrong type.",
			}).Wrap(err)
		}
		if strings.Contains(err.Error(), "unknown field") {
			return ErrBadRequest.Wrap(err)
		}
		return ErrBadRequest.Wrap(err)
	}
	// A second value in the body is a sign of a confused or malicious client.
	if dec.More() {
		return ErrBadRequest.Wrap(errors.New("body contained more than one JSON value"))
	}
	return nil
}
