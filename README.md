## DebugIQ – AI-Powered Simulation Log Intelligence

**DebugIQ** is an AI-powered simulation log analysis system designed to automate debug prioritization during chip verification. The system ingests large simulation logs and intelligently processes them to extract structured information, clean and preprocess error messages, and apply AI-based analysis. It categorizes failures, detects duplicate errors, clusters similar issues, and analyzes their frequency and module impact. Using this information, the system ranks failures based on severity, frequency, and module importance to determine debugging priority. The analyzed data is stored in a structured database and presented through an interactive dashboard with visual insights such as module hotspots and failure timelines. The system also provides advanced capabilities like regression health scoring, known bug detection, failure signature generation, root cause suggestions, and a debug recommendation engine. Finally, DebugIQ generates automated reports that help engineers quickly understand critical issues and focus on fixing the most impactful bugs, significantly reducing manual debugging effort.

---

## 🛠️ Workflow (Covering All 17 Features)

1.  **Simulation Log Ingestion**: Collects raw simulation log files generated during verification runs.
2.  **Intelligent Log Parsing**: Extracts timestamps, module names, severity levels, and error messages.
3.  **Log Preprocessing**: Cleans and normalizes log data for further analysis.
4.  **AI Failure Categorization**: Classifies failures (Assertion, Timeout, Protocol, Data Mismatch) using Machine Learning.
5.  **Duplicate Failure Detection and Clustering**: Groups similar messages into unique failure clusters.
6.  **Failure Frequency Analysis and Signature Generation**: Calculates occurrence rates and generates unique failure signatures.
7.  **Debug Priority Ranking**: Ranks clusters based on severity, frequency, and module criticality.
8.  **Module Hotspot Identification**: Highlights modules with high failure rates.
9.  **Regression Health Score Calculation**: Evaluates the overall quality of the regression run.
10. **Known Bug Detection**: Identifies recurring issues by comparing with stored failure data.
11. **Failure Timeline Analysis**: Detects failure spikes and patterns over time.
12. **Root Cause Suggestion**: Suggests possible causes based on patterns and categories.
13. **Debug Recommendation Engine**: Provides actionable debugging steps.
14. **Structured Failure Database Storage**: Stores all analyzed data in SQLite.
15. **Interactive Debug Dashboard**: Visualizes processing results (10 Major Panels).
16. **Automatic Debug Report Generation**: Exports summarized reports (TXT/MD).
17. **Fast Log Processing Engine**: Efficiently processes large regression outputs.

---

## 🚀 New Features (10 Major Panels)

The dashboard has been enhanced with 10 specialized intelligence panels:

1.  **Regression Overview**: Real-time metrics for health score, total, unique, and critical failures.
2.  **Failure Priority Ranking**: Sortable ranking of failures using the DebugIQ Priority Score.
3.  **Failure Category Distribution**: Visual breakdown of failure types (Assertion, Timeout, etc.).
4.  **Failure Clusters**: Semantic grouping of similar log messages using Sentence-Transformers.
5.  **Module Hotspot Analysis**: Identification of the most problematic RTL modules (e.g., CACHE_CTRL).
6.  **Failure Timeline**: Chronological distribution of failures vs. priority.
7.  **Root Cause Suggestions**: AI/Rule-based analysis of probable failure causes.
8.  **Debug Recommendations**: Concrete, actionable steps for developers based on context.
9.  **Known Bug Detection**: Highlighting failures that match previously identified signatures.
10. **Debug Report Download**: Facility to export analysis results in Text and Markdown formats.

---

## 🏗️ Technical Architecture

DebugIQ now follows a modern full-stack architecture:
- **Core Engine**: Python-based NLP and analysis pipeline.
- **Backend API**: Flask serving structured JSON data and reports.
- **Frontend**: React (Vite) with Recharts for high-performance visualization.
- **Database**: SQLite for persistent storage of enriched failure data.

---

## 📁 Project Structure

```text
debugiq/
├── frontend/              # React (Vite) Application
│   ├── src/App.jsx        # Main Dashboard UI (10 Panels)
│   └── src/index.css      # Custom styling
├── logs/                  # Raw simulation logs (auto-generated if empty)
├── data/                  # SQLite DB + generated reports
├── api.py                 # Flask Backend API
├── main.py                # Analysis Pipeline Entrypoint
├── parser.py              # Log Ingestion & Parsing
├── classifier.py          # TF-IDF + Logistic Regression
├── clustering.py          # Semantic KMeans Clustering
└── database.py            # SQLite Schema & Operations
```

---

## 🛠️ Setup & Execution

### 1. Install Dependencies
Ensure you have Python and Node.js installed.
```bash
# Python dependencies
pip install -r requirements.txt

# Frontend dependencies
cd frontend
npm install
```

### 2. Run the Analysis Pipeline
Extract and analyze log data first:
```bash
python main.py
```

### 3. Start the Dashboard
You need to run both the API and the Frontend:

**Terminal 1 (Backend API):**
```bash
uvicorn api:app --host 0.0.0.0 --port 5000
```

**Terminal 2 (React Frontend):**
```bash
cd frontend
npm run dev
```

The dashboard will be available at **http://localhost:3000**.

---

## 🐳 Docker (Full Stack)

Build and run both backend and frontend with Docker Compose:

```bash
docker compose up --build
```

Services:
- Frontend: http://localhost:3000
- Backend API: http://localhost:5000

### Frontend API Base URL (Deployments)
For hosted frontend (e.g., Vercel), set:
```
VITE_API_BASE_URL=https://your-backend.example.com
```
If unset, the frontend uses same-origin `/api` (works with Docker + nginx).

To stop:
```bash
docker compose down
```

---

## 🚀 Deployment (Vercel + Backend Host)

### 1) Deploy Backend (Docker)
Build and run the backend container on any Docker host:
```bash
docker build -f Dockerfile.backend -t debuqi-backend .
docker run -d -p 5000:5000 --name debuqi-backend debuqi-backend
```
Then run the analysis pipeline once to populate the DB:
```bash
python main.py
```

### 2) Deploy Frontend (Vercel)
In Vercel Project Settings:
- Root Directory: `frontend/`
- Build Command: `npm run build`
- Output Directory: `dist`
- Env Var: `VITE_API_BASE_URL=https://your-backend.example.com`

Alternatively, keep frontend calling `/api` and add a Vercel rewrite:
```
API_BASE_URL=https://your-backend.example.com
```

---

## 🔍 Log Format
DebugIQ expects logs in the following format:
`[TIME:<timestamp>] [<severity>] [<module>] <message>`

*Example:*
`[TIME:12500ns] [ERROR] [CACHE_CTRL] Assertion failed: cache_hit_on_invalid_line`

---

## 📈 Debug Priority Scoring
Priority is calculated using a weighted formula:
\[
\text{priority} = 0.4\cdot \text{severity} + 0.3\cdot \log(\text{freq}) + 0.2\cdot \text{cluster\_size} + 0.1\cdot \text{module\_crit}
\]

