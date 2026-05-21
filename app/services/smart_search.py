from __future__ import annotations

import json
import os
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


EVIDENCE_ROOT = Path(r"C:\tmp\smart-search-evidence\real-decision-agent")


class SmartSearchError(RuntimeError):
    pass


def _candidate_commands() -> list[Path]:
    candidates: list[Path] = []
    configured = os.environ.get("SMART_SEARCH_COMMAND", "").strip()
    if configured:
        candidates.append(Path(configured))

    for name in ("smart-search.cmd", "smart-search.exe", "smart-search"):
        resolved = shutil.which(name)
        if resolved:
            candidates.append(Path(resolved))

    appdata = os.environ.get("APPDATA", "").strip()
    if appdata:
        candidates.extend(
            [
                Path(appdata) / "npm" / "smart-search.cmd",
                Path(appdata) / "npm" / "smart-search.ps1",
            ]
        )

    candidates.extend(
        [
            Path(r"D:\nodejs\node_global\smart-search.cmd"),
            Path(r"D:\nodejs\node_global\smart-search.ps1"),
        ]
    )
    return candidates


def _smart_search_command(args: list[str]) -> list[str]:
    for candidate in _candidate_commands():
        if not candidate.is_file():
            continue
        if candidate.suffix.lower() == ".ps1":
            return [
                "powershell",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(candidate),
                *args,
            ]
        return [str(candidate), *args]
    raise SmartSearchError(
        "找不到 smart-search CLI。请确认它在 PATH 中，或在 .env 设置 SMART_SEARCH_COMMAND 为 smart-search.cmd 的完整路径。"
    )


def _run_command(command: list[str], timeout: int) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
        )
    except OSError as exc:
        raise SmartSearchError(f"smart-search CLI 启动失败：{exc}") from exc


def run_search(query: str, extra_sources: int = 2, timeout: int = 120) -> dict[str, Any]:
    EVIDENCE_ROOT.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    output = EVIDENCE_ROOT / f"{stamp}-search.json"
    command = _smart_search_command(
        [
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
    )
    completed = _run_command(command, timeout)
    if completed.returncode != 0:
        stderr = (completed.stderr or "").strip()
        stdout = (completed.stdout or "").strip()
        raise SmartSearchError(stderr or stdout or "smart-search failed")

    raw = (completed.stdout or "").strip()
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
    command = _smart_search_command(
        [
            "fetch",
            url,
            "--format",
            "json",
            "--output",
            str(output),
        ]
    )
    completed = _run_command(command, timeout)
    if completed.returncode != 0:
        stderr = (completed.stderr or "").strip()
        stdout = (completed.stdout or "").strip()
        raise SmartSearchError(stderr or stdout or "smart-search fetch failed")

    raw = (completed.stdout or "").strip()
    if not raw and output.exists():
        raw = output.read_text(encoding="utf-8")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SmartSearchError(f"smart-search fetch returned non-JSON output: {exc}") from exc

    data["_command"] = " ".join(command)
    data["_output_path"] = str(output)
    return data
