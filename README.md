# DebugIQ — AI-Enabled Debug Prioritization

DebugIQ is an AI-powered simulation log analysis platform that parses regression logs, detects duplicate failures, categorizes errors, clusters related issues, and ranks failures by debugging priority. Results are stored in SQLite and surfaced through a React dashboard.

## Tech Stack
- Frontend: React (Vite) + Recharts + Axios + TailwindCSS
- Backend: FastAPI (Python)
- NLP: Sentence Transformers (all-MiniLM-L6-v2)
- Clustering: DBSCAN / K-Means (Scikit-learn)
- Data: Pandas / NumPy
- DB: SQLite (SQLAlchemy)
- Deployment: Docker + docker-compose

## Project Structure
```
debugiq/
+-- backend/
¦   +-- main.py
¦   +-- parser.py
¦   +-- preprocessor.py
¦   +-- categorizer.py
¦   +-- deduplicator.py
¦   +-- clusterer.py
¦   +-- scorer.py
¦   +-- database.py
¦   +-- schemas.py
¦   +-- sample_data.py
¦   +-- requirements.txt
¦   +-- Dockerfile
+-- frontend/
¦   +-- src/
¦   ¦   +-- App.jsx
¦   ¦   +-- components/
¦   ¦   +-- api/api.js
¦   ¦   +-- main.jsx
¦   +-- package.json
¦   +-- Dockerfile
+-- docker-compose.yml
```

## Backend Pipeline
1. Parse logs with regex
2. Preprocess messages (clean + tokenize)
3. Categorize with keywords + sentence-transformers
4. Deduplicate by embedding similarity > 0.92
5. Cluster with DBSCAN, fallback to K-Means
6. Score by severity, frequency, module weight
7. Store in SQLite via SQLAlchemy

## API Endpoints
- `POST /upload` — upload log, run full pipeline
- `GET /dashboard/{run_id}` — dashboard aggregate
- `GET /failures/{run_id}` — full failure list
- `GET /runs` — list runs
- `DELETE /run/{run_id}` — delete run
- `GET /report/{run_id}?format=csv` — export CSV

## Sample Logs
Generate sample log:
```bash
cd backend
python sample_data.py
```
Output: `backend/sample_logs/test.log`

## Local Development
Backend:
```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000
```
Frontend:
```bash
cd frontend
npm install
npm run dev
```
Frontend runs on `http://localhost:5173` and calls backend at `http://localhost:8000`.

## Docker
```bash
docker compose up --build
```
Frontend: `http://localhost:5173`
Backend: `http://localhost:8000`