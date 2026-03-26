import optuna
from typing import Dict, List, Tuple
from collections import Counter

SEVERITY_WEIGHTS = {
    "FATAL": 1.0,
    "ERROR": 0.7,
    "WARNING": 0.4,
    "INFO": 0.1,
}

MODULE_WEIGHTS = {
    "AXI_INTERFACE": 1.0,
    "MEMORY_CTRL": 0.9,
    "CACHE_CTRL": 0.8,
    "ALU": 0.7,
}

_current_weights = {
    "severity": 0.4,
    "frequency": 0.3,
    "module": 0.2,
    "history": 0.1,
}

def get_current_weights() -> Dict[str, float]:
    return _current_weights

def set_current_weights(w_sev: float, w_freq: float, w_mod: float, w_hist: float = 0.0):
    global _current_weights
    total = w_sev + w_freq + w_mod + w_hist
    if total > 0:
        _current_weights["severity"] = w_sev / total
        _current_weights["frequency"] = w_freq / total
        _current_weights["module"] = w_mod / total
        _current_weights["history"] = w_hist / total

def compute_scores(
    severities: List[str],
    modules: List[str],
    unique_ids: List[int],
    history_keys: List[str] | None = None,
    history_counts: Dict[str, int] | None = None,
    weights: Dict[str, float] | None = None,
) -> Tuple[List[float], Dict[int, int]]:
    freq_counter = Counter(unique_ids)
    max_freq = max(freq_counter.values()) if freq_counter else 1
    history_counts = history_counts or {}
    max_hist = max(history_counts.values()) if history_counts else 1

    w = weights or _current_weights
    scores: List[float] = []
    for idx, (sev, mod, uid) in enumerate(zip(severities, modules, unique_ids)):
        sev_w = SEVERITY_WEIGHTS.get(sev, 0.1)
        freq_w = freq_counter[uid] / max_freq
        mod_w = MODULE_WEIGHTS.get(mod, 0.5)
        hist_key = history_keys[idx] if history_keys else f"{mod}:{sev}"
        hist_w = history_counts.get(hist_key, 0) / max_hist
        
        score = (
            (sev_w * w["severity"])
            + (freq_w * w["frequency"])
            + (mod_w * w["module"])
            + (hist_w * w["history"])
        )
        scores.append(round(score, 4))

    return scores, dict(freq_counter)

def optimize_weights(feedback_data: List[Dict]):
    if not feedback_data:
        return get_current_weights()

    def objective(trial):
        w_sev = trial.suggest_float("w_sev", 0.0, 1.0)
        w_freq = trial.suggest_float("w_freq", 0.0, 1.0)
        w_mod = trial.suggest_float("w_mod", 0.0, 1.0)
        w_hist = trial.suggest_float("w_hist", 0.0, 1.0)
        
        total = w_sev + w_freq + w_mod + w_hist
        if total == 0:
            return 1e6
        w_sev /= total
        w_freq /= total
        w_mod /= total
        w_hist /= total
        
        loss = 0.0
        max_freq = max([d["frequency"] for d in feedback_data])
        max_hist = max([d.get("history", 0) for d in feedback_data]) or 1
        
        for d in feedback_data:
            sev_w = SEVERITY_WEIGHTS.get(d["severity"], 0.1)
            freq_w = d["frequency"] / max_freq
            mod_w = MODULE_WEIGHTS.get(d["module"], 0.5)
            hist_w = d.get("history", 0) / max_hist
            
            score = (sev_w * w_sev) + (freq_w * w_freq) + (mod_w * w_mod) + (hist_w * w_hist)
            if d.get("is_critical"):
                loss += (1.0 - score) ** 2
            else:
                loss += (0.0 - score) ** 2
        return loss

    optuna.logging.set_verbosity(optuna.logging.WARNING)
    study = optuna.create_study(direction="minimize")
    study.optimize(objective, n_trials=50)
    
    best = study.best_params
    set_current_weights(best["w_sev"], best["w_freq"], best["w_mod"], best["w_hist"])
    return get_current_weights()


def prioritize_failures(items: List[Dict]) -> List[Dict]:
    """
    Real-time multi-factor priority calculation for external callers.
    Expected fields per item:
      - severity (str)
      - module (str)
      - frequency (int)
      - history (int, optional)
      - module_impact (float, optional, default 1.0)
    """
    if not items:
        return []

    w = get_current_weights()
    max_freq = max([max(int(i.get("frequency", 0)), 0) for i in items]) or 1
    max_hist = max([max(int(i.get("history", 0)), 0) for i in items]) or 1
    max_mod_impact = max([max(float(i.get("module_impact", 1.0)), 0.0) for i in items]) or 1.0

    ranked = []
    for idx, item in enumerate(items):
        sev = str(item.get("severity", "INFO")).upper()
        mod = str(item.get("module", "UNKNOWN"))
        sev_w = SEVERITY_WEIGHTS.get(sev, 0.1)
        freq_w = max(int(item.get("frequency", 0)), 0) / max_freq
        hist_w = max(int(item.get("history", 0)), 0) / max_hist
        mod_base_w = MODULE_WEIGHTS.get(mod, 0.5)
        mod_impact = max(float(item.get("module_impact", 1.0)), 0.0) / max_mod_impact
        mod_w = min(1.0, mod_base_w * (0.5 + 0.5 * mod_impact))

        score = (
            sev_w * w["severity"]
            + freq_w * w["frequency"]
            + mod_w * w["module"]
            + hist_w * w["history"]
        )
        ranked.append({**item, "score": round(float(score), 4), "rank": idx + 1})

    ranked.sort(key=lambda x: x["score"], reverse=True)
    for i, r in enumerate(ranked):
        r["rank"] = i + 1
    return ranked
