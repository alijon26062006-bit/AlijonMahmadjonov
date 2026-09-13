# Identity verification: documents, who may look, and when they are deleted

A passport photograph is not an upload. It is the one thing on this platform
that, leaked, cannot be rotated, revoked or apologised away. Everything below
follows from that.

| Question | Answered by | Where |
| --- | --- | --- |
| Where do the images live? | a private prefix, random keys, no public URL | `internal/identity/store.go` |
| Who may open one? | a permission no role grants, plus a password typed again | `internal/security/rbac.go`, `internal/identity/service.go` |
| How does the browser get the bytes? | a ticket valid two minutes, for one reviewer | `Service.ViewToken`, `Service.Stream` |
| Who looked, and why? | `admin_access_logs`, written before the bytes are served | `Service.logAccess` |
| When do the images go away? | a retention date set by the decision | `Store.PurgeExpired`, the worker |

## 1. Storage

Documents go to their own prefix in the **private** bucket, under names made
of random bytes:

```
identity/3f/8c21…d0.jpg
```

The key contains no user id, so a leaked listing of object names tells an
attacker nothing about whose documents they are. They are never written to the
`files` table that everything else uses, never given a `PublicURL`, and never
handed to the CDN. `Cache-Control: no-store` is set on the object itself as
well as on every response that serves it.

The file's type is decided by **reading the bytes** (`imaging.Inspect`), never
from the filename or the browser's `Content-Type`. Anything that is not a JPEG,
PNG or WebP at least 300 pixels on its shortest side is refused.

## 2. Who may look

Two permissions exist for this, and **no role grants either of them**:

| Permission | What it allows |
| --- | --- |
| `identity_verification.view` | open a case and its images |
| `identity_verification.review` | approve, reject, ask for a new photograph |

They are handed to one account at a time, by name, from the user's page in the
admin panel (`admin_permission_grants`). Being an administrator is not enough;
being the person who wrote the code is not enough. Revoking takes effect on the
next request — the grant is read as part of resolving the session, not cached
in a token.

On top of the grant, every read of anything sensitive requires the reviewer to
type their password again. That unlock lives in Redis, keyed by **session**,
for ten minutes. A stolen session cookie on its own opens nothing.

```
POST /api/v1/admin/identity/unlock      { "password": "…" }
→ 200 { "unlocked_until": "2026-09-13T12:40:00Z" }
```

## 3. Getting the bytes into a browser

There are no signed object URLs and no permanent links. A reviewer asks for a
ticket per image, and says why:

```
POST /api/v1/admin/identity/documents/{id}/token   { "reason": "сверка имени" }
→ 201 { "token": "…", "url": "/api/v1/admin/identity/documents/{id}/file?t=…",
        "expires_at": "…" }
```

The ticket is bound to that reviewer, that signed-in session and that one
document, and it expires in **two minutes**. A URL copied out of the panel and
pasted into a message is useless: to the next person immediately, to everyone
two minutes later. It is not consumed on first use, because a viewer that zooms
or rotates re-requests the same bytes — it simply dies with the clock and with
the session.

The image response is built to survive nowhere:

```
Cache-Control: no-store, no-cache, must-revalidate, private
Pragma: no-cache
Content-Security-Policy: default-src 'none'; sandbox
Referrer-Policy: no-referrer
X-Content-Type-Options: nosniff
Content-Disposition: inline
```

The panel shows no thumbnails anywhere — a preview of a passport is still a
passport, and it would sit in the browser cache of every screen that merely
listed the case.

## 4. The record of who looked

`admin_access_logs` gets a row **before** the bytes are served: who, what,
when, from which address, and the reason the reviewer typed. Opening a case,
listing the queue, reading the log itself and every decision are all recorded
the same way. A reviewer who opened a passport and changed nothing still leaves
a trace.

Reading that log needs `audit.read` in addition to the identity permission: the
question "who has been looking at this person's documents" is itself a sensitive
one.

## 5. Decisions

Four of them, and each needs at least ten characters of explanation — the next
reviewer has to be able to see what this one checked:

| Action | Effect |
| --- | --- |
| `approve` | marks `users.identity_verified_at`, sets the retention date |
| `reject` | clears any verification mark, tells the person why |
| `request_resubmit` | names which photographs to retake, keeps the rest of the case |
| `suspend` | pauses the case without deciding it |

`request_resubmit` takes its reasons from a **closed list** (`ResubmitReasons`),
each tied to the images it is about. Free text alone produces "переснимите" with
no explanation of what was wrong; the closed list produces "лицевая сторона не в
фокусе" and a form that asks for exactly that one photograph again.

Nothing about a decision is automatic. No model, no heuristic and no scheduled
job ever approves, rejects, verifies or bans — those are acts of a person with a
name, recorded with it.

## 6. Retention

`identity.retention_days` (default **180**) is the number of days after a
decision that the raw images survive. The worker runs `PurgeExpired` hourly: it
deletes the object from the bucket, clears the storage key and marks the
document `deleted`. What remains is the decision, its reason, the history of the
case and the access log — enough to prove the check happened, without keeping
the thing that was checked.

Set the value to `0` to keep images until somebody deletes them by hand. That is
a deliberate choice an operator has to make; the default is not it.

## 7. What never leaves the server

- Document numbers and dates of birth are stored for matching against the
  profile, and are **not** returned to the panel. A reviewer compares the name
  on the image with the name on the profile.
- The user list, search results, public profiles, the sitemap and every other
  ordinary screen show at most `identity_status` — "подтверждена" or not. Never
  a number, never an image, never a payment destination.
- The staff chat (Telegram, optional) receives one line and a link into the
  panel. It cannot receive anything else: `identity.Chat` has no method that
  takes bytes, a storage key or a document id. A passport in a chat history
  cannot be deleted by this platform when the retention date arrives, so it
  never goes there in the first place. See `internal/telegram`.
  The chat id in `TELEGRAM_CHAT_ID` is a Telegram id — your own (a positive
  number, from @userinfobot) or a group's (usually negative). It is **not** the
  administrator of the site: that is an account with an email address, made
  with `averixctl create-admin`, and it has nothing to do with Telegram. If
  you point it at yourself, open your bot and press Start first — Telegram does
  not let a bot write to a person who never started it. `averixctl chat-test`
  sends one line and prints Telegram's own explanation when it does not arrive.
- Payment destinations are masked at the database query (`maskedInstrument`):
  a brand, the last four digits, a bank name. The platform stores no card
  number and no account number — there is no column for one — and never a CVV.

## 8. Testing what matters

`internal/identity/identity_integration_test.go` drives the real HTTP surface
and asserts the rules above rather than the implementation:

- an administrator without the grant is refused, the grant opens the door, and
  revoking it closes it again on the next request;
- a case carries no URL, no storage key and no `http` anywhere;
- the image endpoint refuses a request without a ticket, and refuses another
  reviewer's ticket;
- a decision without a reason is refused; asking for one photograph does not
  reset the case; approval verifies the account and notifies the person;
- retention deletes the images and keeps the decision.

If one of those tests starts failing, the fix is not in the test.
