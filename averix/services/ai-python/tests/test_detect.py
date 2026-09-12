"""Detection is deterministic, explainable and cheap, and these tests hold it
to all three."""

from __future__ import annotations

import json

from app.github import detect


def slugs(findings: list[detect.Finding]) -> dict[str, float]:
    out: dict[str, float] = {}
    for found in findings:
        if found.skill_slug:
            out[found.skill_slug] = max(out.get(found.skill_slug, 0.0), found.confidence)
    return out


def test_go_mod_proves_go_and_its_dependencies() -> None:
    content = """module github.com/example/service

go 1.25.0

require (
	github.com/gin-gonic/gin v1.10.0
	github.com/jackc/pgx/v5 v5.11.0
	github.com/redis/go-redis/v9 v9.22.0
	github.com/go-telegram-bot-api/telegram-bot-api/v5 v5.5.1
	github.com/example/never-heard-of-it v0.1.0
)"""
    found = slugs(detect.detect("go.mod", content))

    assert found["go"] == 1.0
    assert found["gin"] >= 0.9
    assert found["postgresql"] >= 0.85
    assert found["redis"] >= 0.85
    assert found["telegram-api"] >= 0.9

    # An unrecognised dependency is recorded but never becomes a skill.
    unknown = [f for f in detect.detect("go.mod", content) if "never-heard-of-it" in f.raw_name]
    assert unknown, "an unrecognised dependency should still be recorded"
    assert unknown[0].skill_slug == ""


def test_python_manifests() -> None:
    requirements = "\n".join(
        [
            "# production",
            "fastapi==0.115.0",
            "uvicorn[standard]>=0.30",
            "asyncpg~=0.29",
            "aiogram==3.13.1",
            "anthropic==0.40.0",
            "-r dev-requirements.txt",
        ]
    )
    found = slugs(detect.detect("requirements.txt", requirements))
    for slug in ("python", "fastapi", "postgresql", "aiogram", "anthropic-api"):
        assert slug in found, f"requirements.txt did not detect {slug}"

    poetry = """[tool.poetry.dependencies]
python = "^3.12"
django = "^5.0"
psycopg2-binary = "^2.9"
celery = "^5.4"
"""
    found = slugs(detect.detect("pyproject.toml", poetry))
    for slug in ("python", "django", "postgresql", "celery"):
        assert slug in found, f"pyproject.toml did not detect {slug}"


def test_package_json_weighs_dev_dependencies_lower() -> None:
    content = json.dumps(
        {
            "dependencies": {
                "next": "15.0.0",
                "react": "19.0.0",
                "@telegram-apps/sdk": "^2.0.0",
                "stripe": "^16.0.0",
            },
            "devDependencies": {"typescript": "^5.6.0", "@playwright/test": "^1.48.0"},
        }
    )
    found = slugs(detect.detect("package.json", content))
    for slug in ("nextjs", "react", "telegram-mini-apps", "stripe", "typescript", "testing"):
        assert slug in found, f"package.json did not detect {slug}"
    assert found["typescript"] < found["nextjs"], (
        "a dev dependency should count for less than a production one"
    )


def test_most_specific_dependency_wins() -> None:
    """react-native must not resolve to react."""
    findings = detect.detect("package.json", json.dumps({
        "dependencies": {"react-native": "0.76.0", "react": "18.3.1"}
    }))
    by_raw = {f.raw_name: f.skill_slug for f in findings}
    assert by_raw["react-native"] == "react-native"
    assert by_raw["react"] == "react"


def test_infrastructure_manifests() -> None:
    dockerfile = "FROM golang:1.25-alpine AS build\nRUN go build ./...\nFROM alpine:3.20\n"
    found = slugs(detect.detect("Dockerfile", dockerfile))
    assert found["docker"] == 1.0
    assert "go" in found

    compose = """services:
  db:
    image: postgres:16-alpine
  cache:
    image: redis:7-alpine
  proxy:
    image: nginx:1.27
"""
    found = slugs(detect.detect("docker-compose.yml", compose))
    for slug in ("docker", "postgresql", "redis", "nginx"):
        assert slug in found, f"docker-compose.yml did not detect {slug}"


def test_malformed_manifests_produce_nothing() -> None:
    for filename, content in [
        ("package.json", "not json"),
        ("package.json", "{{{"),
        ("go.mod", ""),
        ("composer.json", "[]"),
        ("unknown-file.txt", "fastapi==1.0"),
    ]:
        # No exception, and no invented technologies.
        findings = detect.detect(filename, content)
        assert all(not f.skill_slug or filename != "unknown-file.txt" for f in findings)


def test_language_shares_report_code_only() -> None:
    """The specification forbids turning code share into a competence rating.

    LanguageShares returns shares and byte counts, with no field a rating
    could be put in — a function that cannot express one cannot be misused
    into expressing one.
    """
    totals = {
        "Go": 390_000,
        "Python": 310_000,
        "TypeScript": 180_000,
        "Shell": 60_000,
        "Dockerfile": 30_000,
        "HTML": 20_000,
        "CSS": 10_000,
    }
    shares = detect.language_shares(totals, top_n=3)

    assert len(shares) == 4, "the top three plus a collapsed Other"
    assert [lang for lang, _, _ in shares[:3]] == ["Go", "Python", "TypeScript"]
    assert shares[3][0] == "Other"

    # Collapsing the tail must not lose any share.
    assert abs(sum(share for _, _, share in shares) - 1.0) < 0.001
    assert 0.38 < shares[0][2] < 0.40
    assert shares[0][1] == 390_000, "the raw byte count is preserved"


def test_language_shares_are_stable_for_equal_counts() -> None:
    totals = {"Go": 1000, "Rust": 1000, "Python": 1000}
    first = detect.language_shares(totals)
    for _ in range(20):
        assert detect.language_shares(totals) == first, "ordering must be deterministic"


def test_language_shares_handle_empty_input() -> None:
    assert detect.language_shares({}) == []
    assert detect.language_shares({"Go": 0}) == []


def test_aggregate_rewards_breadth_across_repositories() -> None:
    one = [[detect.Finding(raw_name="go.mod", source="go.mod", confidence=1.0, skill_slug="go")]]
    four = [
        [detect.Finding(raw_name="r", source="requirements.txt", confidence=0.9, skill_slug="python")],
        [detect.Finding(raw_name="p", source="pyproject.toml", confidence=0.9, skill_slug="python")],
        [detect.Finding(raw_name="d", source="Dockerfile", confidence=0.7, skill_slug="python")],
        [detect.Finding(raw_name="r", source="requirements.txt", confidence=0.9, skill_slug="python")],
    ]

    single = detect.aggregate(one)
    across = detect.aggregate(four)

    assert single[0].repositories == 1
    assert across[0].repositories == 4
    assert across[0].confidence >= 0.85, "four repositories is strong evidence"
    assert across[0].sources == {"requirements.txt", "pyproject.toml", "Dockerfile"}


def test_aggregate_orders_by_strength() -> None:
    per_repo = [
        [
            detect.Finding(raw_name="a", source="go.mod", confidence=1.0, skill_slug="go"),
            detect.Finding(raw_name="b", source="go.mod", confidence=0.9, skill_slug="redis"),
            detect.Finding(raw_name="c", source="go.mod", confidence=0.5, skill_slug="testing"),
        ],
        [
            detect.Finding(raw_name="a", source="go.mod", confidence=1.0, skill_slug="go"),
            detect.Finding(raw_name="b", source="docker-compose.yml", confidence=0.85, skill_slug="redis"),
        ],
    ]
    out = detect.aggregate(per_repo)
    assert out[0].skill_slug == "go"
    assert out[-1].skill_slug == "testing"
    assert all(out[i - 1].confidence >= out[i].confidence for i in range(1, len(out)))


def test_portfolio_worthiness() -> None:
    ok, reason = detect.portfolio_worthiness(
        is_fork=False, is_private=False, is_archived=False, size_kb=1800,
        description="Backend for a marketplace, Go and PostgreSQL.",
        has_readme=True, detected_count=8, stars=12,
        homepage="https://demo.example.com", topic_count=2,
    )
    assert ok and reason

    rejected = [
        dict(is_fork=True, is_private=False, is_archived=False, size_kb=5000,
             description="d", has_readme=True, detected_count=9, stars=100,
             homepage="https://x.example", topic_count=3),
        dict(is_fork=False, is_private=True, is_archived=False, size_kb=5000,
             description="d", has_readme=True, detected_count=9, stars=0,
             homepage="", topic_count=0),
        dict(is_fork=False, is_private=False, is_archived=True, size_kb=5000,
             description="d", has_readme=True, detected_count=9, stars=0,
             homepage="https://x.example", topic_count=0),
        dict(is_fork=False, is_private=False, is_archived=False, size_kb=4,
             description="d", has_readme=True, detected_count=9, stars=0,
             homepage="", topic_count=0),
        dict(is_fork=False, is_private=False, is_archived=False, size_kb=200,
             description="", has_readme=False, detected_count=0, stars=0,
             homepage="", topic_count=0),
    ]
    for case in rejected:
        assert not detect.portfolio_worthiness(**case)[0]

    # A useful internal tool with no stars still qualifies on substance.
    unstarred, _ = detect.portfolio_worthiness(
        is_fork=False, is_private=False, is_archived=False, size_kb=900,
        description="Zero-downtime deploys for our services.",
        has_readme=True, detected_count=5, stars=0, homepage="", topic_count=0,
    )
    assert unstarred
