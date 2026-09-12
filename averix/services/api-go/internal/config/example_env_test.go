package config

import (
	"bufio"
	"os"
	"strings"
	"testing"
)

// The stack ships .env.example and install.sh copies it, filling in the
// domain and the secrets. If the result does not load, every container that
// calls Load — the API, the worker, and the migration job — exits 1 on a
// fresh deployment. That happened once, with a check that refused the
// filesystem storage driver the compose file itself configures. This test is
// the guard: the file we ship must be a configuration the binary accepts.
func TestExampleEnvIsAValidProductionConfig(t *testing.T) {
	for k, v := range exampleEnv(t) {
		t.Setenv(k, v)
	}

	// What install.sh generates rather than copies.
	t.Setenv("COOKIE_SECRET", strings.Repeat("a", 64))
	t.Setenv("DATA_ENCRYPTION_KEY", strings.Repeat("b", 64))
	t.Setenv("AI_SERVICE_TOKEN", strings.Repeat("c", 64))
	t.Setenv("POSTGRES_PASSWORD", strings.Repeat("d", 32))
	// Composed from the Postgres credentials by the compose file.
	t.Setenv("DATABASE_URL", "postgres://averix:pw@postgres:5432/averix?sslmode=disable")

	cfg, err := Load()
	if err != nil {
		t.Fatalf(".env.example is not a loadable production configuration:\n%v", err)
	}
	if !cfg.Env.IsProduction() {
		t.Fatalf("expected .env.example to describe a production deployment, got %q", cfg.Env)
	}
}

func exampleEnv(t *testing.T) map[string]string {
	t.Helper()
	const path = "../../../../.env.example"
	f, err := os.Open(path)
	if err != nil {
		t.Fatalf("open %s: %v", path, err)
	}
	defer f.Close()

	values := map[string]string{}
	scan := bufio.NewScanner(f)
	for scan.Scan() {
		line := strings.TrimSpace(scan.Text())
		if line == "" || strings.HasPrefix(line, "#") {
			continue
		}
		key, value, ok := strings.Cut(line, "=")
		if !ok {
			continue
		}
		values[strings.TrimSpace(key)] = strings.TrimSpace(value)
	}
	if err := scan.Err(); err != nil {
		t.Fatalf("read %s: %v", path, err)
	}
	return values
}
