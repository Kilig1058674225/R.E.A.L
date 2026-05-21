from __future__ import annotations

import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


EVIDENCE_ROOT = Path(r"C:\tmp\smart-search-evidence\real-decision-agent")


class SmartSearchError(RuntimeError):
    pass


def run_search(query: str, extra_sources: int = 2, timeout: int = 120) -> dict[str, Any]:
    EVIDENCE_ROOT.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    output = EVIDENCE_ROOT / f"{stamp}-search.json"
    command = [
        "smart-search",
        "search",
        query,
        "--validation",
        "balanced",
        "--extra-sources",
        str(extra_sources),
        "--format",
        "json",
        "--output",
        str(output),
    ]
    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    if completed.returncode != 0:
        raise SmartSearchError(completed.stderr.strip() or completed.stdout.strip() or "smart-search failed")

    raw = completed.stdout.strip()
    if not raw and output.exists():
        raw = output.read_text(encoding="utf-8")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SmartSearchError(f"smart-search returned non-JSON output: {exc}") from exc

    data["_command"] = " ".join(command)
    data["_output_path"] = str(output)
    return data


def run_fetch(url: str, timeout: int = 120) -> dict[str, Any]:
    EVIDENCE_ROOT.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    output = EVIDENCE_ROOT / f"{stamp}-fetch.json"
    command = [
        "smart-search",
        "fetch",
        url,
        "--format",
        "json",
        "--output",
        str(output),
    ]
    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    if completed.returncode != 0:
        raise SmartSearchError(completed.stderr.strip() or completed.stdout.strip() or "smart-search fetch failed")

    raw = completed.stdout.strip()
    if not raw and output.exists():
        raw = output.read_text(encoding="utf-8")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SmartSearchError(f"smart-search fetch returned non-JSON output: {exc}") from exc

    data["_command"] = " ".join(command)
    data["_output_path"] = str(output)
    return data
