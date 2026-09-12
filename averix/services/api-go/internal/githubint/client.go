// Package githubint connects a developer's GitHub account and mirrors what it
// needs for analysis.
//
// Three rules the product depends on:
//
//  1. An account is linked only through the OAuth callback, so the stored
//     github_user_id is proof of ownership. Nothing is ever inferred from a
//     person's name, however obvious the guess looks.
//  2. The default scope reads public data only. Private repository access is a
//     separate, explicit second consent.
//  3. The access token is encrypted at rest and is never returned by any
//     endpoint, to any role.
package githubint

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"strconv"
	"strings"
	"time"

	"github.com/averix/api/internal/config"
	"github.com/averix/api/internal/platform/logx"
)

// Client talks to the GitHub REST API on one developer's behalf.
type Client struct {
	http    *http.Client
	baseURL string
	token   string
	// Rate limit state from the last response, so a sync can stop before
	// GitHub starts refusing.
	remaining int
	resetAt   time.Time
	calls     int
}

const (
	userAgent      = "AVERIX/1.0 (+https://averix.dev)"
	apiVersion     = "2022-11-28"
	requestTimeout = 20 * time.Second
)

func NewClient(cfg config.GitHub, token string) *Client {
	return &Client{
		http: &http.Client{
			Timeout: requestTimeout,
			// GitHub's API never redirects for the endpoints used here; a
			// redirect would be a sign something is wrong.
			CheckRedirect: func(*http.Request, []*http.Request) error {
				return errors.New("unexpected redirect from the GitHub API")
			},
		},
		baseURL:   strings.TrimRight(cfg.APIBaseURL, "/"),
		token:     token,
		remaining: -1,
	}
}

// Calls reports how many API requests this client has made, recorded on the
// analysis row so the admin panel can show quota use.
func (c *Client) Calls() int { return c.calls }

// Remaining reports the rate-limit budget GitHub last reported.
func (c *Client) Remaining() int { return c.remaining }

var (
	ErrUnauthorised = errors.New("github rejected the credentials")
	ErrRateLimited  = errors.New("github rate limit reached")
	ErrNotFound     = errors.New("github resource not found")
)

// get performs an authenticated GET and decodes the body.
func (c *Client) get(ctx context.Context, path string, dst any) error {
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, c.baseURL+path, nil)
	if err != nil {
		return fmt.Errorf("build github request: %w", err)
	}
	req.Header.Set("Accept", "application/vnd.github+json")
	req.Header.Set("X-GitHub-Api-Version", apiVersion)
	req.Header.Set("User-Agent", userAgent)
	if c.token != "" {
		req.Header.Set("Authorization", "Bearer "+c.token)
	}

	resp, err := c.http.Do(req)
	if err != nil {
		return fmt.Errorf("call github %s: %w", path, err)
	}
	defer func() {
		// The body must be drained for the connection to be reused.
		_, _ = io.Copy(io.Discard, io.LimitReader(resp.Body, 4<<10))
		_ = resp.Body.Close()
	}()

	c.calls++
	if raw := resp.Header.Get("X-RateLimit-Remaining"); raw != "" {
		if n, err := strconv.Atoi(raw); err == nil {
			c.remaining = n
		}
	}
	if raw := resp.Header.Get("X-RateLimit-Reset"); raw != "" {
		if n, err := strconv.ParseInt(raw, 10, 64); err == nil {
			c.resetAt = time.Unix(n, 0)
		}
	}

	switch resp.StatusCode {
	case http.StatusOK:
	case http.StatusUnauthorized:
		return ErrUnauthorised
	case http.StatusForbidden:
		// GitHub uses 403 for both rate limiting and permission problems; the
		// remaining budget distinguishes them.
		if c.remaining == 0 {
			return fmt.Errorf("%w: resets at %s", ErrRateLimited, c.resetAt.Format(time.RFC3339))
		}
		return fmt.Errorf("%w: forbidden", ErrUnauthorised)
	case http.StatusNotFound:
		return ErrNotFound
	case http.StatusTooManyRequests:
		return ErrRateLimited
	default:
		return fmt.Errorf("github %s returned %d", path, resp.StatusCode)
	}

	if dst == nil {
		return nil
	}
	// A response body is bounded: a repository list is not a stream, and an
	// unbounded read is a memory exhaustion vector.
	body := io.LimitReader(resp.Body, 8<<20)
	if err := json.NewDecoder(body).Decode(dst); err != nil {
		return fmt.Errorf("decode github response from %s: %w", path, err)
	}
	return nil
}

// ── Types, narrowed to what AVERIX uses ─────────────────────────────────────

type User struct {
	ID          int64     `json:"id"`
	Login       string    `json:"login"`
	Name        string    `json:"name"`
	AvatarURL   string    `json:"avatar_url"`
	HTMLURL     string    `json:"html_url"`
	Company     string    `json:"company"`
	Blog        string    `json:"blog"`
	Location    string    `json:"location"`
	Bio         string    `json:"bio"`
	PublicRepos int       `json:"public_repos"`
	Followers   int       `json:"followers"`
	CreatedAt   time.Time `json:"created_at"`
}

type Repository struct {
	ID            int64      `json:"id"`
	Name          string     `json:"name"`
	FullName      string     `json:"full_name"`
	Description   string     `json:"description"`
	HTMLURL       string     `json:"html_url"`
	Homepage      string     `json:"homepage"`
	Private       bool       `json:"private"`
	Fork          bool       `json:"fork"`
	Archived      bool       `json:"archived"`
	Language      string     `json:"language"`
	Stars         int        `json:"stargazers_count"`
	Forks         int        `json:"forks_count"`
	OpenIssues    int        `json:"open_issues_count"`
	Size          int        `json:"size"`
	Topics        []string   `json:"topics"`
	DefaultBranch string     `json:"default_branch"`
	PushedAt      *time.Time `json:"pushed_at"`
	CreatedAt     *time.Time `json:"created_at"`
	License       *struct {
		SPDXID string `json:"spdx_id"`
	} `json:"license"`
}

func (r Repository) LicenseID() string {
	if r.License == nil {
		return ""
	}
	return r.License.SPDXID
}

// Email is one of the addresses on the account, used to match an existing
// AVERIX account during OAuth sign-in.
type Email struct {
	Email    string `json:"email"`
	Primary  bool   `json:"primary"`
	Verified bool   `json:"verified"`
}

// ── Calls ───────────────────────────────────────────────────────────────────

// CurrentUser identifies the account the token belongs to. This is the call
// whose result becomes the stored github_user_id.
func (c *Client) CurrentUser(ctx context.Context) (*User, error) {
	var u User
	if err := c.get(ctx, "/user", &u); err != nil {
		return nil, err
	}
	if u.ID == 0 || u.Login == "" {
		return nil, errors.New("github returned a user with no id")
	}
	return &u, nil
}

// VerifiedEmails returns the verified addresses on the account.
//
// Only verified ones are returned: an unverified address on a GitHub account
// proves nothing and must not be used to claim an AVERIX account.
func (c *Client) VerifiedEmails(ctx context.Context) ([]Email, error) {
	var emails []Email
	if err := c.get(ctx, "/user/emails", &emails); err != nil {
		// The email scope may not have been granted, which is not an error:
		// the flow falls back to asking the user.
		if errors.Is(err, ErrUnauthorised) || errors.Is(err, ErrNotFound) {
			return nil, nil
		}
		return nil, err
	}
	out := make([]Email, 0, len(emails))
	for _, e := range emails {
		if e.Verified && e.Email != "" {
			out = append(out, e)
		}
	}
	return out, nil
}

// Repositories lists the account's repositories, newest push first.
//
// maxRepos bounds the work: a developer with 400 repositories does not need
// all of them analysed, and the most recently pushed are the ones that say
// something about what they do now.
func (c *Client) Repositories(ctx context.Context, includePrivate bool, maxRepos int) ([]Repository, error) {
	if maxRepos <= 0 || maxRepos > 200 {
		maxRepos = 100
	}
	visibility := "public"
	if includePrivate {
		visibility = "all"
	}

	var out []Repository
	const perPage = 50
	for page := 1; len(out) < maxRepos; page++ {
		query := url.Values{}
		query.Set("per_page", strconv.Itoa(perPage))
		query.Set("page", strconv.Itoa(page))
		query.Set("sort", "pushed")
		query.Set("direction", "desc")
		query.Set("visibility", visibility)
		// Affiliation is limited to what the developer actually owns or
		// collaborates on; organisation repositories they merely have read
		// access to are not theirs to show as portfolio work.
		query.Set("affiliation", "owner,collaborator")

		var batch []Repository
		if err := c.get(ctx, "/user/repos?"+query.Encode(), &batch); err != nil {
			if len(out) > 0 {
				// A partial result is still useful; the caller records the
				// analysis as partial rather than failed.
				logx.From(ctx).Warn("github repository listing stopped early",
					"page", page, "error", err)
				return out, nil
			}
			return nil, err
		}
		if len(batch) == 0 {
			break
		}
		out = append(out, batch...)
		if len(batch) < perPage {
			break
		}
	}
	if len(out) > maxRepos {
		out = out[:maxRepos]
	}
	return out, nil
}

// Languages returns GitHub's byte counts per language for a repository.
//
// These are bytes of code, nothing more. The product reports them as code
// share and never converts them into a competence rating.
func (c *Client) Languages(ctx context.Context, fullName string) (map[string]int64, error) {
	var langs map[string]int64
	if err := c.get(ctx, "/repos/"+fullName+"/languages", &langs); err != nil {
		return nil, err
	}
	return langs, nil
}

// FileContent fetches a single file's decoded contents.
//
// Used for the manifests that prove a technology is actually in use: go.mod,
// requirements.txt, package.json and the rest. A missing file is not an error.
func (c *Client) FileContent(ctx context.Context, fullName, path string, maxBytes int64) (string, error) {
	var payload struct {
		Content  string `json:"content"`
		Encoding string `json:"encoding"`
		Size     int64  `json:"size"`
		Type     string `json:"type"`
	}
	if err := c.get(ctx, "/repos/"+fullName+"/contents/"+path, &payload); err != nil {
		if errors.Is(err, ErrNotFound) {
			return "", nil
		}
		return "", err
	}
	if payload.Type != "file" {
		return "", nil
	}
	if maxBytes > 0 && payload.Size > maxBytes {
		// A 4 MB lockfile says nothing a 64 KB manifest does not.
		return "", nil
	}
	if payload.Encoding != "base64" {
		return payload.Content, nil
	}
	decoded, err := decodeBase64(payload.Content)
	if err != nil {
		return "", fmt.Errorf("decode %s from %s: %w", path, fullName, err)
	}
	return decoded, nil
}

// Readme fetches the repository's README, which the AI summary draws on.
func (c *Client) Readme(ctx context.Context, fullName string, maxBytes int64) (string, error) {
	var payload struct {
		Content  string `json:"content"`
		Encoding string `json:"encoding"`
		Size     int64  `json:"size"`
	}
	if err := c.get(ctx, "/repos/"+fullName+"/readme", &payload); err != nil {
		if errors.Is(err, ErrNotFound) {
			return "", nil
		}
		return "", err
	}
	decoded, err := decodeBase64(payload.Content)
	if err != nil {
		return "", nil
	}
	if maxBytes > 0 && int64(len(decoded)) > maxBytes {
		decoded = decoded[:maxBytes]
	}
	return decoded, nil
}

// RootEntries lists the top-level files in a repository, so the analyser knows
// which manifests to fetch rather than guessing and burning API calls on 404s.
func (c *Client) RootEntries(ctx context.Context, fullName string) ([]string, error) {
	var entries []struct {
		Name string `json:"name"`
		Type string `json:"type"`
	}
	if err := c.get(ctx, "/repos/"+fullName+"/contents/", &entries); err != nil {
		if errors.Is(err, ErrNotFound) {
			return nil, nil
		}
		return nil, err
	}
	out := make([]string, 0, len(entries))
	for _, e := range entries {
		out = append(out, e.Name)
	}
	return out, nil
}

func decodeBase64(encoded string) (string, error) {
	// GitHub wraps base64 at 60 characters.
	cleaned := strings.NewReplacer("\n", "", "\r", "", " ", "").Replace(encoded)
	decoded, err := base64Decode(cleaned)
	if err != nil {
		return "", err
	}
	return string(decoded), nil
}
