# External content: portfolio links and the in-app preview

AVERIX shows work that lives on other people's servers. A developer's portfolio
carries live links, and a client can open one without leaving the product. That
means two different trust problems, and they are solved in two different
places.

| Question | Answered by | Where |
| --- | --- | --- |
| May we **store and render** this URL as a link? | `urlguard.Normalise` | `internal/platform/urlguard` |
| May the **server fetch** this URL? | `urlguard.SafeDialerFor`, at connect time | `internal/platform/urlguard` |
| May the **browser frame** this page, and with what? | `preview.Prober` / `preview.BuildFrame` | `internal/preview` |

## 1. Storing a URL

Every URL a user types — `project_url`, `repository_url`, each extra link —
goes through `Normalise` before it reaches the database. It refuses:

- any scheme but `https` (and `http` in development): `javascript:`, `data:`,
  `vbscript:`, `file:`, `blob:`, `ws:`, `ftp:` and the rest of the list are
  rejected by name, including the `scheme:no-slashes` spelling;
- control characters and whitespace inside the URL, which is how scheme
  filters get bypassed (`java\tscript:`);
- credentials in the authority (`https://trusted.com@evil.example`);
- the cloud metadata endpoints, in **every** environment;
- private, loopback, link-local, CGNAT, multicast and reserved IP literals;
- private-network suffixes (`.internal`, `.corp`, `.lan`, `.local`, …);
- single-label hosts, and well-known service ports (SSH, SMTP, PostgreSQL,
  Redis, …).

It then rebuilds the URL from the validated parts: punycode host, lowercased,
default port dropped, fragment discarded. The host is stored separately because
the preview's address bar and the frame-ancestors comparison both need it.

**Development is narrower than it looks.** `AllowLoopback` permits `localhost`,
`127.0.0.1`, `::1` and `*.localhost` — nothing else. Private ranges and
intranet names stay refused even locally, so the development flag cannot widen
into an SSRF against the host's own network.

## 2. Fetching a URL

One thing in the product makes an outbound request to a user-supplied address:
the preview prober, checking whether a developer's own stored link can be
framed. There is deliberately **no endpoint that takes a URL in the body and
fetches it** — `POST /portfolio/{id}/check-url` probes only what the developer
already saved, and it is rate limited to 20 an hour.

The address check that matters happens in `net.Dialer.Control`, after DNS, on
the socket's real peer. A name that resolved to a public address a moment ago
can resolve to `127.0.0.1` now, deliberately (DNS rebinding) or by accident
(a CNAME). Checking the dialled IP closes that window; the metadata addresses
are refused there too, whatever the options say. Redirects are followed at most
four hops and every hop is re-validated. TLS verification stays on: a site with
a broken certificate is not one to embed, and turning verification off would
make the verdict meaningless.

## 3. Framing a page

`Probe` does a GET (not a HEAD — too many sites answer HEAD differently) and
reads the framing headers. `Content-Security-Policy: frame-ancestors` takes
precedence over `X-Frame-Options`, because that is what browsers do. A site
that names our origin in `frame-ancestors` is honoured as permission; scheme
comparison is exact, so `http://averix.dev` does not match an `https`
origin.

**A refusal is final.** If a site sends `X-Frame-Options: DENY` or a
`frame-ancestors` that excludes us, the verdict is `blocked` and the API
returns a frame with no attributes at all. Nothing in the product attempts a
workaround — no server-side proxying of the page, no header stripping. The
client shows the developer's own screenshot and a button that opens the site in
a new tab. The developer, and only the developer, sees the reason.

When the verdict is `allowed`, the server — not the front end — decides the
frame's permissions:

```
sandbox            allow-scripts allow-popups-to-escape-sandbox
referrerpolicy     strict-origin
allow (permissions) camera=(), geolocation=(), microphone=(), payment=(), usb=(), …
csp                sandbox allow-scripts allow-popups-to-escape-sandbox
```

`allow-same-origin` is **absent**, and that is the important one: with it, an
embedded page served from our own origin could reach into the parent document
and read a session. Without it the frame is an opaque origin with no access to
AVERIX — no tokens, no cookies, no parent DOM. `allow-top-navigation`,
`allow-forms`, `allow-modals` and `allow-downloads` are absent too, so an
embedded page cannot navigate the visitor away, phish them with a form, or
start a download.

The device buttons (Mobile 390, Tablet 768, Desktop 1280) resize the preview
viewport only.

### Caching

A verdict is stored on the project row with the time it was taken and trusted
for 24 hours, so opening a popular profile does not re-probe. Changing the URL
clears the verdict: the old answer described a different site.

## 4. Screenshots

Uploads are typed from their magic bytes only — never the filename, the
extension or the browser's `Content-Type`, all three of which are recorded and
ignored. The upload is then **decoded and re-encoded** into the sizes the
product renders (480 / 960 / 1920 in WebP and JPEG), which is both a
compression decision and a security one: a trailing payload, an odd colour
profile or EXIF with a home address does not survive a re-encode. Storage keys
are random and never derived from the filename, so an upload called
`../../etc/passwd` or `avatar.php.jpg` cannot influence where it is written or
what it is served as.

Objects are served with `X-Content-Type-Options: nosniff`, a
`default-src 'none'; sandbox` CSP, and `Content-Disposition: attachment` for
anything that is not an image.

## 5. What a visitor may see

A portfolio item is the developer's own claim, and the API labels it
`kind: "portfolio"`. A finished AVERIX contract is the platform's claim and
lives in a different table with a unique key on the contract, so a verified
entry cannot be fabricated. The two are never merged.

Drafts, hidden and rejected items answer 404 rather than 403 — a refusal that
confirms the id exists is itself a disclosure, and the same rule is why another
developer changing the id in the URL gets 404 on every write path.

Money follows the visibility ladder, resolved **on the server**:

| `value_visibility` | A visitor sees |
| --- | --- |
| `public` | the exact figure |
| `range` | a band, e.g. `$1,000–$2,500` |
| `private` | `Private contract` — the work happened, the figure is withheld |
| `hidden` | nothing |

The raw `value_minor` is serialised only for the owner, because they have to
edit it. A developer's balance and earnings are never part of any public
response.
