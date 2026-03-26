## DebugIQ (Hackathon Submission)

DebugIQ is an AI-powered simulation log analysis + failure prioritization platform:
- Context-aware failure extraction (multi-line)
- Transformer embeddings (CodeBERT / Longformer switch)
- Intelligent dedup (MinHash LSH + embeddings + Siamese training scaffold)
- Dynamic prioritization (multi-factor + Optuna tuning)
- Root cause analysis (temporal graph + causal scoring)
- Explainability (RAG-style retrieval + **Gemini-first** LLM + SHAP)
- React dashboard (clusters graph, heatmap, timeline, drill-down)

### Quickstart (Docker) — recommended

1) Create a local backend env file (do **not** commit it):
- Copy `backend/.env.example` → `backend/.env`
- Fill:
  - `DEBUGIQ_JWT_SECRET` (required)
  - `GEMINI_API_KEY` (recommended for live explanations)

2) Start the stack:

```bash
docker compose up --build
```

3) Open:
- **Frontend**: `http://localhost:5173`
- **Backend docs**: `http://localhost:8000/docs`
- **RabbitMQ UI**: `http://localhost:15672` (guest/guest)

### Demo flow (what judges should do)

1) Go to `http://localhost:5173/login`
2) Login (defaults):
   - username: `admin`
   - password: `admin123`
   (configure via `DEBUGIQ_ADMIN_USERNAME` / `DEBUGIQ_ADMIN_PASSWORD`)
3) Upload a `.log`, `.txt`, or `.gz`
4) On the dashboard, click a failure row → see:
   - **AI explanation** (Gemini)
   - **SHAP feature importance**

### Async ingestion (queue-based)

- `POST /upload-async` → returns `{ job_id }`
- `GET /job-status/{job_id}` → returns job status and `run_id` when complete

Worker runs automatically in Docker (`worker` service).

### Security / secrets

- Do **not** hardcode or commit API keys.
- Use `backend/.env` (gitignored) or environment variables.

