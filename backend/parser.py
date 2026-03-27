import re
from typing import List, Dict, Optional

from nlp.log_extractor import extract_failures

_UVM_SEV_MAP = {
    "UVM_FATAL": "FATAL",
    "UVM_ERROR": "ERROR",
    "UVM_WARNING": "WARNING",
    "UVM_INFO": "INFO",
}

UVM_PHASES = [
    "build_phase",
    "connect_phase",
    "run_phase",
    "extract_phase",
    "check_phase",
    "report_phase",
]

PATTERNS = [
    re.compile(
        r"\[?(\d{2}:\d{2}:\d{2}[\.,]\d+)\]?\s+"
        r"(FATAL|ERROR|WARNING|WARN|INFO|CRITICAL)\s+"
        r"(\w+)\s+line\s+(\d+)\s+(.*)",
        re.IGNORECASE,
    ),
    re.compile(
        r"(FATAL|ERROR|WARNING|WARN|INFO|CRITICAL)\s+"
        r"(\w+)\s+line\s+(\d+)\s+(.*)",
        re.IGNORECASE,
    ),
    re.compile(
        r"\[?(\d{2}:\d{2}:\d{2}[\.,]\d+)\]?\s+"
        r"(FATAL|ERROR|WARNING|WARN|INFO|CRITICAL)[:\s]+(.*)",
        re.IGNORECASE,
    ),
    re.compile(
        r"\[?(\d{2}:\d{2}:\d{2}[\.,]\d+)\]?\s+"
        r"(UVM_FATAL|UVM_ERROR|UVM_WARNING|UVM_INFO)\s+(.*)",
        re.IGNORECASE,
    ),
    re.compile(
        r".*\b(ASSERTION FAILED|SVA ERROR|SVA FAILURE|SVA ASSERTION)\b[:\s]+(.*)",
        re.IGNORECASE,
    ),
    re.compile(
        r"\[TIME:(\d+ns)\]\s+\[(FATAL|ERROR|WARNING|INFO)\]\s+\[(\w+)\]\s+(.*)",
        re.IGNORECASE,
    ),
    re.compile(
        r".*(FATAL|ERROR|WARNING|INFO|CRITICAL).*",
        re.IGNORECASE,
    ),
]


def extract_module(text: str) -> str:
    known = [
        "AXI_INTERFACE",
        "AXI",
        "MEMORY_CTRL",
        "CACHE_CTRL",
        "ALU",
        "DMA",
        "UART",
        "SPI",
        "I2C",
        "CPU",
        "GPU",
        "MMU",
    ]
    text_up = text.upper()
    for mod in known:
        if mod in text_up:
            return mod
    match = re.search(r"\b([A-Z_]{3,})\b", text)
    if match:
        return match.group(1)
    return "UNKNOWN"

def _normalize_severity(raw: str) -> str:
    upper = raw.upper()
    return _UVM_SEV_MAP.get(upper, upper).replace("WARN", "WARNING")


def _detect_failure_type(raw: str, is_sva: bool) -> str:
    if is_sva:
        return "SVA"
    if raw.upper().startswith("UVM_"):
        return "UVM"
    return "LOG"


def _extract_uvm_phase(text: str) -> Optional[str]:
    lower = text.lower()
    for phase in UVM_PHASES:
        if phase in lower:
            return phase
    return None


def _extract_sim_time(text: str) -> Optional[str]:
    m = re.search(r"\[TIME:(\d+(?:\.\d+)?(?:ns|ps|us|ms))\]", text, re.IGNORECASE)
    return m.group(1) if m else None


def _extract_test_name(text: str) -> Optional[str]:
    m = re.search(r"\btest(?:name)?\s*[:=]\s*([A-Za-z0-9_./-]+)", text, re.IGNORECASE)
    return m.group(1) if m else None


def _extract_seed(text: str) -> Optional[str]:
    m = re.search(r"\bseed\s*[:=]\s*(\d+)", text, re.IGNORECASE)
    return m.group(1) if m else None


def _extract_dut_path(text: str) -> Optional[str]:
    m = re.search(r"\bDUT\s*[:=]\s*([A-Za-z0-9_.]+)", text, re.IGNORECASE)
    return m.group(1) if m else None


def _extract_source_file_line(text: str) -> tuple[Optional[str], Optional[int]]:
    m = re.search(r"\b([A-Za-z0-9_./-]+\.(?:sv|svh|v|vh)):(\d+)\b", text, re.IGNORECASE)
    if not m:
        return None, None
    try:
        return m.group(1), int(m.group(2))
    except ValueError:
        return m.group(1), None

def parse_logs_advanced(text: str) -> List[Dict]:
    failures = extract_failures(text.splitlines())
    return [
        {
            "timestamp": f.timestamp,
            "severity": f.severity,
            "severity_raw": f.severity_raw,
            "module": f.module,
            "line_no": f.line_no,
            "message": f.message,
            "context": f.context,
            "failure_type": f.failure_type,
            "sim_time": f.sim_time,
            "test_name": f.test_name,
            "seed": f.seed,
            "dut_path": f.dut_path,
            "uvm_phase": f.uvm_phase,
            "source_file": f.source_file,
            "source_line": f.source_line,
        }
        for f in failures
    ]


def parse_logs(text: str) -> List[Dict]:
    """
    Backward-compatible parser.
    Uses advanced extractor with multi-line context.
    """
    results = parse_logs_advanced(text)
    if results:
        return results
    # Fallback to legacy regex if advanced extractor yields nothing
    legacy: List[Dict] = []
    lines = text.splitlines()
    for i, line in enumerate(lines):
        line = line.strip()
        if not line:
            continue
        parsed = None
        m = PATTERNS[0].match(line)
        if m:
            parsed = {
                "timestamp": m.group(1),
                "severity": _normalize_severity(m.group(2)),
                "severity_raw": m.group(2).upper(),
                "module": m.group(3).upper(),
                "line_no": int(m.group(4)),
                "message": m.group(5).strip(),
                "failure_type": _detect_failure_type(m.group(2), False),
            }
        if not parsed:
            m = PATTERNS[1].match(line)
            if m:
                parsed = {
                    "timestamp": "00:00:00.000",
                    "severity": _normalize_severity(m.group(1)),
                    "severity_raw": m.group(1).upper(),
                    "module": m.group(2).upper(),
                    "line_no": int(m.group(3)),
                    "message": m.group(4).strip(),
                    "failure_type": _detect_failure_type(m.group(1), False),
                }
        if not parsed:
            m = PATTERNS[2].match(line)
            if m:
                parsed = {
                    "timestamp": m.group(1),
                    "severity": _normalize_severity(m.group(2)),
                    "severity_raw": m.group(2).upper(),
                    "module": extract_module(m.group(3)),
                    "line_no": i + 1,
                    "message": m.group(3).strip(),
                    "failure_type": _detect_failure_type(m.group(2), False),
                }
        if not parsed:
            m = PATTERNS[3].match(line)
            if m:
                sev_raw = m.group(2).upper()
                sev = _normalize_severity(sev_raw)
                parsed = {
                    "timestamp": m.group(1),
                    "severity": sev,
                    "severity_raw": sev_raw,
                    "module": extract_module(m.group(3)),
                    "line_no": i + 1,
                    "message": m.group(3).strip(),
                    "failure_type": _detect_failure_type(sev_raw, False),
                }
        if not parsed:
            m = PATTERNS[4].match(line)
            if m:
                parsed = {
                    "timestamp": "00:00:00.000",
                    "severity": "ERROR",
                    "severity_raw": "SVA_ERROR" if "SVA" in line.upper() else "ASSERTION_FAILED",
                    "module": extract_module(m.group(2)),
                    "line_no": i + 1,
                    "message": line.strip(),
                    "failure_type": _detect_failure_type("SVA_ERROR", True),
                }
        if not parsed:
            m = PATTERNS[5].match(line)
            if m:
                parsed = {
                    "timestamp": m.group(1),
                    "severity": _normalize_severity(m.group(2)),
                    "severity_raw": m.group(2).upper(),
                    "module": m.group(3).upper(),
                    "line_no": i + 1,
                    "message": m.group(4).strip(),
                    "failure_type": _detect_failure_type(m.group(2), False),
                }
        if not parsed:
            m = PATTERNS[6].match(line)
            if m:
                sev = _normalize_severity(m.group(1))
                if sev in ["FATAL", "ERROR", "WARNING", "INFO", "CRITICAL"]:
                    parsed = {
                        "timestamp": "00:00:00.000",
                        "severity": sev,
                        "severity_raw": m.group(1).upper(),
                        "module": extract_module(line),
                        "line_no": i + 1,
                        "message": line.strip(),
                        "failure_type": _detect_failure_type(m.group(1), False),
                    }
        if parsed:
            parsed["sim_time"] = _extract_sim_time(line)
            parsed["test_name"] = _extract_test_name(line)
            parsed["seed"] = _extract_seed(line)
            parsed["dut_path"] = _extract_dut_path(line)
            parsed["uvm_phase"] = _extract_uvm_phase(line)
            source_file, source_line = _extract_source_file_line(line)
            parsed["source_file"] = source_file
            parsed["source_line"] = source_line
            legacy.append(parsed)
    return legacy
