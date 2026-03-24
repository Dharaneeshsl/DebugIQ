from typing import List
from sentence_transformers import SentenceTransformer
import numpy as np

CATEGORIES = [
    "assertion_failure",
    "timeout_error",
    "protocol_violation",
    "data_mismatch",
    "memory_error",
]

KEYWORDS = {
    "assertion_failure": ["assertion", "assert"],
    "timeout_error": ["timeout", "timed out", "stall"],
    "protocol_violation": ["protocol", "handshake", "sequence", "ordering"],
    "data_mismatch": ["mismatch", "expected", "got"],
    "memory_error": ["ecc", "decode", "address", "memory"],
}

_model = None
_label_embeddings = None


def _get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        _model = SentenceTransformer("all-MiniLM-L6-v2")
    return _model


def _get_label_embeddings() -> np.ndarray:
    global _label_embeddings
    if _label_embeddings is None:
        model = _get_model()
        _label_embeddings = model.encode(CATEGORIES, normalize_embeddings=True)
    return _label_embeddings


def categorize_message(message: str) -> str:
    lowered = message.lower()
    for category, keys in KEYWORDS.items():
        if any(k in lowered for k in keys):
            return category
    model = _get_model()
    label_embeddings = _get_label_embeddings()
    msg_emb = model.encode([message], normalize_embeddings=True)[0]
    scores = np.dot(label_embeddings, msg_emb)
    return CATEGORIES[int(np.argmax(scores))]


def categorize_messages(messages: List[str]) -> List[str]:
    return [categorize_message(m) for m in messages]