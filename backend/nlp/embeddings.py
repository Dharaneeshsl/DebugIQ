from typing import List, Optional
import logging
import os

import numpy as np
from pydantic import BaseModel

SentenceTransformer = None
try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.preprocessing import normalize as sk_normalize
except ImportError:
    TfidfVectorizer = None
    sk_normalize = None

logger = logging.getLogger(__name__)

class EmbeddingConfig(BaseModel):
    use_longformer: bool = False
    max_length: int = 512

_models = {}
_failed_models = set()


def _load_sentence_transformer():
    global SentenceTransformer
    if SentenceTransformer is not None:
        return SentenceTransformer
    try:
        from sentence_transformers import SentenceTransformer as _SentenceTransformer
    except Exception as exc:
        raise ImportError("sentence-transformers is missing") from exc
    SentenceTransformer = _SentenceTransformer
    return SentenceTransformer

def _get_model(config: EmbeddingConfig):
    sentence_transformer_cls = _load_sentence_transformer()
        
    model_name = "allenai/longformer-base-4096" if config.use_longformer else "microsoft/codebert-base"
    if model_name in _failed_models:
        raise RuntimeError(f"Transformer model previously failed to load: {model_name}")
    if model_name not in _models:
        logger.info(f"Loading NLP Transformer model: {model_name}")
        try:
            _models[model_name] = sentence_transformer_cls(model_name)
        except Exception as exc:
            _failed_models.add(model_name)
            raise exc
    return _models[model_name]

def _tfidf_fallback_embeddings(texts: List[str], max_features: int = 512) -> np.ndarray:
    if TfidfVectorizer is None or sk_normalize is None:
        raise ImportError("scikit-learn is required for TF-IDF fallback embeddings")
    vectorizer = TfidfVectorizer(ngram_range=(1, 2), max_features=max_features)
    matrix = vectorizer.fit_transform(texts)
    return sk_normalize(matrix).toarray()

def generate_embeddings(texts: List[str], config: Optional[EmbeddingConfig] = None) -> np.ndarray:
    if config is None:
        config = EmbeddingConfig()
        
    if not texts:
        return np.array([])
    
    backend_override = os.environ.get("DEBUGIQ_EMBEDDINGS_BACKEND", "").strip().lower()
    if backend_override in {"tfidf", "hash"}:
        logger.warning("DEBUGIQ_EMBEDDINGS_BACKEND=%s set; using TF-IDF fallback.", backend_override)
        return _tfidf_fallback_embeddings(texts)

    try:
        model = _get_model(config)
        return model.encode(texts, normalize_embeddings=True)
    except Exception as exc:
        logger.warning("Transformer embeddings unavailable, falling back to TF-IDF. Error: %s", exc)
        return _tfidf_fallback_embeddings(texts)
