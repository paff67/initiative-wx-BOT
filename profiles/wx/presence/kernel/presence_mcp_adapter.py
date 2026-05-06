#!/usr/bin/env python3
"""Small stdio MCP adapter for Presence world collectors."""
from __future__ import annotations

import json
import os
import re
import select
import subprocess
import time
from datetime import datetime, timedelta
from typing import Any

from presence_common import HERMES_HOME, load_env_file, local_now, read_json, read_yaml, redact, runtime_path, sha256_text, write_json


def collect_mcp_sources(
    profile: dict[str, Any],
    *,
    tick_run_id: str | None,
    collector_run_id: str,
    phase: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    world_policy = profile.get("world_policy", {}) or {}
    sources = [
        src for src in world_policy.get("mcp_sources", []) or []
        if src.get("enabled", False) and str(src.get("phase") or "prefilter") == phase
    ]
    if not sources:
        return [], []

    load_env_file(HERMES_HOME / ".env")
    server_cfgs = ((read_yaml(HERMES_HOME / "config.yaml", {}) or {}).get("mcp_servers") or {})
    now = local_now(profile)
    cache = read_json(runtime_path("world-mcp-cache.json"), {"schema_version": 1, "items": {}})
    signals: list[dict[str, Any]] = []
    tool_calls: list[dict[str, Any]] = []

    for source in sources:
        call = _call_source(source, server_cfgs, cache, now, profile)
        call["tick_run_id"] = tick_run_id
        call["collector_run_id"] = collector_run_id
        tool_calls.append(call)
        if not call.get("ok"):
            continue
        signals.append(_signal_from_call(profile, source, call, collector_run_id, tick_run_id, now))

    write_json(runtime_path("world-mcp-cache.json"), cache)
    return signals, tool_calls


def _call_source(
    source: dict[str, Any],
    server_cfgs: dict[str, Any],
    cache: dict[str, Any],
    now: datetime,
    profile: dict[str, Any],
) -> dict[str, Any]:
    server_name = str(source.get("server") or "").strip()
    tool_name = str(source.get("tool") or "").strip()
    args = source.get("arguments") if isinstance(source.get("arguments"), dict) else {}
    tool_call_id = f"mcp_{_slug(server_name)}_{_slug(tool_name)}_{sha256_text(json.dumps(args, ensure_ascii=False, sort_keys=True))[:8]}"
    base = {
        "tool_call_id": tool_call_id,
        "server": server_name,
        "tool": tool_name,
        "args_summary": _compact_json(args, 500),
        "sensitivity": source.get("sensitivity", "public"),
        "policy_decision": source.get("policy_decision", "auto_allow"),
        "allowed_use": source.get("allowed_use", "mood_only"),
        "phase": source.get("phase") or "prefilter",
    }
    if not server_name or not tool_name:
        return base | {"ok": False, "error": "mcp source requires server and tool"}
    server_cfg = server_cfgs.get(server_name)
    if not isinstance(server_cfg, dict):
        return base | {"ok": False, "error": f"mcp server not configured: {server_name}"}
    if server_cfg.get("enabled") is False:
        return base | {"ok": False, "error": f"mcp server disabled: {server_name}"}

    cache_key = sha256_text(json.dumps({"server": server_name, "tool": tool_name, "args": args}, ensure_ascii=False, sort_keys=True))
    cached = _cache_get(cache, cache_key, now)
    if cached is not None:
        return base | {"ok": True, "cached": True, "latency_ms": 0, "result_summary": cached.get("result_summary", ""), "raw_result": cached.get("raw_result")}

    command = server_cfg.get("command")
    if not command:
        return base | {"ok": False, "error": "only stdio MCP servers with command are supported by this collector"}
    cmd = [str(command)] + [str(arg) for arg in (server_cfg.get("args") or [])]
    timeout = float(source.get("timeout_seconds") or server_cfg.get("timeout") or 60)
    started = time.time()
    try:
        raw = _mcp_tools_call(cmd, _resolve_env(server_cfg.get("env") or {}), tool_name, args, timeout)
        latency_ms = round((time.time() - started) * 1000)
        summary = _summarize_mcp_result(raw, int(source.get("max_result_chars") or 1200))
        record = base | {"ok": True, "cached": False, "latency_ms": latency_ms, "result_summary": summary, "raw_result": raw}
        _cache_set(cache, cache_key, record, now, float(source.get("cache_ttl_minutes") or 0))
        return record
    except Exception as exc:
        return base | {"ok": False, "cached": False, "latency_ms": round((time.time() - started) * 1000), "error": redact(str(exc)[:800])}


def _mcp_tools_call(command: list[str], env_overrides: dict[str, str], tool_name: str, args: dict[str, Any], timeout: float) -> dict[str, Any]:
    env = os.environ.copy()
    env.update(env_overrides)
    proc = subprocess.Popen(
        command,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
        env=env,
    )
    stderr_lines: list[str] = []
    try:
        _send(proc, {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "presence-world-collector", "version": "1.0"}}})
        init = _read_response(proc, 1, timeout, stderr_lines)
        if "error" in init:
            raise RuntimeError(f"MCP initialize failed: {init['error']}")
        _send(proc, {"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}})
        _send(proc, {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": tool_name, "arguments": args}})
        result = _read_response(proc, 2, timeout, stderr_lines)
        if "error" in result:
            raise RuntimeError(f"MCP tool failed: {result['error']}")
        return result.get("result") or {}
    finally:
        try:
            proc.terminate()
            proc.wait(timeout=2)
        except Exception:
            proc.kill()


def _send(proc: subprocess.Popen, payload: dict[str, Any]) -> None:
    if proc.stdin is None:
        raise RuntimeError("MCP process stdin unavailable")
    proc.stdin.write(json.dumps(payload, ensure_ascii=False) + "\n")
    proc.stdin.flush()


def _read_response(proc: subprocess.Popen, want_id: int, timeout: float, stderr_lines: list[str]) -> dict[str, Any]:
    if proc.stdout is None or proc.stderr is None:
        raise RuntimeError("MCP process pipes unavailable")
    deadline = time.time() + timeout
    while time.time() < deadline:
        ready, _, _ = select.select([proc.stdout, proc.stderr], [], [], 0.25)
        for stream in ready:
            line = stream.readline()
            if not line:
                continue
            if stream is proc.stderr:
                stderr_lines.append(line.strip()[:500])
                continue
            try:
                message = json.loads(line)
            except Exception:
                continue
            if message.get("id") == want_id:
                return message
    extra = "; ".join(stderr_lines[-4:])
    raise TimeoutError(redact(f"MCP response timeout for id={want_id}. stderr={extra}"[:900]))


def _signal_from_call(
    profile: dict[str, Any],
    source: dict[str, Any],
    call: dict[str, Any],
    collector_run_id: str,
    tick_run_id: str | None,
    now: datetime,
) -> dict[str, Any]:
    name = source.get("name") or f"{call.get('server')}_{call.get('tool')}"
    ttl = float(source.get("signal_ttl_minutes") or source.get("cache_ttl_minutes") or 60)
    return {
        "id": f"ws_{collector_run_id}_{_slug(str(name))}",
        "profile_id": profile["profile_id"],
        "run_id": collector_run_id,
        "kind": source.get("kind", "mcp_signal"),
        "source": {"type": "mcp", "name": name, "server": call.get("server"), "tool": call.get("tool"), "cached": call.get("cached", False)},
        "raw_summary": str(call.get("result_summary") or "")[:1200],
        "normalized_fact": str(call.get("result_summary") or "").strip().replace("\n", " ")[:360],
        "fetched_at": now.isoformat(),
        "expires_at": (now + timedelta(minutes=ttl)).isoformat() if ttl > 0 else None,
        "confidence": float(source.get("confidence", 0.75)),
        "sensitivity": source.get("sensitivity", "public"),
        "policy_decision": source.get("policy_decision", "auto_allow"),
        "allowed_use": source.get("allowed_use", "mood_only"),
        "operator_review": "unreviewed",
        "trace": {"collector_run_id": collector_run_id, "tick_run_id": tick_run_id, "tool_calls": [call.get("tool_call_id")]},
    }


def _cache_get(cache: dict[str, Any], key: str, now: datetime) -> dict[str, Any] | None:
    item = (cache.get("items") or {}).get(key)
    if not isinstance(item, dict):
        return None
    try:
        expires_at = datetime.fromisoformat(str(item.get("expires_at")))
    except Exception:
        return None
    if expires_at <= now:
        cache.setdefault("items", {}).pop(key, None)
        return None
    return item.get("value") if isinstance(item.get("value"), dict) else None


def _cache_set(cache: dict[str, Any], key: str, value: dict[str, Any], now: datetime, ttl_minutes: float) -> None:
    if ttl_minutes <= 0:
        return
    cache.setdefault("items", {})[key] = {
        "created_at": now.isoformat(),
        "expires_at": (now + timedelta(minutes=ttl_minutes)).isoformat(),
        "value": {
            "result_summary": value.get("result_summary", ""),
            "raw_result": value.get("raw_result"),
        },
    }


def _resolve_env(values: dict[str, Any]) -> dict[str, str]:
    resolved: dict[str, str] = {}
    for key, value in values.items():
        text = str(value)
        match = re.fullmatch(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}", text)
        if match:
            text = os.environ.get(match.group(1), "")
        resolved[str(key)] = text
    return resolved


def _summarize_mcp_result(result: dict[str, Any], limit: int) -> str:
    content = result.get("content")
    parts: list[str] = []
    if isinstance(content, list):
        for item in content:
            if not isinstance(item, dict):
                continue
            if item.get("type") == "text" and item.get("text"):
                parts.append(str(item.get("text")))
            elif item:
                parts.append(_compact_json(item, limit))
    if not parts and result.get("structuredContent") is not None:
        parts.append(_compact_json(result.get("structuredContent"), limit))
    if not parts:
        parts.append(_compact_json(result, limit))
    return "\n".join(parts).strip()[:limit]


def _compact_json(value: Any, limit: int) -> str:
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True)[:limit]
    except Exception:
        return str(value)[:limit]


def _slug(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_]+", "_", value).strip("_")[:80] or "mcp"
