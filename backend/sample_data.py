import random
from pathlib import Path
from datetime import datetime, timedelta

SEVERITIES = ["FATAL", "ERROR", "WARNING", "INFO"]
MODULES = ["AXI_INTERFACE", "CACHE_CTRL", "MEMORY_CTRL", "ALU"]
MESSAGES = {
    "AXI_INTERFACE": [
        "UVM_ERROR: Assertion failed: axi_ready timeout",
        "Protocol violation: unexpected burst termination",
    ],
    "CACHE_CTRL": [
        "Protocol violation: unexpected cache miss",
        "Assertion failed: cache_hit_on_invalid_line",
    ],
    "MEMORY_CTRL": [
        "Data mismatch: expected 0xAB got 0xCD",
        "ECC error: parity mismatch",
    ],
    "ALU": [
        "Timeout: operation exceeded 100ns limit",
        "Assertion failed: divide by zero",
    ],
}


def generate_sample_log(path: Path, lines: int = 500) -> None:
    start = datetime(2026, 3, 16, 10, 23, 41, 123000)
    entries = []
    for idx in range(lines):
        ts = start + timedelta(milliseconds=10 * idx)
        severity = random.choices(SEVERITIES, weights=[10, 20, 30, 40])[0]
        module = random.choice(MODULES)
        line_no = random.randint(50, 500)
        message = random.choice(MESSAGES[module])

        if random.random() < 0.2:
            message = message.replace("0xAB", "0xAB").replace("0xCD", "0xCD")

        entries.append(
            f"[{ts.strftime('%H:%M:%S.%f')[:-3]}] {severity:<7} {module:<13} line {line_no}  {message}"
        )

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(entries), encoding="utf-8")


if __name__ == "__main__":
    generate_sample_log(Path("sample_logs") / "test.log")