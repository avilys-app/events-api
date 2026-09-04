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

Set `JWT_SECRET`, `RESEND_API_KEY`, `EMAIL_FROM`, `EMAIL_CONFIRMATION_URL`, and
`REPORT_TO_EMAIL` in `.env`, then start PostgreSQL and initialise it.
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

Login returns a short-lived access token and a rotating refresh token. Refresh
sessions expire after 180 days of inactivity by default; configure the access
and refresh lifetimes with `JWT_EXPIRES_IN` and `REFRESH_TOKEN_EXPIRES_IN`.
Clients should use `POST /api/auth/refresh` to rotate credentials,
`GET /api/auth/me` to restore the current user, and `POST /api/auth/logout` to
revoke the current refresh session.

The development database uses temporary storage. Running `docker compose down`
removes its data, so rerun the migration and fixture commands after starting a
fresh database.

## Checks

```bash
uv run pytest
uv run ruff check .
uv run mypy app
```
