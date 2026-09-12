"""The copies of the reference data must not drift.

/database is the source of truth. The Go binary embeds its copy so a
deployment is a single artefact, and this image carries its copy for the same
reason. `make sync-reference` copies one to the other; this test is what stops
them from diverging unnoticed — which would make technology detection depend
on which service happened to answer.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

SERVICE_ROOT = Path(__file__).resolve().parent.parent
LOCAL_MAP = SERVICE_ROOT / "app/github/reference/dependency-map.json"
CANONICAL_MAP = SERVICE_ROOT / "../../database/reference/dependency-map.json"
CANONICAL_TAXONOMY = SERVICE_ROOT / "../../database/migrations/0016_reference_data.up.sql"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_local_dependency_map_matches_the_canonical_one() -> None:
    if not CANONICAL_MAP.exists():
        pytest.skip("the canonical reference directory is not reachable from here")
    assert digest(LOCAL_MAP) == digest(CANONICAL_MAP), (
        "app/github/reference/dependency-map.json has drifted from "
        "database/reference/dependency-map.json; run `make sync-reference`"
    )


def test_dependency_map_is_well_formed() -> None:
    raw = json.loads(LOCAL_MAP.read_text(encoding="utf-8"))

    assert len(raw["dependencies"]) >= 80
    seen: set[str] = set()
    for entry in raw["dependencies"]:
        assert entry["match"], "a rule with no match string would match nothing"
        assert entry["skill"], "a rule with no skill would detect nothing"
        assert 0 < float(entry["confidence"]) <= 1.0
        assert entry["match"] not in seen, f"{entry['match']} appears twice"
        seen.add(entry["match"])

    for group in ("base_images", "compose_services"):
        for entry in raw[group]:
            assert entry["prefix"] and entry["skill"]


def test_every_mapped_skill_exists_in_the_taxonomy() -> None:
    """A rule pointing at a slug the database does not have detects nothing.

    This is the failure that would be invisible in production: the analysis
    would run, find the dependency, and store a row whose skill_id resolved to
    NULL — evidence that silently never reaches a profile.
    """
    from app.taxonomy import SKILL_SLUGS

    raw = json.loads(LOCAL_MAP.read_text(encoding="utf-8"))
    referenced = {entry["skill"] for entry in raw["dependencies"]}
    referenced |= {entry["skill"] for entry in raw["base_images"]}
    referenced |= {entry["skill"] for entry in raw["compose_services"]}

    unknown = sorted(referenced - SKILL_SLUGS)
    assert not unknown, (
        f"the dependency map points at technologies the taxonomy does not contain: {unknown}"
    )


def test_taxonomy_is_generated_from_the_migration() -> None:
    if not CANONICAL_TAXONOMY.exists():
        pytest.skip("the canonical migration is not reachable from here")

    from app.taxonomy import CATEGORY_SLUGS, SKILL_SLUGS, SPECIALISATION_SLUGS

    sql = CANONICAL_TAXONOMY.read_text(encoding="utf-8")
    # A handful of spot checks rather than reparsing the migration: the
    # generator already does that, and this catches a stale generated file.
    for slug in ("backend-developer", "telegram-developer", "ui-ux-designer"):
        assert slug in SPECIALISATION_SLUGS
        assert f"'{slug}'" in sql
    for slug in ("telegram-bots", "backend-development", "saas", "backend-go"):
        assert slug in CATEGORY_SLUGS, f"{slug} is missing from the generated taxonomy"
    for slug in ("go", "python", "telegram-api", "postgresql", "nextjs"):
        assert slug in SKILL_SLUGS

    assert len(SPECIALISATION_SLUGS) == 8
    assert len(CATEGORY_SLUGS) >= 55
    assert len(SKILL_SLUGS) >= 85
