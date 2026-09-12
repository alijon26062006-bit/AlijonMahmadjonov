package urlguard

import (
	"net"
	"strings"
	"testing"
)

func TestNormaliseAcceptsRealProjectURLs(t *testing.T) {
	cases := []struct {
		in       string
		wantURL  string
		wantHost string
	}{
		{"https://project.example.com", "https://project.example.com/", "project.example.com"},
		{"project.example.com", "https://project.example.com/", "project.example.com"},
		{"  https://shop.example.com/catalog?ref=averix  ", "https://shop.example.com/catalog?ref=averix", "shop.example.com"},
		{"https://EXAMPLE.COM/Path", "https://example.com/Path", "example.com"},
		{"https://example.com/a#section", "https://example.com/a", "example.com"},
		{"https://example.com:8443/app", "https://example.com:8443/app", "example.com"},
		{"https://sub.domain.example.co.uk/", "https://sub.domain.example.co.uk/", "sub.domain.example.co.uk"},
	}
	for _, c := range cases {
		got, err := Normalise(c.in, DefaultOptions())
		if err != nil {
			t.Errorf("Normalise(%q) rejected: %v", c.in, err)
			continue
		}
		if got.URL != c.wantURL {
			t.Errorf("Normalise(%q).URL = %q, want %q", c.in, got.URL, c.wantURL)
		}
		if got.Host != c.wantHost {
			t.Errorf("Normalise(%q).Host = %q, want %q", c.in, got.Host, c.wantHost)
		}
	}
}

// Every one of these has been used to turn a "just a link" field into code
// execution, credential theft or an internal port scan.
func TestNormaliseRejectsHostileURLs(t *testing.T) {
	cases := []struct{ name, in string }{
		{"javascript", "javascript:alert(document.cookie)"},
		{"javascript uppercase", "JavaScript:alert(1)"},
		{"javascript with tab", "java\tscript:alert(1)"},
		{"javascript with newline", "java\nscript:alert(1)"},
		{"data url", "data:text/html;base64,PHNjcmlwdD5hbGVydCgxKTwvc2NyaXB0Pg=="},
		{"data svg", "data:image/svg+xml,<svg onload=alert(1)>"},
		{"vbscript", "vbscript:msgbox(1)"},
		{"file", "file:///etc/passwd"},
		{"file windows", "file://C:/Windows/System32/config/SAM"},
		{"blob", "blob:https://example.com/uuid"},
		{"about", "about:blank"},
		{"chrome extension", "chrome-extension://abcdef/page.html"},
		{"ftp", "ftp://files.example.com/x"},
		{"gopher", "gopher://example.com:70/_GET"},
		{"ssh", "ssh://root@example.com"},
		{"websocket", "wss://example.com/socket"},
		{"localhost", "http://localhost:8080/admin"},
		{"localhost https", "https://localhost/admin"},
		{"loopback v4", "http://127.0.0.1:5432"},
		{"loopback obscured", "http://127.1/"},
		{"loopback v6", "http://[::1]:6379/"},
		{"all zeroes", "http://0.0.0.0:8080/"},
		{"aws metadata", "http://169.254.169.254/latest/meta-data/iam/security-credentials/"},
		{"gcp metadata", "http://metadata.google.internal/computeMetadata/v1/"},
		{"private 10", "http://10.0.0.5/internal"},
		{"private 172", "http://172.16.30.1/"},
		{"private 192", "http://192.168.1.1/router"},
		{"cgnat", "http://100.64.2.3/"},
		{"ipv4-mapped ipv6", "http://[::ffff:127.0.0.1]/"},
		{"unique local v6", "http://[fc00::1]/"},
		{"link local v6", "http://[fe80::1]/"},
		{"dot local", "https://printer.local/status"},
		{"dot internal", "https://wiki.internal/secrets"},
		{"onion", "https://abcdefghij.onion/"},
		{"credentials", "https://trusted.example.com@evil.example/"},
		{"credentials with password", "https://user:pw@evil.example/"},
		{"no host", "https:///path"},
		{"single label", "https://intranet/"},
		{"plain http", "http://example.com/"},
		{"odd port", "https://example.com:22/"},
		{"redis port", "https://example.com:6379/"},
		{"empty", ""},
		{"whitespace only", "   "},
		{"trailing dot loopback", "http://localhost./"},
	}
	for _, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			got, err := Normalise(c.in, DefaultOptions())
			if err == nil {
				t.Fatalf("Normalise(%q) was accepted as %q; it must be rejected", c.in, got.URL)
			}
			var rej *Rejection
			if !asRejection(err, &rej) {
				t.Fatalf("Normalise(%q) returned %T, want *Rejection", c.in, err)
			}
			if rej.Human() == "" {
				t.Errorf("rejection for %q has no message for the user", c.in)
			}
			// The message a developer sees must not leak the internals of the
			// check (range names, resolver detail).
			if strings.Contains(rej.Human(), "/") && !strings.Contains(rej.Human(), "https://") {
				t.Errorf("rejection message for %q looks internal: %q", c.in, rej.Human())
			}
		})
	}
}

func asRejection(err error, target **Rejection) bool {
	r, ok := err.(*Rejection)
	if ok {
		*target = r
	}
	return ok
}

func TestNormaliseTooLong(t *testing.T) {
	long := "https://example.com/" + strings.Repeat("a", 3000)
	if _, err := Normalise(long, DefaultOptions()); err == nil {
		t.Fatal("an over-length URL must be rejected")
	}
}

func TestDevelopmentOptionsAllowLocalhost(t *testing.T) {
	// Local development needs to preview http://localhost:3000; production
	// must not, which is exactly why this is an explicit option.
	got, err := Normalise("http://localhost:3000/demo", DevelopmentOptions())
	if err != nil {
		t.Fatalf("development options should accept localhost: %v", err)
	}
	if got.Host != "localhost" {
		t.Errorf("Host = %q, want localhost", got.Host)
	}
	if _, err := Normalise("http://localhost:3000/demo", DefaultOptions()); err == nil {
		t.Fatal("default options must still reject localhost")
	}
}

func TestClassifyIPBlocksEveryPrivateRange(t *testing.T) {
	blocked := []string{
		"0.0.0.0", "127.0.0.1", "127.255.255.254", "10.1.2.3", "10.255.255.255",
		"100.64.0.1", "169.254.169.254", "172.16.0.1", "172.31.255.255",
		"192.168.0.1", "192.0.0.1", "192.0.2.1", "198.18.0.1", "198.51.100.1",
		"203.0.113.1", "224.0.0.1", "239.255.255.255", "240.0.0.1",
		"255.255.255.255", "::1", "::", "fc00::1", "fd12:3456::1", "fe80::1",
		"ff02::1", "2001:db8::1", "::ffff:10.0.0.1", "::ffff:127.0.0.1",
	}
	for _, s := range blocked {
		ip := net.ParseIP(s)
		if ip == nil {
			t.Fatalf("test fixture %q is not a valid IP", s)
		}
		if IsPublicIP(ip) {
			t.Errorf("%s was treated as publicly routable", s)
		}
	}

	public := []string{"8.8.8.8", "1.1.1.1", "93.184.216.34", "2606:2800:220:1:248:1893:25c8:1946"}
	for _, s := range public {
		ip := net.ParseIP(s)
		if !IsPublicIP(ip) {
			t.Errorf("%s should be treated as publicly routable", s)
		}
	}
}

// The dialler's Control hook is the real defence: a hostname can pass the
// name check and then resolve to a private address. This asserts the hook
// rejects the address it is actually handed.
func TestSafeDialerControlRejectsPrivateTargets(t *testing.T) {
	d := SafeDialer(0)
	if d.Control == nil {
		t.Fatal("SafeDialer must install a Control hook")
	}
	blocked := []string{
		"127.0.0.1:80", "169.254.169.254:80", "10.0.0.1:443",
		"192.168.1.1:8080", "[::1]:443", "[fd00::1]:443",
	}
	for _, addr := range blocked {
		if err := d.Control("tcp", addr, nil); err == nil {
			t.Errorf("Control allowed a connection to %s", addr)
		}
	}
	for _, addr := range []string{"8.8.8.8:443", "93.184.216.34:80"} {
		if err := d.Control("tcp", addr, nil); err != nil {
			t.Errorf("Control blocked a public address %s: %v", addr, err)
		}
	}
	// A hostname reaching Control means DNS was bypassed; refuse it.
	if err := d.Control("tcp", "example.com:443", nil); err == nil {
		t.Error("Control must refuse a non-IP address")
	}
}

func TestNormaliseIsIdempotent(t *testing.T) {
	first, err := Normalise("project.example.com/app?a=1", DefaultOptions())
	if err != nil {
		t.Fatalf("first pass: %v", err)
	}
	second, err := Normalise(first.URL, DefaultOptions())
	if err != nil {
		t.Fatalf("second pass: %v", err)
	}
	if first.URL != second.URL {
		t.Errorf("normalisation is not idempotent: %q then %q", first.URL, second.URL)
	}
}
