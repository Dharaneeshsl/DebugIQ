import re
from dataclasses import dataclass
from typing import List

@dataclass
class ExtractedFailure:
    timestamp: str
    severity: str
    module: str
    line_no: int
    message: str
    context: str

def extract_failures(lines: List[str]) -> List[ExtractedFailure]:
    """
    Context-aware failure extraction.
    Identifies error traces and grabs surrounding standard lines to form a complete context block.
    """
    failures = []
    
    sev_pattern = re.compile(r"\b(FATAL|ERROR|WARNING|CRITICAL|UVM_FATAL|UVM_ERROR)\b", re.IGNORECASE)
    mod_pattern = re.compile(r"\b([A-Z_]{3,})\b")
    time_pattern = re.compile(r"(\d{2}:\d{2}:\d{2}[\.,]\d+)")
    
    for i, line in enumerate(lines):
        if sev_pattern.search(line):
            sev_match = sev_pattern.search(line)
            severity = sev_match.group(1).upper().replace("UVM_", "")
            
            mod_match = mod_pattern.search(line)
            module = mod_match.group(1) if mod_match else "UNKNOWN_MOD"
            
            t_match = time_pattern.search(line)
            timestamp = t_match.group(1) if t_match else "00:00:00.000"
            
            # Grab context window (2 lines before, 2 lines after)
            start = max(0, i - 2)
            end = min(len(lines), i + 3)
            context = "\n".join(lines[start:end])
            
            failures.append(ExtractedFailure(
                timestamp=timestamp,
                severity=severity,
                module=module,
                line_no=i + 1,
                message=line.strip(),
                context=context
            ))
            
    return failures
