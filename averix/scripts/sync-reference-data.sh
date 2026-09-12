#!/usr/bin/env bash
# Copies the canonical reference data into both services.
#
# /database is the source of truth. The Go binary embeds its copy so a
# deployment is a single artefact, and the Python image carries its copy for
# the same reason. Each service has a test that fails if its copy has drifted.
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Migrations, embedded by the Go service.
migrations_src="$root/database/migrations"
migrations_dst="$root/services/api-go/internal/platform/database/migrations"
mkdir -p "$migrations_dst"
find "$migrations_dst" -name '*.sql' -delete
cp "$migrations_src"/*.sql "$migrations_dst"/
echo "synced $(ls -1 "$migrations_dst"/*.sql | wc -l | tr -d ' ') migrations"

# The dependency map, read by both detectors.
map_src="$root/database/reference/dependency-map.json"
cp "$map_src" "$root/services/api-go/internal/githubint/reference/dependency-map.json"
cp "$map_src" "$root/services/ai-python/app/github/reference/dependency-map.json"
echo "synced the dependency map into both services"

# The taxonomy slugs the Python service validates against.
python3 "$root/scripts/generate-python-taxonomy.py"
