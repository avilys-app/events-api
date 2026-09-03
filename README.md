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

Set `JWT_SECRET`, `RESEND_API_KEY`, `EMAIL_FROM`, and `EMAIL_CONFIRMATION_URL`
in `.env`, then start PostgreSQL and initialise it. `EMAIL_FROM` must use a
domain verified in Resend.

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

The API runs at `http://localhost:3000`. Interactive documentation is available
at `http://localhost:3000/api/docs`.

The development database uses temporary storage. Running `docker compose down`
removes its data, so rerun the migration and fixture commands after starting a
fresh database.

## Checks

```bash
uv run pytest
uv run ruff check .
uv run mypy app
```
