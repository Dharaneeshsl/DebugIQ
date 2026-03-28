"""
Full log → ML pipeline (parse → preprocess → categorize → dedup → cluster → score)
with Mongo I/O mocked so tests run without a live database.
"""
from __future__ import annotations

from datetime import datetime
from unittest.mock import patch

import pytest

from services.pipeline import process_log_text


SAMPLE_LOG = """[12:00:00.100] ERROR CPU line 10 UVM_ERROR: instruction fetch timeout
[12:00:01.200] FATAL MMU line 55 UVM_FATAL: page table walk failed
[12:00:02.190] ERROR CACHE_CTRL line 730 UVM_ERROR: cache line dirty miss
ASSERTION FAILED: axi_valid_stable at axi_intf.sv:142
"""


@pytest.fixture
def mongo_patches():
    fake_run = {"_id": 4242, "uploaded_at": datetime.utcnow()}
    with (
        patch("services.pipeline.get_history_counts", return_value={}),
        patch("services.pipeline.get_weights", return_value=None),
        patch("services.pipeline.create_run", return_value=fake_run) as cr,
        patch("services.pipeline.add_failures") as af,
    ):
        yield {"create_run": cr, "add_failures": af, "fake_run": fake_run}


def test_process_log_text_full_pipeline(mongo_patches) -> None:
    out = process_log_text(SAMPLE_LOG, "unit_test.log", user_id=7)

    assert out["run_id"] == 4242
    assert out["total_failures"] >= 1
    assert out["unique_failures"] >= 1
    assert "health_score" in out
    assert "critical_count" in out

    mongo_patches["create_run"].assert_called_once()
    mongo_patches["add_failures"].assert_called_once()
    _run_id, failures = mongo_patches["add_failures"].call_args[0]
    assert _run_id == 4242
    assert len(failures) == out["total_failures"]
    for row in failures:
        assert "category" in row
        assert "priority_score" in row
        assert "cluster_id" in row
        assert "unique_failure_id" in row


def test_process_log_text_empty_raises() -> None:
    with (
        patch("services.pipeline.get_history_counts", return_value={}),
        patch("services.pipeline.get_weights", return_value=None),
    ):
        with pytest.raises(ValueError, match="No valid log lines"):
            process_log_text("   \n\t  ", "empty.log", user_id=1)
