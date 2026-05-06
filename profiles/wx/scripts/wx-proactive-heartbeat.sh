#!/usr/bin/env python3
import os
import runpy
import sys
from pathlib import Path

home = Path(os.environ.get("HERMES_HOME", str(Path.home() / ".hermes" / "profiles" / "wx"))).expanduser()
os.environ["HERMES_HOME"] = str(home)

env_path = Path(os.environ.get("WX_LINJIANG_LLM_ENV_PATH", str(home / "linjiang-llm.env"))).expanduser()
if env_path.exists():
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        value = value.strip().strip('"').strip("'")
        os.environ[key.strip()] = value

target = home / "wx-proactive-heartbeat.py"
sys.argv = [str(target)] + sys.argv[1:]
runpy.run_path(str(target), run_name="__main__")
