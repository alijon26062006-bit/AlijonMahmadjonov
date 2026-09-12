"""GitHub repository analysis.

Two layers, deliberately separated:

The deterministic layer parses manifests, computes code share and judges
portfolio candidacy. It always runs, always produces the same answer for the
same input, and costs nothing. Its output is what becomes evidence attached to
a developer's profile.

The generative layer writes the prose technical profile and infers what each
repository is for. It runs only when a model is configured, and its absence is
reported rather than hidden — the deterministic findings stand on their own.
"""

from __future__ import annotations

import asyncio

from app.ai.client import ModelClient, ModelUnavailable
from app.ai.prompts import (
    REPOSITORY_PURPOSE_SYSTEM,
    TECHNICAL_PROFILE_SYSTEM,
    repository_purpose_prompt,
    technical_profile_prompt,
)
from app.config import Settings
from app.github import detect
from app.logging import get_logger
from app.schemas.github import (
    AnalyseRequest,
    AnalyseResponse,
    DetectedTechnology,
    LanguageShare,
    RepositoryFinding,
    RepositoryInput,
    TechnologySummary,
)
from app.taxonomy import CATEGORY_SLUGS, SKILL_SLUGS

log = get_logger(__name__)

# How many repositories get a generated purpose line. Each one is a model
# call, and the portfolio suggestion flow shows a handful — spending a call on
# the fiftieth repository buys nothing.
_PURPOSE_BUDGET = 8


class AnalysisService:
    def __init__(self, settings: Settings, model: ModelClient) -> None:
        self._settings = settings
        self._model = model

    async def analyse(self, request: AnalyseRequest) -> AnalyseResponse:
        repositories = request.repositories[: self._settings.max_repositories]

        per_repository: list[list[detect.Finding]] = []
        findings: list[RepositoryFinding] = []
        language_totals: dict[str, int] = {}

        for repo in repositories:
            repo_findings = self._detect_repository(repo)
            per_repository.append(repo_findings)

            # Forks and archived repositories still contribute technology
            # evidence — the developer did work in them — but they are not
            # offered as portfolio pieces, and their language bytes would
            # distort the share with code they did not write.
            if not repo.is_fork:
                for language, byte_count in repo.languages.items():
                    if byte_count > 0:
                        language_totals[language] = language_totals.get(language, 0) + byte_count

            candidate, reason = detect.portfolio_worthiness(
                is_fork=repo.is_fork,
                is_private=repo.is_private,
                is_archived=repo.is_archived,
                size_kb=repo.size_kb,
                description=repo.description,
                has_readme=bool(repo.readme.strip()),
                detected_count=sum(1 for f in repo_findings if f.skill_slug),
                stars=repo.stars,
                homepage=repo.homepage,
                topic_count=len(repo.topics),
            )

            findings.append(
                RepositoryFinding(
                    repository_id=repo.repository_id,
                    technologies=[
                        DetectedTechnology(
                            skill_slug=f.skill_slug,
                            raw_name=f.raw_name,
                            source=f.source,
                            confidence=f.confidence,
                            version_spec=f.version_spec,
                        )
                        for f in repo_findings
                    ],
                    portfolio_candidate=candidate,
                    candidate_reason=reason,
                    readme_excerpt=_excerpt(repo.readme, 600),
                )
            )

        shares = detect.language_shares(language_totals, top_n=6)
        aggregates = detect.aggregate(per_repository)

        response = AnalyseResponse(
            analysis_id=request.analysis_id,
            status="succeeded",
            repositories_seen=len(request.repositories),
            repositories_analysed=len(repositories),
            language_shares=[
                LanguageShare(language=lang, bytes=count, share=share) for lang, count, share in shares
            ],
            technologies=[
                TechnologySummary(
                    skill_slug=entry.skill_slug,
                    repositories=entry.repositories,
                    confidence=entry.confidence,
                    sources=sorted(entry.sources),
                )
                for entry in aggregates
            ],
            findings=findings,
            focus_areas=_focus_areas(aggregates),
        )

        detected_slugs = {entry.skill_slug for entry in aggregates}
        declared = {slug.strip().lower() for slug in request.declared_skills if slug.strip()}
        response.corroborated_skills = sorted(declared & detected_slugs)
        response.unsupported_skills = sorted(declared - detected_slugs)
        # Offered, never applied: the analysis does not add technologies to
        # anyone's profile on their behalf.
        response.suggested_skills = sorted(
            entry.skill_slug
            for entry in aggregates
            if entry.skill_slug not in declared and entry.confidence >= 0.7
        )

        if not request.want_summary:
            return response
        if not self._model.configured:
            response.status = "partial"
            response.degraded_reason = "no model is configured on this environment"
            return response

        await self._add_generated_layer(request, repositories, findings, shares, aggregates, response)
        return response

    def _detect_repository(self, repo: RepositoryInput) -> list[detect.Finding]:
        findings: list[detect.Finding] = []
        for manifest in repo.manifests:
            content = manifest.content[: self._settings.max_manifest_chars]
            findings.extend(detect.detect(manifest.name, content))

        # The primary language is recorded as a weak, separately-sourced
        # signal so the matcher can tell a byte count from a manifest entry.
        if repo.primary_language:
            slug = _language_slug(repo.primary_language)
            if slug and not any(f.skill_slug == slug for f in findings):
                findings.append(
                    detect.Finding(
                        raw_name=repo.primary_language,
                        source="language-stats",
                        confidence=0.35,
                        skill_slug=slug,
                    )
                )
        return findings

    async def _add_generated_layer(
        self,
        request: AnalyseRequest,
        repositories: list[RepositoryInput],
        findings: list[RepositoryFinding],
        shares: list[tuple[str, int, float]],
        aggregates: list[detect.Aggregate],
        response: AnalyseResponse,
    ) -> None:
        """Adds the prose, leaving the deterministic findings intact on failure."""
        summary_task = self._technical_profile(request, repositories, shares, aggregates)
        purpose_task = self._repository_purposes(repositories, findings)

        summary_result, purpose_result = await asyncio.gather(
            summary_task, purpose_task, return_exceptions=True
        )

        if isinstance(summary_result, tuple):
            response.summary, response.summary_model = summary_result
            response.summary_generated = bool(response.summary)
        else:
            response.status = "partial"
            response.degraded_reason = _reason_of(summary_result)

        if isinstance(purpose_result, dict):
            by_id = {f.repository_id: f for f in response.findings}
            for repository_id, (purpose, category) in purpose_result.items():
                finding = by_id.get(repository_id)
                if finding is None:
                    continue
                finding.inferred_purpose = purpose
                finding.suggested_category = category

    async def _technical_profile(
        self,
        request: AnalyseRequest,
        repositories: list[RepositoryInput],
        shares: list[tuple[str, int, float]],
        aggregates: list[detect.Aggregate],
    ) -> tuple[str, str]:
        if not aggregates and not shares:
            # Nothing to summarise. Saying so is more useful than a sentence
            # padded out of nothing.
            return "", ""

        prompt = technical_profile_prompt(
            login=request.github_login,
            language_shares=shares,
            technologies=[(a.skill_slug, a.repositories, a.confidence) for a in aggregates],
            repositories=[
                (
                    repo.full_name,
                    repo.description,
                    _excerpt(repo.readme, self._settings.max_readme_chars // 8),
                )
                for repo in repositories
                if not repo.is_fork
            ],
            declared_specialisation=request.declared_specialisation,
        )
        completion = await self._model.complete(
            system=TECHNICAL_PROFILE_SYSTEM, prompt=prompt, max_tokens=400
        )
        return _clean_prose(completion.text), completion.model

    async def _repository_purposes(
        self, repositories: list[RepositoryInput], findings: list[RepositoryFinding]
    ) -> dict[str, tuple[str, str]]:
        """Infers what each candidate repository is for."""
        by_id = {f.repository_id: f for f in findings}
        candidates = [
            repo
            for repo in repositories
            if by_id.get(repo.repository_id, RepositoryFinding(repository_id="")).portfolio_candidate
        ][:_PURPOSE_BUDGET]

        if not candidates:
            return {}

        async def one(repo: RepositoryInput) -> tuple[str, tuple[str, str]]:
            finding = by_id[repo.repository_id]
            technologies = [t.skill_slug for t in finding.technologies if t.skill_slug]
            try:
                payload, _ = await self._model.complete_json(
                    system=REPOSITORY_PURPOSE_SYSTEM,
                    prompt=repository_purpose_prompt(
                        name=repo.full_name,
                        description=repo.description,
                        readme=_excerpt(repo.readme, 1500),
                        technologies=technologies,
                        categories=list(CATEGORY_SLUGS),
                    ),
                    max_tokens=200,
                )
            except ModelUnavailable:
                return repo.repository_id, ("", "")

            purpose = _clean_prose(str(payload.get("purpose", "")))[:280]
            category = str(payload.get("category", "")).strip()
            # A category the model invented is dropped rather than stored: the
            # taxonomy is closed, and a slug nobody can search for is worse
            # than none.
            if category not in CATEGORY_SLUGS:
                category = ""
            return repo.repository_id, (purpose, category)

        results = await asyncio.gather(*(one(repo) for repo in candidates), return_exceptions=True)
        out: dict[str, tuple[str, str]] = {}
        for result in results:
            if isinstance(result, tuple):
                out[result[0]] = result[1]
        return out


def _focus_areas(aggregates: list[detect.Aggregate]) -> list[str]:
    """The technologies the code most consistently shows.

    Breadth across repositories first, then confidence: something appearing in
    five repositories is a focus, while one high-confidence hit is a data
    point.
    """
    ranked = sorted(aggregates, key=lambda a: (-a.repositories, -a.confidence, a.skill_slug))
    return [entry.skill_slug for entry in ranked[:6] if entry.repositories >= 2]


def _excerpt(text: str, limit: int) -> str:
    cleaned = " ".join(text.split())
    if len(cleaned) <= limit:
        return cleaned
    cut = cleaned[:limit]
    if " " in cut:
        cut = cut[: cut.rfind(" ")]
    return cut + "…"


def _clean_prose(text: str) -> str:
    """Strips the packaging a model sometimes adds around prose."""
    cleaned = text.strip()
    for fence in ("```", "~~~"):
        if cleaned.startswith(fence):
            cleaned = cleaned.split("\n", 1)[-1]
            cleaned = cleaned.rsplit(fence, 1)[0]
    cleaned = cleaned.strip().strip('"').strip()
    # A leading label ("Summary:") is noise in a profile.
    for prefix in ("Summary:", "Technical summary:", "Profile:"):
        if cleaned.lower().startswith(prefix.lower()):
            cleaned = cleaned[len(prefix) :].strip()
    return cleaned


def _reason_of(error: object) -> str:
    if isinstance(error, ModelUnavailable):
        return str(error)
    if isinstance(error, BaseException):
        log.warning("analysis generative layer failed", error=str(error))
        return "the summary could not be generated"
    return ""


def _language_slug(language: str) -> str:
    """Maps a GitHub language name onto a taxonomy slug."""
    direct = {
        "Go": "go",
        "Python": "python",
        "TypeScript": "typescript",
        "JavaScript": "javascript",
        "PHP": "php",
        "Java": "java",
        "Kotlin": "kotlin",
        "Swift": "swift",
        "Rust": "rust",
        "C#": "csharp",
        "Ruby": "ruby",
        "Dart": "dart",
        "Shell": "bash",
        "Shell Script": "bash",
        "PLpgSQL": "sql",
        "TSQL": "sql",
        "SQL": "sql",
        "Dockerfile": "docker",
        "HCL": "terraform",
        "Svelte": "svelte",
        "Vue": "vue",
    }
    if language in direct:
        return direct[language]
    lowered = language.lower().replace(" ", "-").replace("_", "-")
    return lowered if lowered in SKILL_SLUGS else ""
