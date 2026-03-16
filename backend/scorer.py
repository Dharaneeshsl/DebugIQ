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


def compute_scores(severities: List[str], modules: List[str], unique_ids: List[int]) -> Tuple[List[float], Dict[int, int]]:
    freq_counter = Counter(unique_ids)
    max_freq = max(freq_counter.values()) if freq_counter else 1

    scores: List[float] = []
    for sev, mod, uid in zip(severities, modules, unique_ids):
        sev_w = SEVERITY_WEIGHTS.get(sev, 0.1)
        freq_w = freq_counter[uid] / max_freq
        mod_w = MODULE_WEIGHTS.get(mod, 0.5)
        score = (sev_w * 0.4) + (freq_w * 0.3) + (mod_w * 0.3)
        scores.append(round(score, 4))

    return scores, dict(freq_counter)