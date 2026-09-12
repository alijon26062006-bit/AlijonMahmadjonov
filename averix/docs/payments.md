# Payments without a gateway

AVERIX is not a payment institution, does not hold funds, and makes no escrow
claim. What it owns is the ledger: what was asked for, what actually moved, and
what a developer has earned.

This deployment runs the **manual provider**: the money moves by bank transfer
between the two people, and an administrator confirms it. That is a real
workflow, not a placeholder — and everything the product says about it is
worded to match.

## The seam

`payments.Provider` is the only thing the rest of the product talks to:

```go
CreatePayment(ctx, Request) (Result, error)
GetStatus(ctx, Intent) (Result, error)
Release(ctx, Intent) (Result, error)
Refund(ctx, Intent, amountMinor, reason) (Result, error)
GetTransaction(ctx, providerRef) (Transaction, error)
```

Nothing above it knows which provider is in use. Adding Stripe, Paddle or a
local gateway later is a new file in `internal/payments` plus credentials —
not a change to contracts, milestones or the workspace. A provider also
declares its **capabilities**, and the product only says what the capabilities
support: the manual provider does not declare `hold`, so nothing in the
interface calls it escrow.

## The flow, end to end

1. **The client funds a milestone.** `POST /api/v1/milestones/{id}/fund`
   records an intent and returns the transfer details plus a payment
   reference. The amount comes from the milestone, never from the request. The
   milestone does **not** move — the status reads "Waiting for your transfer".
2. **The client transfers the money** to the account shown, quoting the
   reference.
3. **An administrator confirms it.** `POST /api/v1/admin/payments/{id}/confirm`
   with the exact amount and the bank reference. Only then does the milestone
   become `funded` and the contract become `active`. A wrong amount is refused,
   not rounded away. A second confirmation of the same transfer is refused too.
   If nothing arrives, `…/reject` fails it with a reason the client reads.
4. **The developer works**, submits, the client approves.
5. **Approval queues a payout** — it does not pay. The developer sees it as
   *pending*: earned, not yet received.
6. **An administrator sends the money and confirms it** with
   `…/confirm-payout`, for the net amount (milestone less the platform fee).
   That writes three ledger lines — earning, fee, payout — and only then is the
   milestone `released`.

Approving work and paying for it stay separate events on purpose: that gap is
where a dispute fits.

## What stops this being abused

- **Only an administrator confirms money.** `payment.manage` for incoming
  transfers, `payment.release` for outgoing ones — separate permissions,
  because taking money in and sending it out are different powers.
- **Every confirmation is audited** with the actor, the amount and the bank
  reference. With no gateway to check against, that record is the only
  evidence there is, so it is written before anything else happens and is
  never editable.
- **Amounts are checked against the intent.** Confirming the wrong line of a
  bank statement is stopped by the figure rather than by luck.
- **Confirmation is a single-shot state move.** The expected status is part of
  the `UPDATE`'s `WHERE` clause, so two administrators clicking at the same
  moment cannot fund a milestone twice.
- **Funding is idempotent.** The key is derived from the milestone, so a
  double-clicked button, a retry and a refreshed page all land on one charge.
- **No party can declare their own money received or paid.** There is no
  release endpoint at all; the only path to `released` is a confirmed payout.
- **The ledger is serialised per user and currency** with an advisory lock, so
  two concurrent releases cannot both read the same balance and write two rows
  claiming the same total.
- **A developer's balance is private.** There is one endpoint, `/me/balance`,
  and it only ever returns the caller's own. Nothing about earnings appears on
  a public profile.

## Setting it up

An administrator fills in the transfer details once, in the admin panel
(`PUT /api/v1/admin/payments/manual-details`): account name, account number or
an IBAN/SWIFT/card/wallet pair, bank name, and an optional note. Until they
do, the provider reports itself unconfigured and funding answers
`503 payments_not_configured` with an explanation — the product never asks
anyone to send money nowhere, and never pretends a milestone was funded.

The details live in platform settings rather than environment variables,
because a bank account changes as an operational act by a person with an admin
session, not as a redeployment.

## Fees

The platform fee comes from `fee_schedules` (10% by default, 8% above $2,000,
6% above $10,000) and is **frozen onto the contract at signature**. Changing
the schedule later never rewrites a signed deal. All arithmetic is on integer
minor units with an explicit currency; a float percentage of money is how
rounding errors become accounting disputes.

## When a gateway is added

The webhook endpoint already exists: `POST /api/v1/payments/webhook/{provider}`.
It reads the raw body (a signature is computed over the bytes that arrived, so
nothing is re-encoded first), verifies it through the provider's own
`VerifyWebhook`, and records **every** delivery — verified or not — before
anything acts on it. A replay is then a no-op against the unique event id, and
a run of rejected signatures is visible rather than silently dropped. A
provider with no callbacks, like the manual one, answers "this provider does
not send webhooks" instead of accepting a body and pretending to process it.
