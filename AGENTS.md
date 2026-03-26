# AGENTS.md

This file provides guidance for running and developing DebugIQ.

## What to run

DebugIQ consists of:
- `backend/` : FastAPI service (port `8000`) + RabbitMQ worker support
- `frontend/`: React dashboard
- RabbitMQ: job queue for async log ingestion

## Backend (local)

```bash
cd backend
pip install -r requirements.txt

# Start the API
uvicorn main:app --host 0.0.0.0 --port 8000

# In another terminal, start the worker (needs RabbitMQ)
python worker.py
```

DB + tables are created automatically on startup.

## Frontend (local)

```bash
cd frontend
npm install
npm run dev
```

## Docker (full stack)

```bash
docker compose up --build
```

Access:
- Frontend: `http://localhost:5173`
- Backend: `http://localhost:8000/docs`
- RabbitMQ UI: `http://localhost:15672`

## Auth (JWT)

The backend exposes `POST /token` and expects `Authorization: Bearer <token>` for protected endpoints.
The frontend login page is at `/login`.

Demo credentials are configured via environment variables:
- `DEBUGIQ_ADMIN_USERNAME` (default: `admin`)
- `DEBUGIQ_ADMIN_PASSWORD` (default: `admin123`)

## Async ingestion (RabbitMQ)

1) `POST /upload-async` uploads a log and returns a `job_id`
2) `GET /job-status/{job_id}` returns status and, once complete, the created `run_id`
