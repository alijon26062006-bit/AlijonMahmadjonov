package database

import (
	"crypto/sha256"
	"encoding/hex"
	"os"
	"path/filepath"
	"testing"
)

// The repository keeps migrations in /database/migrations (the structure the
// project specifies) while the Go binary embeds its own copy so a deployment is
// a single artefact. `make sync-migrations` copies one to the other; this test
// is what stops the two from drifting apart unnoticed.
func TestEmbeddedMigrationsMatchRepository(t *testing.T) {
	const canonical = "../../../../../database/migrations"

	entries, err := os.ReadDir(canonical)
	if err != nil {
		t.Skipf("canonical migration directory not reachable from here: %v", err)
	}

	repo := map[string]string{}
	for _, e := range entries {
		if e.IsDir() || filepath.Ext(e.Name()) != ".sql" {
			continue
		}
		body, err := os.ReadFile(filepath.Join(canonical, e.Name()))
		if err != nil {
			t.Fatalf("read %s: %v", e.Name(), err)
		}
		sum := sha256.Sum256(body)
		repo[e.Name()] = hex.EncodeToString(sum[:])
	}
	if len(repo) == 0 {
		t.Fatal("no migrations found in the canonical directory")
	}

	embedded := map[string]string{}
	dir, err := migrationFS.ReadDir("migrations")
	if err != nil {
		t.Fatalf("read embedded migrations: %v", err)
	}
	for _, e := range dir {
		body, err := migrationFS.ReadFile("migrations/" + e.Name())
		if err != nil {
			t.Fatalf("read embedded %s: %v", e.Name(), err)
		}
		sum := sha256.Sum256(body)
		embedded[e.Name()] = hex.EncodeToString(sum[:])
	}

	for name, want := range repo {
		got, ok := embedded[name]
		if !ok {
			t.Errorf("%s exists in /database/migrations but is not embedded; run `make sync-migrations`", name)
			continue
		}
		if got != want {
			t.Errorf("%s differs between /database/migrations and the embedded copy; run `make sync-migrations`", name)
		}
	}
	for name := range embedded {
		if _, ok := repo[name]; !ok {
			t.Errorf("%s is embedded but no longer exists in /database/migrations", name)
		}
	}
}

// A migration that cannot be parsed, or is missing its up file, must fail the
// build rather than the deployment.
func TestMigrationsLoadAndArePaired(t *testing.T) {
	migrations, err := LoadMigrations()
	if err != nil {
		t.Fatalf("LoadMigrations: %v", err)
	}
	if len(migrations) == 0 {
		t.Fatal("no migrations were loaded")
	}
	for i, m := range migrations {
		if m.UpSQL == "" {
			t.Errorf("migration %d (%s) has no up SQL", m.Version, m.Name)
		}
		if m.DownSQL == "" {
			t.Errorf("migration %d (%s) has no down SQL; every migration must be reversible", m.Version, m.Name)
		}
		if m.Checksum == "" {
			t.Errorf("migration %d (%s) has no checksum", m.Version, m.Name)
		}
		if i > 0 && migrations[i-1].Version >= m.Version {
			t.Errorf("migrations are not strictly ordered: %d follows %d", m.Version, migrations[i-1].Version)
		}
	}
}
