from typing import List, Tuple

import numpy as np

from ml.dedup_engine import DedupEngine, DedupConfig


def deduplicate(messages: List[str]) -> Tuple[List[int], List[bool], np.ndarray]:
    engine = DedupEngine(DedupConfig())
    return engine.deduplicate(messages)
