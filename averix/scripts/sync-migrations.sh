#!/usr/bin/env bash
# Copies the canonical migrations into the Go service so the binary embeds them.
# /database/migrations is the source of truth; the embedded copy is a build input.
# internal/platform/database/migrations_sync_test.go fails if the two drift.
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
src="$root/database/migrations"
dst="$root/services/api-go/internal/platform/database/migrations"

mkdir -p "$dst"
# Remove stale files first so a deleted migration does not linger in the binary.
find "$dst" -name '*.sql' -delete
cp "$src"/*.sql "$dst"/
echo "synced $(ls -1 "$dst"/*.sql | wc -l | tr -d ' ') migration files into the Go service"
