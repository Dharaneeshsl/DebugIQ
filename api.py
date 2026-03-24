from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pathlib import Path

from database import read_failures
from analysis import summarize_for_report

app = FastAPI(title="DebugIQ API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DATA_DIR = Path("data")


@app.get("/api/failures")
def get_failures():
    df = read_failures()
    if df.empty:
        return []
    return df.to_dict(orient="records")


@app.get("/api/summary")
def get_summary():
    df = read_failures()
    if df.empty:
        return {
            "total_failures": 0,
            "unique_failures": 0,
            "regression_health_score": 100,
            "problematic_modules": [],
        }
    return summarize_for_report(df)


@app.get("/api/report/{filename}")
def get_report(filename: str):
    if filename not in ("debug_report.txt", "debug_report.md"):
        raise HTTPException(status_code=404, detail="File not found")
    file_path = DATA_DIR / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(file_path)
