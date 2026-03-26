import re
from typing import List, Dict

from nlp.log_extractor import extract_failures

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
        r".*(FATAL|ERROR|WARNING|INFO|CRITICAL).*",
        re.IGNORECASE,
    ),
    re.compile(
        r"\[TIME:(\d+ns)\]\s+\[(FATAL|ERROR|WARNING|INFO)\]\s+\[(\w+)\]\s+(.*)",
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


def parse_logs_advanced(text: str) -> List[Dict]:
    failures = extract_failures(text.splitlines())
    return [
        {
            "timestamp": f.timestamp,
            "severity": f.severity,
            "module": f.module,
            "line_no": f.line_no,
            "message": f.message,
            "context": f.context,
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
                "severity": m.group(2).upper().replace("WARN", "WARNING"),
                "module": m.group(3).upper(),
                "line_no": int(m.group(4)),
                "message": m.group(5).strip(),
            }
        if not parsed:
            m = PATTERNS[1].match(line)
            if m:
                parsed = {
                    "timestamp": "00:00:00.000",
                    "severity": m.group(1).upper().replace("WARN", "WARNING"),
                    "module": m.group(2).upper(),
                    "line_no": int(m.group(3)),
                    "message": m.group(4).strip(),
                }
        if not parsed:
            m = PATTERNS[2].match(line)
            if m:
                parsed = {
                    "timestamp": m.group(1),
                    "severity": m.group(2).upper().replace("WARN", "WARNING"),
                    "module": extract_module(m.group(3)),
                    "line_no": i + 1,
                    "message": m.group(3).strip(),
                }
        if not parsed:
            m = PATTERNS[3].match(line)
            if m:
                sev = m.group(2).upper()
                sev = (
                    sev.replace("UVM_FATAL", "FATAL")
                    .replace("UVM_ERROR", "ERROR")
                    .replace("UVM_WARNING", "WARNING")
                    .replace("UVM_INFO", "INFO")
                )
                parsed = {
                    "timestamp": m.group(1),
                    "severity": sev,
                    "module": extract_module(m.group(3)),
                    "line_no": i + 1,
                    "message": m.group(3).strip(),
                }
        if not parsed:
            m = PATTERNS[5].match(line)
            if m:
                parsed = {
                    "timestamp": m.group(1),
                    "severity": m.group(2).upper().replace("WARN", "WARNING"),
                    "module": m.group(3).upper(),
                    "line_no": i + 1,
                    "message": m.group(4).strip(),
                }
        if not parsed:
            m = PATTERNS[4].match(line)
            if m:
                sev = m.group(1).upper().replace("WARN", "WARNING")
                if sev in ["FATAL", "ERROR", "WARNING", "INFO", "CRITICAL"]:
                    parsed = {
                        "timestamp": "00:00:00.000",
                        "severity": sev,
                        "module": extract_module(line),
                        "line_no": i + 1,
                        "message": line.strip(),
                    }
        if parsed:
            legacy.append(parsed)
    return legacy
