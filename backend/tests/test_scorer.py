from scorer import compute_scores


def test_compute_scores_basic():
    severities = ["ERROR", "WARNING", "FATAL"]
    modules = ["AXI_INTERFACE", "ALU", "MEMORY_CTRL"]
    unique_ids = [1, 2, 1]

    scores, freq = compute_scores(severities, modules, unique_ids)
    assert len(scores) == 3
    assert freq[1] == 2
    for score in scores:
        assert 0.0 <= score <= 1.0
