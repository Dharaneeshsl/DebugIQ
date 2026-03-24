# AGENTS.md

This file provides guidance to WARP (warp.dev) when working with code in this repository.

## Project Overview

DebugIQ is an AI-powered simulation log analysis system for chip verification. It ingests raw simulation logs, runs them through an NLP/ML pipeline to categorize, cluster, rank, and annotate failures, stores results in SQLite, and exposes them via a FastAPI backend and a React dashboard.

## Commands

### Backend

```bash
# Install Python dependencies
pip install -r requirements.txt

# Run the full analysis pipeline (must be run before the API has data)
python main.py

# Start the FastAPI backend (port 5000)
uvicorn api:app --host 0.0.0.0 --port 5000

# Run the legacy Streamlit dashboard (alternative to React frontend)
streamlit run dashboard.py
```

### Frontend

```bash
# Install frontend dependencies
cd frontend && npm install

# Start the Vite dev server (port 3000, proxies /api to localhost:5000)
cd frontend && npm run dev

# Production build
cd frontend && npm run build
```

### Docker (full stack)

```bash
docker compose up --build
# Frontend: http://localhost:3000  Backend: http://localhost:5000
docker compose down
```

### Running individual pipeline modules

Each backend module (`parser.py`, `preprocess.py`, `classifier.py`, `clustering.py`, `ranking.py`, `recommendations.py`) has a `__main__` block for standalone smoke-testing:

```bash
python parser.py
python classifier.py
# etc.
```

## Architecture

### Data Flow

The pipeline in `main.py` is strictly sequential:

```
logs/*.log
  → parser.py        (ingest_and_parse)      → DataFrame with raw_line, timestamp, severity, module, message
  → preprocess.py    (preprocess_logs)        → adds normalized_message, failure_signature (hash-based)
  → classifier.py    (categorize_failures)    → adds category (TF-IDF + LogReg, trained at init)
  → clustering.py    (add_clusters)           → adds cluster_id (sentence-transformer embeddings + KMeans)
  → ranking.py       (compute_priority_scores)→ adds priority_score, frequency, cluster_size, severity_score
  → main.py          (apply_known_bug_flags)  → adds known_bug_flag (matches KNOWN_BUG_SIGNATURES dict)
  → recommendations.py (add_recommendations) → adds root_cause_suggestion, debug_actions (rule-based)
  → database.py      (write_failures)         → writes to data/debugiq.db (REPLACES table each run)
  → report_generator.py (save_report)        → writes data/debug_report.txt and data/debug_report.md
```

### Backend API (`api.py`)

FastAPI with three endpoints:
- `GET /api/failures` — returns all rows from the `failures` SQLite table as JSON
- `GET /api/summary` — returns aggregated stats (health score, module hotspots, severity distribution)
- `GET /api/report/{filename}` — serves `debug_report.txt` or `debug_report.md` for download

### Frontend (`frontend/src/App.jsx`)

Single React component (`App.jsx`) containing all 10 dashboard panels. It fetches from `/api/failures` and `/api/summary` on mount. If the backend is unreachable, it automatically enters **demo mode** with hardcoded `MOCK_FAILURES` / `MOCK_SUMMARY` data. The Vite dev server (`vite.config.js`) proxies `/api/*` to `http://localhost:5000`.

In production builds, `VITE_API_BASE_URL` controls the API base URL (see `frontend/.env.example`). When unset, the frontend calls same-origin `/api` — this is the correct behavior behind the Docker + nginx setup.

### Docker / nginx

In Docker Compose, nginx proxies `/api/` to `http://backend:5000/` (note: nginx strips the `/api/` prefix before forwarding). The React build is served as static files.

### Legacy Streamlit Dashboard (`dashboard.py`)

An older alternative dashboard using Streamlit + Plotly that renders the same 10 panels by reading directly from the SQLite database. Kept alongside the React frontend; both are fully functional.

## Key Implementation Details

**Log format** expected by `parser.py`:
```
[TIME:<timestamp>] [<severity>] [<module>] <message>
```
If no `.log` files exist in `logs/`, the parser auto-generates synthetic logs for demo purposes.

**Database writes are destructive**: `write_failures()` in `database.py` uses `if_exists="replace"`, so each `python main.py` run fully replaces the `failures` table.

**Known bug detection** (`KNOWN_BUG_SIGNATURES` in `main.py`) is an empty dict by default — nothing will be flagged as a known bug until signatures are added there.

**Classifier**: `FailureClassifier` in `classifier.py` trains a TF-IDF + Logistic Regression model on 12 hardcoded heuristic examples at instantiation time. The model is not persisted to disk.

**Semantic clustering**: Uses the `all-MiniLM-L6-v2` sentence-transformer model (downloaded on first run via HuggingFace cache). Number of clusters adapts dynamically: `min(8, max(2, len(rows) // 5))`.

**Priority scoring formula**:
```
priority = 0.4 × severity_score + 0.3 × log(frequency + 1) + 0.2 × cluster_size + 0.1 × module_criticality
```
Severity scores: INFO=1, WARNING=3, ERROR=7, FATAL=10.
Module criticality (hardcoded in `ranking.py`): MEMORY_CTRL=10, CACHE_CTRL=9, AXI_INTERFACE=9, ALU=8. Unknown modules default to 5.
