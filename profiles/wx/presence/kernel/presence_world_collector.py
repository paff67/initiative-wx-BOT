#!/usr/bin/env python3
"""Non-LLM world signal collector for Presence Kernel."""
from __future__ import annotations

import subprocess
from datetime import datetime
from typing import Any

from presence_common import append_jsonl, event, event_path, local_now, make_run_id
from presence_mcp_adapter import collect_mcp_sources


def collect_world_signals(profile: dict[str, Any], tick_run_id: str | None = None, phase: str = "prefilter") -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    run_id = make_run_id("world")
    now = local_now(profile)
    signals: list[dict[str, Any]] = []
    tool_calls: list[dict[str, Any]] = []

    if phase == "prefilter":
        signals.append(_time_signal(profile, now, run_id, tick_run_id))

    world_policy = profile.get("world_policy", {}) or {}
    for source in world_policy.get("command_sources", []) or []:
        source_phase = str(source.get("phase") or "prefilter")
        if source_phase != phase:
            continue
        if not source.get("enabled", False):
            continue
        result = _run_command_source(source)
        tool_calls.append(result)
        if result.get("ok"):
            signals.append({
                "id": f"ws_{run_id}_{source.get('name', 'command')}",
                "profile_id": profile["profile_id"],
                "run_id": run_id,
                "kind": source.get("kind", "custom_command"),
                "source": {"type": "script", "name": source.get("name", "command"), "command": source.get("command", [])},
                "raw_summary": result.get("stdout", "")[:1000],
                "normalized_fact": result.get("stdout", "").strip()[:240],
                "fetched_at": now.isoformat(),
                "expires_at": None,
                "confidence": float(source.get("confidence", 0.7)),
                "sensitivity": source.get("sensitivity", "public"),
                "policy_decision": "auto_allow",
                "allowed_use": source.get("allowed_use", "mood_only"),
                "operator_review": "unreviewed",
                "trace": {"collector_run_id": run_id, "tick_run_id": tick_run_id, "tool_calls": [source.get("name", "command")]},
            })

    mcp_signals, mcp_tool_calls = collect_mcp_sources(profile, tick_run_id=tick_run_id, collector_run_id=run_id, phase=phase)
    signals.extend(mcp_signals)
    tool_calls.extend(mcp_tool_calls)

    record = event({
        "run_id": run_id,
        "tick_run_id": tick_run_id,
        "phase": phase,
        "signals": signals,
        "tool_calls": tool_calls,
    }, profile, run_id)
    append_jsonl(event_path("world-signal-events.jsonl"), record)
    return signals, tool_calls


def _time_signal(profile: dict[str, Any], now: datetime, run_id: str, tick_run_id: str | None) -> dict[str, Any]:
    return {
        "id": f"ws_{run_id}_time",
        "profile_id": profile["profile_id"],
        "run_id": run_id,
        "kind": "time",
        "source": {"type": "script", "name": "local_clock"},
        "raw_summary": now.isoformat(),
        "normalized_fact": f"当前本地时间 {now.strftime('%Y-%m-%d %H:%M')}，星期{_weekday_cn(now.weekday())}",
        "fetched_at": now.isoformat(),
        "expires_at": (now.replace(second=0, microsecond=0)).isoformat(),
        "confidence": 1.0,
        "sensitivity": "public",
        "policy_decision": "auto_allow",
        "allowed_use": "mood_only",
        "operator_review": "unreviewed",
        "trace": {"collector_run_id": run_id, "tick_run_id": tick_run_id, "tool_calls": ["local_clock"]},
    }


def _weekday_cn(idx: int) -> str:
    return "一二三四五六日"[idx]


def _run_command_source(source: dict[str, Any]) -> dict[str, Any]:
    command = source.get("command") or []
    if isinstance(command, str):
        command = [command]
    if not command:
        return {"name": source.get("name"), "ok": False, "error": "empty command"}
    try:
        proc = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=float(source.get("timeout_seconds", 10)),
            check=False,
        )
        return {
            "name": source.get("name"),
            "command": command,
            "ok": proc.returncode == 0,
            "exit_code": proc.returncode,
            "stdout": (proc.stdout or "").strip()[:2000],
            "stderr": (proc.stderr or "").strip()[:1000],
        }
    except Exception as exc:
        return {"name": source.get("name"), "command": command, "ok": False, "error": str(exc)[:500]}
