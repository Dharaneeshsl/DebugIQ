import re
from dataclasses import dataclass
from typing import List, Optional

@dataclass
class ExtractedFailure:
    timestamp: str
    severity: str
    severity_raw: str
    module: str
    line_no: int
    message: str
    context: str
    failure_type: str
    sim_time: Optional[str] = None
    test_name: Optional[str] = None
    seed: Optional[str] = None
    dut_path: Optional[str] = None
    uvm_phase: Optional[str] = None
    source_file: Optional[str] = None
    source_line: Optional[int] = None


_UVM_SEV_MAP = {
    "UVM_FATAL": "FATAL",
    "UVM_ERROR": "ERROR",
    "UVM_WARNING": "WARNING",
    "UVM_INFO": "INFO",
}


def _normalize_severity(raw: str) -> str:
    upper = raw.upper()
    return _UVM_SEV_MAP.get(upper, upper)


def _detect_failure_type(raw: str, is_sva: bool) -> str:
    if is_sva:
        return "SVA"
    if raw.upper().startswith("UVM_"):
        return "UVM"
    return "LOG"

def extract_failures(lines: List[str]) -> List[ExtractedFailure]:
    """
    Context-aware failure extraction.
    Identifies error traces and grabs surrounding standard lines to form a complete context block.
    """
    failures = []
    
    sev_pattern = re.compile(
        r"\b(FATAL|ERROR|WARNING|CRITICAL|UVM_FATAL|UVM_ERROR|UVM_WARNING|UVM_INFO)\b",
        re.IGNORECASE,
    )
    sva_pattern = re.compile(r"\b(ASSERTION FAILED|SVA ERROR|SVA FAILURE|SVA ASSERTION)\b", re.IGNORECASE)
    mod_pattern = re.compile(r"\b([A-Z_]{3,})\b")
    time_pattern = re.compile(r"(\d{2}:\d{2}:\d{2}[\.,]\d+)")
    sim_time_pattern = re.compile(r"\[TIME:(\d+(?:\.\d+)?(?:ns|ps|us|ms))\]", re.IGNORECASE)
    phase_pattern = re.compile(r"\b(build_phase|connect_phase|run_phase|extract_phase|check_phase|report_phase)\b", re.IGNORECASE)
    test_pattern = re.compile(r"\btest(?:name)?\s*[:=]\s*([A-Za-z0-9_./-]+)", re.IGNORECASE)
    seed_pattern = re.compile(r"\bseed\s*[:=]\s*(\d+)", re.IGNORECASE)
    dut_pattern = re.compile(r"\bDUT\s*[:=]\s*([A-Za-z0-9_.]+)", re.IGNORECASE)
    file_line_pattern = re.compile(r"\b([A-Za-z0-9_./-]+\.(?:sv|svh|v|vh)):(\d+)\b", re.IGNORECASE)
    
    for i, line in enumerate(lines):
        sev_match = sev_pattern.search(line)
        sva_match = sva_pattern.search(line)
        if sev_match or sva_match:
            if sev_match:
                severity_raw = sev_match.group(1).upper()
                severity = _normalize_severity(severity_raw)
            else:
                severity_raw = "SVA_ERROR" if "SVA" in line.upper() else "ASSERTION_FAILED"
                severity = "ERROR"
            
            mod_match = mod_pattern.search(line)
            module = mod_match.group(1) if mod_match else "UNKNOWN_MOD"
            
            t_match = time_pattern.search(line)
            timestamp = t_match.group(1) if t_match else "00:00:00.000"

            sim_match = sim_time_pattern.search(line)
            sim_time = sim_match.group(1) if sim_match else None

            phase_match = phase_pattern.search(line)
            uvm_phase = phase_match.group(1).lower() if phase_match else None

            test_match = test_pattern.search(line)
            test_name = test_match.group(1) if test_match else None

            seed_match = seed_pattern.search(line)
            seed = seed_match.group(1) if seed_match else None

            dut_match = dut_pattern.search(line)
            dut_path = dut_match.group(1) if dut_match else None

            source_file = None
            source_line = None
            file_line_match = file_line_pattern.search(line)
            if file_line_match:
                source_file = file_line_match.group(1)
                try:
                    source_line = int(file_line_match.group(2))
                except ValueError:
                    source_line = None
                if module == "UNKNOWN_MOD" and source_file:
                    module = source_file.split("/")[-1].split(".")[0].upper()
            
            # Grab context window (2 lines before, 2 lines after)
            start = max(0, i - 2)
            end = min(len(lines), i + 3)
            context = "\n".join(lines[start:end])
            
            failures.append(ExtractedFailure(
                timestamp=timestamp,
                severity=severity,
                severity_raw=severity_raw,
                module=module,
                line_no=i + 1,
                message=line.strip(),
                context=context,
                failure_type=_detect_failure_type(severity_raw, bool(sva_match)),
                sim_time=sim_time,
                test_name=test_name,
                seed=seed,
                dut_path=dut_path,
                uvm_phase=uvm_phase,
                source_file=source_file,
                source_line=source_line,
            ))
            
    return failures
