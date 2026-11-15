import numpy as np

from clusterer import cluster_embeddings
from ml.dedup_engine import DedupEngine
from nlp.embeddings import generate_embeddings


def test_duplicate_representatives_after_repeated_messages(monkeypatch):
    monkeypatch.setenv("DEBUGIQ_EMBEDDINGS_BACKEND", "tfidf")
    ids, duplicates, _ = DedupEngine().deduplicate([
        "alpha transfer timeout", "alpha transfer timeout",
        "beta memory corruption", "beta memory corruption",
        "gamma protocol violation", "gamma protocol violation",
    ])
    assert ids == [1, 1, 2, 2, 3, 3]
    assert duplicates == [False, True, False, True, False, True]


def test_single_and_identical_cluster_points():
    for matrix in (np.array([[1.0]]), np.ones((3, 1))):
        labels, points = cluster_embeddings(matrix)
        assert len(labels) == len(matrix)
        assert all(np.isfinite(point["x"]) and np.isfinite(point["y"]) for point in points)


def test_short_messages_have_finite_embeddings(monkeypatch):
    monkeypatch.setenv("DEBUGIQ_EMBEDDINGS_BACKEND", "tfidf")
    result = generate_embeddings(["x", "!"])
    assert result.shape[0] == 2
    assert np.isfinite(result).all()


def test_matching_ignores_timestamps_and_positions(monkeypatch):
    from preprocessor import preprocess_records
    monkeypatch.setenv("DEBUGIQ_EMBEDDINGS_BACKEND", "tfidf")
    messages = preprocess_records([
        "[12:00:00.100] ERROR CPU line 10 UVM_ERROR: instruction fetch timeout",
        "[12:00:03.100] ERROR CPU line 14 UVM_ERROR: instruction fetch timeout",
    ])
    ids, _, _ = DedupEngine().deduplicate(messages)
    assert ids == [1, 1]
