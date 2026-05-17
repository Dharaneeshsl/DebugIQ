# DebugIQ - AI-Assisted Simulation Log Analysis

> DebugIQ turns raw verification and simulation logs into prioritized, explainable failure insights using parsing, deduplication, clustering, scoring, and dashboard-based triage.

## Pitch

DebugIQ is an end-to-end log intelligence platform for regression-style hardware or verification logs. It ingests noisy `.log`, `.txt`, and `.gz` files, extracts failures with context, groups semantically similar issues, ranks them by impact, and presents the results in a FastAPI + React workflow built for fast debugging.

This project is best described as:
- AI-assisted
- explainable
- production-oriented
- demo-ready and submission-ready

It should not be described as:
- guaranteed 100% accurate
- fully validated for all unseen logs
- proven live-production infrastructure in every environment

## What DebugIQ Does

1. Parse failure lines and nearby context from raw logs.
2. Normalize and preprocess messages for downstream analysis.
3. Categorize failures into common debugging buckets.
4. Generate embeddings for semantic comparison.
5. Deduplicate repeated or highly similar failures.
6. Cluster related failures for dashboard visualization.
7. Score failures by severity, recurrence, module impact, and history.
8. Surface root-cause suggestions and explainability signals.
9. Present results through an interactive dashboard and report export flow.

## Core Pipeline

The pipeline looks like this:

`Raw logs -> Parsing -> Preprocessing -> Categorization -> Embeddings -> Deduplication -> Clustering -> Priority scoring -> Explainability -> Dashboard`

Main pipeline stages:
- Parsing: regex-based failure extraction with context windows
- Categorization: rule-based and embedding-assisted labeling
- Deduplication: hybrid similarity flow with LSH and semantic matching
- Clustering: grouping similar failures for triage and graph views
- Priority scoring: weighted ranking using severity, frequency, module, and history
- Explainability: root-cause hints, context retrieval, and SHAP-style feature importance

## Tech Stack

### Backend
- Python
- FastAPI
- PyMongo / MongoDB
- Scikit-learn
- NetworkX
- PyTorch scaffolding for Siamese-style similarity experiments
- SlowAPI rate limiting
- JWT authentication

### Frontend
- React 18
- Vite
- Tailwind CSS
- Axios
- Recharts
- react-force-graph-2d

### Infrastructure
- Docker
- Docker Compose
- Nginx
- RabbitMQ for async ingestion
- MongoDB container for local stack runs

## Project Structure

- `backend/main.py`: FastAPI app and API routes
- `backend/services/pipeline.py`: main log-processing pipeline
- `backend/mongo_store.py`: MongoDB access layer
- `backend/ml/`: ML and analytics components
- `frontend/src/components/Dashboard.jsx`: main analytics dashboard
- `frontend/src/api/api.js`: frontend API client
- `scripts/run_full_check.ps1`: backend tests + frontend production build
- `scripts/smoke_test.ps1`: live API smoke test

## Verified Status

As checked on May 7, 2026:

- Backend unit and integration tests pass
- Frontend production build passes
- The repository is packaged in a submission-ready way
- Environment templates are present
- Docker ignore files are present

What is verified:
- code builds
- backend tests pass
- frontend production bundle builds successfully

What is not yet fully verified in this repository alone:
- a successful live full-stack run in every environment
- guaranteed accuracy on every possible log dataset
- a valid claim of 100% ML correctness

## Accuracy Claim

DebugIQ uses ML-assisted heuristics and explainable ranking to improve debugging speed and triage quality. It is appropriate to claim:

- high-value failure prioritization
- explainable ML-assisted analysis
- tested end-to-end pipeline behavior

It is not appropriate to claim:

- 100% accurate results
- perfect detection on all unseen logs
- guaranteed root-cause correctness

## Getting Started

### Prerequisites

- Python 3.10+
- Node.js 18+
- MongoDB
- RabbitMQ for async ingestion

### Backend setup

```bash
cd backend
pip install -r requirements.txt
python -m uvicorn main:app --reload --port 8000
```

Set the required backend environment values in `backend/.env` before starting the API.

### Frontend setup

```bash
cd frontend
npm install
npm run dev
```

Set `VITE_API_BASE_URL` in `frontend/.env` if the frontend should call a backend URL other than the local default.

### Docker

```bash
docker compose up --build
```

This starts:
- `frontend` on `http://localhost:5173`
- `backend` on `http://localhost:8000`
- `mongo` on `localhost:27017`
- `rabbitmq` on `localhost:5672`
- RabbitMQ management UI on `http://localhost:15672`

The Compose stack now includes:
- health checks for MongoDB, RabbitMQ, backend, and frontend
- startup ordering based on service health
- persistent MongoDB storage through a named volume
- local-container defaults for `MONGO_URI` and `RABBITMQ_URL`

If you want to stop the stack:

```bash
docker compose down
```

If you want to stop it and also remove the MongoDB volume:

```bash
docker compose down -v
```

### Render backend deployment

For a Render Web Service, set the backend Dockerfile path to `backend/Dockerfile`.
The container command reads Render's `PORT` automatically.

Required environment variables:
- `MONGO_URI` or `MONGODB_URI`: a reachable MongoDB connection string, such as MongoDB Atlas or a Render private service URL. Do not use `localhost:27017` on Render, because localhost points to the web container itself.
- `MONGO_DB_NAME`: database name, usually `debugiq`.
- `DEBUGIQ_JWT_SECRET`: a long random secret.
- `DEBUGIQ_ADMIN_USERNAME` and `DEBUGIQ_ADMIN_PASSWORD`: initial admin account values.

Optional:
- `RABBITMQ_URL`: needed only for `/upload-async`; synchronous `/upload` works without RabbitMQ.
- `CORS_ALLOWED_ORIGINS`: comma-separated deployed frontend origins.

## Local Verification

### Offline/full check

```powershell
powershell -ExecutionPolicy Bypass -File scripts/run_full_check.ps1
```

This runs:
- backend pytest suite
- frontend production build

### Live smoke test

With the backend and database running:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/smoke_test.ps1
```

## Demo Flow

1. Open the app and sign in.
2. Upload a simulation log.
3. Review totals, health score, and unique failure counts.
4. Inspect clustered issues and priority rankings.
5. Open a failure to review context, recommendations, and explainability output.
6. Export CSV or compare recent uploads for triage.

## Suggested Submission Wording

Use wording like this in your submission:

> DebugIQ is an end-to-end AI-assisted verification log analysis platform that parses raw simulation logs, deduplicates repeated failures, clusters related issues, prioritizes them with explainable scoring, and presents the results in an interactive dashboard for faster debugging.

Short version:

> End-to-end AI-assisted log triage with explainable failure prioritization.

Avoid wording like:

- "100% accurate"
- "guaranteed correct"
- "perfect ML detection"
- "fully proven production deployment in every environment"

## Current Limitations

- Live deployment still depends on a working MongoDB connection and runtime environment
- Async ingestion requires RabbitMQ
- Large logs may need pagination and more tuning for UI responsiveness
- LLM-backed explanation quality depends on external provider availability and API keys

## Security Note

- Do not commit real API keys, passwords, or database credentials
- Rotate any secrets that were previously exposed during development
- Keep real environment files local and out of commits

## Final Verdict

DebugIQ is in a strong state for hackathon submission and demo use. The codebase is buildable, test-backed, and structured like a production-oriented prototype. The correct claim is that it is submission-ready and demo-ready, not that it delivers guaranteed 100% accurate ML outcomes.
