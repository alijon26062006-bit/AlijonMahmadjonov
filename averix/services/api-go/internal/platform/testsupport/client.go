package testsupport

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/http/cookiejar"
	"net/url"
	"testing"
)

// Client is an HTTP client that behaves like the web app: it keeps cookies and
// replays the CSRF token on every mutation. Tests therefore exercise the same
// path a browser does, including the CSRF check.
type Client struct {
	t    *testing.T
	h    *Harness
	http *http.Client
	csrf string
	// Set by tests that need to send a deliberately wrong or absent token.
	SuppressCSRF bool
	OverrideCSRF string
}

func (h *Harness) Client() *Client {
	h.T.Helper()
	jar, err := cookiejar.New(nil)
	if err != nil {
		h.T.Fatalf("create cookie jar: %v", err)
	}
	return &Client{
		t:    h.T,
		h:    h,
		http: &http.Client{Jar: jar, CheckRedirect: NoRedirect},
	}
}

// Response is a decoded API response.
type Response struct {
	Status int
	Raw    []byte
	// Data is the decoded "data" envelope for a success.
	Data map[string]any
	// List is the decoded "data" when it is an array.
	List []any
	Meta map[string]any
	// Error fields for a failure.
	Code      string
	Message   string
	Fields    map[string]string
	RequestID string
	Header    http.Header
}

// OK asserts a successful status and returns the response.
func (r *Response) OK(t *testing.T, want int) *Response {
	t.Helper()
	if r.Status != want {
		t.Fatalf("status = %d, want %d\n  code: %s\n  message: %s\n  fields: %v\n  body: %s",
			r.Status, want, r.Code, r.Message, r.Fields, truncateBody(r.Raw))
	}
	return r
}

// Fails asserts a failure status and error code.
func (r *Response) Fails(t *testing.T, wantStatus int, wantCode string) *Response {
	t.Helper()
	if r.Status != wantStatus {
		t.Fatalf("status = %d, want %d (body: %s)", r.Status, wantStatus, truncateBody(r.Raw))
	}
	if wantCode != "" && r.Code != wantCode {
		t.Fatalf("error code = %q, want %q (body: %s)", r.Code, wantCode, truncateBody(r.Raw))
	}
	return r
}

// String reads a string out of the data envelope.
func (r *Response) String(key string) string {
	if v, ok := r.Data[key].(string); ok {
		return v
	}
	return ""
}

func (r *Response) Bool(key string) bool {
	if v, ok := r.Data[key].(bool); ok {
		return v
	}
	return false
}

func (r *Response) Float(key string) float64 {
	if v, ok := r.Data[key].(float64); ok {
		return v
	}
	return 0
}

func (r *Response) Strings(key string) []string {
	raw, ok := r.Data[key].([]any)
	if !ok {
		return nil
	}
	out := make([]string, 0, len(raw))
	for _, v := range raw {
		if s, ok := v.(string); ok {
			out = append(out, s)
		}
	}
	return out
}

// Has reports whether a string slice in the data envelope contains a value,
// which is how permission assertions read.
func (r *Response) Has(key, value string) bool {
	for _, v := range r.Strings(key) {
		if v == value {
			return true
		}
	}
	return false
}

func (c *Client) GET(path string) *Response { return c.do(http.MethodGet, path, nil) }
func (c *Client) POST(path string, body any) *Response {
	return c.do(http.MethodPost, path, body)
}
func (c *Client) PUT(path string, body any) *Response {
	return c.do(http.MethodPut, path, body)
}
func (c *Client) PATCH(path string, body any) *Response {
	return c.do(http.MethodPatch, path, body)
}
func (c *Client) DELETE(path string) *Response { return c.do(http.MethodDelete, path, nil) }

func (c *Client) do(method, path string, body any) *Response {
	c.t.Helper()

	var reader io.Reader
	if body != nil {
		raw, err := json.Marshal(body)
		if err != nil {
			c.t.Fatalf("encode request body: %v", err)
		}
		reader = bytes.NewReader(raw)
	}

	req, err := http.NewRequest(method, c.h.APIURL(path), reader)
	if err != nil {
		c.t.Fatalf("build request: %v", err)
	}
	if body != nil {
		req.Header.Set("Content-Type", "application/json")
	}
	switch {
	case c.OverrideCSRF != "":
		req.Header.Set("X-CSRF-Token", c.OverrideCSRF)
	case c.SuppressCSRF:
		// Deliberately absent.
	case c.csrf != "":
		req.Header.Set("X-CSRF-Token", c.csrf)
	}
	req.Header.Set("Origin", "http://localhost:3000")

	resp, err := c.http.Do(req)
	if err != nil {
		c.t.Fatalf("%s %s: %v", method, path, err)
	}
	defer resp.Body.Close()

	raw, err := io.ReadAll(resp.Body)
	if err != nil {
		c.t.Fatalf("read response body: %v", err)
	}

	return c.decode(resp, raw)
}

// decode turns an HTTP response into the envelope shape the tests assert on,
// capturing any CSRF token it carries.
func (c *Client) decode(resp *http.Response, raw []byte) *Response {
	c.t.Helper()

	out := &Response{Status: resp.StatusCode, Raw: raw, Header: resp.Header}
	if len(raw) == 0 {
		return out
	}

	var envelope struct {
		Data  json.RawMessage `json:"data"`
		Meta  map[string]any  `json:"meta"`
		Error struct {
			Code      string            `json:"code"`
			Message   string            `json:"message"`
			Fields    map[string]string `json:"fields"`
			RequestID string            `json:"request_id"`
		} `json:"error"`
	}
	if err := json.Unmarshal(raw, &envelope); err != nil {
		c.t.Fatalf("%s %s returned a body that is not the API envelope: %s",
			resp.Request.Method, resp.Request.URL.Path, truncateBody(raw))
	}
	out.Meta = envelope.Meta
	out.Code = envelope.Error.Code
	out.Message = envelope.Error.Message
	out.Fields = envelope.Error.Fields
	out.RequestID = envelope.Error.RequestID

	if len(envelope.Data) > 0 {
		// Data is an object for most endpoints and an array for collections.
		if err := json.Unmarshal(envelope.Data, &out.Data); err != nil {
			_ = json.Unmarshal(envelope.Data, &out.List)
		}
	}

	// Every successful auth response carries the current CSRF token; capturing
	// it here is what lets a test chain mutations without plumbing it by hand.
	if token := out.String("csrf_token"); token != "" {
		c.csrf = token
	}
	return out
}

// Register signs up and leaves the client authenticated.
func (c *Client) Register(email, username, password, name, role string) *Response {
	c.t.Helper()
	return c.POST("/auth/register", map[string]any{
		"email": email, "username": username, "password": password,
		"full_name": name, "role": role, "accept_terms": true,
	})
}

// RegisterDeveloper and RegisterClient are the two shapes tests need most.
func (c *Client) RegisterDeveloper(username string) *Response {
	c.t.Helper()
	return c.Register(username+"@example.test", username, defaultPassword,
		"Test "+username, "developer").OK(c.t, http.StatusCreated)
}

func (c *Client) RegisterClient(username string) *Response {
	c.t.Helper()
	return c.Register(username+"@example.test", username, defaultPassword,
		"Test "+username, "client").OK(c.t, http.StatusCreated)
}

// defaultPassword satisfies the validator without being a common password.
const defaultPassword = "quiet-lantern-4417"

func (c *Client) Login(email, password string) *Response {
	c.t.Helper()
	return c.POST("/auth/login", map[string]any{"email": email, "password": password})
}

func (c *Client) Logout() *Response {
	c.t.Helper()
	return c.POST("/auth/logout", nil)
}

// Session fetches the current session, refreshing the stored CSRF token.
func (c *Client) Session() *Response {
	c.t.Helper()
	return c.GET("/auth/session")
}

// CSRF exposes the captured token for tests that assert on rotation.
func (c *Client) CSRF() string { return c.csrf }

// UserID returns the signed-in user's id, failing the test when anonymous.
func (c *Client) UserID() string {
	c.t.Helper()
	id := c.Session().String("user_id")
	if id == "" {
		c.t.Fatal("client is not signed in")
	}
	return id
}

func truncateBody(raw []byte) string {
	const limit = 600
	if len(raw) > limit {
		return string(raw[:limit]) + fmt.Sprintf("… (%d bytes)", len(raw))
	}
	return string(raw)
}

// SetRawSessionCookie plants a cookie value directly, for tests that need to
// present a tampered or forged session.
func (c *Client) SetRawSessionCookie(value string) {
	c.t.Helper()
	u, err := url.Parse(c.h.Server.URL)
	if err != nil {
		c.t.Fatalf("parse server URL: %v", err)
	}
	c.http.Jar.SetCookies(u, []*http.Cookie{{
		Name:  "averix_session",
		Value: value,
		Path:  "/",
	}})
}

// CSRFTokenChanged reports whether the response carries a token different from
// the one supplied, which is how rotation is asserted.
func (r *Response) CSRFTokenChanged(previous string) bool {
	current := r.String("csrf_token")
	return current != "" && current != previous
}

// Multipart posts a pre-encoded multipart body, for the upload endpoints.
func (c *Client) Multipart(path, contentType string, body []byte) *Response {
	c.t.Helper()

	req, err := http.NewRequest(http.MethodPost, c.h.APIURL(path), bytes.NewReader(body))
	if err != nil {
		c.t.Fatalf("build multipart request: %v", err)
	}
	req.Header.Set("Content-Type", contentType)
	req.Header.Set("Origin", "http://localhost:3000")
	switch {
	case c.OverrideCSRF != "":
		req.Header.Set("X-CSRF-Token", c.OverrideCSRF)
	case c.SuppressCSRF:
	case c.csrf != "":
		req.Header.Set("X-CSRF-Token", c.csrf)
	}

	resp, err := c.http.Do(req)
	if err != nil {
		c.t.Fatalf("POST %s: %v", path, err)
	}
	defer resp.Body.Close()

	raw, err := io.ReadAll(resp.Body)
	if err != nil {
		c.t.Fatalf("read response body: %v", err)
	}
	return c.decode(resp, raw)
}
