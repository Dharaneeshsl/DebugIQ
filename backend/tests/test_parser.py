from parser import parse_logs


def test_parse_logs_basic():
    text = "00:00:01.000 ERROR AXI line 42 Something bad happened"
    results = parse_logs(text)
    assert results
    assert results[0]["severity"] in {"ERROR", "FATAL", "WARNING", "INFO", "CRITICAL"}


def test_parse_logs_sva():
    text = "ASSERTION FAILED: axi_valid_stable at axi_intf.sv:142"
    results = parse_logs(text)
    assert results
    assert results[0]["failure_type"] == "SVA"
    assert results[0]["severity"] == "ERROR"


def test_parse_logs_module_not_severity_token():
    text = "[12:00:00.234] ERROR MEMORY_CTRL line 78 UVM_ERROR: sample issue"
    results = parse_logs(text)
    assert results
    assert results[0]["module"] == "MEMORY_CTRL"
    assert results[0]["module"] != "ERROR"
