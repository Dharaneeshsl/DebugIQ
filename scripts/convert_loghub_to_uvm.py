from __future__ import annotations

from pathlib import Path
from datetime import datetime, timedelta
import re


ROOT = Path(__file__).resolve().parents[1]
LOGHUB_DIR = ROOT / "loghub"
OUTPUT_DIR = ROOT / "logs"

MODULES = [
    "AXI_INTERFACE",
    "MEMORY_CTRL",
    "CACHE_CTRL",
    "ALU",
    "DMA",
    "CPU",
    "MMU",
]

SEVERITY_RULES = [
    ("FATAL", ["panic", "fatal", "crash", "segfault", "kernel bug"]),
    ("ERROR", ["error", "failed", "exception", "refused", "denied", "invalid", "abort"]),
    ("WARNING", ["warn", "timeout", "retry", "slow", "unstable"]),
]

SVA_HINTS = ["assert", "violation", "mismatch", "overflow", "underflow", "handshake", "protocol"]


def infer_severity(line: str) -> str:
    lower = line.lower()
    for sev, keys in SEVERITY_RULES:
        if any(k in lower for k in keys):
            return sev
    return "INFO"


def infer_module(dataset: str, line: str, line_no: int) -> str:
    dataset_upper = dataset.upper()
    if "HDFS" in dataset_upper:
        return "MEMORY_CTRL"
    if "SPARK" in dataset_upper or "HADOOP" in dataset_upper:
        return "DMA"
    if "OPENSSH" in dataset_upper or "APACHE" in dataset_upper:
        return "AXI_INTERFACE"
    if "ANDROID" in dataset_upper or "LINUX" in dataset_upper:
        return "CPU"
    if "WINDOWS" in dataset_upper or "MAC" in dataset_upper:
        return "MMU"
    return MODULES[line_no % len(MODULES)]


def to_uvm_sva_line(dataset: str, raw: str, line_no: int, ts: datetime) -> str:
    sev = infer_severity(raw)
    module = infer_module(dataset, raw, line_no)
    clean = re.sub(r"\s+", " ", raw.strip())
    lower = clean.lower()

    if any(k in lower for k in SVA_HINTS):
        msg = f"SVA_ASSERTION {sev}: {clean}"
    elif sev in {"ERROR", "FATAL"}:
        msg = f"UVM_{sev}: {clean}"
    else:
        msg = clean

    t = ts.strftime("%H:%M:%S.%f")[:-3]
    return f"[{t}] {sev:<7} {module:<13} line {line_no:<5} {msg}"


def convert_file(src: Path, dst: Path) -> int:
    dataset = src.parent.name
    lines = src.read_text(encoding="utf-8", errors="ignore").splitlines()
    out = []
    base = datetime(2026, 3, 27, 12, 0, 0, 0)
    for i, raw in enumerate(lines, start=1):
        if not raw.strip():
            continue
        ts = base + timedelta(milliseconds=i * 3)
        out.append(to_uvm_sva_line(dataset, raw, i, ts))
    dst.write_text("\n".join(out), encoding="utf-8")
    return len(out)


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    sources = sorted(LOGHUB_DIR.glob("*/*_2k.log"))
    if not sources:
        raise RuntimeError("No LogHub source files found. Clone loghub first.")

    total = 0
    for src in sources:
        name = f"{src.parent.name}_uvm_sva.log"
        dst = OUTPUT_DIR / name
        count = convert_file(src, dst)
        total += count
        print(f"converted: {src} -> {dst} ({count} lines)")

    print(f"done: {len(sources)} files, {total} lines")


if __name__ == "__main__":
    main()

