# Events API

FastAPI backend for the Events application.

## Prerequisites

- [uv](https://docs.astral.sh/uv/)
- Docker with Docker Compose

Python 3.14 is installed automatically by `uv` when needed.

## Local development

Install the dependencies and create your environment file:

```bash
uv sync
cp .env.example .env
```

Set `JWT_SECRET`, `RESEND_API_KEY`, `EMAIL_FROM`, `EMAIL_CONFIRMATION_URL`,
`PASSWORD_RESET_URL`, and `REPORT_TO_EMAIL` in `.env`, then start PostgreSQL
and initialise it.
`EMAIL_FROM` must use a domain verified in Resend.

```bash
docker compose up -d db
docker compose run --rm migrate
docker compose run --rm fixtures
```

Start the API:

```bash
uv run python -m app.main
```

The API process also runs a durable email-outbox worker. Registration queues
confirmation email in PostgreSQL and returns immediately; the worker delivers
queued messages and retries transient Resend failures automatically. Configure
it with `EMAIL_OUTBOX_WORKER_ENABLED` and `EMAIL_OUTBOX_POLL_INTERVAL`.

`POST /api/submit-report` accepts issue reports from the web and mobile apps
and queues them for delivery to `REPORT_TO_EMAIL`. Both the legacy `issue`
field and the preferred `message` field are accepted.

The API runs at `http://localhost:3000`. Interactive documentation is available
at `http://localhost:3000/api/docs`.

Registration requires `acceptedTerms: true`. The optional
`marketingEmailConsent` and `marketingPushConsent` fields default to `false`.
Terms acceptance and both marketing preferences are stored with timestamps.
Clients must not supply `termsVersion`: registration reads it from the matching
`terms-and-conditions` row in `legal_pages`. The accepted version is returned in
authenticated user responses.

When the published Terms change, update both localized rows and give them the
same new version, such as `v2`. Do not overwrite existing users' stored versions:
each value records the version that user actually accepted.

Alembic adopts the existing Supabase `legal_pages` table and creates it in fresh
local/test databases. Future schema changes to this table should use Alembic.

Authenticated users can independently grant or withdraw email and push marketing
consent with `PATCH /api/users/marketing-consents`. Transactional account emails
such as confirmation and password reset are not marketing and are unaffected.

Login returns a short-lived access token and a rotating refresh token. Refresh
sessions expire after 180 days of inactivity by default; configure the access
and refresh lifetimes with `JWT_EXPIRES_IN` and `REFRESH_TOKEN_EXPIRES_IN`.
Clients should use `POST /api/auth/refresh` to rotate credentials,
`GET /api/users/profile` to restore the current user, and
`POST /api/auth/logout` to revoke the current refresh session.

Password recovery uses `POST /api/auth/forgot-password` and
`POST /api/auth/reset-password`. Reset messages are queued through the same
durable email outbox and link to `PASSWORD_RESET_URL`. Authenticated users can
use `POST /api/auth/change-password`. Resetting or changing a password revokes
all of that user's refresh sessions, so clients should clear authentication and
return to login.

Authenticated users can permanently remove their account with
`DELETE /api/users/profile` by supplying their current password. The user and
all associated authentication tokens and sessions are deleted.

The development database uses temporary storage. Running `docker compose down`
removes its data, so rerun the migration and fixture commands after starting a
fresh database.

## Saved events and Lithuanian time

The favorites endpoint supports the Upcoming / Passed tabs with an optional
`status` filter:

```text
GET /api/users/favorites?status=upcoming&page=1&pageSize=20
GET /api/users/favorites?status=past&page=1&pageSize=20
```

Upcoming includes ongoing events. If `endTime` exists, the event becomes past
at that instant. Otherwise, it becomes past at midnight after its `startTime`
date in **Europe/Vilnius**. Events with neither timestamp remain upcoming;
an event with only an end time is classified by that time.

Results default to `startTime ASC` for upcoming and `startTime DESC` for past.
When using `startTime ASC`, events whose total duration exceeds
`LONG_EVENT_THRESHOLD_MONTHS` (**6 calendar months** by default) appear after
other dated events. Each group keeps ascending start time and ID ordering.
Durations exactly at the threshold, missing timestamps, and invalid
negative durations are not classified as long-term. Other sort fields and
descending date order keep their existing behavior. This grouping applies to
both public events and favorites, before pagination, and does not remove events.

Configure this shared sorting rule in the backend environment:

```env
LONG_EVENT_THRESHOLD_MONTHS=6
```

The value must be a positive integer. Restart/redeploy the API after changing it,
because settings are cached per process. It measures total event duration in
calendar months, not elapsed time since the start or fixed 30-day periods.
The frontend keeps using `orderBy=startTime&orderDirection=ASC`; there is no
per-request threshold parameter.
Unknown start times go last in both groups, with ID breaking ties. Existing
`orderBy` and `orderDirection` parameters can override the sort. Filtering and
sorting happen before pagination; `total` counts only the matching group.
The frontend must load additional pages and reset pagination when switching tabs.
Omitting `status` still returns both groups with the existing descending default.

The same filter is available on `/api/events`. `hideExpired=true` now uses the
same end-time-aware upcoming rule, so ongoing events remain visible. Combining
`status=past` with `hideExpired=true` is rejected as contradictory.

Event `start_time` and `end_time` database columns contain Lithuanian wall-clock
timestamps without a timezone. Responses preserve the legacy format expected by
the frontend's `dayjs.utc` formatters: local `2026-06-01 20:00` is returned as
`2026-06-01T20:00:00Z`, so the existing UI displays `20:00`. This applies to both
`startTime` and `endTime`, in all event endpoints. Null timestamps stay null.
The `Z` suffix is a compatibility convention for these event fields, not their
true UTC instant. Do not use it to calculate expiry on the frontend; use `status`
to request the backend's classification. Correct timezone-bearing responses
require a coordinated frontend update, including calendar exports. No stored
event values are shifted or migrated.

Offset-free `startDate` and `endDate` query values are interpreted in Lithuania;
offset-bearing values are converted to Lithuanian time before querying.
`endDate` includes that entire Lithuanian calendar day. The timezone follows
daylight-saving changes rather than using a fixed UTC offset or server timezone.
Date filters match the event's active period, not just its start date. For
example, an event starting September 11 at 17:00 and ending September 12 at 22:00
is included by `startDate=2026-09-12&endDate=2026-09-12`. Events ending exactly at
the window's beginning do not carry over into it. Missing end times fall back
to midnight after the start day; unknown start times retain their existing
inclusion in date-filtered results. `hideExpired=true` additionally removes
events already finished at the current time, even if they overlap the selected
day. Existing query parameters are sufficient; no frontend request changes are
required for the new overlap matching or long-term ordering.
The timezone-free columns cannot distinguish the two occurrences of the repeated
autumn hour; ambiguous wall-clock times use the later, standard-time occurrence,
consistently with PostgreSQL.

System instants (authentication expiry, audit records, and email queue scheduling)
retain their existing UTC storage semantics. Email timestamp displays use
Lithuanian time in both languages. Event wall-clock values must not be confused
with these UTC system timestamps.

## Checks

```bash
uv run pytest
uv run ruff check .
uv run mypy app
```
