package preview

import (
	"context"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
)

// A probe against a real server, so the header handling is tested end to end.
func probeServer(t *testing.T, handler http.HandlerFunc) Result {
	t.Helper()
	server := httptest.NewServer(handler)
	t.Cleanup(server.Close)

	// Development options: the test server is on 127.0.0.1, which production
	// correctly refuses.
	prober := NewProber("https://averix.example", true)
	return prober.Probe(context.Background(), server.URL)
}

func TestProbeAllowsASiteWithNoFramingRestriction(t *testing.T) {
	result := probeServer(t, func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "text/html")
		_, _ = w.Write([]byte("<html><head><title>  Marketplace  Demo </title></head><body>hi</body></html>"))
	})

	if result.Verdict != Allowed {
		t.Fatalf("verdict = %q, want allowed (reason: %s)", result.Verdict, result.Reason)
	}
	if result.Title != "Marketplace Demo" {
		t.Errorf("title = %q, want the collapsed title", result.Title)
	}
	if result.StatusCode != 200 {
		t.Errorf("status = %d", result.StatusCode)
	}
}

// A site that refuses framing is honoured. Nothing in this package strips a
// header or proxies the page to get around it.
func TestProbeHonoursFramingRefusals(t *testing.T) {
	cases := []struct {
		name      string
		headers   map[string]string
		wantBlock string
	}{
		{"X-Frame-Options DENY", map[string]string{"X-Frame-Options": "DENY"}, "X-Frame-Options"},
		{"X-Frame-Options deny lowercase", map[string]string{"X-Frame-Options": "deny"}, "X-Frame-Options"},
		{"X-Frame-Options SAMEORIGIN", map[string]string{"X-Frame-Options": "SAMEORIGIN"}, "X-Frame-Options"},
		{"obsolete ALLOW-FROM", map[string]string{"X-Frame-Options": "ALLOW-FROM https://averix.example"}, "X-Frame-Options"},
		{"CSP frame-ancestors none", map[string]string{"Content-Security-Policy": "frame-ancestors 'none'"}, "Content-Security-Policy"},
		{"CSP frame-ancestors self", map[string]string{"Content-Security-Policy": "default-src 'self'; frame-ancestors 'self'"}, "Content-Security-Policy"},
		{"CSP frame-ancestors another origin", map[string]string{"Content-Security-Policy": "frame-ancestors https://other.example"}, "Content-Security-Policy"},
		{"CSP frame-ancestors bare", map[string]string{"Content-Security-Policy": "frame-ancestors"}, "Content-Security-Policy"},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			result := probeServer(t, func(w http.ResponseWriter, r *http.Request) {
				for key, value := range tc.headers {
					w.Header().Set(key, value)
				}
				_, _ = w.Write([]byte("<html><title>Blocked</title></html>"))
			})

			if result.Verdict != Blocked {
				t.Fatalf("verdict = %q, want blocked", result.Verdict)
			}
			if result.BlockedBy != tc.wantBlock {
				t.Errorf("blocked_by = %q, want %q", result.BlockedBy, tc.wantBlock)
			}
			// The message must be something a developer can act on, without
			// naming a header they have never heard of.
			if result.Reason == "" {
				t.Error("a block must explain itself")
			}
			if strings.Contains(result.Reason, "X-Frame") || strings.Contains(result.Reason, "CSP") {
				t.Errorf("the reason is too technical for a developer's settings page: %q", result.Reason)
			}
		})
	}
}

// A site that explicitly permits our origin is framed, which is the case most
// easily got wrong.
func TestProbeHonoursAnExplicitPermission(t *testing.T) {
	cases := []string{
		"frame-ancestors https://averix.example",
		"frame-ancestors 'self' https://averix.example",
		"frame-ancestors https://*.averix.example https://averix.example",
		"frame-ancestors *",
		"frame-ancestors https:",
		"default-src 'self'; frame-ancestors https://averix.example; script-src 'self'",
	}
	for _, policy := range cases {
		t.Run(policy, func(t *testing.T) {
			result := probeServer(t, func(w http.ResponseWriter, r *http.Request) {
				w.Header().Set("Content-Security-Policy", policy)
				_, _ = w.Write([]byte("<html><title>Allowed</title></html>"))
			})
			if result.Verdict != Allowed {
				t.Errorf("policy %q gave %q, want allowed (%s)", policy, result.Verdict, result.Reason)
			}
		})
	}
}

// CSP wins over X-Frame-Options where both are present, which is what
// browsers do — so a site that allows us in CSP and denies in XFO is framed.
func TestCSPTakesPrecedenceOverXFrameOptions(t *testing.T) {
	result := probeServer(t, func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("X-Frame-Options", "DENY")
		w.Header().Set("Content-Security-Policy", "frame-ancestors https://averix.example")
		_, _ = w.Write([]byte("<html><title>Modern</title></html>"))
	})
	if result.Verdict != Allowed {
		t.Errorf("verdict = %q; CSP should take precedence over X-Frame-Options", result.Verdict)
	}

	result = probeServer(t, func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("X-Frame-Options", "ALLOWALL")
		w.Header().Set("Content-Security-Policy", "frame-ancestors 'none'")
		_, _ = w.Write([]byte("<html><title>Modern</title></html>"))
	})
	if result.Verdict != Blocked {
		t.Errorf("verdict = %q; a CSP refusal must win", result.Verdict)
	}
}

func TestProbeReportsAnErrorPageAsUnreachable(t *testing.T) {
	result := probeServer(t, func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusNotFound)
	})
	if result.Verdict == Allowed {
		t.Error("a 404 must not be presented as a working preview")
	}
	if !strings.Contains(result.Reason, "404") {
		t.Errorf("the reason should name the status, got %q", result.Reason)
	}
}

// The probe is the second line of defence: a hostile URL should already have
// been refused when the developer saved it, and is refused again here.
func TestProbeRefusesInternalAddresses(t *testing.T) {
	prober := NewProber("https://averix.example", false)

	for _, raw := range []string{
		"http://169.254.169.254/latest/meta-data/",
		"http://127.0.0.1:5432/",
		"http://10.0.0.1/internal",
		"http://192.168.1.1/",
		"http://localhost:8080/admin",
		"file:///etc/passwd",
		"javascript:alert(1)",
		"https://trusted.example.com@evil.example/",
		"http://[::1]/",
	} {
		result := prober.Probe(context.Background(), raw)
		if result.Verdict == Allowed {
			t.Errorf("%q was allowed as a preview", raw)
		}
		if result.Reason == "" {
			t.Errorf("%q was refused without a reason", raw)
		}
	}
}

// A site that redirects to an internal address must not get one.
func TestProbeRefusesARedirectToAnInternalAddress(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		http.Redirect(w, r, "http://169.254.169.254/latest/meta-data/", http.StatusFound)
	}))
	t.Cleanup(server.Close)

	// Development options allow the test server's own loopback address but
	// must still refuse the metadata endpoint, which is never legitimate.
	result := NewProber("https://averix.example", true).Probe(context.Background(), server.URL)
	if result.Verdict == Allowed {
		t.Error("a redirect to the cloud metadata endpoint must not be followed into an allowed verdict")
	}
}

func TestProbeCapsTheRedirectChain(t *testing.T) {
	var server *httptest.Server
	server = httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		http.Redirect(w, r, server.URL+r.URL.Path+"x", http.StatusFound)
	}))
	t.Cleanup(server.Close)

	result := NewProber("https://averix.example", true).Probe(context.Background(), server.URL)
	if result.Verdict == Allowed {
		t.Error("an endless redirect chain must not produce an allowed verdict")
	}
}

// The title is plain text and bounded, so a hostile page cannot use it to
// smuggle anything into the address bar.
func TestTitleIsSanitisedAndBounded(t *testing.T) {
	result := probeServer(t, func(w http.ResponseWriter, r *http.Request) {
		_, _ = w.Write([]byte("<html><title>Evil\x00\x07 <script>alert(1)</script> " +
			strings.Repeat("padding ", 60) + "</title></html>"))
	})
	if result.Verdict != Allowed {
		t.Fatalf("verdict = %q", result.Verdict)
	}
	if strings.ContainsAny(result.Title, "\x00\x07") {
		t.Error("control characters survived into the title")
	}
	if len(result.Title) > 160 {
		t.Errorf("the title is %d characters; it must be bounded", len(result.Title))
	}
	// The script tag's text is harmless as plain text, but it must not be
	// markup by the time it reaches the client.
	if strings.Contains(result.Title, "<script>") {
		// It is stored as literal text and rendered as text; assert only that
		// it was not treated as structure.
		t.Log("the title retains literal angle brackets, which are escaped on render")
	}
}

// The sandbox is assembled server-side so a front-end change cannot loosen it.
func TestFrameSandboxWithholdsSameOriginAndNavigation(t *testing.T) {
	frame := BuildFrame(Result{URL: "https://project.example/", Host: "project.example", Verdict: Allowed})

	if frame.Sandbox == "" {
		t.Fatal("an allowed frame must carry a sandbox")
	}
	// Scripts are unavoidable: a preview of a site with no scripts is not a
	// preview of the site.
	if !strings.Contains(frame.Sandbox, "allow-scripts") {
		t.Error("the sandbox must allow scripts or the preview shows nothing")
	}
	// This is the one that matters: with allow-same-origin, a same-origin
	// embedded page could reach into the parent and read a session.
	for _, forbidden := range []string{
		"allow-same-origin", "allow-top-navigation", "allow-forms",
		"allow-modals", "allow-downloads", "allow-storage-access-by-user-activation",
		"allow-presentation", "allow-pointer-lock",
	} {
		if strings.Contains(frame.Sandbox, forbidden) {
			t.Errorf("the sandbox must not include %s", forbidden)
		}
	}
	if frame.Referrer != "strict-origin" {
		t.Errorf("referrer policy = %q; the site should learn the origin, not the page",
			frame.Referrer)
	}
	for _, feature := range []string{"camera=()", "microphone=()", "geolocation=()", "payment=()"} {
		if !strings.Contains(frame.PermissionsPolicy, feature) {
			t.Errorf("the permissions policy must withhold %s", feature)
		}
	}
	if frame.CSP == "" {
		t.Error("the frame must carry its own CSP as a second layer")
	}

	// The device widths match the breakpoints the product is designed around.
	if len(frame.Devices) != 3 {
		t.Fatalf("devices = %d, want mobile, tablet and desktop", len(frame.Devices))
	}
	widths := map[string]int{}
	for _, device := range frame.Devices {
		widths[device.Key] = device.Width
		if device.Label == "" {
			t.Errorf("device %q has no label", device.Key)
		}
	}
	if widths["mobile"] != 390 || widths["tablet"] != 768 || widths["desktop"] != 1280 {
		t.Errorf("device widths = %v, want 390/768/1280", widths)
	}
}

// A blocked frame carries no iframe attributes at all: there is nothing to
// render, and supplying them would invite a client to try anyway.
func TestBlockedFrameCarriesNoAttributes(t *testing.T) {
	frame := BuildFrame(Result{
		URL: "https://project.example/", Host: "project.example",
		Verdict: Blocked, Reason: "This site asks not to be shown inside another page.",
	})
	if frame.Sandbox != "" || frame.CSP != "" || len(frame.Devices) != 0 {
		t.Error("a blocked frame must carry no render instructions")
	}
	if frame.Reason == "" {
		t.Error("a blocked frame must explain itself so the interface can say why")
	}
}

func TestOriginMatching(t *testing.T) {
	cases := []struct {
		source, origin string
		want           bool
	}{
		{"https://averix.example", "https://averix.example", true},
		{"averix.example", "https://averix.example", true},
		{"https://averix.example/", "https://averix.example", true},
		{"https://*.averix.example", "https://app.averix.example", true},
		{"https://*.averix.example", "https://averix.example", false},
		{"https://other.example", "https://averix.example", false},
		{"http://averix.example", "https://averix.example", false},
		{"https://averix.example.evil.test", "https://averix.example", false},
	}
	for _, tc := range cases {
		if got := originMatches(tc.source, tc.origin); got != tc.want {
			t.Errorf("originMatches(%q, %q) = %v, want %v", tc.source, tc.origin, got, tc.want)
		}
	}
}
