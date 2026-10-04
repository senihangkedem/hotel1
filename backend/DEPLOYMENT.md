# Production Deployment Runbook

## Required Configuration

Set these values through the deployment platform's secret/configuration store. Do not commit a populated `.env` file.

| Variable | Production requirement |
| --- | --- |
| `ENVIRONMENT` | `production` |
| `DEBUG` | `0` |
| `DJANGO_SECRET_KEY` | Unique, high-entropy secret; rotate using the platform secret manager |
| `ALLOWED_HOSTS` | API hostnames plus the frontend origin hostname used by websocket Origin validation; no schemes or paths |
| `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST` | Managed PostgreSQL connection values |
| `DB_SSLMODE` | `require` or the provider's verified TLS mode |
| `DB_PORT`, `DB_CONN_MAX_AGE` | Optional port and persistent-connection lifetime; PostgreSQL connection attempts time out after three seconds |
| `REDIS_URL` | Shared Redis URL; use `rediss://` where TLS is available |
| `CORS_ALLOWED_ORIGINS` | Exact frontend origins, including scheme; never `*` |
| `CSRF_TRUSTED_ORIGINS` | Exact trusted origins, including scheme |
| `API_NUM_PROXIES` | Number of trusted proxies used to resolve client IPs for throttling |
| `TRUST_PROXY_SSL_HEADER` | Set to `1` only behind a trusted proxy that overwrites forwarded-protocol headers |
| `VITE_API_BASE_URL` | HTTPS API base URL for the frontend build |
| `VITE_WS_BASE_URL` | Matching WSS API origin for browser sockets |

Production settings refuse to start with `DEBUG=True`, a missing secret/host/database credential, or no Redis URL. Redis backs both the Channels groups and shared API throttle counters. API defaults are 100 anonymous requests/minute and 1000 authenticated requests/hour; token login is limited to 10/minute. Tune these against measured traffic and provider limits. Set `API_NUM_PROXIES` to the exact trusted reverse-proxy count and ensure the edge strips client-provided forwarded-for headers; never expose the app directly if throttle identity depends on forwarded headers.

Outside development, HTTPS redirects are enabled by default. When TLS terminates at a trusted reverse proxy, configure `TRUST_PROXY_SSL_HEADER=1` only when that proxy strips client-supplied forwarded-protocol headers and sets its own; otherwise Django cannot recognize the original HTTPS request. HSTS defaults to one hour; increase it only after all subdomains are HTTPS-ready. The CORS list does not enable credentialed cross-origin requests.

`VITE_API_BASE_URL` and `VITE_WS_BASE_URL` are public browser configuration, not secrets. The frontend defaults to localhost in Vite development and to same-origin `/api`, HTTPS, and WSS behavior in a production build. Set the Vite variables at build time when frontend and backend use different hostnames. Never place database, Redis, or Django secrets in `VITE_*` values.

## Health Checks

- `GET /health/` is liveness only. It returns `200 {"status":"ok"}` when Django can serve the request and does not contact external dependencies.
- `GET /ready/` runs `SELECT 1` against the configured database and a bounded message roundtrip through the configured Channels layer. It returns HTTP 200 with `status: ok` only when both checks succeed; otherwise it returns HTTP 503 with generic `ok`/`unavailable` dependency states. It never returns connection strings, exception text, or secrets.

The PostgreSQL connection attempt is bounded by a three-second driver timeout; each channel-layer operation is bounded to one second. The channel-layer roundtrip validates the Redis-backed Channels path when Redis is configured, but is not a full Redis capacity, persistence, or cache-throttle load test. These endpoints are unauthenticated and intentionally reveal only dependency availability.

## Build and Start

Run commands from `backend/` with the production virtual environment activated:

```powershell
python manage.py check --deploy
python manage.py makemigrations --check --dry-run
python manage.py migrate --plan
python manage.py collectstatic --noinput
daphne -b 0.0.0.0 -p 8000 config.asgi:application
```

Review the migration plan and apply `python manage.py migrate` as a separate, controlled release step after a backup. Do not apply migrations automatically as part of process startup. Run the Vite production build with the production `VITE_*` values; those values are public browser configuration, never secrets.

Expose the service only through TLS termination. Keep PostgreSQL and Redis on private networks, restrict inbound ports, run Daphne under a process supervisor/container health policy, and configure platform log retention and alerts for repeated 5xx, 429, database, and Redis failures. Avoid recording authorization headers, request bodies, or websocket query tokens in proxy/access logs.

`collectstatic` writes to `STATIC_ROOT`; serve that directory through the selected platform or a static-file service. `MEDIA_ROOT` is local storage, not a durable production media solution. Configure persistent storage or object storage before accepting production uploads, and include it in backup/restore procedures.

## Backup and Restore

Take encrypted, access-controlled, off-host PostgreSQL backups using provider snapshots or `pg_dump`. Example for a host with PostgreSQL client tools installed:

```sh
pg_dump --format=custom --no-owner \
  --host="$DB_HOST" --port="${DB_PORT:-5432}" --username="$DB_USER" \
  --file="restaurant-saas-$(date -u +%Y%m%dT%H%M%SZ).dump" "$DB_NAME"
```

Supply the database password through the host's protected PostgreSQL password mechanism (for example, a restricted `PGPASSFILE`); do not put it in shell history or command arguments. Back up uploaded media separately if it is stored on a persistent volume. Redis is a delivery/cache dependency, not the system of record; order and payment state must remain recoverable from PostgreSQL.

Document backup frequency and retention against the service's recovery-point objective. Periodically restore a backup to an isolated environment and verify Django checks, migration state, and representative restaurant/order/billing reads before relying on the backup process.

## Migration State and Known Discrepancy

Use these commands against the database selected by the current environment:

```powershell
python manage.py makemigrations --check --dry-run
python manage.py showmigrations
python manage.py migrate --plan
python manage.py sqlmigrate user_accounts 0003_alter_user_id
```

These checks answer different questions:

1. `makemigrations --check --dry-run` compares model definitions with migration files and reports whether new migration files are needed. “No changes detected” does not show that migrations have been applied to any database.
2. `showmigrations` reads the selected database's migration recorder and marks which migration files are applied there. Its output is environment/database-specific.
3. `migrate --plan` shows operations Django would run against the selected database; it does not apply them.
4. `sqlmigrate` displays the SQL represented by a migration; it does not execute the SQL.

The development database inspected during Stage 16B reported `user_accounts.0003_alter_user_id` as unapplied. Before production, inspect `showmigrations`, `migrate --plan`, the migration dependency/SQL, and the actual target schema after taking a backup. Determine whether the target schema needs this migration or whether the state reflects a prior controlled operation. Do not delete, rewrite, or fake the migration based only on `makemigrations --check`; do not edit the migration recorder manually. Resolve any discrepancy with a reviewed, backed-up migration plan.

## Provider-Neutral Release Checklist

### Before Deployment

- Take and verify a database backup; include persistent media storage if used.
- Confirm all required backend variables and exact CORS, CSRF, and allowed-host origins.
- Confirm PostgreSQL TLS/connectivity and Redis TLS/auth/connectivity from the deployment network.
- Run `python manage.py check --deploy`, the backend test suite, frontend `npm run lint`, and `npm run build`.
- Inspect `showmigrations` and `migrate --plan` against the target database; investigate the known `user_accounts.0003_alter_user_id` state.
- Confirm the target platform's static/media serving, health probes, secret storage, logs, and backup schedule.

### Deployment

- Deploy the ASGI backend and confirm its HTTPS route.
- Apply the reviewed migration plan as an explicit release operation after backup; do not run migrations automatically at process startup.
- Publish collected static files and configure durable media storage if uploads are enabled.
- Build and deploy the frontend with its production API and WebSocket origins.
- Verify HTTPS, WSS, `GET /health/`, and `GET /ready/` from the deployment network.

### After Deployment

- Test login, a QR menu visit, cart/checkout, test order creation, and WebSocket delivery to a staff dashboard.
- Verify staff status updates, billing/payment, and analytics.
- Inspect application, database, and Redis logs/health; verify uptime monitoring and backup scheduling.
- Perform a restore drill in an isolated environment before relying on production backups.

### Rollback

- Roll back application artifacts using the selected platform's release process.
- Do not assume database migrations automatically roll back with the application. Review backward compatibility and the specific migration before any reverse migration; use a verified database backup/restore when reversal is unsafe.
- Redis contains transient delivery/cache state, not the order/payment source of truth. Reconnect/restart may lose queued transient events; clients should recover state from REST APIs.

## CI Readiness

No CI workflow is currently present. A future provider-neutral CI job should install the pinned backend dependencies, use an isolated SQLite test database, run Django checks/tests and the migration dry-run, then install frontend dependencies and run lint/build. It should not deploy or apply migrations. CI is deferred here because the current full backend suite is slow and no CI platform/runtime policy has been selected.

## Render Free Test Deployment

The repository includes a provider-specific `render.yaml` for a **test/demo deployment only**. It defines a free ASGI web service, free Render Postgres, free Key Value, and a free static frontend. It does not run migrations, provision anything until you create/apply the Blueprint yourself, or deploy automatically on later commits (`autoDeployTrigger: off`). Review every resource and current Render pricing/plan limits before applying it. This is not a production deployment configuration.

### Blueprint Resources and Commands

- Backend: root directory `backend`; build runs `pip install -r requirements.txt && python manage.py collectstatic --noinput`; start runs `daphne -b 0.0.0.0 -p $PORT config.asgi:application`; Render health path is `/ready/`.
- PostgreSQL: Render-managed free Postgres in Oregon, internal-only networking, TLS required with `DB_SSLMODE=require`.
- Key Value: Render-managed free Redis-compatible Valkey in Oregon, internal-only networking; its generated internal connection URL is supplied to the existing `REDIS_URL` setting.
- Frontend: root directory `frontend`; build runs `npm ci && npm run build`; publishes `dist`; rewrites client routes to `/index.html` for React Router.
- The Blueprint has no `preDeployCommand`, `initialDeployHook`, or build/start migration command. It never runs `python manage.py migrate`.

Render's `fromDatabase`/`fromService` references populate database credentials, Redis URL, and the backend's own hostname. Render generates `DJANGO_SECRET_KEY`. These values are not written into this repository. Cross-service URLs are deliberately `sync: false` manual inputs to avoid a Blueprint dependency cycle: the backend needs the frontend origin for host/CORS/CSRF checks while the frontend needs the backend origin for API/WebSockets. `NODE_VERSION` and `PYTHON_VERSION` are pinned in the Blueprint. No credentials or Render service domains are hard-coded in source.

When creating the Blueprint, connect the repository and review the listed services/regions/plans. The Blueprint's first apply creates the services and starts their first builds; later code commits will not auto-deploy. Manually deploy after changes from the Render Dashboard.

### URLs, TLS, and Static/Media Files

Render supplies HTTPS URLs for the public backend and static frontend. Configure no `ws://` URL for deployment: the frontend accepts the backend's `https://` origin and converts it to `wss://`. Render TLS terminates at its edge; the backend Blueprint enables Django's secure redirect and trusted forwarded-protocol handling. The internal PostgreSQL connection uses `sslmode=require`; Render documents self-signed TLS support for internal Postgres connections.

`collectstatic` runs in the backend build and WhiteNoise serves Django static files, including admin/DRF assets. The React frontend is separately served from Render's static-site CDN. Restaurant/menu uploads still use `MEDIA_ROOT` on the web service's ephemeral filesystem. They can be lost on restart, spin-down, or deploy; persistent media/object storage is not included in this free test setup.

### Free-Tier Limitations

Render's free plans are for testing, not production:

- A free web service spins down after 15 minutes without inbound HTTP/WebSocket activity; waking may take about a minute. Existing WebSockets are interrupted by spin-down or restart and must reconnect/reload state.
- Free web service instance hours are limited to 750 per workspace/month and shared by its free web services. Usage limits can suspend services or builds.
- Free Postgres is limited to 1 GB, expires 30 days after creation, has a 14-day upgrade grace period after expiry, and does not include Render backups/PITR. Export important demo data before expiry.
- Free Key Value is 25 MB, has a 50-connection limit, and has no persistence. Restarts/upgrades lose all Redis data. Its internal URL is unauthenticated by default; keep `ipAllowList: []`, use the same-region private network, and do not expose the external URL. Redis holds cache/throttle/channel state, not order/payment records.
- The web service filesystem is ephemeral; local media is not durable.
- Free plans have no guaranteed uptime or production-grade backup guarantee. External monitoring and alerting are not configured by this repository.

Free-tier limits can change. Review Render's [free instance limits](https://render.com/docs/free), [Key Value behavior](https://render.com/docs/key-value), and [Blueprint reference](https://render.com/docs/blueprint-spec) before applying the file.

`/ready/` proves that the database accepts `SELECT 1` and that the configured Channels layer can pass a message. It does **not** prove that the application's tables exist or that migrations have been applied; a newly created empty database can be dependency-ready before the manual migration step.

### Manual Render Setup and Environment

The Blueprint handles or prompts for variables as follows:

- Render-generated or service-referenced: `DJANGO_SECRET_KEY`, Postgres database name/user/password/host/port, Key Value `REDIS_URL`, and the backend `ALLOWED_HOSTS` hostname.
- Manually supplied in Render after service URLs are known (`sync: false`): `FRONTEND_HOSTNAME` (hostname only), `CORS_ALLOWED_ORIGINS` and `CSRF_TRUSTED_ORIGINS` (the exact frontend `https://` origin), plus frontend `VITE_API_BASE_URL` and `VITE_WS_BASE_URL` (the backend `https://` origin). Render prompts for `sync: false` values during initial Blueprint setup; if URLs are not yet known, set/update them in the Dashboard after services receive URLs and redeploy the frontend so Vite rebuilds with them.
- Blueprint values: `ENVIRONMENT=production`, `DEBUG=0`, PostgreSQL engine, `DB_SSLMODE=require`, secure proxy/HTTPS flags, free plan/region settings, and Vite/Node/Python build configuration.
- Public frontend build values: `VITE_API_BASE_URL` and `VITE_WS_BASE_URL` contain only the backend's public HTTPS origin; they are not credentials. Frontend code normalizes the API path and WebSocket scheme.

The public service hostnames/origins themselves are not secrets. Do not copy secret-bearing Postgres/Redis connection strings into issue trackers, logs, or Vite variables. For this test deployment, leave Key Value internal authentication disabled unless you deliberately configure and verify an authenticated URL; the Blueprint's generated internal connection string is the existing `REDIS_URL` input. The Key Value policy is `noeviction`: at capacity, writes fail explicitly rather than silently evicting Channels messages or throttle keys. A free Key Value instance cannot provide production-grade durable data.

### Controlled Migration Procedure

Do not add a migration command to the Blueprint. After manually applying the Blueprint and confirming the database service is available:

1. Review the target Postgres details and connection mode; take a backup/export where the selected plan supports it. The free Postgres plan has no managed backup guarantee, so keep a protected export outside Render.
2. In the backend Shell or another secure environment with the same database settings, run `python manage.py showmigrations` to inspect the target database's applied-state table.
3. Run `python manage.py migrate --plan` and `python manage.py sqlmigrate user_accounts 0003_alter_user_id`; compare migration dependencies and SQL with the actual target schema.
4. Investigate whether `user_accounts.0003_alter_user_id` is unapplied and needed, or whether the database was already changed by a controlled operation. `makemigrations --check --dry-run` only verifies model/migration files; it says nothing about applied state.
5. Only after that review and an available recovery path, manually run `python manage.py migrate` once. Never delete, rewrite, squash, or fake migration history to silence a discrepancy.
6. Verify `/health/`, `/ready/`, login, and core application flows after migration.

The Render free Postgres service may expire before a long investigation completes; do not treat it as a durable environment.

### Test Deployment Checklist

**Create/review services**

- [ ] Confirm the Blueprint defines Postgres, Key Value, Django backend, and React static site in one region where applicable.
- [ ] Review free-tier plans, expiration, resource names, and manual deploy behavior before applying.

**Inspect configuration**

- [ ] Confirm generated Django secret and Render-managed database/Redis/service references.
- [ ] Confirm `ALLOWED_HOSTS`, CORS, and CSRF origins resolve to the two Render hostnames.
- [ ] Confirm database TLS, internal-only Redis, `DEBUG=0`, HTTPS redirect, and trusted proxy header.
- [ ] Confirm production frontend values resolve to `https://...` and `wss://...`.

**Deploy and verify manually**

- [ ] Backend build and static collection succeed; Daphne starts the ASGI app.
- [ ] `/health/` and `/ready/` return the expected statuses.
- [ ] Frontend loads and React Router routes refresh successfully.
- [ ] Login/JWT, QR menu, order submission, WebSocket events, staff dashboard, billing, and analytics work.
- [ ] Inspect Render logs and service metrics; acknowledge that external uptime monitoring is not configured.

**Migration gate**

- [ ] Inspect applied migrations and migration plan against this Render database.
- [ ] Reconcile `user_accounts.0003_alter_user_id` against the actual schema.
- [ ] Take/export a backup where possible and run `migrate` manually only after review.
- [ ] Recheck readiness and application behavior after migration.