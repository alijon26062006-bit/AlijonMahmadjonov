// Package preview decides whether a developer's project URL can be shown
// inside AVERIX, and records the answer.
//
// The product requirement is that clicking "Live preview" keeps the visitor
// inside AVERIX, in a browser-like frame. The security requirement is that
// this must never be achieved by defeating the target site's own wishes.
//
// So the flow is:
//
//  1. The URL is normalised and validated when the developer saves it
//     (package urlguard). A javascript: or an internal address never reaches
//     this package.
//  2. The site is probed once, server-side, through a dialler that re-checks
//     the address it is actually connecting to. The probe reads headers only.
//  3. If the site sends X-Frame-Options or a CSP frame-ancestors that
//     excludes us, the answer is "blocked" and the interface shows a
//     screenshot and an external link. Nothing here strips a header, proxies
//     the page, or renders it through a third party to get around the block.
//
// The frame itself is sandboxed by the web app; this package supplies the
// verdict and the attributes it should use.
package preview

import (
	"context"
	"crypto/tls"
	"errors"
	"fmt"
	"io"
	"net/http"
	"strings"
	"time"

	"github.com/averix/api/internal/platform/logx"
	"github.com/averix/api/internal/platform/urlguard"
)

// Verdict is what the probe concluded.
type Verdict string

const (
	// Allowed: no framing restriction was found, so the in-app browser can
	// show it.
	Allowed Verdict = "allowed"
	// Blocked: the site refuses to be framed. Its choice, and it is honoured.
	Blocked Verdict = "blocked"
	// Unreachable: the probe could not complete. Shown as "we couldn't reach
	// this site" rather than as a refusal, because those are different things
	// to a developer checking their own link.
	Unreachable Verdict = "unreachable"
	// Unknown: not probed yet.
	Unknown Verdict = "unknown"
)

// Result is one probe's outcome.
type Result struct {
	URL     string  `json:"url"`
	Host    string  `json:"host"`
	Verdict Verdict `json:"verdict"`
	// A short, non-technical explanation for the developer's own settings
	// page. Never shown to a visitor.
	Reason string `json:"reason,omitempty"`
	// The header that caused a block, for the developer to act on.
	BlockedBy  string    `json:"blocked_by,omitempty"`
	StatusCode int       `json:"status_code,omitempty"`
	Title      string    `json:"title,omitempty"`
	CheckedAt  time.Time `json:"checked_at"`
	// How long the answer may be cached before another probe is worthwhile.
	TTL time.Duration `json:"-"`
}

// Prober performs the server-side check.
type Prober struct {
	http *http.Client
	// The app's own origin, used to read frame-ancestors correctly: a site
	// may allow framing by us specifically.
	appOrigin string
	options   urlguard.Options
}

func NewProber(appOrigin string, devMode bool) *Prober {
	options := urlguard.DefaultOptions()
	if devMode {
		// A developer building locally genuinely wants to preview
		// http://localhost:3000. Production never allows it.
		options = urlguard.DevelopmentOptions()
	}

	dialer := urlguard.SafeDialerFor(5*time.Second, options)
	transport := &http.Transport{
		DialContext:           dialer.DialContext,
		TLSHandshakeTimeout:   5 * time.Second,
		ResponseHeaderTimeout: 8 * time.Second,
		// The probe reads headers; there is no reason to hold connections.
		DisableKeepAlives: true,
		MaxIdleConns:      0,
		// A site with a broken certificate is not one to embed, so
		// verification stays on. This is deliberate and must not be relaxed:
		// turning it off would make the probe's verdict meaningless.
		TLSClientConfig: &tls.Config{MinVersion: tls.VersionTLS12},
	}

	return &Prober{
		http: &http.Client{
			Transport: transport,
			Timeout:   12 * time.Second,
			// Redirects are followed, but every hop is re-validated: a site
			// that redirects to an internal address must not get one.
			CheckRedirect: func(req *http.Request, via []*http.Request) error {
				if len(via) >= 4 {
					return errors.New("too many redirects")
				}
				result, err := urlguard.Normalise(req.URL.String(), options)
				if err != nil {
					return fmt.Errorf("redirect to a disallowed address: %w", err)
				}
				_ = result
				return nil
			},
		},
		appOrigin: strings.TrimRight(appOrigin, "/"),
		options:   options,
	}
}

// Probe checks one URL.
//
// A GET with a tiny read is used rather than HEAD: too many sites answer HEAD
// with 405 or with different headers than they send for a real request, and
// the framing headers are what matter here. The body is read only far enough
// to find a <title>.
func (p *Prober) Probe(ctx context.Context, rawURL string) Result {
	result := Result{CheckedAt: time.Now(), Verdict: Unreachable, TTL: 6 * time.Hour}

	normalised, err := urlguard.Normalise(rawURL, p.options)
	if err != nil {
		result.Verdict = Blocked
		var rejection *urlguard.Rejection
		if errors.As(err, &rejection) {
			result.Reason = rejection.Human()
		} else {
			result.Reason = "That address can't be used for a preview."
		}
		// A rejected URL will not become acceptable on its own.
		result.TTL = 24 * time.Hour
		return result
	}
	result.URL = normalised.URL
	result.Host = normalised.Host

	// An early DNS check is cheaper than a connection attempt and gives a
	// clearer reason. The dialler's Control hook remains the authority.
	if err := urlguard.ResolvePublicFor(ctx, normalised.Host, p.options); err != nil {
		result.Verdict = Blocked
		result.Reason = "That address doesn't resolve to a public server."
		result.TTL = time.Hour
		logx.From(ctx).Info("preview probe refused a non-public host",
			"host", normalised.Host, "error", err)
		return result
	}

	probeCtx, cancel := context.WithTimeout(ctx, 12*time.Second)
	defer cancel()

	req, err := http.NewRequestWithContext(probeCtx, http.MethodGet, normalised.URL, nil)
	if err != nil {
		result.Reason = "That address can't be requested."
		return result
	}
	// An honest user agent: the site owner should be able to see what this is
	// and block it if they want to.
	req.Header.Set("User-Agent",
		"AVERIX-PreviewBot/1.0 (+https://averix.dev/preview-bot; checks whether a page can be embedded)")
	req.Header.Set("Accept", "text/html,application/xhtml+xml")
	req.Header.Set("Accept-Language", "en")
	// Sending the origin lets a site answer with a frame-ancestors that names
	// us, which is the case worth getting right.
	if p.appOrigin != "" {
		req.Header.Set("Sec-Fetch-Dest", "iframe")
		req.Header.Set("Sec-Fetch-Mode", "navigate")
		req.Header.Set("Sec-Fetch-Site", "cross-site")
	}

	resp, err := p.http.Do(req)
	if err != nil {
		if errors.Is(err, urlguard.ErrBlockedAddress) ||
			strings.Contains(err.Error(), urlguard.ErrBlockedAddress.Error()) {
			result.Verdict = Blocked
			result.Reason = "That address points inside a private network."
			result.TTL = time.Hour
			return result
		}
		result.Reason = "We couldn't reach that site."
		result.TTL = 30 * time.Minute
		logx.From(ctx).Info("preview probe could not reach the site",
			"host", normalised.Host, "error", err)
		return result
	}
	defer func() {
		_, _ = io.Copy(io.Discard, io.LimitReader(resp.Body, 4<<10))
		_ = resp.Body.Close()
	}()

	result.StatusCode = resp.StatusCode
	if resp.StatusCode >= 400 {
		result.Reason = fmt.Sprintf("That page returned %d.", resp.StatusCode)
		result.TTL = time.Hour
		return result
	}

	// The framing decision.
	if blocked, header, reason := p.framingRefused(resp.Header); blocked {
		result.Verdict = Blocked
		result.BlockedBy = header
		result.Reason = reason
		result.TTL = 12 * time.Hour
		return result
	}

	result.Verdict = Allowed
	result.Title = readTitle(resp.Body, 64<<10)
	result.TTL = 12 * time.Hour
	return result
}

// framingRefused reads the two headers that decide whether a page may be
// framed.
//
// CSP takes precedence over X-Frame-Options where both are present, which is
// what browsers do. A site that names our origin in frame-ancestors is
// honoured as permission.
func (p *Prober) framingRefused(headers http.Header) (bool, string, string) {
	for _, raw := range headers.Values("Content-Security-Policy") {
		directive, found := frameAncestors(raw)
		if !found {
			continue
		}
		if p.frameAncestorsAllowUs(directive) {
			return false, "", ""
		}
		return true, "Content-Security-Policy",
			"This site's security policy doesn't allow it to be shown inside another page."
	}

	switch strings.ToLower(strings.TrimSpace(headers.Get("X-Frame-Options"))) {
	case "":
	case "deny":
		return true, "X-Frame-Options",
			"This site asks not to be shown inside another page."
	case "sameorigin":
		return true, "X-Frame-Options",
			"This site can only be shown inside its own pages."
	default:
		// ALLOW-FROM is obsolete and ignored by modern browsers; an
		// unrecognised value is treated as a refusal rather than guessed at.
		return true, "X-Frame-Options",
			"This site restricts where it can be shown."
	}
	return false, "", ""
}

// frameAncestors extracts the directive's source list.
func frameAncestors(policy string) (string, bool) {
	for _, directive := range strings.Split(policy, ";") {
		directive = strings.TrimSpace(directive)
		lowered := strings.ToLower(directive)
		if lowered == "frame-ancestors" {
			// Present with no sources is the same as 'none'.
			return "", true
		}
		if strings.HasPrefix(lowered, "frame-ancestors ") {
			return strings.TrimSpace(directive[len("frame-ancestors "):]), true
		}
	}
	return "", false
}

// frameAncestorsAllowUs reports whether a source list permits our origin.
func (p *Prober) frameAncestorsAllowUs(sources string) bool {
	if sources == "" {
		return false
	}
	for _, source := range strings.Fields(sources) {
		lowered := strings.ToLower(strings.Trim(source, "'\""))
		switch lowered {
		case "none":
			return false
		case "*", "https:":
			return true
		case "self":
			continue
		}
		if p.appOrigin != "" && originMatches(lowered, p.appOrigin) {
			return true
		}
	}
	return false
}

// originMatches compares a CSP source against our origin, handling the
// wildcard host form (*.averix.dev).
func originMatches(source, origin string) bool {
	origin = strings.ToLower(origin)
	originHost := origin
	if idx := strings.Index(origin, "://"); idx >= 0 {
		originHost = origin[idx+3:]
	}

	sourceHost := source
	if idx := strings.Index(source, "://"); idx >= 0 {
		sourceHost = source[idx+3:]
		// The schemes must be equal, not merely prefixes of one another:
		// "http" is a prefix of "https", so a prefix test read a CSP naming
		// http://averix.example as permission for our https origin.
		originScheme := ""
		if originIdx := strings.Index(origin, "://"); originIdx >= 0 {
			originScheme = origin[:originIdx]
		}
		if source[:idx] != originScheme {
			return false
		}
	}
	sourceHost = strings.TrimSuffix(sourceHost, "/")

	if strings.HasPrefix(sourceHost, "*.") {
		suffix := sourceHost[1:]
		return strings.HasSuffix(originHost, suffix)
	}
	return sourceHost == originHost
}

// readTitle pulls the <title> out of the start of a document.
//
// Bounded and tag-only: the body is never parsed as HTML, stored, or shown as
// anything but plain text, so a hostile page cannot inject anything through it.
func readTitle(body io.Reader, limit int64) string {
	raw, err := io.ReadAll(io.LimitReader(body, limit))
	if err != nil || len(raw) == 0 {
		return ""
	}
	lowered := strings.ToLower(string(raw))
	start := strings.Index(lowered, "<title")
	if start < 0 {
		return ""
	}
	open := strings.Index(lowered[start:], ">")
	if open < 0 {
		return ""
	}
	start += open + 1
	end := strings.Index(lowered[start:], "</title")
	if end < 0 {
		return ""
	}

	title := strings.TrimSpace(string(raw[start : start+end]))
	// Collapse whitespace and drop anything that is not printable, so the
	// address bar cannot be used to smuggle control characters.
	var b strings.Builder
	lastSpace := false
	for _, r := range title {
		switch {
		case r < 0x20 || r == 0x7f:
			continue
		case r == ' ' || r == '\t':
			if !lastSpace && b.Len() > 0 {
				b.WriteByte(' ')
				lastSpace = true
			}
		default:
			b.WriteRune(r)
			lastSpace = false
		}
	}
	out := strings.TrimSpace(b.String())
	if len(out) > 160 {
		out = out[:160]
	}
	return out
}

// ── The frame's attributes ──────────────────────────────────────────────────

// Frame is what the web app needs to render the in-app browser.
//
// The sandbox is assembled here rather than in the client so it cannot be
// loosened by a front-end change: an embedded page gets scripts (or it is not
// a preview of anything) and nothing else.
type Frame struct {
	URL     string  `json:"url"`
	Host    string  `json:"host"`
	Verdict Verdict `json:"verdict"`
	Title   string  `json:"title,omitempty"`
	Reason  string  `json:"reason,omitempty"`

	// The iframe attributes. Absent when the verdict is not "allowed".
	Sandbox           string `json:"sandbox,omitempty"`
	Referrer          string `json:"referrer_policy,omitempty"`
	PermissionsPolicy string `json:"permissions_policy,omitempty"`
	CSP               string `json:"csp,omitempty"`

	// Device widths the viewer offers. These resize the preview viewport only.
	Devices []Device `json:"devices,omitempty"`
}

type Device struct {
	Key   string `json:"key"`
	Label string `json:"label"`
	Width int    `json:"width"`
	// Zero means "fill the available height".
	Height int `json:"height,omitempty"`
}

// Devices are the widths the preview offers, matching the breakpoints the rest
// of the product is designed around.
var Devices = []Device{
	{Key: "mobile", Label: "Mobile", Width: 390, Height: 844},
	{Key: "tablet", Label: "Tablet", Width: 768, Height: 1024},
	{Key: "desktop", Label: "Desktop", Width: 1280},
}

// BuildFrame turns a probe result into render instructions.
func BuildFrame(result Result) Frame {
	frame := Frame{
		URL:     result.URL,
		Host:    result.Host,
		Verdict: result.Verdict,
		Title:   result.Title,
		Reason:  result.Reason,
	}
	if result.Verdict != Allowed {
		return frame
	}

	// allow-scripts is unavoidable: a preview of a site with no scripts is not
	// a preview of the site. Everything else is withheld.
	//
	// allow-same-origin is deliberately absent, which is the important one:
	// with it, a same-origin embedded page could reach into the parent
	// document and read a session. Without it the frame is an opaque origin
	// with no access to AVERIX at all.
	//
	// allow-popups, allow-top-navigation, allow-forms, allow-modals,
	// allow-downloads and allow-storage-access-by-user-activation are all
	// absent so an embedded page cannot navigate the visitor away, phish them
	// with a form, or start a download.
	frame.Sandbox = "allow-scripts allow-popups-to-escape-sandbox"
	// The embedded site learns that it was opened from AVERIX, not which
	// profile or project the visitor was looking at.
	frame.Referrer = "strict-origin"
	// No camera, microphone, location, payment or USB inside a preview.
	frame.PermissionsPolicy = "accelerometer=(), camera=(), display-capture=(), " +
		"encrypted-media=(), geolocation=(), gyroscope=(), magnetometer=(), " +
		"microphone=(), midi=(), payment=(), usb=(), xr-spatial-tracking=()"
	// A CSP on the frame element itself, so the embedded document cannot
	// escape into a top-level navigation even if the sandbox were relaxed.
	frame.CSP = "sandbox allow-scripts allow-popups-to-escape-sandbox"
	frame.Devices = Devices
	return frame
}
