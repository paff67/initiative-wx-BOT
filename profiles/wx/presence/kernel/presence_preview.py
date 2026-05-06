#!/usr/bin/env python3
"""Dry-run preview entrypoint."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", default=os.environ.get("PRESENCE_PROFILE_ID"))
    parser.add_argument("--force-llm", action="store_true", default=True)
    args = parser.parse_args()
    if not args.profile:
        raise SystemExit("presence_preview requires --profile or PRESENCE_PROFILE_ID")
    target = Path(__file__).resolve().parent / "presence_tick.py"
    cmd = [sys.executable, str(target), "--profile", args.profile, "--dry-run", "--force-llm"]
    proc = subprocess.run(cmd, capture_output=True, text=True, cwd=str(target.parent), timeout=240)
    print(json.dumps({
        "ok": proc.returncode == 0,
        "exit_code": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
