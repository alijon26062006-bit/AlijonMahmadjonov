package githubint

import (
	_ "embed"
	"encoding/json"
	"regexp"
	"strings"
)

// Manifest detection.
//
// The distinction this file exists to make: a language byte count says what
// files are in a repository, while a manifest entry says what the code
// actually depends on. A go.mod line naming gin is evidence that the developer
// has written a Gin service; 90% Go in a repository of exercises is not.
//
// Everything here maps onto the taxonomy's slugs, so an unrecognised
// dependency is recorded with no skill link rather than inventing a
// technology nobody can search for.

// Manifests are the files worth fetching, in the order they are most
// informative. The list is closed: each entry has a parser below.
var Manifests = []string{
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
}

// Finding is one technology detected in one manifest.
type Finding struct {
	SkillSlug   string
	RawName     string
	Source      string
	Confidence  float64
	VersionSpec string
}

// Detect parses a manifest and returns what it proves.
func Detect(filename, content string) []Finding {
	if strings.TrimSpace(content) == "" {
		return nil
	}
	switch filename {
	case "go.mod":
		return detectGoMod(content)
	case "requirements.txt":
		return detectRequirements(content)
	case "pyproject.toml":
		return detectPyProject(content)
	case "Pipfile":
		return detectPipfile(content)
	case "package.json":
		return detectPackageJSON(content)
	case "composer.json":
		return detectComposer(content)
	case "Dockerfile":
		return detectDockerfile(content)
	case "docker-compose.yml", "docker-compose.yaml":
		return detectCompose(content)
	case "Cargo.toml":
		return detectCargo(content)
	case "pom.xml":
		return detectPom(content)
	case "build.gradle", "build.gradle.kts":
		return detectGradle(content)
	case "Gemfile":
		return detectGemfile(content)
	case "pubspec.yaml":
		return detectPubspec(content)
	case "Package.swift":
		return detectSwiftPackage(content)
	}
	return nil
}

// The dependency map, the container base images and the composed services all
// come from database/reference/dependency-map.json, embedded at build time.
//
// Both this service and the Python analysis service read the same file. A
// second hand-maintained copy would drift, and detection that differed
// depending on which service answered would change a developer's evidence
// without their profile changing.
//
//go:embed reference/dependency-map.json
var dependencyMapJSON []byte

type dependencyRule struct {
	Match      string  `json:"match"`
	Skill      string  `json:"skill"`
	Confidence float64 `json:"confidence"`
}

type prefixRule struct {
	Prefix string `json:"prefix"`
	Skill  string `json:"skill"`
}

type referenceData struct {
	Dependencies    []dependencyRule `json:"dependencies"`
	BaseImages      []prefixRule     `json:"base_images"`
	ComposeServices []prefixRule     `json:"compose_services"`
	Separators      []string         `json:"separators"`
}

var reference = func() referenceData {
	var data referenceData
	if err := json.Unmarshal(dependencyMapJSON, &data); err != nil {
		// A malformed reference file is a build problem, not a runtime one:
		// failing at start-up is better than detecting nothing all day.
		panic("githubint: could not parse the embedded dependency map: " + err.Error())
	}
	if len(data.Dependencies) == 0 {
		panic("githubint: the embedded dependency map is empty")
	}
	if len(data.Separators) == 0 {
		data.Separators = []string{"/", "@", "-", ":", "."}
	}
	return data
}()

// resolve maps a raw dependency name onto a taxonomy slug.
func resolve(raw string) (string, float64) {
	name := strings.ToLower(strings.TrimSpace(raw))
	if name == "" {
		return "", 0
	}
	best, bestConfidence, bestLength := "", 0.0, 0
	for _, rule := range reference.Dependencies {
		matched := name == rule.Match
		if !matched {
			for _, separator := range reference.Separators {
				if strings.HasPrefix(name, rule.Match+separator) {
					matched = true
					break
				}
			}
		}
		if !matched {
			continue
		}
		// The most specific match wins: react-native must not resolve to
		// react merely because react is in the table.
		if len(rule.Match) > bestLength {
			best, bestConfidence, bestLength = rule.Skill, rule.Confidence, len(rule.Match)
		}
	}
	return best, bestConfidence
}

func finding(source, raw, version string) *Finding {
	slug, confidence := resolve(raw)
	if slug == "" {
		// Recorded without a skill link: useful for improving the map later,
		// and it never becomes a technology tag on a profile.
		return &Finding{RawName: raw, Source: source, Confidence: 0.1, VersionSpec: version}
	}
	return &Finding{
		SkillSlug: slug, RawName: raw, Source: source,
		Confidence: confidence, VersionSpec: version,
	}
}

// ── Per-manifest parsers ────────────────────────────────────────────────────

var goModRequire = regexp.MustCompile(`(?m)^\s*(?:require\s+)?([\w./~-]+\.[\w./~-]+)\s+v([\w.\-+]+)`)

func detectGoMod(content string) []Finding {
	out := []Finding{
		// A go.mod is proof of Go itself, which a language byte count only
		// suggests.
		{SkillSlug: "go", RawName: "go.mod", Source: "go.mod", Confidence: 1.0},
	}
	for _, m := range goModRequire.FindAllStringSubmatch(content, -1) {
		if f := finding("go.mod", m[1], "v"+m[2]); f != nil {
			out = append(out, *f)
		}
	}
	return out
}

var requirementLine = regexp.MustCompile(`^([A-Za-z0-9._-]+)\s*(\[[^\]]*\])?\s*([=<>!~]=?[^;#]*)?`)

func detectRequirements(content string) []Finding {
	out := []Finding{
		{SkillSlug: "python", RawName: "requirements.txt", Source: "requirements.txt", Confidence: 1.0},
	}
	for _, raw := range strings.Split(content, "\n") {
		line := strings.TrimSpace(raw)
		if line == "" || strings.HasPrefix(line, "#") || strings.HasPrefix(line, "-") {
			continue
		}
		m := requirementLine.FindStringSubmatch(line)
		if m == nil || m[1] == "" {
			continue
		}
		if f := finding("requirements.txt", m[1], strings.TrimSpace(m[3])); f != nil {
			out = append(out, *f)
		}
	}
	return out
}

var tomlDependency = regexp.MustCompile(`(?m)^\s*"?([A-Za-z0-9._-]+)"?\s*=\s*["{]`)

func detectPyProject(content string) []Finding {
	out := []Finding{
		{SkillSlug: "python", RawName: "pyproject.toml", Source: "pyproject.toml", Confidence: 1.0},
	}
	// PEP 621 style: dependencies = ["fastapi>=0.100", ...]
	if start := strings.Index(content, "dependencies"); start >= 0 {
		section := content[start:]
		if end := strings.Index(section, "]"); end > 0 {
			for _, raw := range strings.Split(section[:end], ",") {
				name := strings.Trim(strings.TrimSpace(raw), `"'[]`)
				name = strings.FieldsFunc(name, func(r rune) bool {
					return r == '>' || r == '<' || r == '=' || r == '!' || r == '~' || r == '['
				})[0:1][0]
				if name == "" || name == "dependencies" {
					continue
				}
				if f := finding("pyproject.toml", name, ""); f != nil {
					out = append(out, *f)
				}
			}
		}
	}
	// Poetry style: [tool.poetry.dependencies] followed by name = "^1.0"
	if start := strings.Index(content, "[tool.poetry.dependencies]"); start >= 0 {
		section := content[start+len("[tool.poetry.dependencies]"):]
		if end := strings.Index(section, "\n["); end > 0 {
			section = section[:end]
		}
		for _, m := range tomlDependency.FindAllStringSubmatch(section, -1) {
			if m[1] == "python" {
				continue
			}
			if f := finding("pyproject.toml", m[1], ""); f != nil {
				out = append(out, *f)
			}
		}
	}
	return out
}

func detectPipfile(content string) []Finding {
	out := []Finding{
		{SkillSlug: "python", RawName: "Pipfile", Source: "requirements.txt", Confidence: 1.0},
	}
	if start := strings.Index(content, "[packages]"); start >= 0 {
		section := content[start+len("[packages]"):]
		if end := strings.Index(section, "\n["); end > 0 {
			section = section[:end]
		}
		for _, m := range tomlDependency.FindAllStringSubmatch(section, -1) {
			if f := finding("requirements.txt", m[1], ""); f != nil {
				out = append(out, *f)
			}
		}
	}
	return out
}

func detectPackageJSON(content string) []Finding {
	var pkg struct {
		Dependencies    map[string]string `json:"dependencies"`
		DevDependencies map[string]string `json:"devDependencies"`
		Scripts         map[string]string `json:"scripts"`
	}
	if err := json.Unmarshal([]byte(content), &pkg); err != nil {
		return nil
	}

	out := []Finding{
		{SkillSlug: "javascript", RawName: "package.json", Source: "package.json", Confidence: 0.8},
	}
	for name, version := range pkg.Dependencies {
		if f := finding("package.json", name, version); f != nil {
			out = append(out, *f)
		}
	}
	// Dev dependencies are weaker evidence of what the project is, but
	// typescript and the test runners live there and are worth knowing.
	for name, version := range pkg.DevDependencies {
		if f := finding("package.json", name, version); f != nil {
			f.Confidence *= 0.8
			out = append(out, *f)
		}
	}
	return out
}

func detectComposer(content string) []Finding {
	var pkg struct {
		Require    map[string]string `json:"require"`
		RequireDev map[string]string `json:"require-dev"`
	}
	if err := json.Unmarshal([]byte(content), &pkg); err != nil {
		return nil
	}
	out := []Finding{
		{SkillSlug: "php", RawName: "composer.json", Source: "composer.json", Confidence: 1.0},
	}
	for name, version := range pkg.Require {
		if name == "php" {
			continue
		}
		if f := finding("composer.json", name, version); f != nil {
			out = append(out, *f)
		}
	}
	for name, version := range pkg.RequireDev {
		if f := finding("composer.json", name, version); f != nil {
			f.Confidence *= 0.8
			out = append(out, *f)
		}
	}
	return out
}

var dockerFrom = regexp.MustCompile(`(?mi)^\s*FROM\s+([\w./:-]+)`)

func detectDockerfile(content string) []Finding {
	out := []Finding{
		{SkillSlug: "docker", RawName: "Dockerfile", Source: "Dockerfile", Confidence: 1.0},
	}
	// The base image says which runtime the developer actually deploys.
	for _, m := range dockerFrom.FindAllStringSubmatch(content, -1) {
		image := strings.ToLower(m[1])
		for _, rule := range reference.BaseImages {
			if strings.HasPrefix(image, rule.Prefix) {
				out = append(out, Finding{
					SkillSlug: rule.Skill, RawName: m[1], Source: "Dockerfile", Confidence: 0.75,
				})
				break
			}
		}
	}
	return out
}

var composeImage = regexp.MustCompile(`(?mi)^\s*image:\s*["']?([\w./:-]+)`)

func detectCompose(content string) []Finding {
	out := []Finding{
		{SkillSlug: "docker", RawName: "docker-compose.yml", Source: "docker-compose.yml", Confidence: 1.0},
	}
	// The services a developer composes are the infrastructure they have
	// actually run, which is stronger evidence than a dependency line.
	for _, m := range composeImage.FindAllStringSubmatch(content, -1) {
		image := strings.ToLower(m[1])
		for _, rule := range reference.ComposeServices {
			if strings.HasPrefix(image, rule.Prefix) {
				out = append(out, Finding{
					SkillSlug: rule.Skill, RawName: m[1], Source: "docker-compose.yml", Confidence: 0.85,
				})
				break
			}
		}
	}
	return out
}

func detectCargo(content string) []Finding {
	out := []Finding{
		{SkillSlug: "rust", RawName: "Cargo.toml", Source: "Cargo.toml", Confidence: 1.0},
	}
	if start := strings.Index(content, "[dependencies]"); start >= 0 {
		section := content[start+len("[dependencies]"):]
		if end := strings.Index(section, "\n["); end > 0 {
			section = section[:end]
		}
		for _, m := range tomlDependency.FindAllStringSubmatch(section, -1) {
			if f := finding("Cargo.toml", m[1], ""); f != nil {
				out = append(out, *f)
			}
		}
	}
	return out
}

var pomArtifact = regexp.MustCompile(`(?s)<groupId>([^<]+)</groupId>\s*<artifactId>([^<]+)</artifactId>`)

func detectPom(content string) []Finding {
	out := []Finding{
		{SkillSlug: "java", RawName: "pom.xml", Source: "pom.xml", Confidence: 1.0},
	}
	for _, m := range pomArtifact.FindAllStringSubmatch(content, -1) {
		name := strings.TrimSpace(m[1]) + ":" + strings.TrimSpace(m[2])
		if f := finding("pom.xml", strings.TrimSpace(m[1]), ""); f != nil {
			f.RawName = name
			out = append(out, *f)
		}
	}
	return out
}

var gradleDependency = regexp.MustCompile(`(?m)(?:implementation|api|compile)\s*[( ]\s*["']([^"']+)["']`)

func detectGradle(content string) []Finding {
	out := []Finding{
		{SkillSlug: "java", RawName: "build.gradle", Source: "build.gradle", Confidence: 0.8},
	}
	if strings.Contains(content, "kotlin(") || strings.Contains(content, "org.jetbrains.kotlin") {
		out = append(out, Finding{
			SkillSlug: "kotlin", RawName: "kotlin", Source: "build.gradle", Confidence: 0.9,
		})
	}
	for _, m := range gradleDependency.FindAllStringSubmatch(content, -1) {
		if f := finding("build.gradle", m[1], ""); f != nil {
			out = append(out, *f)
		}
	}
	return out
}

var gemLine = regexp.MustCompile(`(?m)^\s*gem\s+["']([^"']+)["']`)

func detectGemfile(content string) []Finding {
	out := []Finding{
		{SkillSlug: "ruby", RawName: "Gemfile", Source: "Gemfile", Confidence: 1.0},
	}
	for _, m := range gemLine.FindAllStringSubmatch(content, -1) {
		if f := finding("Gemfile", m[1], ""); f != nil {
			out = append(out, *f)
		}
	}
	return out
}

func detectPubspec(content string) []Finding {
	out := []Finding{
		{SkillSlug: "dart", RawName: "pubspec.yaml", Source: "pubspec.yaml", Confidence: 1.0},
	}
	if strings.Contains(content, "flutter:") || strings.Contains(content, "sdk: flutter") {
		out = append(out, Finding{
			SkillSlug: "flutter", RawName: "flutter", Source: "pubspec.yaml", Confidence: 0.95,
		})
	}
	return out
}

func detectSwiftPackage(content string) []Finding {
	return []Finding{
		{SkillSlug: "swift", RawName: "Package.swift", Source: "Package.swift", Confidence: 1.0},
	}
}

// ── Aggregation ─────────────────────────────────────────────────────────────

// LanguageShares turns raw byte counts into shares.
//
// The result is labelled "code usage" wherever it is displayed. The
// specification is explicit that 97% Go must never be presented as "Go
// knowledge 97%", and this function returning only shares — with no
// competence field to fill in — is how that stays true.
func LanguageShares(totals map[string]int64, topN int) []LanguageStat {
	var sum int64
	for _, bytes := range totals {
		sum += bytes
	}
	if sum == 0 {
		return nil
	}

	stats := make([]LanguageStat, 0, len(totals))
	for language, bytes := range totals {
		stats = append(stats, LanguageStat{
			Language: language,
			Bytes:    bytes,
			Share:    float64(bytes) / float64(sum),
		})
	}
	// Descending by bytes, with the name as a tiebreaker so the order is
	// stable between runs.
	for i := 1; i < len(stats); i++ {
		for j := i; j > 0; j-- {
			if stats[j-1].Bytes > stats[j].Bytes ||
				(stats[j-1].Bytes == stats[j].Bytes && stats[j-1].Language <= stats[j].Language) {
				break
			}
			stats[j-1], stats[j] = stats[j], stats[j-1]
		}
	}

	if topN > 0 && len(stats) > topN {
		// The tail is collapsed into "Other" rather than dropped, so the
		// shares still add to 100%.
		var otherBytes int64
		for _, s := range stats[topN:] {
			otherBytes += s.Bytes
		}
		stats = stats[:topN]
		if otherBytes > 0 {
			stats = append(stats, LanguageStat{
				Language: "Other",
				Bytes:    otherBytes,
				Share:    float64(otherBytes) / float64(sum),
			})
		}
	}
	return stats
}

// SummariseTechnologies aggregates per-repository findings across an account.
func SummariseTechnologies(perRepo [][]Finding, names map[string]string) []TechnologySummary {
	type accumulator struct {
		repositories int
		best         float64
		sources      map[string]struct{}
	}
	agg := map[string]*accumulator{}

	for _, findings := range perRepo {
		seenInRepo := map[string]bool{}
		for _, f := range findings {
			if f.SkillSlug == "" {
				continue
			}
			entry, ok := agg[f.SkillSlug]
			if !ok {
				entry = &accumulator{sources: map[string]struct{}{}}
				agg[f.SkillSlug] = entry
			}
			if !seenInRepo[f.SkillSlug] {
				entry.repositories++
				seenInRepo[f.SkillSlug] = true
			}
			if f.Confidence > entry.best {
				entry.best = f.Confidence
			}
			entry.sources[f.Source] = struct{}{}
		}
	}

	out := make([]TechnologySummary, 0, len(agg))
	for slug, entry := range agg {
		sources := make([]string, 0, len(entry.sources))
		for source := range entry.sources {
			sources = append(sources, source)
		}
		sortStrings(sources)

		name := names[slug]
		if name == "" {
			name = slug
		}
		// Appearing across several repositories is stronger evidence than one
		// high-confidence hit, so the two are combined.
		breadth := float64(entry.repositories)
		if breadth > 4 {
			breadth = 4
		}
		confidence := entry.best*0.7 + (breadth/4)*0.3
		if confidence > 1 {
			confidence = 1
		}
		out = append(out, TechnologySummary{
			Slug:         slug,
			Name:         name,
			Repositories: entry.repositories,
			Confidence:   confidence,
			Sources:      sources,
		})
	}

	for i := 1; i < len(out); i++ {
		for j := i; j > 0; j-- {
			a, b := out[j-1], out[j]
			if a.Confidence > b.Confidence ||
				(a.Confidence == b.Confidence && a.Repositories >= b.Repositories) {
				break
			}
			out[j-1], out[j] = out[j], out[j-1]
		}
	}
	return out
}

func sortStrings(s []string) {
	for i := 1; i < len(s); i++ {
		for j := i; j > 0 && s[j-1] > s[j]; j-- {
			s[j-1], s[j] = s[j], s[j-1]
		}
	}
}

// PortfolioWorthiness judges whether a repository is worth offering as
// portfolio work.
//
// The bar is "would a client learn something from this": a described,
// non-forked, recently-touched repository with real code. Stars are a weak
// input, because a useful internal tool has none and a joke repository can
// have thousands.
func PortfolioWorthiness(r Repository, hasReadme bool, detectedCount int) (bool, string) {
	switch {
	case r.Fork:
		return false, "a fork rather than the developer's own work"
	case r.Private:
		return false, "private"
	case r.Archived:
		return false, "archived"
	case r.Size < 40:
		return false, "too small to show anything"
	}

	var reasons []string
	score := 0
	if strings.TrimSpace(r.Description) != "" {
		score += 2
		reasons = append(reasons, "described")
	}
	if hasReadme {
		score += 2
		reasons = append(reasons, "has a README")
	}
	if detectedCount >= 3 {
		score += 2
		reasons = append(reasons, "a real dependency set")
	}
	if r.Stars >= 3 {
		score++
		reasons = append(reasons, "has stars")
	}
	if r.Homepage != "" {
		score += 2
		reasons = append(reasons, "has a live URL")
	}
	if len(r.Topics) > 0 {
		score++
	}
	if r.Size > 500 {
		score++
		reasons = append(reasons, "substantial")
	}

	if score < 4 {
		return false, "not enough to show a client yet"
	}
	return true, strings.Join(reasons, ", ")
}
