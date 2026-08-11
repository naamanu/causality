# Railway deployment

## Visual demo

The public design-review demo is deployed at
[`web-production-24389.up.railway.app`](https://web-production-24389.up.railway.app).
It runs the same production image with `APP_ENV=demo`, which creates an ephemeral
SQLite control plane, a deterministic incident, realistic trace data, usage, and
precomputed analysis results. It needs no customer data or external credentials
and must never be used as the production environment.

The demo environment is intentionally disposable. Its state resets whenever the
service restarts; this keeps pull-request visual review reproducible and cheap.

Create one Railway project with `staging` and `production` environments. Add the
same GitHub repository three times:

| Service | Config file | Public |
| --- | --- | --- |
| `web` | `/railway.json` | yes |
| `worker` | `/railway.worker.json` | no |
| `cleanup` | `/railway.cleanup.json` | no (daily cron) |

Set each service's config-file path to the corresponding file. Add Railway
PostgreSQL and Redis services and reference their `DATABASE_URL` and `REDIS_URL`
variables from all three application services. Add the ClickHouse Cloud, WorkOS,
Anthropic, session, and application variables listed in `.env.example`.

Use `APP_ENV=production`, set `APP_BASE_URL` to the web service's custom domain,
and keep `DEV_AUTH_ENABLED=false`. Only the web service receives a public domain.

Before onboarding production users:

1. Enable PostgreSQL point-in-time recovery and daily backups.
2. Configure WorkOS callback URL as `<APP_BASE_URL>/api/v1/auth/callback`.
3. Verify `/health/ready`, create an environment and key, send OTLP traces, and
   complete an analysis in staging.
4. Exercise a database restore into a sibling Railway service and document the
   cutover procedure.

The application uses only standard URLs and environment variables. A future
Render deployment maps the three processes to web, background-worker, and cron
services without application changes.
