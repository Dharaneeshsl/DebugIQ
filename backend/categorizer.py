from typing import List
import logging
import os

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

SentenceTransformer = None

CATEGORIES = [
    "uvm_fatal",
    "uvm_error",
    "uvm_warning",
    "uvm_phase_error",
    "uvm_sequence_error",
    "uvm_scoreboard_mismatch",
    "sva_assertion_failure",
    "assertion_failure",
    "timeout_error",
    "protocol_violation",
    "data_mismatch",
    "memory_error",
]

KEYWORDS = {
    "uvm_fatal": ["uvm_fatal", "uvm fatal"],
    "uvm_error": ["uvm_error", "uvm error"],
    "uvm_warning": ["uvm_warning", "uvm warning"],
    "uvm_phase_error": ["build_phase", "connect_phase", "run_phase", "extract_phase", "check_phase", "report_phase"],
    "uvm_sequence_error": ["uvm_sequence", "sequence error", "sequence", "objection dropped"],
    "uvm_scoreboard_mismatch": ["scoreboard", "scb", "expected got", "compare fail", "mismatch in scoreboard"],
    "sva_assertion_failure": ["sva", "assert property", "assertion failed", "sva error"],
    "assertion_failure": ["assertion", "assert"],
    "timeout_error": ["timeout", "timed out", "stall"],
    "protocol_violation": ["protocol", "handshake", "sequence", "ordering"],
    "data_mismatch": ["mismatch", "expected", "got"],
    "memory_error": ["ecc", "decode", "address", "memory"],
}

logger = logging.getLogger(__name__)
_model = None
_label_embeddings = None
_tfidf_skip_logged = False


def _force_tfidf_semantic_categorization() -> bool:
    """Match nlp/embeddings.py: skip sentence-transformers when offline/fast path requested."""
    b = os.environ.get("DEBUGIQ_EMBEDDINGS_BACKEND", "").strip().lower()
    return b in {"tfidf", "hash"}


def _categorize_tfidf_semantic(message: str) -> str:
    corpus = CATEGORIES + [message]
    vec = TfidfVectorizer(ngram_range=(1, 2))
    mat = vec.fit_transform(corpus)
    sims = cosine_similarity(mat[-1], mat[:-1])[0]
    return CATEGORIES[int(np.argmax(sims))]


def _get_model() -> SentenceTransformer:
    global _model, SentenceTransformer
    if SentenceTransformer is None:
        try:
            from sentence_transformers import SentenceTransformer as _SentenceTransformer
            SentenceTransformer = _SentenceTransformer
        except Exception as exc:
            raise ImportError("sentence-transformers unavailable") from exc
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
    if _force_tfidf_semantic_categorization():
        global _tfidf_skip_logged
        if not _tfidf_skip_logged:
            logger.warning(
                "DEBUGIQ_EMBEDDINGS_BACKEND=tfidf (or hash); categorizer uses TF-IDF only — not loading MiniLM."
            )
            _tfidf_skip_logged = True
        return _categorize_tfidf_semantic(message)
    try:
        model = _get_model()
        label_embeddings = _get_label_embeddings()
        msg_emb = model.encode([message], normalize_embeddings=True)[0]
        scores = np.dot(label_embeddings, msg_emb)
        return CATEGORIES[int(np.argmax(scores))]
    except Exception:
        return _categorize_tfidf_semantic(message)


def categorize_messages(messages: List[str]) -> List[str]:
    return [categorize_message(m) for m in messages]
