"""Request and response shapes for GitHub repository analysis.

The Go API fetches from GitHub — it holds the encrypted OAuth token, and
handing that token to a second service would widen the blast radius of a
compromise for no benefit. What arrives here is the already-fetched material:
manifests, language byte counts and READMEs. This service decides what it
means.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class ManifestFile(BaseModel):
    """One dependency manifest, as fetched."""

    name: str = Field(max_length=120)
    content: str = Field(max_length=200_000)


class RepositoryInput(BaseModel):
    """A repository to analyse."""

    repository_id: str
    name: str = Field(max_length=200)
    full_name: str = Field(max_length=400)
    description: str = Field(default="", max_length=2_000)
    homepage: str = Field(default="", max_length=500)
    topics: list[str] = Field(default_factory=list, max_length=40)
    primary_language: str = Field(default="", max_length=80)
    # Byte counts straight from GitHub's languages endpoint. Reported as code
    # share and never converted into a competence rating.
    languages: dict[str, int] = Field(default_factory=dict)
    stars: int = 0
    forks: int = 0
    size_kb: int = 0
    is_fork: bool = False
    is_private: bool = False
    is_archived: bool = False
    pushed_at: datetime | None = None
    readme: str = Field(default="", max_length=40_000)
    manifests: list[ManifestFile] = Field(default_factory=list, max_length=24)

    @field_validator("topics")
    @classmethod
    def _trim_topics(cls, value: list[str]) -> list[str]:
        return [t.strip()[:60] for t in value if t.strip()][:40]


class AnalyseRequest(BaseModel):
    """A whole account's worth of repositories."""

    # Correlates this analysis with the row the Go service created, so a
    # failure here can be traced to a specific run.
    analysis_id: str
    github_login: str = Field(max_length=120)
    repositories: list[RepositoryInput] = Field(default_factory=list, max_length=200)
    # The technologies the developer declared. The summary is written about
    # their code, but knowing what they claim lets the analysis report
    # corroboration and gaps rather than guessing at intent.
    declared_skills: list[str] = Field(default_factory=list, max_length=40)
    declared_specialisation: str = Field(default="", max_length=80)
    # When false, the prose summary is skipped and only the deterministic
    # findings are returned.
    want_summary: bool = True


class DetectedTechnology(BaseModel):
    """A technology found in a manifest, with where and how strongly."""

    # The AVERIX taxonomy slug, or empty when the dependency is not one we
    # know. An unknown dependency is recorded, never invented into a skill.
    skill_slug: str = ""
    raw_name: str
    source: str
    confidence: float = Field(ge=0.0, le=1.0)
    version_spec: str = ""


class RepositoryFinding(BaseModel):
    """What the analysis concluded about one repository."""

    repository_id: str
    technologies: list[DetectedTechnology] = Field(default_factory=list)
    # A one-line description of what the repository is, drawn from its README
    # and dependencies. Labelled as generated wherever it is shown.
    inferred_purpose: str = ""
    # The AVERIX category this repository most resembles, for the portfolio
    # suggestion flow.
    suggested_category: str = ""
    portfolio_candidate: bool = False
    candidate_reason: str = ""
    readme_excerpt: str = ""


class LanguageShare(BaseModel):
    """Code share by language.

    Named "share" throughout, with no competence field to fill in, because the
    product must never present 97% Go code as "Go knowledge 97%".
    """

    language: str
    bytes: int
    share: float = Field(ge=0.0, le=1.0)


class TechnologySummary(BaseModel):
    skill_slug: str
    repositories: int
    confidence: float = Field(ge=0.0, le=1.0)
    sources: list[str] = Field(default_factory=list)


class AnalyseResponse(BaseModel):
    analysis_id: str
    # "succeeded" when everything ran, "partial" when the prose summary was
    # skipped or a repository could not be read.
    status: str
    repositories_seen: int
    repositories_analysed: int
    language_shares: list[LanguageShare] = Field(default_factory=list)
    technologies: list[TechnologySummary] = Field(default_factory=list)
    findings: list[RepositoryFinding] = Field(default_factory=list)

    # The prose technical profile. Always accompanied by the two fields below
    # so the interface can label it honestly; the API contract makes it
    # impossible to display the text without knowing it was generated.
    summary: str = ""
    summary_model: str = ""
    summary_generated: bool = False
    # What the code suggests the developer concentrates on, as taxonomy slugs.
    focus_areas: list[str] = Field(default_factory=list)
    # Declared technologies the code corroborates, and ones it does not.
    corroborated_skills: list[str] = Field(default_factory=list)
    unsupported_skills: list[str] = Field(default_factory=list)
    # Technologies in the code that the developer has not claimed, offered as
    # a suggestion rather than added to their profile.
    suggested_skills: list[str] = Field(default_factory=list)
    # Set when the model was unavailable, so the caller can show a
    # configuration state rather than a silent absence.
    degraded_reason: str = ""
