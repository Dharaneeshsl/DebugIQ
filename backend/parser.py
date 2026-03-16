import re
from typing import List, Dict

LOG_PATTERN_STD = re.compile(
    r"\[(?P<timestamp>\d{2}:\d{2}:\d{2}\.\d{3})\]\s+"
    r"(?P<severity>FATAL|ERROR|WARNING|INFO)\s+"
    r"(?P<module>[A-Z0-9_]+)\s+line\s+"
    r"(?P<line_no>\d+)\s+"
    r"(?P<message>.+)$"
)

LOG_PATTERN_SIM = re.compile(
    r"\[TIME:(?P<timestamp>\d+ns)\]\s+\[(?P<severity>FATAL|ERROR|WARNING|INFO)\]\s+"
    r"\[(?P<module>[A-Z0-9_]+)\]\s+(?P<message>.+)$"
)


def _parse_line(line: str) -> Dict | None:
    match = LOG_PATTERN_STD.search(line)
    if match:
        return {
            "timestamp": match.group("timestamp"),
            "severity": match.group("severity"),
            "module": match.group("module"),
            "line_no": int(match.group("line_no")),
            "message": match.group("message").strip(),
        }

    match = LOG_PATTERN_SIM.search(line)
    if match:
        return {
            "timestamp": match.group("timestamp"),
            "severity": match.group("severity"),
            "module": match.group("module"),
            "line_no": 0,
            "message": match.group("message").strip(),
        }

    return None


def parse_logs(text: str) -> List[Dict]:
    records: List[Dict] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        parsed = _parse_line(line)
        if parsed:
            records.append(parsed)
    return records
