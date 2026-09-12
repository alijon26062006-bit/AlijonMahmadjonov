// Package urlguard normalises and validates the external URLs developers put on
// their portfolio, and decides whether the backend may fetch one.
//
// Two separate questions, deliberately kept apart:
//
//	Normalise  — is this URL safe to store and to render as a link or an iframe?
//	Resolve    — is this URL safe for the server to fetch?
//
// The second is much stricter. A hostname that passes the first can still
// resolve to 127.0.0.1 or 169.254.169.254, so anything the backend fetches is
// checked again at connection time against the address actually dialled. That
// closes the DNS-rebinding hole that a name-only check leaves open.
package urlguard

import (
	"context"
	"errors"
	"fmt"
	"net"
	"net/url"
	"strings"
	"time"
	"unicode"

	"golang.org/x/net/idna"
)

// Result is a URL that passed normalisation.
type Result struct {
	// Canonical form, safe to store and to hand to the browser.
	URL string
	// Registrable host, lowercased and punycode-encoded. Shown in the preview
	// browser's address bar.
	Host string
	Port string
	// True when the host is a literal IP rather than a name.
	IsIPLiteral bool
}

type Rejection struct {
	Code   string
	Reason string
	// Why the check failed, in engineering terms. Logged, never shown.
	Detail string
}

func (r *Rejection) Error() string {
	if r.Detail != "" {
		return r.Code + ": " + r.Reason + " (" + r.Detail + ")"
	}
	return r.Code + ": " + r.Reason
}

func reject(code, reason string) *Rejection { return &Rejection{Code: code, Reason: reason} }

func rejectDetail(code, reason, detail string) *Rejection {
	return &Rejection{Code: code, Reason: reason, Detail: detail}
}

// Human returns a message safe to show a developer editing their portfolio.
func (r *Rejection) Human() string { return r.Reason }

// Options tunes normalisation for the environment.
type Options struct {
	// Allow http:// as well as https://. Off outside development: a portfolio
	// link is public-facing and a plain-HTTP page cannot be framed from an
	// HTTPS app anyway.
	AllowInsecure bool
	// Allow localhost and private ranges. Development only.
	AllowLoopback bool
	MaxLength     int
}

func DefaultOptions() Options { return Options{MaxLength: 2048} }

func DevelopmentOptions() Options {
	return Options{AllowInsecure: true, AllowLoopback: true, MaxLength: 2048}
}

// Schemes that are never acceptable, whatever else is true. javascript: and
// data: would execute in the visitor's context; the rest reach the local
// machine or a legacy protocol nobody should be linking to from a portfolio.
var deniedSchemes = map[string]struct{}{
	"javascript": {}, "data": {}, "vbscript": {}, "file": {}, "blob": {},
	"about": {}, "chrome": {}, "chrome-extension": {}, "resource": {},
	"filesystem": {}, "ftp": {}, "sftp": {}, "gopher": {}, "ldap": {},
	"ldaps": {}, "dict": {}, "tftp": {}, "telnet": {}, "ssh": {},
	"jar": {}, "mailto": {}, "tel": {}, "sms": {}, "intent": {},
	"ws": {}, "wss": {},
}

// Hostnames that reach the machine itself. Allowed only when the caller opts
// in (development, previewing a project on localhost).
var loopbackHosts = map[string]struct{}{
	"localhost": {}, "localhost.localdomain": {}, "ip6-localhost": {},
	"ip6-loopback": {},
}

// Hostnames that are never acceptable, in any environment. These are the cloud
// metadata endpoints — there is no development scenario where a portfolio link
// should point at one, and reaching them is how an SSRF becomes stolen
// infrastructure credentials.
var alwaysDeniedHosts = map[string]struct{}{
	"metadata": {}, "metadata.google.internal": {}, "instance-data": {},
	"metadata.goog": {}, "169.254.169.254": {}, "fd00:ec2::254": {},
}

// Suffixes that only resolve inside a private network.
var deniedSuffixes = []string{
	".localhost", ".local", ".internal", ".intranet", ".corp", ".home",
	".lan", ".private", ".test", ".example", ".invalid", ".onion",
}

// Normalise validates and canonicalises a user-supplied URL.
func Normalise(raw string, opts Options) (Result, error) {
	if opts.MaxLength == 0 {
		opts.MaxLength = 2048
	}
	raw = strings.TrimSpace(raw)
	if raw == "" {
		return Result{}, reject("empty", "Enter a URL.")
	}
	if len(raw) > opts.MaxLength {
		return Result{}, reject("too_long",
			fmt.Sprintf("That URL is longer than %d characters.", opts.MaxLength))
	}
	// Control characters and whitespace inside a URL are how scheme filters get
	// bypassed ("java\tscript:"), so they are rejected before parsing.
	for _, r := range raw {
		if r < 0x20 || r == 0x7f || unicode.IsSpace(r) {
			return Result{}, reject("control_characters",
				"That URL contains characters that aren't allowed.")
		}
	}
	// A bare "example.com" is what people actually type; assume https rather
	// than failing, but never assume a scheme for something that has one.
	if !strings.Contains(raw, "://") {
		if i := strings.Index(raw, ":"); i >= 0 && i < 12 {
			// "javascript:alert(1)" — has a scheme, just not one with a slash.
			scheme := strings.ToLower(raw[:i])
			if _, denied := deniedSchemes[scheme]; denied {
				return Result{}, reject("scheme_not_allowed",
					"Only https:// links can be added here.")
			}
		}
		raw = "https://" + raw
	}

	u, err := url.Parse(raw)
	if err != nil {
		return Result{}, reject("unparseable", "That doesn't look like a valid URL.")
	}

	scheme := strings.ToLower(u.Scheme)
	if _, denied := deniedSchemes[scheme]; denied {
		return Result{}, reject("scheme_not_allowed", "Only https:// links can be added here.")
	}
	switch scheme {
	case "https":
	case "http":
		if !opts.AllowInsecure {
			return Result{}, reject("insecure_scheme",
				"Use an https:// address — plain http isn't accepted.")
		}
	default:
		return Result{}, reject("scheme_not_allowed", "Only https:// links can be added here.")
	}

	// Credentials in a URL are a phishing vector: https://trusted.com@evil.com
	// reads as trusted to a human and resolves to evil.com.
	if u.User != nil {
		return Result{}, reject("credentials_in_url",
			"Remove the username and password from the URL.")
	}

	host := u.Hostname()
	if host == "" {
		return Result{}, reject("no_host", "That URL is missing a domain name.")
	}

	// Punycode, so a Unicode homograph cannot masquerade as an ASCII domain.
	ascii, err := idna.Lookup.ToASCII(host)
	if err != nil {
		return Result{}, reject("invalid_host", "That domain name isn't valid.")
	}
	host = strings.ToLower(strings.TrimSuffix(ascii, "."))

	if _, denied := alwaysDeniedHosts[host]; denied {
		return Result{}, reject("host_not_allowed",
			"Local and internal addresses can't be used for a public project link.")
	}
	if !opts.AllowLoopback {
		if _, denied := loopbackHosts[host]; denied {
			return Result{}, reject("host_not_allowed",
				"Local and internal addresses can't be used for a public project link.")
		}
		for _, suffix := range deniedSuffixes {
			if strings.HasSuffix(host, suffix) {
				return Result{}, reject("host_not_allowed",
					"That address only resolves on a private network.")
			}
		}
	}

	isIP := false
	if ip := net.ParseIP(host); ip != nil {
		isIP = true
		if !opts.AllowLoopback {
			if why := classifyIP(ip); why != "" {
				return Result{}, rejectDetail("ip_not_allowed",
					"That IP address isn't reachable from the public internet.", why)
			}
		}
	} else if !strings.Contains(host, ".") {
		// A single-label host is an intranet name, not a public site — except
		// when the caller has allowed loopback, where "localhost" is the point.
		if !opts.AllowLoopback {
			return Result{}, reject("invalid_host",
				"Enter a full domain name, for example project.example.com.")
		}
	} else if !validHostname(host) {
		return Result{}, reject("invalid_host", "That domain name isn't valid.")
	}

	port := u.Port()
	if port != "" {
		if !allowedPort(port, scheme) {
			return Result{}, reject("port_not_allowed",
				"Only the standard web ports can be used.")
		}
	}

	// Rebuild from validated parts rather than trusting the input string; a
	// fragment is dropped because it is never meaningful server-side.
	clean := &url.URL{
		Scheme:   scheme,
		Host:     u.Host,
		Path:     u.EscapedPath(),
		RawQuery: u.RawQuery,
	}
	if clean.Path == "" {
		clean.Path = "/"
	}
	if isIP && strings.Contains(host, ":") {
		clean.Host = "[" + host + "]"
		if port != "" {
			clean.Host += ":" + port
		}
	} else {
		clean.Host = host
		if port != "" {
			clean.Host += ":" + port
		}
	}

	return Result{
		URL:         clean.String(),
		Host:        host,
		Port:        port,
		IsIPLiteral: isIP,
	}, nil
}

func allowedPort(port, scheme string) bool {
	switch port {
	case "80", "443", "8080", "8443", "3000":
		return true
	}
	return false
}

func validHostname(host string) bool {
	if len(host) > 253 {
		return false
	}
	for _, label := range strings.Split(host, ".") {
		if len(label) == 0 || len(label) > 63 {
			return false
		}
		if label[0] == '-' || label[len(label)-1] == '-' {
			return false
		}
		for i := 0; i < len(label); i++ {
			c := label[i]
			isAlnum := (c >= 'a' && c <= 'z') || (c >= '0' && c <= '9')
			if !isAlnum && c != '-' {
				return false
			}
		}
	}
	// The TLD must be alphabetic.
	labels := strings.Split(host, ".")
	tld := labels[len(labels)-1]
	if len(tld) < 2 {
		return false
	}
	for i := 0; i < len(tld); i++ {
		if tld[i] < 'a' || tld[i] > 'z' {
			return false
		}
	}
	return true
}

// Ranges that must never be reachable from a server-side fetch. The cloud
// metadata endpoints are the ones that turn an SSRF into stolen credentials.
var blockedNets = func() []*net.IPNet {
	cidrs := []string{
		"0.0.0.0/8",          // "this host on this network"
		"10.0.0.0/8",         // RFC1918 private
		"100.64.0.0/10",      // carrier-grade NAT
		"127.0.0.0/8",        // loopback
		"169.254.0.0/16",     // link-local, incl. 169.254.169.254 metadata
		"172.16.0.0/12",      // RFC1918 private
		"192.0.0.0/24",       // IETF protocol assignments
		"192.0.2.0/24",       // documentation
		"192.88.99.0/24",     // 6to4 relay anycast
		"192.168.0.0/16",     // RFC1918 private
		"198.18.0.0/15",      // benchmarking
		"198.51.100.0/24",    // documentation
		"203.0.113.0/24",     // documentation
		"224.0.0.0/4",        // multicast
		"240.0.0.0/4",        // reserved
		"255.255.255.255/32", // broadcast
		"::/128",             // unspecified
		"::1/128",            // loopback
		// ::ffff:0:0/96 is deliberately absent: net.IPNet.Contains folds an
		// IPv4-mapped network into 4-byte form, where its /96 mask becomes
		// 0.0.0.0/0 and matches every address on the internet. IPv4-mapped
		// addresses are handled by the To4() normalisation below instead, so
		// ::ffff:127.0.0.1 is judged as 127.0.0.1 against 127.0.0.0/8.
		"64:ff9b::/96",  // NAT64
		"100::/64",      // discard-only
		"2001:db8::/32", // documentation
		"fc00::/7",      // unique local
		"fe80::/10",     // link-local
		"ff00::/8",      // multicast
	}
	out := make([]*net.IPNet, 0, len(cidrs))
	for _, c := range cidrs {
		if _, n, err := net.ParseCIDR(c); err == nil {
			out = append(out, n)
		}
	}
	return out
}()

// classifyIP returns a reason when an address must not be dialled.
func classifyIP(ip net.IP) string {
	if ip == nil {
		return "unparseable address"
	}
	if ip.IsLoopback() {
		return "loopback address"
	}
	if ip.IsPrivate() {
		return "private address"
	}
	if ip.IsLinkLocalUnicast() || ip.IsLinkLocalMulticast() {
		return "link-local address"
	}
	if ip.IsUnspecified() {
		return "unspecified address"
	}
	if ip.IsMulticast() || ip.IsInterfaceLocalMulticast() {
		return "multicast address"
	}
	// An IPv4-mapped IPv6 address must be judged as the IPv4 address it carries.
	if v4 := ip.To4(); v4 != nil {
		ip = v4
	}
	for _, n := range blockedNets {
		if n.Contains(ip) {
			return "reserved range " + n.String()
		}
	}
	return ""
}

// IsPublicIP reports whether an address is safe for the server to connect to.
func IsPublicIP(ip net.IP) bool { return classifyIP(ip) == "" }

var ErrBlockedAddress = errors.New("address is not publicly routable")

// SafeDialer builds a net.Dialer whose Control hook re-checks the address that
// is actually about to be dialled.
//
// This is the part that matters. A hostname validated a moment ago can resolve
// to a private address now — deliberately, in a rebinding attack, or by
// accident through a CNAME. Checking in Control means the verdict is made on
// the socket's real peer, after DNS, with no window in between.
func SafeDialer(timeout time.Duration) *net.Dialer {
	return &net.Dialer{
		Timeout: timeout,
		Control: func(network, address string, _ syscallRawConn) error {
			host, _, err := net.SplitHostPort(address)
			if err != nil {
				return fmt.Errorf("%w: cannot parse %q", ErrBlockedAddress, address)
			}
			ip := net.ParseIP(host)
			if ip == nil {
				return fmt.Errorf("%w: %q is not an IP address", ErrBlockedAddress, host)
			}
			if why := classifyIP(ip); why != "" {
				return fmt.Errorf("%w: %s is a %s", ErrBlockedAddress, ip, why)
			}
			return nil
		},
	}
}

// ResolvePublic checks that every address a hostname resolves to is public.
// Used as an early, cheap rejection; SafeDialer remains the authority.
func ResolvePublic(ctx context.Context, host string) error {
	resolveCtx, cancel := context.WithTimeout(ctx, 3*time.Second)
	defer cancel()

	addrs, err := net.DefaultResolver.LookupIPAddr(resolveCtx, host)
	if err != nil {
		return fmt.Errorf("resolve %s: %w", host, err)
	}
	if len(addrs) == 0 {
		return fmt.Errorf("%w: %s resolved to nothing", ErrBlockedAddress, host)
	}
	for _, a := range addrs {
		if why := classifyIP(a.IP); why != "" {
			return fmt.Errorf("%w: %s resolves to %s (%s)", ErrBlockedAddress, host, a.IP, why)
		}
	}
	return nil
}
