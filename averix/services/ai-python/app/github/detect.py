"""Deterministic technology detection from dependency manifests.

The distinction this module exists to make: a language byte count says what
files are in a repository, while a manifest entry says what the code actually
depends on. A `go.mod` line naming Gin is evidence the developer has written a
Gin service; 90% Go in a repository of exercises is not.

No model is involved. Detection has to be reproducible, explainable and free,
because it runs over every repository of every developer and its output
becomes evidence attached to a profile. The model's job starts afterwards,
with the prose.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

# Manifests worth reading, each with a parser below.
MANIFESTS: tuple[str, ...] = (
    "go.mod",
    "requirements.txt",
    "pyproject.toml",
    "Pipfile",
    "package.json",
    "composer.json",
    "Dockerfile",
    "docker-compose.yml",
    "docker-compose.yaml",
    "Cargo.toml",
    "pom.xml",
    "build.gradle",
    "build.gradle.kts",
    "Gemfile",
    "pubspec.yaml",
    "Package.swift",
)


@dataclass(slots=True)
class Finding:
    raw_name: str
    source: str
    confidence: float
    skill_slug: str = ""
    version_spec: str = ""


@dataclass(slots=True)
class Aggregate:
    """One technology across an account."""

    skill_slug: str
    repositories: int = 0
    confidence: float = 0.0
    sources: set[str] = field(default_factory=set)


# The dependency map, the container base images and the composed services all
# come from database/reference/dependency-map.json, shipped alongside this
# module. The Go service reads the same file: a second hand-maintained copy
# would drift, and detection that differed depending on which service answered
# would change a developer's evidence without their profile changing.
_REFERENCE_PATH = Path(__file__).parent / "reference" / "dependency-map.json"


@dataclass(slots=True, frozen=True)
class _Rule:
    match: str
    skill: str
    confidence: float


@dataclass(slots=True, frozen=True)
class _PrefixRule:
    prefix: str
    skill: str


def _load_reference() -> tuple[tuple[_Rule, ...], tuple[_PrefixRule, ...], tuple[_PrefixRule, ...], tuple[str, ...]]:
    """Loads the canonical map.

    A missing or malformed file is fatal at import: failing to start is better
    than silently detecting nothing all day.
    """
    raw = json.loads(_REFERENCE_PATH.read_text(encoding="utf-8"))

    dependencies = tuple(
        _Rule(match=entry["match"], skill=entry["skill"], confidence=float(entry["confidence"]))
        for entry in raw["dependencies"]
    )
    if not dependencies:
        raise RuntimeError(f"{_REFERENCE_PATH} contains no dependency rules")

    base_images = tuple(
        _PrefixRule(prefix=entry["prefix"], skill=entry["skill"]) for entry in raw["base_images"]
    )
    compose_services = tuple(
        _PrefixRule(prefix=entry["prefix"], skill=entry["skill"])
        for entry in raw["compose_services"]
    )
    separators = tuple(raw.get("separators") or ("/", "@", "-", ":", "."))
    return dependencies, base_images, compose_services, separators


_DEPENDENCY_RULES, _BASE_IMAGES, _COMPOSE_SERVICES, _SEPARATORS = _load_reference()


def resolve(raw: str) -> tuple[str, float]:
    """Maps a raw dependency name onto a taxonomy slug."""
    name = raw.strip().lower()
    if not name:
        return "", 0.0

    best_slug, best_confidence, best_length = "", 0.0, 0
    for rule in _DEPENDENCY_RULES:
        if name != rule.match and not any(
            name.startswith(rule.match + sep) for sep in _SEPARATORS
        ):
            continue
        # The most specific match wins: react-native must not resolve to react
        # merely because react appears in the table.
        if len(rule.match) > best_length:
            best_slug, best_confidence, best_length = rule.skill, rule.confidence, len(rule.match)
    return best_slug, best_confidence


def _finding(source: str, raw: str, version: str = "") -> Finding:
    slug, confidence = resolve(raw)
    if not slug:
        # Recorded without a skill link: useful for widening the map later, and
        # it never becomes a technology tag on anyone's profile.
        return Finding(raw_name=raw, source=source, confidence=0.1, version_spec=version)
    return Finding(
        raw_name=raw, source=source, confidence=confidence, skill_slug=slug, version_spec=version
    )


_GO_REQUIRE = re.compile(r"(?m)^\s*(?:require\s+)?([\w./~-]+\.[\w./~-]+)\s+v([\w.\-+]+)")
_REQUIREMENT = re.compile(r"^([A-Za-z0-9._-]+)\s*(?:\[[^\]]*\])?\s*([=<>!~]=?[^;#]*)?")
_TOML_DEP = re.compile(r'(?m)^\s*"?([A-Za-z0-9._-]+)"?\s*=\s*["{]')
_DOCKER_FROM = re.compile(r"(?mi)^\s*FROM\s+([\w./:-]+)")
_COMPOSE_IMAGE = re.compile(r"""(?mi)^\s*image:\s*["']?([\w./:-]+)""")
_POM_ARTIFACT = re.compile(r"(?s)<groupId>([^<]+)</groupId>\s*<artifactId>([^<]+)</artifactId>")
_GRADLE_DEP = re.compile(r"""(?m)(?:implementation|api|compile)\s*[( ]\s*["']([^"']+)["']""")
_GEM = re.compile(r"""(?m)^\s*gem\s+["']([^"']+)["']""")


def detect(filename: str, content: str) -> list[Finding]:
    """Parses one manifest and returns what it proves."""
    if not content.strip():
        return []
    parser = _PARSERS.get(filename)
    if parser is None:
        return []
    try:
        return parser(content)
    except (ValueError, TypeError, json.JSONDecodeError):
        # A malformed manifest is common in real repositories and is not worth
        # failing an analysis over.
        return []


def _go_mod(content: str) -> list[Finding]:
    # A go.mod is proof of Go itself, which a byte count only suggests.
    out = [Finding(raw_name="go.mod", source="go.mod", confidence=1.0, skill_slug="go")]
    out.extend(
        _finding("go.mod", m.group(1), "v" + m.group(2)) for m in _GO_REQUIRE.finditer(content)
    )
    return out


def _requirements(content: str, source: str = "requirements.txt") -> list[Finding]:
    out = [Finding(raw_name=source, source=source, confidence=1.0, skill_slug="python")]
    for raw_line in content.splitlines():
        line = raw_line.strip()
        if not line or line.startswith(("#", "-")):
            continue
        match = _REQUIREMENT.match(line)
        if not match or not match.group(1):
            continue
        out.append(_finding(source, match.group(1), (match.group(2) or "").strip()))
    return out


def _pyproject(content: str) -> list[Finding]:
    out = [
        Finding(raw_name="pyproject.toml", source="pyproject.toml", confidence=1.0, skill_slug="python")
    ]

    # PEP 621: dependencies = ["fastapi>=0.100", ...]
    start = content.find("dependencies")
    if start >= 0:
        section = content[start:]
        end = section.find("]")
        if end > 0:
            for raw in section[:end].split(","):
                name = re.split(r"[<>=!~\[]", raw.strip().strip("\"'[]"))[0].strip()
                if name and name != "dependencies":
                    out.append(_finding("pyproject.toml", name))

    # Poetry: [tool.poetry.dependencies] followed by name = "^1.0"
    marker = "[tool.poetry.dependencies]"
    start = content.find(marker)
    if start >= 0:
        section = content[start + len(marker) :]
        end = section.find("\n[")
        if end > 0:
            section = section[:end]
        for match in _TOML_DEP.finditer(section):
            if match.group(1) != "python":
                out.append(_finding("pyproject.toml", match.group(1)))
    return out


def _pipfile(content: str) -> list[Finding]:
    out = [Finding(raw_name="Pipfile", source="requirements.txt", confidence=1.0, skill_slug="python")]
    start = content.find("[packages]")
    if start >= 0:
        section = content[start + len("[packages]") :]
        end = section.find("\n[")
        if end > 0:
            section = section[:end]
        out.extend(_finding("requirements.txt", m.group(1)) for m in _TOML_DEP.finditer(section))
    return out


def _package_json(content: str) -> list[Finding]:
    package = json.loads(content)
    if not isinstance(package, dict):
        return []

    out = [
        Finding(raw_name="package.json", source="package.json", confidence=0.8, skill_slug="javascript")
    ]
    for name, version in (package.get("dependencies") or {}).items():
        out.append(_finding("package.json", str(name), str(version)))
    # Dev dependencies say less about what the project is, but typescript and
    # the test runners live there and are worth knowing.
    for name, version in (package.get("devDependencies") or {}).items():
        finding = _finding("package.json", str(name), str(version))
        finding.confidence *= 0.8
        out.append(finding)
    return out


def _composer(content: str) -> list[Finding]:
    package = json.loads(content)
    if not isinstance(package, dict):
        return []

    out = [Finding(raw_name="composer.json", source="composer.json", confidence=1.0, skill_slug="php")]
    for name, version in (package.get("require") or {}).items():
        if name == "php":
            continue
        out.append(_finding("composer.json", str(name), str(version)))
    for name, version in (package.get("require-dev") or {}).items():
        finding = _finding("composer.json", str(name), str(version))
        finding.confidence *= 0.8
        out.append(finding)
    return out


def _dockerfile(content: str) -> list[Finding]:
    out = [Finding(raw_name="Dockerfile", source="Dockerfile", confidence=1.0, skill_slug="docker")]
    for match in _DOCKER_FROM.finditer(content):
        image = match.group(1).lower()
        for rule in _BASE_IMAGES:
            if image.startswith(rule.prefix):
                out.append(
                    Finding(
                        raw_name=match.group(1),
                        source="Dockerfile",
                        confidence=0.75,
                        skill_slug=rule.skill,
                    )
                )
                break
    return out


def _compose(content: str) -> list[Finding]:
    out = [
        Finding(
            raw_name="docker-compose.yml",
            source="docker-compose.yml",
            confidence=1.0,
            skill_slug="docker",
        )
    ]
    for match in _COMPOSE_IMAGE.finditer(content):
        image = match.group(1).lower()
        for rule in _COMPOSE_SERVICES:
            if image.startswith(rule.prefix):
                out.append(
                    Finding(
                        raw_name=match.group(1),
                        source="docker-compose.yml",
                        confidence=0.85,
                        skill_slug=rule.skill,
                    )
                )
                break
    return out


def _cargo(content: str) -> list[Finding]:
    out = [Finding(raw_name="Cargo.toml", source="Cargo.toml", confidence=1.0, skill_slug="rust")]
    start = content.find("[dependencies]")
    if start >= 0:
        section = content[start + len("[dependencies]") :]
        end = section.find("\n[")
        if end > 0:
            section = section[:end]
        out.extend(_finding("Cargo.toml", m.group(1)) for m in _TOML_DEP.finditer(section))
    return out


def _pom(content: str) -> list[Finding]:
    out = [Finding(raw_name="pom.xml", source="pom.xml", confidence=1.0, skill_slug="java")]
    for match in _POM_ARTIFACT.finditer(content):
        group, artifact = match.group(1).strip(), match.group(2).strip()
        finding = _finding("pom.xml", group)
        finding.raw_name = f"{group}:{artifact}"
        out.append(finding)
    return out


def _gradle(content: str) -> list[Finding]:
    out = [Finding(raw_name="build.gradle", source="build.gradle", confidence=0.8, skill_slug="java")]
    if "kotlin(" in content or "org.jetbrains.kotlin" in content:
        out.append(
            Finding(raw_name="kotlin", source="build.gradle", confidence=0.9, skill_slug="kotlin")
        )
    out.extend(_finding("build.gradle", m.group(1)) for m in _GRADLE_DEP.finditer(content))
    return out


def _gemfile(content: str) -> list[Finding]:
    out = [Finding(raw_name="Gemfile", source="Gemfile", confidence=1.0, skill_slug="ruby")]
    out.extend(_finding("Gemfile", m.group(1)) for m in _GEM.finditer(content))
    return out


def _pubspec(content: str) -> list[Finding]:
    out = [Finding(raw_name="pubspec.yaml", source="pubspec.yaml", confidence=1.0, skill_slug="dart")]
    if "flutter:" in content or "sdk: flutter" in content:
        out.append(
            Finding(raw_name="flutter", source="pubspec.yaml", confidence=0.95, skill_slug="flutter")
        )
    return out


def _swift_package(content: str) -> list[Finding]:
    return [
        Finding(raw_name="Package.swift", source="Package.swift", confidence=1.0, skill_slug="swift")
    ]


_PARSERS = {
    "go.mod": _go_mod,
    "requirements.txt": _requirements,
    "pyproject.toml": _pyproject,
    "Pipfile": _pipfile,
    "package.json": _package_json,
    "composer.json": _composer,
    "Dockerfile": _dockerfile,
    "docker-compose.yml": _compose,
    "docker-compose.yaml": _compose,
    "Cargo.toml": _cargo,
    "pom.xml": _pom,
    "build.gradle": _gradle,
    "build.gradle.kts": _gradle,
    "Gemfile": _gemfile,
    "pubspec.yaml": _pubspec,
    "Package.swift": _swift_package,
}


def language_shares(totals: dict[str, int], top_n: int = 6) -> list[tuple[str, int, float]]:
    """Turns byte counts into shares.

    Returns shares only. There is deliberately no competence field: the
    product must never present 97% Go code as "Go knowledge 97%", and a
    function that cannot express a rating cannot be misused into one.
    """
    total = sum(v for v in totals.values() if v > 0)
    if total <= 0:
        return []

    ordered = sorted(
        ((lang, count) for lang, count in totals.items() if count > 0),
        # Name as the tiebreaker, so equal counts order the same way every run
        # and a profile does not reshuffle between analyses.
        key=lambda item: (-item[1], item[0]),
    )

    if top_n > 0 and len(ordered) > top_n:
        head = ordered[:top_n]
        tail_bytes = sum(count for _, count in ordered[top_n:])
        # The tail is collapsed rather than dropped, so the shares still add
        # to 100%.
        head.append(("Other", tail_bytes))
        ordered = head

    return [(lang, count, count / total) for lang, count in ordered]


def aggregate(per_repository: list[list[Finding]]) -> list[Aggregate]:
    """Combines per-repository findings across an account."""
    totals: dict[str, Aggregate] = {}

    for findings in per_repository:
        seen_here: set[str] = set()
        for found in findings:
            if not found.skill_slug:
                continue
            entry = totals.setdefault(found.skill_slug, Aggregate(skill_slug=found.skill_slug))
            if found.skill_slug not in seen_here:
                entry.repositories += 1
                seen_here.add(found.skill_slug)
            entry.confidence = max(entry.confidence, found.confidence)
            entry.sources.add(found.source)

    out: list[Aggregate] = []
    for entry in totals.values():
        # Appearing across several repositories is stronger evidence than one
        # high-confidence hit, so the two are combined.
        breadth = min(entry.repositories, 4) / 4
        entry.confidence = min(entry.confidence * 0.7 + breadth * 0.3, 1.0)
        out.append(entry)

    out.sort(key=lambda e: (-e.confidence, -e.repositories, e.skill_slug))
    return out


def portfolio_worthiness(
    *,
    is_fork: bool,
    is_private: bool,
    is_archived: bool,
    size_kb: int,
    description: str,
    has_readme: bool,
    detected_count: int,
    stars: int,
    homepage: str,
    topic_count: int,
) -> tuple[bool, str]:
    """Judges whether a repository is worth offering as portfolio work.

    The bar is "would a client learn something from this". Stars are a weak
    input: a useful internal tool has none, and a joke repository can have
    thousands.
    """
    if is_fork:
        return False, "a fork rather than the developer's own work"
    if is_private:
        return False, "private"
    if is_archived:
        return False, "archived"
    if size_kb < 40:
        return False, "too small to show anything"

    score = 0
    reasons: list[str] = []
    if description.strip():
        score += 2
        reasons.append("described")
    if has_readme:
        score += 2
        reasons.append("has a README")
    if detected_count >= 3:
        score += 2
        reasons.append("a real dependency set")
    if homepage.strip():
        score += 2
        reasons.append("has a live URL")
    if stars >= 3:
        score += 1
        reasons.append("has stars")
    if topic_count > 0:
        score += 1
    if size_kb > 500:
        score += 1
        reasons.append("substantial")

    if score < 4:
        return False, "not enough to show a client yet"
    return True, ", ".join(reasons)
