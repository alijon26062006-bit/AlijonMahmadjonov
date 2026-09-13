package githubint

import (
	"context"
	"errors"
	"time"

	"github.com/google/uuid"

	"github.com/averix/api/internal/aiclient"
	"github.com/averix/api/internal/audit"
	"github.com/averix/api/internal/config"
	"github.com/averix/api/internal/platform/cache"
	"github.com/averix/api/internal/platform/httpx"
	"github.com/averix/api/internal/platform/logx"
	"github.com/averix/api/internal/security"
)

// MatchInvalidator lets a completed analysis drop stale match scores, since
// new GitHub evidence changes the score.
type MatchInvalidator interface {
	InvalidateForDeveloper(ctx context.Context, developerID uuid.UUID) error
}

// SkillNames resolves taxonomy slugs to display names for the summary.
type SkillNames interface {
	Names(ctx context.Context, slugs []string) (map[string]string, error)
}

// Notifier tells the developer their analysis finished.
type Notifier interface {
	GitHubAnalysisComplete(ctx context.Context, userID uuid.UUID, technologies int)
	GitHubAnalysisFailed(ctx context.Context, userID uuid.UUID, reason string)
}

type Service struct {
	store    *Store
	oauth    *OAuth
	cfg      *config.Config
	ai       *aiclient.Client
	audit    *audit.Recorder
	cache    *cache.Cache
	matching MatchInvalidator
	notifier Notifier
}

func NewService(store *Store, oauth *OAuth, cfg *config.Config, ai *aiclient.Client,
	rec *audit.Recorder, c *cache.Cache, matching MatchInvalidator, notifier Notifier) *Service {
	return &Service{
		store: store, oauth: oauth, cfg: cfg, ai: ai,
		audit: rec, cache: c, matching: matching, notifier: notifier,
	}
}

// ── Connection ──────────────────────────────────────────────────────────────

// StartConnect returns the URL to send a signed-in developer to.
func (s *Service) StartConnect(ctx context.Context, id *security.Identity, redirectTo string, wantPrivate bool) (string, error) {
	if !id.Authenticated() {
		return "", httpx.ErrUnauthenticated
	}
	if err := security.RequirePermission(id, security.PermGitHubConnect); err != nil {
		return "", httpx.ErrForbidden.Wrap(err)
	}
	if !s.oauth.Configured() {
		e := *httpx.ErrNotConfigured
		e.Message = "GitHub пока не настроен на этой площадке."
		return "", &e
	}

	intent := IntentConnect
	if wantPrivate {
		// The second consent. Asked for separately and only on request: a
		// developer must never find that connecting their account also gave
		// away read access to their private code.
		if _, err := s.store.ByUser(ctx, id.UserID); err != nil {
			return "", httpx.Validation(map[string]string{
				"github": "Сначала подключите GitHub, потом открывайте доступ к закрытым репозиториям.",
			})
		}
		intent = IntentPrivate
	}

	url, err := s.oauth.Start(ctx, intent, id.UserID, redirectTo)
	if err != nil {
		return "", httpx.Internalf(err, "start github authorisation")
	}
	return url, nil
}

// CallbackResult is what the callback handler needs to finish the flow.
type CallbackResult struct {
	Account    *Account
	RedirectTo string
	// Set when the developer granted private repository access on this pass.
	PrivateGranted bool
}

// Callback completes the flow: validates the state, exchanges the code and
// links the verified identity.
//
// The identity comes from GitHub's /user response under the freshly issued
// token, which is what makes the stored github_user_id proof of ownership.
// Nothing is ever inferred from a name.
func (s *Service) Callback(ctx context.Context, code, state string) (*CallbackResult, error) {
	record, err := s.oauth.ConsumeState(ctx, state)
	if err != nil {
		if errors.Is(err, ErrStateInvalid) {
			e := *httpx.ErrBadRequest
			e.Code = "github_state_invalid"
			e.Message = "Ссылка GitHub устарела или уже использована. Начните подключение заново."
			return nil, &e
		}
		return nil, httpx.Internalf(err, "consume oauth state")
	}
	if record.UserID == nil {
		// Sign-in through GitHub is a separate flow; a connect callback
		// without a user is a malformed state.
		return nil, httpx.ErrBadRequest.Wrap(errors.New("oauth state carries no user"))
	}
	userID := *record.UserID

	token, err := s.oauth.Exchange(ctx, code)
	if err != nil {
		logx.From(ctx).Warn("github token exchange failed", "error", err)
		e := *httpx.ErrBadRequest
		e.Code = "github_exchange_failed"
		e.Message = "GitHub не завершил подключение. Попробуйте ещё раз."
		return nil, &e
	}

	client := NewClient(s.cfg.GitHub, token.AccessToken)
	user, err := client.CurrentUser(ctx)
	if err != nil {
		logx.From(ctx).Warn("could not identify the github account", "error", err)
		e := *httpx.ErrUnavailable
		e.Code = "github_unreachable"
		e.Message = "Не удалось связаться с GitHub, чтобы подтвердить аккаунт. Попробуйте чуть позже."
		return nil, &e
	}

	account, err := s.store.Link(ctx, LinkInput{
		UserID:       userID,
		User:         user,
		AccessToken:  token.AccessToken,
		RefreshToken: token.RefreshToken,
		TokenExpires: token.ExpiresAt,
		Scopes:       token.Scopes,
	})
	if errors.Is(err, ErrAlreadyClaimed) {
		e := *httpx.ErrConflict
		e.Code = "github_already_connected"
		e.Message = "Этот GitHub уже привязан к другому аккаунту AVERIX."
		return nil, &e
	}
	if err != nil {
		return nil, httpx.Internalf(err, "link github account")
	}

	privateGranted := account.HasPrivateAccess()
	action := audit.ActionGitHubConnected
	if privateGranted {
		action = audit.ActionGitHubPrivateGranted
	}
	s.audit.Record(ctx, audit.Entry{
		ActorID: &userID, ActorRole: "developer",
		Action: action, SubjectType: "github_account", SubjectID: &account.ID,
		After: map[string]any{
			"login":  account.Login,
			"scopes": account.Scopes,
		},
	})

	return &CallbackResult{
		Account:        account,
		RedirectTo:     SafeRedirect(s.cfg.AppURL, record.RedirectTo),
		PrivateGranted: privateGranted,
	}, nil
}

// Disconnect removes the link and destroys the stored tokens.
func (s *Service) Disconnect(ctx context.Context, id *security.Identity) error {
	if !id.Authenticated() {
		return httpx.ErrUnauthenticated
	}
	if err := s.store.Revoke(ctx, id.UserID); err != nil {
		return httpx.Internalf(err, "disconnect github")
	}
	// GitHub evidence on skills and the cached match scores both came from
	// the connection; leaving them would advertise a link that no longer
	// exists.
	if s.matching != nil {
		_ = s.matching.InvalidateForDeveloper(context.WithoutCancel(ctx), id.UserID)
	}
	s.audit.RecordRequest(ctx, audit.Entry{
		Action: audit.ActionGitHubDisconnected, SubjectType: "github_account",
		SubjectID: &id.UserID,
	})
	return nil
}

// Status is what the settings page and the onboarding step show.
type Status struct {
	Configured bool      `json:"configured"`
	Connected  bool      `json:"connected"`
	Account    *Account  `json:"account,omitempty"`
	Analysis   *Analysis `json:"analysis,omitempty"`
	// Whether the developer may grant private repository access, and whether
	// they already have.
	CanGrantPrivate bool `json:"can_grant_private"`
	PrivateGranted  bool `json:"private_granted"`
	// Set when the analysis service is unavailable, so the UI explains the
	// missing summary rather than showing a blank panel.
	AnalysisDegraded string `json:"analysis_degraded,omitempty"`
}

func (s *Service) Status(ctx context.Context, id *security.Identity) (*Status, error) {
	if !id.Authenticated() {
		return nil, httpx.ErrUnauthenticated
	}

	status := &Status{Configured: s.oauth.Configured()}
	if !status.Configured {
		return status, nil
	}

	account, err := s.store.ByUser(ctx, id.UserID)
	if errors.Is(err, ErrNoAccount) {
		return status, nil
	}
	if err != nil {
		return nil, httpx.Internalf(err, "load github account")
	}

	status.Connected = true
	status.Account = account
	status.CanGrantPrivate = true
	status.PrivateGranted = account.HasPrivateAccess()

	if analysis, err := s.store.LatestAnalysis(ctx, id.UserID); err == nil {
		status.Analysis = analysis
	}
	if !s.ai.Configured() {
		status.AnalysisDegraded = "The analysis service isn't configured on this environment, " +
			"so technologies are detected but no written summary is produced."
	}
	return status, nil
}

// ── Analysis ────────────────────────────────────────────────────────────────

// Sync fetches the repositories and runs the analysis.
//
// A lock keeps one sync per account in flight: the work is expensive in GitHub
// API quota, and two concurrent runs would race on the mirrored rows.
func (s *Service) Sync(ctx context.Context, id *security.Identity, trigger string) (*Analysis, error) {
	if !id.Authenticated() {
		return nil, httpx.ErrUnauthenticated
	}
	if err := security.RequirePermission(id, security.PermGitHubConnect); err != nil {
		return nil, httpx.ErrForbidden.Wrap(err)
	}

	account, err := s.store.ByUser(ctx, id.UserID)
	if errors.Is(err, ErrNoAccount) {
		e := *httpx.ErrNotFound
		e.Code = "github_not_connected"
		e.Message = "Сначала подключите аккаунт GitHub."
		return nil, &e
	}
	if err != nil {
		return nil, httpx.Internalf(err, "load github account")
	}

	if s.cache != nil {
		release, ok := s.cache.Lock(ctx, "github-sync:"+account.ID.String(), 10*time.Minute)
		if !ok {
			e := *httpx.ErrConflict
			e.Code = "github_sync_in_progress"
			e.Message = "Анализ вашего GitHub уже идёт."
			return nil, &e
		}
		defer release()
	}

	analysis, err := s.runSync(ctx, account, trigger)
	if err != nil {
		return nil, err
	}
	return analysis, nil
}

// SyncForUser runs a sync for one account without a session.
//
// The background worker's entry point: the same path a developer's own
// refresh takes, minus the identity checks that only make sense inside a
// request. It acts on behalf of nobody — it re-reads what the developer
// already connected.
func (s *Service) SyncForUser(ctx context.Context, userID uuid.UUID, trigger string) error {
	account, err := s.store.ByUser(ctx, userID)
	if err != nil {
		return err
	}
	if account == nil {
		// Disconnected between the enqueue and now; nothing to do.
		return nil
	}
	_, err = s.runSync(ctx, account, trigger)
	return err
}

func (s *Service) runSync(ctx context.Context, account *Account, trigger string) (*Analysis, error) {
	analysisID, err := s.store.StartAnalysis(ctx, account.ID, trigger)
	if err != nil {
		return nil, httpx.Internalf(err, "start analysis")
	}

	result, syncErr := s.fetchAndAnalyse(ctx, account, analysisID)
	if syncErr != nil {
		result.Status = "failed"
		if result.ErrorCode == "" {
			result.ErrorCode = "sync_failed"
		}
		result.ErrorDetail = syncErr.Error()
	}

	if err := s.store.FinishAnalysis(ctx, analysisID, result); err != nil {
		logx.From(ctx).Error("could not record the analysis result", "error", err)
	}
	if err := s.store.MarkSynced(ctx, account.ID, result.ErrorDetail); err != nil {
		logx.From(ctx).Warn("could not mark the account synced", "error", err)
	}

	if s.notifier != nil {
		if result.Status == "failed" {
			s.notifier.GitHubAnalysisFailed(context.WithoutCancel(ctx), account.UserID, result.ErrorCode)
		} else {
			s.notifier.GitHubAnalysisComplete(context.WithoutCancel(ctx), account.UserID,
				len(result.TechnologySummary))
		}
	}
	if s.matching != nil {
		// New evidence changes every score this developer has.
		_ = s.matching.InvalidateForDeveloper(context.WithoutCancel(ctx), account.UserID)
	}

	if syncErr != nil {
		switch {
		case errors.Is(syncErr, ErrUnauthorised):
			e := *httpx.ErrForbidden
			e.Code = "github_authorisation_expired"
			e.Message = "GitHub больше не принимает наш доступ. Подключите аккаунт заново."
			return nil, &e
		case errors.Is(syncErr, ErrRateLimited):
			e := *httpx.ErrRateLimited
			e.Code = "github_rate_limited"
			e.Message = "Достигнут лимит запросов к GitHub. Попробуйте через час."
			e.RetryAfter = 3600
			return nil, &e
		}
		return nil, httpx.Internalf(syncErr, "github analysis")
	}

	return s.store.LatestAnalysis(ctx, account.UserID)
}

// fetchAndAnalyse does the work: fetch from GitHub, hand the material to the
// analysis service, persist what comes back.
func (s *Service) fetchAndAnalyse(ctx context.Context, account *Account, analysisID uuid.UUID) (AnalysisResult, error) {
	result := AnalysisResult{Status: "succeeded", RateLimitRemaining: -1}

	token, err := s.store.AccessToken(ctx, account.ID)
	if err != nil {
		result.ErrorCode = "token_unavailable"
		return result, err
	}
	client := NewClient(s.cfg.GitHub, token)

	repos, err := client.Repositories(ctx, account.HasPrivateAccess(), 100)
	result.APICallsUsed = client.Calls()
	result.RateLimitRemaining = client.Remaining()
	if err != nil {
		result.ErrorCode = "repository_listing_failed"
		return result, err
	}
	result.ReposSeen = len(repos)

	if err := s.store.SaveRepositories(ctx, account.ID, repos); err != nil {
		result.ErrorCode = "mirror_failed"
		return result, err
	}
	repoIDs, err := s.store.RepositoryIDs(ctx, account.ID)
	if err != nil {
		result.ErrorCode = "mirror_failed"
		return result, err
	}

	// Fetch the material the analysis needs. Bounded per repository: a
	// developer with a hundred repositories must not consume their whole
	// GitHub quota in one sync.
	inputs := make([]aiclient.RepositoryInput, 0, len(repos))
	languageTotals := map[string]int64{}
	perRepoFindings := make([][]Finding, 0, len(repos))

	for _, repo := range repos {
		rowID, ok := repoIDs[repo.ID]
		if !ok {
			continue
		}

		languages, err := client.Languages(ctx, repo.FullName)
		if err != nil {
			if errors.Is(err, ErrRateLimited) {
				result.Status = "partial"
				result.ErrorCode = "rate_limited_partway"
				break
			}
			logx.From(ctx).Debug("could not read languages", "repo", repo.FullName, "error", err)
		}
		if err := s.store.SaveLanguages(ctx, rowID, languages); err != nil {
			logx.From(ctx).Warn("could not store languages", "repo", repo.FullName, "error", err)
		}
		if !repo.Fork {
			// A fork's bytes were not written by this developer; counting
			// them would credit them with someone else's code.
			for language, bytes := range languages {
				languageTotals[language] += bytes
			}
		}

		manifests := s.fetchManifests(ctx, client, repo)
		readme, _ := client.Readme(ctx, repo.FullName, 8<<10)

		findings := make([]Finding, 0, 8)
		for _, manifest := range manifests {
			findings = append(findings, Detect(manifest.Name, manifest.Content)...)
		}
		perRepoFindings = append(perRepoFindings, findings)

		input := aiclient.RepositoryInput{
			RepositoryID:    rowID.String(),
			Name:            repo.Name,
			FullName:        repo.FullName,
			Description:     repo.Description,
			Homepage:        repo.Homepage,
			Topics:          repo.Topics,
			PrimaryLanguage: repo.Language,
			Languages:       languages,
			Stars:           repo.Stars,
			Forks:           repo.Forks,
			SizeKB:          repo.Size,
			IsFork:          repo.Fork,
			IsPrivate:       repo.Private,
			IsArchived:      repo.Archived,
			PushedAt:        repo.PushedAt,
			Readme:          readme,
			Manifests:       manifests,
		}
		inputs = append(inputs, input)
		result.ReposAnalysed++
	}

	result.APICallsUsed = client.Calls()
	result.RateLimitRemaining = client.Remaining()

	// The analysis service does the semantic work. When it is unavailable, the
	// deterministic detection above is persisted on its own — a smaller
	// product, not a broken one.
	if s.ai.Configured() {
		if err := s.applyRemoteAnalysis(ctx, account, analysisID, inputs, &result); err != nil {
			logx.From(ctx).Warn("analysis service unavailable, using deterministic findings only",
				"error", err)
			result.Status = "partial"
			s.applyLocalAnalysis(ctx, account.UserID, repoIDs, repos, perRepoFindings, languageTotals, &result)
		}
	} else {
		result.Status = "partial"
		s.applyLocalAnalysis(ctx, account.UserID, repoIDs, repos, perRepoFindings, languageTotals, &result)
	}
	return result, nil
}

// fetchManifests reads the dependency manifests a repository actually has.
//
// The root listing is fetched first so only present files are requested:
// guessing sixteen filenames per repository would burn the API quota on 404s.
func (s *Service) fetchManifests(ctx context.Context, client *Client, repo Repository) []aiclient.ManifestFile {
	entries, err := client.RootEntries(ctx, repo.FullName)
	if err != nil {
		return nil
	}
	present := make(map[string]bool, len(entries))
	for _, name := range entries {
		present[name] = true
	}

	out := make([]aiclient.ManifestFile, 0, 4)
	for _, name := range Manifests {
		if !present[name] {
			continue
		}
		content, err := client.FileContent(ctx, repo.FullName, name, 64<<10)
		if err != nil || content == "" {
			continue
		}
		out = append(out, aiclient.ManifestFile{Name: name, Content: content})
		// Four manifests is enough to characterise any repository; more is
		// quota spent for no additional signal.
		if len(out) >= 4 {
			break
		}
	}
	return out
}

// applyRemoteAnalysis persists what the analysis service returned.
func (s *Service) applyRemoteAnalysis(ctx context.Context, account *Account, analysisID uuid.UUID,
	inputs []aiclient.RepositoryInput, result *AnalysisResult) error {

	declared, specialisation := s.declaredProfile(ctx, account.UserID)

	response, err := s.ai.AnalyseGitHub(ctx, aiclient.AnalyseRequest{
		AnalysisID:             analysisID.String(),
		GitHubLogin:            account.Login,
		Repositories:           inputs,
		DeclaredSkills:         declared,
		DeclaredSpecialisation: specialisation,
		WantSummary:            true,
	})
	if err != nil {
		return err
	}

	for _, finding := range response.Findings {
		rowID, parseErr := uuid.Parse(finding.RepositoryID)
		if parseErr != nil {
			continue
		}
		detected := make([]DetectedTechnology, 0, len(finding.Technologies))
		for _, tech := range finding.Technologies {
			detected = append(detected, DetectedTechnology{
				RepositoryID: rowID,
				SkillSlug:    tech.SkillSlug,
				RawName:      tech.RawName,
				Source:       tech.Source,
				Confidence:   tech.Confidence,
				VersionSpec:  tech.VersionSpec,
			})
		}
		if err := s.store.SaveDetectedTechnologies(ctx, rowID, detected); err != nil {
			logx.From(ctx).Warn("could not store detected technologies", "error", err)
		}

		reason := finding.CandidateReason
		if finding.InferredPurpose != "" {
			reason = finding.InferredPurpose
		}
		if err := s.store.MarkPortfolioCandidate(ctx, rowID,
			finding.PortfolioCandidate, reason, finding.ReadmeExcerpt); err != nil {
			logx.From(ctx).Warn("could not mark portfolio candidacy", "error", err)
		}
	}

	names, _ := s.skillNames(ctx)
	for _, share := range response.LanguageShares {
		result.LanguageStats = append(result.LanguageStats, LanguageStat{
			Language: share.Language, Bytes: share.Bytes, Share: share.Share,
		})
	}
	for _, tech := range response.Technologies {
		result.TechnologySummary = append(result.TechnologySummary, TechnologySummary{
			Slug:         tech.SkillSlug,
			Name:         nameOr(names, tech.SkillSlug),
			Repositories: tech.Repositories,
			Confidence:   tech.Confidence,
			Sources:      tech.Sources,
		})
	}
	result.AISummary = response.Summary
	result.AIModel = response.SummaryModel
	result.FocusAreas = response.FocusAreas
	if response.Status == "partial" {
		result.Status = "partial"
		result.ErrorCode = "summary_unavailable"
	}

	// Evidence is attached only to technologies the developer already claimed.
	// The analysis never adds a skill to someone's profile on their behalf;
	// what it found and they did not claim is offered as a suggestion.
	if err := s.store.AttachEvidenceToSkills(ctx, account.UserID, response.CorroboratedSkills); err != nil {
		logx.From(ctx).Warn("could not attach github evidence to skills", "error", err)
	}
	return nil
}

// applyLocalAnalysis persists the deterministic findings when the analysis
// service is unavailable.
//
// This is the whole feature minus the prose: technologies are still detected
// from manifests, evidence is still attached to declared skills, and portfolio
// candidates are still suggested. What is missing is the written summary, and
// the analysis is recorded as partial so the interface says so.
func (s *Service) applyLocalAnalysis(ctx context.Context, userID uuid.UUID,
	repoIDs map[int64]uuid.UUID, repos []Repository, perRepo [][]Finding,
	languageTotals map[string]int64, result *AnalysisResult) {

	names, _ := s.skillNames(ctx)

	for i, repo := range repos {
		rowID, ok := repoIDs[repo.ID]
		if !ok || i >= len(perRepo) {
			continue
		}
		findings := perRepo[i]

		detected := make([]DetectedTechnology, 0, len(findings))
		known := 0
		for _, f := range findings {
			if f.SkillSlug != "" {
				known++
			}
			detected = append(detected, DetectedTechnology{
				RepositoryID: rowID,
				SkillSlug:    f.SkillSlug,
				RawName:      f.RawName,
				Source:       f.Source,
				Confidence:   f.Confidence,
				VersionSpec:  f.VersionSpec,
			})
		}
		if err := s.store.SaveDetectedTechnologies(ctx, rowID, detected); err != nil {
			logx.From(ctx).Warn("could not store detected technologies", "error", err)
		}

		candidate, reason := PortfolioWorthiness(repo, repo.Description != "", known)
		if err := s.store.MarkPortfolioCandidate(ctx, rowID, candidate, reason, ""); err != nil {
			logx.From(ctx).Warn("could not mark portfolio candidacy", "error", err)
		}
	}

	result.LanguageStats = LanguageShares(languageTotals, 6)
	result.TechnologySummary = SummariseTechnologies(perRepo, names)
	if result.ErrorCode == "" {
		result.ErrorCode = "summary_unavailable"
	}

	// Corroborate the technologies the developer declared, so the evidence
	// badges work without the analysis service. Only what they already claimed
	// is touched: nothing is added to their profile on their behalf.
	declared, _ := s.declaredProfile(ctx, userID)
	declaredSet := make(map[string]struct{}, len(declared))
	for _, slug := range declared {
		declaredSet[slug] = struct{}{}
	}
	corroborated := make([]string, 0, len(declared))
	for _, tech := range result.TechnologySummary {
		if tech.Confidence < 0.6 {
			continue
		}
		if _, claimed := declaredSet[tech.Slug]; claimed {
			corroborated = append(corroborated, tech.Slug)
		}
	}
	if err := s.store.AttachEvidenceToSkills(ctx, userID, corroborated); err != nil {
		logx.From(ctx).Warn("could not attach github evidence to skills", "error", err)
	}
}

// declaredProfile returns the developer's declared technologies and their
// primary specialisation's name, which the summary uses for context.
func (s *Service) declaredProfile(ctx context.Context, userID uuid.UUID) ([]string, string) {
	if userID == uuid.Nil {
		return nil, ""
	}
	rows, err := s.store.db.Query(ctx, `
		SELECT sk.slug FROM developer_skills ds
		JOIN skills sk ON sk.id = ds.skill_id
		WHERE ds.user_id = $1`, userID)
	if err != nil {
		return nil, ""
	}
	var slugs []string
	for rows.Next() {
		var slug string
		if err := rows.Scan(&slug); err == nil {
			slugs = append(slugs, slug)
		}
	}
	rows.Close()

	var specialisation string
	_ = s.store.db.QueryRow(ctx, `
		SELECT coalesce(sp.name, '') FROM developer_profiles d
		LEFT JOIN specialisations sp ON sp.id = d.primary_specialisation_id
		WHERE d.user_id = $1`, userID).Scan(&specialisation)
	return slugs, specialisation
}

func (s *Service) skillNames(ctx context.Context) (map[string]string, error) {
	rows, err := s.store.db.Query(ctx, `SELECT slug, name FROM skills WHERE is_active`)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	out := map[string]string{}
	for rows.Next() {
		var slug, name string
		if err := rows.Scan(&slug, &name); err != nil {
			return out, err
		}
		out[slug] = name
	}
	return out, rows.Err()
}

// PortfolioCandidates lists the repositories worth offering as portfolio work.
func (s *Service) PortfolioCandidates(ctx context.Context, id *security.Identity) ([]map[string]any, error) {
	if !id.Authenticated() {
		return nil, httpx.ErrUnauthenticated
	}
	candidates, err := s.store.PortfolioCandidates(ctx, id.UserID, 12)
	if err != nil {
		return nil, httpx.Internalf(err, "load portfolio candidates")
	}
	return candidates, nil
}

func nameOr(names map[string]string, slug string) string {
	if name, ok := names[slug]; ok && name != "" {
		return name
	}
	return slug
}
