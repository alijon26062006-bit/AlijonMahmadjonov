# Recon map: Calendly (web)

Scope: the core scheduling loop. The host sets availability and event types,
shares a link, a guest books a slot with no account, both get a confirmation,
and the guest can reschedule or cancel. Team scheduling, routing and AI
features are listed but kept out of v1.
For: a product to sell to small teams (default, not yet confirmed by the user)
Date: 2026-11-09

> **How this was gathered.** The session's network blocks calendly.com,
> help.calendly.com and developer.calendly.com, so no page was opened
> directly and no screenshots were taken. Everything below comes from web
> search results that quote Calendly's help center, developer docs and blog,
> plus third-party guides (marked as such). Screen layouts are inferred from
> those descriptions and **must be checked** against the user's own free
> Calendly account or public walkthrough videos before `/replica-design`.
> `replica/screens/` is empty for that reason.
>
> **Terms.** Calendly's terms of use were not read, because the host is
> blocked. Read them before using a Calendly account to study the product. If
> they forbid building a competitor with an account, work from public pages
> only.

## Sources

| # | source | URL | notes |
| --- | --- | --- | --- |
| 1 | help: event types overview | https://calendly.com/help/event-types-overview | kinds: one-on-one, group, collective, round robin |
| 2 | help: event types | https://calendly.com/help/event-types | location: in-person, phone, video, custom; invitee can choose |
| 3 | help: customize event types | https://calendly.com/help/how-to-customize-your-event-types | event type settings |
| 4 | help: fine-tune availability | https://calendly.com/help/how-to-fine-tune-your-availability-settings | date range (N days / range / indefinitely), minimum notice |
| 5 | help: meeting limits | https://calendly.com/help/how-to-set-meeting-limits.html | daily / weekly / monthly max per event type |
| 6 | help: buffers | https://calendly.com/help/how-to-use-buffers | before/after buffers per event type |
| 7 | help: availability overview | https://calendly.com/help/availability-overview | weekly hours, date-specific hours |
| 8 | help: set your availability | https://calendly.com/help/how-to-set-your-availability | availability page |
| 9 | help: cancel and reschedule links | https://calendly.com/help/how-to-include-cancel-and-reschedule-links-for-invitees | links in confirmation and reminder emails |
| 10 | help: cancellation policy | https://help.calendly.com/hc/en-us/articles/28926500961431 | policy is shown, not enforced |
| 11 | help: cancel a meeting | https://calendly.com/help/how-to-cancel-a-meeting | host cancels from the meetings page |
| 12 | help: confirmation page links | https://help.calendly.com/hc/en-us/articles/226767207 | custom confirmation page |
| 13 | help: workflows overview | https://calendly.com/help/workflows-overview | reminders and follow-ups, email and SMS |
| 14 | help: text messages in workflows | https://calendly.com/help/how-to-send-text-messages-with-workflows | SMS via Twilio, invitee opt-in, groups ≤100 |
| 15 | help: embed options overview | https://calendly.com/help/embed-options-overview | inline, pop-up widget, pop-up text |
| 16 | dev: embeds getting started | https://developer.calendly.com/api-docs/overview/embedding/getting-started | prefill, event listeners |
| 17 | dev: webhooks | https://developer.calendly.com/receive-data-from-scheduled-events-in-real-time-with-webhook-subscriptions | invitee.created, invitee.canceled, routing_form_submission.created |
| 18 | help: choose a plan | https://calendly.com/help/choose-the-right-calendly-plan-for-your-team | plan gating |
| 19 | 3rd party: pricing guide | https://zeeg.me/post/calendly-pricing | Free / Standard ~$10–12 / Teams ~$16–20 / Enterprise custom. Competitor's site, verify |
| 20 | 3rd party: API connector | https://learn.microsoft.com/en-us/connectors/calendlyv2 | scheduled event and invitee fields |
| 21 | 3rd party: webhook guide | https://hookdeck.com/webhooks/platforms/guide-to-calendly-webhooks-features-and-best-practices | no-show and event type webhooks (unverified) |
| 22 | community: daily cap across types | https://community.calendly.com/how-do-i-40/how-to-set-max-number-of-meetings-per-day-across-event-types-2031 | reportedly not available. A gap to fix |

## Pricing (what they gate)

From third-party guides (official page blocked, verify):

- **Free**: 1 event type, 1 calendar connection.
- **Standard** (~$10/seat/mo yearly, $12 monthly): unlimited event types,
  up to 6 calendars, workflows and reminders, collective events.
- **Teams** (~$16/seat/mo yearly, $20 monthly): round robin, admin, CRM
  integrations, routing.
- **Enterprise** (custom, reported from ~$15k/year): SSO, security, controls.

So the paid line is **more than one event type, more than one calendar, and
automated reminders**. That is what users pay for first.

## Core loop

A guest opens the host's link, picks a free time that already accounts for
the host's real calendar, and the meeting lands on both calendars with no
back-and-forth.

## Screens

| ID | screen | route / how to reach | purpose | key components | states seen |
| --- | --- | --- | --- | --- | --- |
| S01 | Sign up / log in | /signup, /login | create account, email or Google | form, OAuth button | filled, error (inferred) |
| S02 | Onboarding | after first sign up | connect calendar, set weekly hours, pick username | stepper, calendar provider buttons, hours editor | (inferred, verify) |
| S03 | Scheduling home: event types | main nav "Scheduling" | list event types, copy link, create new | event type cards, copy-link button, "+ Create" menu, kebab menu | empty (1 default), filled |
| S04 | Event type editor: details | S03 → card | name, duration, location(s), description, color, slug | text inputs, duration select, location picker (in-person, phone, video, custom) | new, edit, error |
| S05 | Event type editor: scheduling | S04 section | date range, minimum notice, buffers, daily/weekly/monthly max, start time increments, availability schedule | number + unit inputs, toggles, schedule select | defaults, edited |
| S06 | Event type editor: booking form & confirmation | S04 section | invitee questions, confirmation page (redirect or custom links), cancellation policy | question list builder, toggles | default (name, email), custom |
| S07 | Availability | main nav "Availability" | weekly hours, date-specific hours, multiple schedules, time zone | weekday rows with time ranges, + / copy, date override modal, calendar/list view | default 9–5 Mon–Fri, edited, unavailable day |
| S08 | Calendar connections | settings / availability | connect Google, Outlook, iCloud; choose calendars to check for conflicts; choose calendar to add events to | provider list, checkboxes, select | none connected, connected, error/reconnect |
| S09 | Public profile page | /{username} | list of the host's public event types | host name/avatar, event type list | one type, many, none public |
| S10 | Booking page: date and time | /{username}/{event-slug} | pick a date, then a time | event summary panel, month calendar with available dates, time slot list, time zone selector | loading, no slots this month, slots, past dates disabled |
| S11 | Booking page: details form | S10 → slot → Next | name, email, add guests, custom questions, location choice | form, back link | empty, validation error, submitting, slot just taken |
| S12 | Booking confirmed | after submit | confirms time, location, add to calendar | summary, calendar links, optional custom links | confirmed, redirect to external URL |
| S13 | Invitee cancel | email link | cancel with a reason | summary, reason textarea, cancel button | form, cancelled, already cancelled |
| S14 | Invitee reschedule | email link | pick a new time for the same booking | S10 layout with old time noted, reason | slots, no slots, done |
| S15 | Meetings | main nav "Meetings" | upcoming, past, date range; meeting detail; host cancel/reschedule; mark no-show | tabs, list grouped by day, expandable row, filters | empty, filled, cancelled shown |
| S16 | Workflows | main nav "Workflows" | reminders and follow-ups for event types | workflow list, editor: trigger (before/after), offset, action (email/SMS), recipient, template, event type picker | empty with templates, filled |
| S17 | Share / add to website | S03 kebab or share button | copy link, embed code (inline, pop-up widget, pop-up text) | link copy, embed type cards, code block, preview | default |
| S18 | Account settings & billing | avatar menu | profile, username, time zone, branding, plan and seats | forms, plan cards | free, paid, over limit (upgrade prompt) |

## Flows

```
F01 Host gets set up
    S01 sign up -> S02 connect calendar, hours, username -> S03 home with a default event type
    happy path clicks: ~6 (verify)
    edge: Google OAuth denied, calendar has no busy events, username taken

F02 Host creates an event type
    S03 + Create -> S04 details -> S05 scheduling -> S06 form -> save -> S03
    happy path clicks: ~5
    edge: duplicate slug, duration not divisible by increment, Free plan limit of 1 type

F03 Host shares the link
    S03 copy link (1 click) | S17 embed code
    edge: secret event type (not on S09)

F04 Guest books a meeting  ← the core loop
    S09 pick event type -> S10 pick date -> pick time -> Next -> S11 fill name, email -> Schedule -> S12
    happy path clicks: 5 from the profile, 4 from a direct event link (plus typing)
    edge: no slots this month, guest's time zone differs from host's, DST change inside the
          date range, slot taken while filling the form, double-click on submit,
          host calendar busy event added after page load, minimum notice cuts today off

F05 Guest cancels
    confirmation email -> S13 reason -> Cancel -> S13 cancelled; host notified, calendar event removed
    happy path clicks: 2
    edge: link used twice, meeting already in the past, cancellation policy shown but not enforced

F06 Guest reschedules
    confirmation email -> S14 pick date -> time -> confirm -> S12
    happy path clicks: 4
    edge: no slots, rescheduled meeting must replace, not duplicate, the calendar event

F07 Host cancels or reschedules
    S15 meeting row -> Cancel (reason) | Reschedule (send request to invitee)
    happy path clicks: 3
    edge: group event with many invitees

F08 Host changes availability
    S07 edit weekly hours | add date-specific hours -> auto-save
    edge: overnight ranges, overlapping ranges, override on a day with existing bookings

F09 Host adds a reminder
    S16 New workflow -> trigger "24h before" -> action email to invitee -> pick event types -> save
    happy path clicks: ~6
    edge: SMS needs invitee opt-in, booking made inside the reminder window

F10 Host embeds booking on a website
    S17 choose inline/pop-up -> copy code
    edge: prefilled name/email from the site, event listener for "booked"
```

## Components

| component | variants | states | used on |
| --- | --- | --- | --- |
| Button | primary, secondary, ghost, danger, link | default, hover, focus, disabled, loading | all |
| Text input / textarea | text, email, phone, number+unit | default, focus, error, disabled | S01, S04–S06, S11, S13 |
| Select / dropdown | single, with search (time zone) | open, closed, disabled | S04, S05, S07, S10 |
| Toggle / checkbox | | on, off, disabled | S05, S06, S08, S16 |
| Month calendar | booking (available dates bold, past disabled), override picker | loading, no availability, selected | S07, S10, S14 |
| Time slot button | | available, selected (expands to "Next"), hover | S10, S14 |
| Time zone selector | | auto-detected, changed | S07, S10, S14 |
| Time range row | weekday with 0–n ranges | unavailable, ranges, error overlap | S07 |
| Event type card | | active, off (disabled), secret | S03, S09 |
| Location picker | in-person, phone, video, custom, invitee chooses | | S04, S11 |
| Question builder | short text, long text, radio, checkboxes, phone | required, optional | S06 |
| Meeting row | upcoming, past, cancelled | collapsed, expanded | S15 |
| Tabs | | active, inactive | S15 |
| Modal | confirm, form | open, closed | S07, S15, S17 |
| Toast | success, error | | after save/copy |
| Side nav | | active item, collapsed (mobile) | host app |
| Copy-link button | | default, copied | S03, S17 |
| Code block | | | S17 |
| Empty state | per list | | S03, S15, S16 |

## Inferred data model

```
User            id, email, name, username (unique slug), timezone, avatar_url, plan
                evidence: S01, S09 profile URL, S18
                confidence: high

CalendarConnection  id, user_id, provider (google | outlook | icloud), external_account,
                    check_conflicts_calendar_ids[], write_calendar_id, status
                evidence: S08, help "availability overview" (check for conflicts, add to calendar, Free=1, paid up to 6)
                confidence: high

AvailabilitySchedule  id, user_id, name, timezone, is_default,
                      rules: weekly [{weekday, start, end}], date_overrides [{date, ranges[] | unavailable}]
                evidence: S07, help "date-specific hours"
                confidence: high

EventType       id, user_id, name, slug, kind (one_on_one | group | collective | round_robin),
                duration_min, locations (json: type + details), description, color, active, secret,
                schedule_id, buffer_before_min, buffer_after_min, min_notice_min,
                date_range (rolling_days | fixed_range | indefinite), slot_increment_min,
                max_per_day, max_per_week, max_per_month, max_invitees (group),
                questions (json), confirmation (json: redirect_url | links), cancellation_policy
                evidence: S04–S06, help "customize event types", "meeting limits", "buffers", "fine-tune availability"
                confidence: high for the fields, guess for names

ScheduledEvent  id, event_type_id, host_id, start_at, end_at, location (json), status (active | canceled),
                external_calendar_event_id, created_at
                evidence: API connector docs (uri, name, status, start_time, end_time, event_type)
                confidence: medium (status values not confirmed)

Invitee         id, scheduled_event_id, name, email, timezone, status, questions_and_answers (json),
                guests[], cancel_token, reschedule_token, rescheduled (bool), old_invitee_id,
                cancellation (reason, canceled_by), no_show (bool), sms_opt_in, phone
                evidence: API connector (questions_and_answers, cancel_url, rescheduled, status), S11, S13
                confidence: medium

Workflow        id, user_id, name, trigger (before_start | after_end | on_booking | on_cancel),
                offset_min, action (email | sms), recipient (invitee | host), subject, body, event_type_ids[]
                evidence: S16, help "workflows overview"
                confidence: medium (trigger names are a guess)

WebhookSubscription  id, user_id or org_id, url, events[], signing_key
                evidence: developer webhooks page
                confidence: high (could, not v1)

Payment         id, invitee_id, provider (stripe | paypal), amount_cents, currency, status
                evidence: pricing guides mention payments at booking
                confidence: guess
```

Relationships: User 1-n EventType, User 1-n AvailabilitySchedule, EventType n-1
AvailabilitySchedule, User 1-n CalendarConnection, EventType 1-n ScheduledEvent,
ScheduledEvent 1-n Invitee (1 for one-on-one, n for group), User 1-n Workflow,
Workflow n-n EventType, Invitee 0-1 Payment.

## Feature matrix

See `features.csv`. Must: 13, should: 12, could: 11, skip: 3.

## Out of scope (cannot or should not be cloned)

- **The integrations marketplace and partner deals** (CRMs, Salesforce,
  HubSpot listings). That is their partner network. Build integrations
  yourself through each provider's official API if needed.
- **Callie AI assistant and Notetaker add-ons**: paid AI add-ons, not part
  of the scheduling loop. Skip for v1.
- **Their brand**: the name, logo, blue, the word "Calendly" in URLs or
  copy. The public URL becomes `yourapp.com/{username}/{event}`.
- **Enterprise compliance** (SOC 2, HIPAA, SSO/SCIM): not cloneable as a
  feature. It is an audit. Later, if the angle needs it.

## Size

Screens 18, flows 10, entities 8 (6 for v1). Hard parts:

1. **Slot computation**: weekly rules + date overrides + the host's busy
   times from external calendars + buffers + minimum notice + daily/weekly
   limits + slot increments, all across time zones and DST.
2. **Calendar integrations**: Google Calendar and Microsoft Graph OAuth,
   free/busy reads, event writes and updates on reschedule/cancel. Google's
   OAuth verification for Calendar scopes takes weeks: start it early.
3. **No double booking**: a database constraint, not a UI check, when two
   guests submit the same slot.
4. Email deliverability for confirmations and reminders (own domain, SPF,
   DKIM, DMARC), and scheduled reminder jobs.

Size: **M** (a few weeks) for the core loop with Google Calendar, email
confirmations and reminders. Teams (round robin, collective), routing forms
and payments push it to **L**.
