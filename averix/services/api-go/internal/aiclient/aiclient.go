// Package aiclient talks to the Python analysis service.
//
// Two rules hold everywhere in this package:
//
//  1. The analysis service is never trusted to be up. Every method returns a
//     result that says whether it was generated, and callers show a
//     configuration state rather than an empty space or an invented answer.
//  2. No credential crosses this boundary. The GitHub OAuth token stays in
//     this service; what goes over the wire is already-fetched repository
//     material.
package aiclient

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"time"

	"github.com/averix/api/internal/config"
	"github.com/averix/api/internal/platform/logx"
)

type Client struct {
	http    *http.Client
	baseURL string
	token   string
	enabled bool
}

func New(cfg config.AI) *Client {
	return &Client{
		http: &http.Client{
			Timeout: cfg.Timeout,
			// The analysis service is internal and never redirects.
			CheckRedirect: func(*http.Request, []*http.Request) error {
				return errors.New("unexpected redirect from the analysis service")
			},
		},
		baseURL: cfg.ServiceURL,
		token:   cfg.ServiceToken,
		enabled: cfg.Configured(),
	}
}

// Configured reports whether the service is reachable at all, so a caller can
// skip the round trip and the UI can explain the absence.
func (c *Client) Configured() bool { return c.enabled }

var ErrUnavailable = errors.New("the analysis service is unavailable")

// Health probes the service for the readiness endpoint.
func (c *Client) Health(ctx context.Context) error {
	if !c.enabled {
		return fmt.Errorf("%w: not configured", ErrUnavailable)
	}
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, c.baseURL+"/health", nil)
	if err != nil {
		return err
	}
	resp, err := c.http.Do(req)
	if err != nil {
		return fmt.Errorf("%w: %v", ErrUnavailable, err)
	}
	defer drain(resp)
	if resp.StatusCode != http.StatusOK {
		return fmt.Errorf("%w: health returned %d", ErrUnavailable, resp.StatusCode)
	}
	return nil
}

// post sends a JSON request and decodes the response.
func (c *Client) post(ctx context.Context, path string, body, dst any) error {
	if !c.enabled {
		return fmt.Errorf("%w: not configured", ErrUnavailable)
	}

	payload, err := json.Marshal(body)
	if err != nil {
		return fmt.Errorf("encode request for %s: %w", path, err)
	}

	req, err := http.NewRequestWithContext(ctx, http.MethodPost, c.baseURL+path, bytes.NewReader(payload))
	if err != nil {
		return fmt.Errorf("build request for %s: %w", path, err)
	}
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Accept", "application/json")
	if c.token != "" {
		req.Header.Set("Authorization", "Bearer "+c.token)
	}
	if id := logx.RequestID(ctx); id != "" {
		// Correlates a request across both services in the logs.
		req.Header.Set("X-Request-Id", id)
	}

	resp, err := c.http.Do(req)
	if err != nil {
		return fmt.Errorf("%w: %v", ErrUnavailable, err)
	}
	defer drain(resp)

	if resp.StatusCode != http.StatusOK {
		// The body may carry a validation problem worth logging, but nothing
		// from it reaches the user.
		snippet, _ := io.ReadAll(io.LimitReader(resp.Body, 2<<10))
		logx.From(ctx).Warn("analysis service returned an error",
			"path", path, "status", resp.StatusCode, "body", string(snippet))
		return fmt.Errorf("%w: %s returned %d", ErrUnavailable, path, resp.StatusCode)
	}

	if dst == nil {
		return nil
	}
	if err := json.NewDecoder(io.LimitReader(resp.Body, 8<<20)).Decode(dst); err != nil {
		return fmt.Errorf("decode response from %s: %w", path, err)
	}
	return nil
}

func drain(resp *http.Response) {
	_, _ = io.Copy(io.Discard, io.LimitReader(resp.Body, 4<<10))
	_ = resp.Body.Close()
}

// ── GitHub analysis ─────────────────────────────────────────────────────────

type ManifestFile struct {
	Name    string `json:"name"`
	Content string `json:"content"`
}

type RepositoryInput struct {
	RepositoryID    string           `json:"repository_id"`
	Name            string           `json:"name"`
	FullName        string           `json:"full_name"`
	Description     string           `json:"description"`
	Homepage        string           `json:"homepage"`
	Topics          []string         `json:"topics"`
	PrimaryLanguage string           `json:"primary_language"`
	Languages       map[string]int64 `json:"languages"`
	Stars           int              `json:"stars"`
	Forks           int              `json:"forks"`
	SizeKB          int              `json:"size_kb"`
	IsFork          bool             `json:"is_fork"`
	IsPrivate       bool             `json:"is_private"`
	IsArchived      bool             `json:"is_archived"`
	PushedAt        *time.Time       `json:"pushed_at,omitempty"`
	Readme          string           `json:"readme"`
	Manifests       []ManifestFile   `json:"manifests"`
}

type AnalyseRequest struct {
	AnalysisID             string            `json:"analysis_id"`
	GitHubLogin            string            `json:"github_login"`
	Repositories           []RepositoryInput `json:"repositories"`
	DeclaredSkills         []string          `json:"declared_skills"`
	DeclaredSpecialisation string            `json:"declared_specialisation"`
	WantSummary            bool              `json:"want_summary"`
}

type DetectedTechnology struct {
	SkillSlug   string  `json:"skill_slug"`
	RawName     string  `json:"raw_name"`
	Source      string  `json:"source"`
	Confidence  float64 `json:"confidence"`
	VersionSpec string  `json:"version_spec"`
}

type RepositoryFinding struct {
	RepositoryID       string               `json:"repository_id"`
	Technologies       []DetectedTechnology `json:"technologies"`
	InferredPurpose    string               `json:"inferred_purpose"`
	SuggestedCategory  string               `json:"suggested_category"`
	PortfolioCandidate bool                 `json:"portfolio_candidate"`
	CandidateReason    string               `json:"candidate_reason"`
	ReadmeExcerpt      string               `json:"readme_excerpt"`
}

type LanguageShare struct {
	Language string  `json:"language"`
	Bytes    int64   `json:"bytes"`
	Share    float64 `json:"share"`
}

type TechnologySummary struct {
	SkillSlug    string   `json:"skill_slug"`
	Repositories int      `json:"repositories"`
	Confidence   float64  `json:"confidence"`
	Sources      []string `json:"sources"`
}

type AnalyseResponse struct {
	AnalysisID           string              `json:"analysis_id"`
	Status               string              `json:"status"`
	RepositoriesSeen     int                 `json:"repositories_seen"`
	RepositoriesAnalysed int                 `json:"repositories_analysed"`
	LanguageShares       []LanguageShare     `json:"language_shares"`
	Technologies         []TechnologySummary `json:"technologies"`
	Findings             []RepositoryFinding `json:"findings"`
	Summary              string              `json:"summary"`
	SummaryModel         string              `json:"summary_model"`
	SummaryGenerated     bool                `json:"summary_generated"`
	FocusAreas           []string            `json:"focus_areas"`
	CorroboratedSkills   []string            `json:"corroborated_skills"`
	UnsupportedSkills    []string            `json:"unsupported_skills"`
	SuggestedSkills      []string            `json:"suggested_skills"`
	DegradedReason       string              `json:"degraded_reason"`
}

func (c *Client) AnalyseGitHub(ctx context.Context, req AnalyseRequest) (*AnalyseResponse, error) {
	var out AnalyseResponse
	if err := c.post(ctx, "/v1/github/analyse", req, &out); err != nil {
		return nil, err
	}
	return &out, nil
}

// ── Project assistant ───────────────────────────────────────────────────────

type AssistantStartRequest struct {
	Description string `json:"description"`
	Locale      string `json:"locale,omitempty"`
}

type AssistantQuestion struct {
	Key      string   `json:"key"`
	Question string   `json:"question"`
	Options  []string `json:"options,omitempty"`
	Optional bool     `json:"optional"`
	HelpText string   `json:"help_text,omitempty"`
}

type AssistantStartResponse struct {
	SuggestedCategory  string              `json:"suggested_category"`
	CategoryConfidence float64             `json:"category_confidence"`
	Questions          []AssistantQuestion `json:"questions"`
	Understanding      string              `json:"understanding"`
	Generated          bool                `json:"generated"`
	DegradedReason     string              `json:"degraded_reason"`
}

func (c *Client) AssistantStart(ctx context.Context, req AssistantStartRequest) (*AssistantStartResponse, error) {
	var out AssistantStartResponse
	if err := c.post(ctx, "/v1/assistant/start", req, &out); err != nil {
		return nil, err
	}
	return &out, nil
}

type AssistantDraftRequest struct {
	Description string         `json:"description"`
	Answers     map[string]any `json:"answers"`
	Locale      string         `json:"locale,omitempty"`
}

type DraftFeature struct {
	Title    string `json:"title"`
	Detail   string `json:"detail"`
	Required bool   `json:"required"`
}

type DraftMilestone struct {
	Title  string  `json:"title"`
	Detail string  `json:"detail"`
	Share  float64 `json:"share"`
	Days   int     `json:"days"`
}

type AssistantDraftResponse struct {
	Title           string           `json:"title"`
	Summary         string           `json:"summary"`
	Description     string           `json:"description"`
	CategorySlug    string           `json:"category_slug"`
	SuggestedSkills []string         `json:"suggested_skills"`
	Features        []DraftFeature   `json:"features"`
	Milestones      []DraftMilestone `json:"milestones"`
	EstimatedScale  string           `json:"estimated_scale"`
	OpenQuestions   []string         `json:"open_questions"`
	Generated       bool             `json:"generated"`
	Model           string           `json:"model"`
	DegradedReason  string           `json:"degraded_reason"`
}

func (c *Client) AssistantDraft(ctx context.Context, req AssistantDraftRequest) (*AssistantDraftResponse, error) {
	var out AssistantDraftResponse
	if err := c.post(ctx, "/v1/assistant/draft", req, &out); err != nil {
		return nil, err
	}
	return &out, nil
}

// ── Match explanation ───────────────────────────────────────────────────────

type ExplainReason struct {
	Label  string `json:"label"`
	Met    bool   `json:"met"`
	Detail string `json:"detail,omitempty"`
}

type ExplainRequest struct {
	ProjectTitle    string          `json:"project_title"`
	ProjectCategory string          `json:"project_category,omitempty"`
	RequiredSkills  []string        `json:"required_skills,omitempty"`
	Score           int             `json:"score"`
	Reasons         []ExplainReason `json:"reasons"`
	DeveloperTitle  string          `json:"developer_title,omitempty"`
}

type ExplainResponse struct {
	Explanation    string `json:"explanation"`
	Generated      bool   `json:"generated"`
	DegradedReason string `json:"degraded_reason"`
}

func (c *Client) ExplainMatch(ctx context.Context, req ExplainRequest) (*ExplainResponse, error) {
	var out ExplainResponse
	if err := c.post(ctx, "/v1/matching/explain", req, &out); err != nil {
		return nil, err
	}
	return &out, nil
}
