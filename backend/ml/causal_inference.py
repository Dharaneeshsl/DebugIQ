from typing import Dict, List


def estimate_causal_score(failure: Dict, history: List[Dict]) -> float:
    """
    Lightweight causal heuristic:
    - boost if earlier failures share module/category
    - boost for higher severity in history
    This stands in for DoWhy-style analysis without extra deps.
    """
    if not history:
        return 0.0

    module = failure.get("module")
    category = failure.get("category")
    severity = failure.get("severity")

    sev_weight = {"INFO": 0.1, "WARNING": 0.4, "ERROR": 0.7, "FATAL": 1.0}
    base = sev_weight.get(severity, 0.2)

    shared = 0
    for h in history:
        if h.get("module") == module or h.get("category") == category:
            shared += 1
    return round(base + (shared / max(len(history), 1)) * 0.6, 3)
