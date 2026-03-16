from typing import List, Dict, Tuple
from sentence_transformers import SentenceTransformer
import numpy as np

DUP_THRESHOLD = 0.92

_model = None


def _get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        _model = SentenceTransformer("all-MiniLM-L6-v2")
    return _model


def deduplicate(messages: List[str]) -> Tuple[List[int], List[bool], np.ndarray]:
    model = _get_model()
    embeddings = model.encode(messages, normalize_embeddings=True)
    unique_ids: List[int] = []
    is_duplicate: List[bool] = []
    unique_embeddings: List[np.ndarray] = []

    next_id = 1
    for emb in embeddings:
        if not unique_embeddings:
            unique_embeddings.append(emb)
            unique_ids.append(next_id)
            is_duplicate.append(False)
            next_id += 1
            continue

        sims = np.dot(np.vstack(unique_embeddings), emb)
        max_idx = int(np.argmax(sims))
        max_sim = float(sims[max_idx])
        if max_sim >= DUP_THRESHOLD:
            unique_ids.append(unique_ids[max_idx])
            is_duplicate.append(True)
        else:
            unique_embeddings.append(emb)
            unique_ids.append(next_id)
            is_duplicate.append(False)
            next_id += 1

    return unique_ids, is_duplicate, embeddings