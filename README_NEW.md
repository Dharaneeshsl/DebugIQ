# DebugIQ - Production-Grade AI Debugging Platform

DebugIQ is an AI-powered simulation log analysis and failure prioritization system. It ingests large logs, extracts failures with context-aware NLP, deduplicates semantically similar issues, prioritizes failures dynamically, and serves explainable results through a FastAPI backend and a React dashboard.

## System Architecture
Services (microservices-ready):
1. Ingestion + NLP (FastAPI): parses logs, extracts failures with context, generates embeddings.
2. Deduplication + Clustering (ML): LSH + cosine similarity + optional Siamese model, DBSCAN/KMeans.
3. Prioritization (ML): multi-factor scoring, Optuna tuning, real-time recalculation.
4. Root Cause Analysis (Graph): temporal graph traversal + causal scoring.
5. Explainability (RAG-ready): LLM explanation with SHAP feature importance.
6. Frontend (React): dashboard, timelines, heatmaps, graph view.

Data flow (high level):
logs -> parsing + context extraction -> embeddings -> dedup -> clustering -> scoring ->
root cause + explainability -> DB -> API -> dashboard

## Folder Structure
DebugIQ/
  backend/
    main.py                    FastAPI API routes
    parser.py                  Log parsing (context-aware)
    preprocessor.py            Message normalization
    categorizer.py             Category inference
    clusterer.py               DBSCAN/KMeans clustering
    deduplicator.py            Hybrid dedup interface
    scorer.py                  Priority scoring + Optuna tuning
    database.py                SQLAlchemy models
    nlp/
      embeddings.py            Advanced embedding pipeline (CodeBERT/Longformer)
      embeddings_generator.py  Backwards-compatible wrapper
      log_extractor.py         Context-aware failure extraction
    ml/
      dedup_engine.py          LSH + embeddings + optional Siamese
      lsh_deduplicator.py      MinHash LSH
      siamese_network.py       Siamese network + contrastive loss
      train_siamese.py         Synthetic training pipeline
      root_cause_graph.py      Temporal graph RCA
      causal_inference.py      Causal scoring heuristic
      explainability.py        LLM + SHAP explainability
  frontend/
    src/components/            Dashboard components
    nginx.conf                 Production proxy for /api
  docker-compose.yml           Full stack orchestration

## Key API Routes
POST /upload
  - Upload logs and run pipeline
GET /dashboard/{run_id}
  - Dashboard aggregates
GET /failures/{run_id}
  - Row-level failures
POST /deduplicate
  - Hybrid LSH + embeddings dedup
POST /prioritize
  - Weight optimization using feedback
GET /root-cause/{run_id}/{failure_id}
  - Temporal graph root cause analysis
GET /explain/{run_id}/{failure_id}
  - LLM explanation + SHAP importance

## Deployment (Docker)
1. docker compose up --build
2. Frontend: http://localhost:5173
3. Backend: http://localhost:8000

## Notes
- Set OPENAI_API_KEY to enable LLM explanations.
- OPENAI_BASE_URL is supported for OpenAI-compatible endpoints.

## Production Architecture (Text Diagram)
```text
                        +---------------------------+
                        |        React UI           |
                        | Dashboard / Drill-down    |
                        +------------+--------------+
                                     |
                                     v
                         +-----------+-----------+
                         | API Gateway (FastAPI) |
                         | Auth, Rate Limit,     |
                         | Routing, Validation    |
                         +---+----------+---------+
                             |          |
             +---------------+          +------------------+
             v                                             v
  +----------+-----------+                      +----------+------------+
  | Ingestion/NLP Service|                      | Explainability Service |
  | Parse + Context +    |                      | RAG + LLM + SHAP      |
  | Transformer Embeds   |                      +----------+------------+
  +----------+-----------+                                 |
             |                                             v
             v                                   +---------+---------+
  +----------+-----------+                       | Incident KB Store |
  | Dedup/Cluster Service|                       | (docs/playbooks)  |
  | MinHash+LSH+Siamese  |                       +-------------------+
  +----------+-----------+
             |
             v
  +----------+------------+        +--------------------------+
  | Prioritization Service|<------>| Historical Failure Store |
  | Dynamic weighted score|        | SQL (runs, failures)     |
  +----------+------------+        +--------------------------+
             |
             v
  +----------+------------+
  | Root Cause Service    |
  | Temporal Graph +      |
  | Causal Heuristics     |
  +-----------------------+
```

## Model Design Notes
- **Embeddings:** `CodeBERT` for normal logs; optional long-sequence mode via `Longformer` switch.
- **Context-aware extraction:** multi-line context windows and severity-aware extraction in `backend/nlp/log_extractor.py`.
- **Dedup:** MinHash LSH candidate retrieval + embedding cosine confirmation + Siamese model training scaffold (`backend/ml/train_siamese.py`).
- **Prioritization:** weighted score over severity/frequency/module/historical recurrence, with Optuna tuning and real-time reranking.
- **Root Cause:** temporal directed graph + ancestor traversal + causal score estimator.
- **Explainability:** retrieval snippets + LLM summary + SHAP feature contribution.

## API Request/Response Examples
- **POST `/deduplicate`**
  - Request:
    ```json
    {
      "logs": ["ERROR AXI timeout", "ERROR AXI timeout after retry"],
      "similarity_threshold": 0.9
    }
    ```
  - Response:
    ```json
    {
      "unique_ids": [1, 1],
      "is_duplicate": [false, true],
      "total_logs": 2,
      "unique_count": 1,
      "duplicate_count": 1
    }
    ```
- **POST `/prioritize`**
  - Request:
    ```json
    {
      "feedback": [
        {"severity": "FATAL", "module": "AXI_INTERFACE", "frequency": 7, "is_critical": true, "history": 9, "module_impact": 1.0},
        {"severity": "WARNING", "module": "ALU", "frequency": 2, "is_critical": false, "history": 1, "module_impact": 0.3}
      ]
    }
    ```
  - Response:
    ```json
    {
      "new_weights": {"severity": 0.41, "frequency": 0.31, "module": 0.19, "history": 0.09},
      "ranked_failures": [
        {"severity": "FATAL", "module": "AXI_INTERFACE", "frequency": 7, "is_critical": true, "history": 9, "module_impact": 1.0, "score": 0.94, "rank": 1}
      ]
    }
    ```

## Frontend Integration Guide
- API client wrappers are in `frontend/src/api/api.js`.
- Use `deduplicateLogs(logs)` for batch dedup checks.
- Use `prioritizeFailures(feedback)` to rerank live incident lists.
- Use `getRootCause(runId, failureId)` and `getExplanation(runId, failureId)` for drill-down panel content.
- JWT is persisted as `debugiq_token` and attached automatically in request interceptor.

## Deployment Steps (Docker)
1. Set env vars:
   - `DEBUGIQ_JWT_SECRET=<strong-random-secret>`
   - `GEMINI_API_KEY=<your-key>` (optional for live explanation)
2. Build and run:
   - `docker compose up --build`
3. Access:
   - Frontend: `http://localhost:5173`
   - Backend API docs: `http://localhost:8000/docs`
   - RabbitMQ UI: `http://localhost:15672`
4. Scale backend replicas (example): `docker compose up --scale backend=3 -d`
