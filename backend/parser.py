import re
from typing import List, Dict

LOG_PATTERN = re.compile(
    r"\[(?P<timestamp>\d{2}:\d{2}:\d{2}\.\d{3})\]\s+"
    r"(?P<severity>FATAL|ERROR|WARNING|INFO)\s+"
    r"(?P<module>[A-Z0-9_]+)\s+line\s+"
    r"(?P<line_no>\d+)\s+"
    r"(?P<message>.+)$"
)


def parse_logs(text: str) -> List[Dict]:
    records: List[Dict] = []
    for line in text.splitlines():
        match = LOG_PATTERN.search(line.strip())
        if not match:
            continue
        records.append(
            {
                "timestamp": match.group("timestamp"),
                "severity": match.group("severity"),
                "module": match.group("module"),
                "line_no": int(match.group("line_no")),
                "message": match.group("message").strip(),
            }
        )
    return records