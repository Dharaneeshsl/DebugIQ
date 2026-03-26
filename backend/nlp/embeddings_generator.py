import numpy as np
from typing import List

from nlp.embeddings import generate_embeddings as _generate_embeddings


def generate_embeddings(texts: List[str]) -> np.ndarray:
    """
    Backward-compatible wrapper around the advanced embedding pipeline.
    """
    return _generate_embeddings(texts)

def chunk_long_logs(log: str, max_length: int = 512) -> List[str]:
    """
    Utility func to chunk long multi-line logs if they exceed context window.
    CodeBERT has a context window of 512 tokens.
    """
    # A simple word-level chunking for approximation
    words = log.split()
    chunks = []
    # ~380 words is a safe bound for 512 subword tokens
    CHUNK_SIZE = 380 
    for i in range(0, len(words), CHUNK_SIZE):
        chunks.append(" ".join(words[i:i+CHUNK_SIZE]))
    return chunks

def extract_structured_failures(log_messages: List[str]) -> List[dict]:
    """
    Dummy layout for a more context-aware extractor if needed later.
    Currently, the parser handles regex. Here we can integrate LLMs or 
    NLP logic to pull out more complex metadata.
    """
    # ... placeholder for deeper NLP logic ...
    return [{"original": m} for m in log_messages]
