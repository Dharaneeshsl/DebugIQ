from dataclasses import dataclass
from typing import List, Tuple

import numpy as np

from ml.lsh_deduplicator import FastDeduplicator
from nlp.embeddings import generate_embeddings, EmbeddingConfig


@dataclass
class DedupConfig:
    lsh_threshold: float = 0.85
    similarity_threshold: float = 0.9
    use_siamese: bool = False


class DedupEngine:
    """
    Hybrid deduplication:
    1) MinHash LSH for fast candidate retrieval
    2) Embedding cosine similarity for precision
    3) Optional Siamese model for learned similarity
    """

    def __init__(self, config: DedupConfig | None = None):
        self.config = config or DedupConfig()
        self.lsh = FastDeduplicator(threshold=self.config.lsh_threshold)
        self.siamese = None
        if self.config.use_siamese:
            try:
                from ml.siamese_network import SiameseNetwork
                self.siamese = SiameseNetwork()
            except Exception:
                # Keep runtime resilient when torch is unavailable.
                self.siamese = None

    def _cosine_sim(self, a: np.ndarray, b: np.ndarray) -> float:
        denom = float(np.linalg.norm(a) * np.linalg.norm(b))
        if denom == 0:
            return 0.0
        return float(np.dot(a, b) / denom)

    def deduplicate(self, messages: List[str]) -> Tuple[List[int], List[bool], np.ndarray]:
        if not messages:
            return [], [], np.array([])

        embeddings = generate_embeddings(messages, EmbeddingConfig())
        unique_ids: List[int] = []
        is_duplicate: List[bool] = []
        unique_embeddings: List[np.ndarray] = []

        next_id = 1
        lsh_ids, lsh_dup = self.lsh.process_logs(messages)

        for idx, emb in enumerate(embeddings):
            if not unique_embeddings:
                unique_embeddings.append(emb)
                unique_ids.append(next_id)
                is_duplicate.append(False)
                next_id += 1
                continue

            # LSH says duplicate? confirm with embeddings
            if lsh_dup[idx]:
                cand_idx = max(0, lsh_ids[idx] - 1)
                cand_idx = min(cand_idx, len(unique_embeddings) - 1)
                sim = self._cosine_sim(unique_embeddings[cand_idx], emb)
                if sim >= self.config.similarity_threshold:
                    unique_ids.append(unique_ids[cand_idx])
                    is_duplicate.append(True)
                    continue

            # Otherwise do a full scan on unique embeddings
            sims = np.dot(np.vstack(unique_embeddings), emb)
            max_idx = int(np.argmax(sims))
            max_sim = float(sims[max_idx])

            if max_sim >= self.config.similarity_threshold:
                unique_ids.append(unique_ids[max_idx])
                is_duplicate.append(True)
            else:
                unique_embeddings.append(emb)
                unique_ids.append(next_id)
                is_duplicate.append(False)
                next_id += 1

        return unique_ids, is_duplicate, embeddings
