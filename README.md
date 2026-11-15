# DebugIQ

DebugIQ turns simulation and verification logs into failure records, deduplicated patterns, priority rankings, charts, and debugging guidance.

## Run locally without Docker

Tested on Windows with Python 3.14 and Node.js 24. The default installation needs no MongoDB, RabbitMQ, model download, or AI API key. Company release instructions are in [PRODUCTION.md](PRODUCTION.md).

From the repository root in PowerShell:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/start_local.ps1 -Install
```

On subsequent launches:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/start_local.ps1
```

Open [DebugIQ](http://localhost:5173). The initial local account is `admin` / `admin123`. Sign in, upload `data/demo.txt`, and inspect the dashboard. Ctrl+C in the launch terminal stops the app. [API documentation](http://localhost:8000/docs) is also available.

The launcher installs dependencies into `.venv`, starts the API on `127.0.0.1:8000`, and starts the dashboard on `127.0.0.1:5173`. API logs are saved in `backend/local-api.log` and `backend/local-api-error.log`.

To use separate terminals:

```powershell
# Terminal 1, repository root
.\.venv\Scripts\python.exe -m uvicorn main:app --app-dir backend --host 127.0.0.1 --port 8000

# Terminal 2
cd frontend
npm run dev -- --host 127.0.0.1
```

## Product flows

- Sign in, create a user account, and revoke a session on sign-out.
- Upload `.log`, `.txt`, and gzip-compressed logs with progress and useful errors.
- Extract severity, module, simulation time, source location, and surrounding context.
- Normalize changing timestamps and log positions before duplicate matching.
- Cluster failures and prioritize by severity, recurrence, and module impact.
- Inspect priority tables, categories, module hotspots, timelines, and graphs.
- Track failures as open, investigating, closed, or wontfix.
- Compare saved uploads for new, recurring, and resolved patterns.
- Download authenticated CSV reports with status and history fields.
- Delete individual uploads or clear your account's upload history.
- Use evidence summaries and rule-based debugging suggestions without an AI key.
- Configure an AI provider for generated explanations and conversational answers.
- Submit background uploads with `/upload-async` and poll `/job-status/{job_id}`.

Saved-upload selection, upload, export, and sign-out are accessible on small screens. Run and failure APIs enforce account ownership. Changing shared priority weights requires an administrator account.

## Configuration and storage

Copy values from `backend/.env.example` to `backend/.env` as needed. Real environment files, generated secrets, and databases are ignored by Git.

| Setting | Default / purpose |
| --- | --- |
| `DEBUGIQ_STORAGE` | SQLite when no MongoDB URI is configured; explicitly set `sqlite` or `mongo` |
| `DEBUGIQ_SQLITE_PATH` | `backend/data/debugiq.sqlite3` |
| `DEBUGIQ_EMBEDDINGS_BACKEND` | `tfidf`, offline matching; use `transformer` for optional models |
| `DEBUGIQ_ADMIN_USERNAME` | Initial admin username, `admin` |
| `DEBUGIQ_ADMIN_PASSWORD` | Initial admin password, `admin123` |
| `DEBUGIQ_JWT_SECRET` | Generated and persisted in `backend/data/jwt-secret` when omitted |
| `DEBUGIQ_MAX_UPLOAD_BYTES` | 20 MiB, applied to compressed and expanded files |
| `DEBUGIQ_MAX_FAILURES` | 3,000 extracted rows per upload; split larger logs |
| `MONGO_URI` / `MONGODB_URI` | Optional MongoDB service for shared installations |
| `MONGO_DB_NAME` | `debugiq` |
| `RABBITMQ_URL` | Optional queue; omit for in-process local background jobs |
| `CORS_ALLOWED_ORIGINS` | Comma-separated additional frontend origins |
| `OPENAI_API_KEY` | Optional generated AI answers |
| `OPENAI_MODEL` | Optional provider model name |

Groq-compatible (`CHATBOT_API_KEY` / `GROQ_KEY`) and Gemini (`GEMINI_API_KEY`) integrations are also available. Optional transformer, Siamese, and Gemini dependencies are in `backend/requirements-ml.txt`. The normal application uses `backend/requirements.txt`.

`frontend/.env.example` documents the API URL. Both Vite dev and preview proxy `/api` to the local backend. For production hosting, configure an `/api` reverse proxy or set `VITE_API_BASE_URL` at build time.

SQLite persists users, runs, statuses, jobs, settings, and revoked tokens across restarts. It is intended for a single-machine installation; its document adapter scans collections for filters. Use MongoDB for shared or larger deployments. Back up the database and JWT secret together. Initial admin environment values do not change an existing account.

Without `RABBITMQ_URL`, background jobs run inside the API process. Keep the API running until jobs finish. For durable processing across restarts, run native RabbitMQ and start a worker:

```powershell
.\.venv\Scripts\python.exe backend/worker.py
```

The worker and API must share database and queue configuration. If a configured queue cannot be reached, upload returns an error instead of silently leaving a job queued. Synchronous upload remains available.

## Verify

```powershell
powershell -ExecutionPolicy Bypass -File scripts/run_full_check.ps1
```

This runs backend unit and API integration tests and builds the frontend. If the API is running, it also performs a live smoke test. To run only the live test:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/smoke_test.ps1
```

API tests use an isolated temporary SQLite database and exercise account isolation, upload validation, async processing, dashboard, status changes, explanations, chat, comparisons, CSV, deletion, token revocation, and concurrent ID allocation.

## Interpretation and deployment limits

**Failure Repetition** is the percentage of duplicate failure rows. The API retains its historical `health_score` field name for this metric. It does not measure design correctness or pass rate. Module efficiency is relative failure share, not measured hardware performance. Graph links and root-cause suggestions are heuristics requiring engineering validation.

Local rule-based assistance labels its source. Generated AI answers require a working provider and are not guaranteed correct. Ingestion and the dashboard work without a provider.

Before public deployment, configure strong administrator credentials, an explicit JWT secret, HTTPS, allowed origins, database backups, and operational monitoring. Uploaded log excerpts are sent to an AI provider when one is configured; review your data-handling requirements first. MongoDB, RabbitMQ, external AI services, and public hosting need separate validation in their target environment.
