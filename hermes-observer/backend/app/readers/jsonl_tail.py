"""Efficient reverse-read of JSONL files."""
from __future__ import annotations
import json
from pathlib import Path
from typing import Any


def tail_jsonl(path: Path, limit: int = 100) -> list[dict[str, Any]]:
    """Read the last *limit* parseable JSONL rows, newest first.

    Decision events can be very large single-line JSON objects. For small
    limits, the first chunk from the file tail may land in the middle of that
    line, so keep expanding backward until the newest rows are complete.
    """
    try:
        target = int(limit)
    except Exception:
        target = 100
    if target <= 0:
        return []
    if not path.exists():
        return []
    file_size = path.stat().st_size
    if file_size == 0:
        return []

    chunk_size = min(file_size, max(65536, target * 4096))
    data = b""
    results: list[dict[str, Any]] = []

    with path.open("rb") as fh:
        remaining = file_size
        while remaining > 0:
            read_size = min(chunk_size, remaining)
            remaining -= read_size
            fh.seek(remaining)
            data = fh.read(read_size) + data

            lines = data.splitlines()
            # If there is unread data before this buffer, the first split line
            # may be a partial JSON object. Everything after it starts at a real
            # newline boundary and is safe to parse.
            complete_lines = lines if remaining == 0 else lines[1:]

            results = []
            for raw_line in reversed(complete_lines):
                raw_line = raw_line.strip()
                if not raw_line:
                    continue
                try:
                    results.append(json.loads(raw_line.decode("utf-8", "replace")))
                except json.JSONDecodeError:
                    continue
                if len(results) >= target:
                    return results

    return results[:target]


def read_json_file(path: Path) -> dict[str, Any] | list | None:
    """Read a plain JSON file, return None if missing or broken."""
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        pass
    return None
