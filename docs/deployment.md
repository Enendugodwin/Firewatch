# Deployment

## Local development (no containers)

```bash
cp .env.example .env
python scripts/bootstrap.py
cd backend  && uv sync --group dev && uv run uvicorn app.main:app --reload --port 8100
cd frontend && npm install && npm run dev
```

The Vite dev server proxies `/api` and `/health` to `http://127.0.0.1:8100`
(`VITE_PROXY_TARGET` overrides this). Port **8000 is commonly occupied** on this workstation, which
is why 8100 is the default.

## Containers

```bash
cp .env.example .env       # set POSTGRES_PASSWORD (and FIRMS_MAP_KEY when available)
docker compose up --build
```

| Service | Image | Port | Notes |
| --- | --- | --- | --- |
| `db` | `postgis/postgis:16-3.4` | 5433 → 5432 | Named volume `postgres-data` |
| `redis` | `redis:7-alpine` | 6380 → 6379 | No persistence; queues only |
| `api` | `backend/docker/Dockerfile` | 8100 → 8000 | Runs migrations + source seed on boot |
| `worker` | same image | — | `celery -A app.workers.celery_app` |
| `web` | `frontend/Dockerfile` | 8080 → 80 | nginx serving the SPA, proxying `/api` |

Health checks: API `/ready` (database aware), db `pg_isready`, redis `PING`, web `/healthz`.
`api` waits for healthy `db` and `redis`; `worker` and `web` wait for a healthy `api`.

To verify the stack without starting it:

```bash
docker compose config --quiet
```

## Environment

All backend settings come from environment variables (`backend/app/core/config.py`). One root
`.env` is used by Compose and by local runs (`env_file = (".env", "../.env")`).

| Variable | Default | Notes |
| --- | --- | --- |
| `ENVIRONMENT` | `local` | `production` disables nothing automatically — configure hardening |
| `DATABASE_URL` | SQLite file | Must be `postgresql+psycopg://…` for PostGIS capability |
| `REDIS_URL` | `redis://localhost:6379/0` | Broker + result backend |
| `CORS_ORIGINS` | localhost:5173 | Comma-separated or JSON array |
| `FIRMS_MAP_KEY` | empty | **Required for any real observation** |
| `LOG_JSON` | `true` | Structured logs for aggregation |

## Database

Migrations are the only supported way to change schema:

```bash
cd backend
uv run alembic upgrade head        # apply
uv run alembic downgrade -1        # step back (each revision is reversible)
uv run alembic current
uv run python -m scripts.seed_sources
```

Revision `0001_foundation` creates the PostGIS extension on PostgreSQL and the `data_sources`
registry. On SQLite it skips the extension and runs the same table DDL, so CI and local development
exercise the same chain.

## Backup and restore

```bash
# backup (custom format, compressed)
docker compose exec -T db pg_dump -U firewatch -Fc firewatch > firewatch-$(date +%F).dump

# restore into a fresh volume
docker compose exec -T db pg_restore -U firewatch -d firewatch --clean --if-exists < firewatch.dump
```

Back up before any migration that rewrites observation tables, and keep raw retrieved payloads in
object storage so the database can be rebuilt if necessary.

## Health and observability

- `GET /health` — process liveness, no dependencies.
- `GET /ready` — database probe with latency and error detail; 503 when unreachable.
- `GET /api/v1/system/status` — phase, uptime, capabilities, data freshness, module registry.
- Logs are structured JSON with `request_id`, method, path, status and duration.

## Security posture (current)

- No authentication: bind the console to localhost or a trusted network only.
- Secrets are backend-only; the frontend bundle contains no credentials and calls relative paths.
- Security headers are set by the API middleware and nginx; CORS is explicit allow-list.
- Rate limiting, RBAC, CSRF and audit logging arrive in the security phase (8).

## Production checklist (from the specification)

- [ ] Managed PostgreSQL with PostGIS; automated backups verified by restore.
- [ ] Redis with persistence or a managed queue.
- [ ] `FIRMS_MAP_KEY` in a secret manager, never in an image or the repository.
- [ ] TLS termination in front of `web` and `api`.
- [ ] Authentication enabled and expensive endpoints role-restricted.
- [ ] Long-running ingestion in workers only — never inside a request handler.
- [ ] Observability: log aggregation, ingestion success metrics, API latency, queue depth.
- [ ] NASA attribution and the thermal-anomaly disclaimer visible in the UI.
