#!/usr/bin/env python3
"""Hermes cron-safe wrapper for Presence Kernel."""
from __future__ import annotations

import os
import runpy
import sys
from pathlib import Path

import yaml

home = Path(os.environ.get("HERMES_HOME", str(Path.home() / ".hermes" / "profiles" / "wx"))).expanduser()
os.environ["HERMES_HOME"] = str(home)

kernel_dir = home / "presence" / "kernel"
profile_id = os.environ.get("PRESENCE_PROFILE_ID")
if not profile_id:
    config_path = home / "presence" / "config.yaml"
    if config_path.exists():
        data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
        profile_id = str(data.get("default_profile_id") or "").strip()
if not profile_id:
    raise SystemExit("presence wrapper requires PRESENCE_PROFILE_ID or presence/config.yaml:default_profile_id")

sys.path.insert(0, str(kernel_dir))
target = kernel_dir / "presence_tick.py"
sys.argv = [str(target), "--profile", profile_id] + sys.argv[1:]
runpy.run_path(str(target), run_name="__main__")
