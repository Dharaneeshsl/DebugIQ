from typing import List, Optional
from pydantic import BaseModel


class FailureRecord(BaseModel):
    id: Optional[int] = None
    timestamp: str
    severity: str
    module: str
    line_no: int
    message: str
    category: str
    cluster_id: int
    priority_score: float
    is_duplicate: bool
    unique_failure_id: int


class RegressionRunRecord(BaseModel):
    id: int
    filename: str
    uploaded_at: str
    total_failures: int
    unique_failures: int
    critical_count: int
    health_score: float


class UploadResponse(BaseModel):
    run_id: int
    total_failures: int
    unique_failures: int
    critical_count: int
    health_score: float


class DashboardResponse(BaseModel):
    health_score: float
    total_failures: int
    unique_failures: int
    critical_count: int
    category_distribution: List[dict]
    module_hotspots: List[dict]
    priority_ranking: List[dict]
    failure_clusters: List[dict]
    failure_timeline: List[dict]
    root_cause_suggestions: List[dict]
    debug_recommendations: List[dict]