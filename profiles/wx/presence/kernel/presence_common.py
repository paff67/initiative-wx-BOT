#!/usr/bin/env python3
"""Shared utilities for the generic Presence Kernel."""
from __future__ import annotations

import hashlib
import json
import os
import random
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import yaml


HERMES_HOME = Path(os.environ.get("HERMES_HOME", str(Path.home() / ".hermes" / "profiles" / "wx"))).expanduser()
PRESENCE_HOME = HERMES_HOME / "presence"
KERNEL_DIR = PRESENCE_HOME / "kernel"
PROMPTS_DIR = PRESENCE_HOME / "prompts"
PROFILES_DIR = PRESENCE_HOME / "profiles"
RUNTIME_DIR = PRESENCE_HOME / "runtime"
EVENTS_DIR = PRESENCE_HOME / "events"
SCHEMAS_DIR = PRESENCE_HOME / "schemas"


def ensure_dirs() -> None:
    for path in (PRESENCE_HOME, KERNEL_DIR, PROMPTS_DIR, PROFILES_DIR, RUNTIME_DIR, EVENTS_DIR, SCHEMAS_DIR):
        path.mkdir(parents=True, exist_ok=True)


def read_json(path: Path, default: Any) -> Any:
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default
    return default


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def append_jsonl(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(obj, ensure_ascii=False) + "\n")


def read_yaml(path: Path, default: Any = None) -> Any:
    try:
        if path.exists():
            return yaml.safe_load(path.read_text(encoding="utf-8")) or ({} if default is None else default)
    except Exception:
        return {} if default is None else default
    return {} if default is None else default


def write_yaml(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = yaml.safe_dump(obj, allow_unicode=True, sort_keys=False)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def profile_dir(profile_id: str) -> Path:
    return PROFILES_DIR / profile_id


def runtime_path(name: str) -> Path:
    return RUNTIME_DIR / name


def event_path(name: str) -> Path:
    if os.environ.get("PRESENCE_EVENT_STREAM") == "preview" and name != "preview-events.jsonl":
        return EVENTS_DIR / "preview-events.jsonl"
    return EVENTS_DIR / name


def load_profile(profile_id: str) -> dict[str, Any]:
    base = profile_dir(profile_id)
    manifest = read_yaml(base / "manifest.yaml", {})
    timezone_name = manifest.get("timezone") or "Asia/Shanghai"
    cfg = {
        "profile_id": profile_id,
        "profile_dir": str(base),
        "manifest": manifest,
        "profile_metadata": read_yaml(base / "profile_metadata.yaml", {}),
        "identity_canon": soul_identity_canon(),
        "relationship": read_yaml(base / "relationship.yaml", {}),
        "proactive_policy": read_yaml(base / "proactive_policy.yaml", {}),
        "world_policy": read_yaml(base / "world_policy.yaml", {}),
        "permission_policy": read_yaml(base / "permission_policy.yaml", {}),
        "delivery": read_yaml(base / "delivery_weixin.yaml", {}),
        "examples": read_yaml(base / "examples.yaml", {}),
        "voice_text": read_text(base / "voice.md", ""),
        "timezone": timezone_name,
    }
    cfg["config_revision"] = config_revision(cfg)
    return cfg


def config_revision(profile: dict[str, Any]) -> str:
    payload = {
        k: v for k, v in profile.items()
        if k not in {"config_revision", "profile_dir"}
    }
    payload["_prompt_files"] = prompt_revision_payload(profile)
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()[:16]


def prompt_revision_payload(profile: dict[str, Any]) -> dict[str, str]:
    profile_id = str(profile.get("profile_id") or "")
    out: dict[str, str] = {}
    for layer in ("state", "decision", "render"):
        for path in prompt_candidate_paths(profile_id, layer):
            if not path.exists():
                continue
            try:
                out[str(path.relative_to(PRESENCE_HOME))] = path.read_text(encoding="utf-8")
            except Exception:
                continue
    return out


def prompt_candidate_paths(profile_id: str, layer: str) -> list[Path]:
    layer = str(layer or "").strip().lower().replace("_", "-")
    names = [f"{layer}-system.md", f"{layer}.md"]
    paths: list[Path] = []
    if profile_id:
        profile_prompts = profile_dir(profile_id) / "prompts"
        paths.extend(profile_prompts / name for name in names)
    paths.extend(PROMPTS_DIR / name for name in names)
    return paths


def load_prompt(profile: dict[str, Any], layer: str) -> str:
    profile_id = str(profile.get("profile_id") or "")
    for path in prompt_candidate_paths(profile_id, layer):
        text = read_text(path, "", limit=None).strip()
        if text:
            return text
    searched = ", ".join(str(path) for path in prompt_candidate_paths(profile_id, layer))
    raise FileNotFoundError(f"Presence prompt not found for layer={layer!r}; searched: {searched}")


def local_now(profile: dict[str, Any]) -> datetime:
    return datetime.now(ZoneInfo(profile.get("timezone") or "Asia/Shanghai"))


def make_run_id(prefix: str, now: datetime | None = None) -> str:
    now = now or utc_now()
    return f"{prefix}_{now.strftime('%Y%m%d_%H%M%S')}_{random.randint(1000, 9999)}"


def read_text(path: Path, default: str = "", limit: int | None = None) -> str:
    try:
        text = path.read_text(encoding="utf-8")
        if limit and len(text) > limit:
            return text[:limit] + "\n...[truncated]"
        return text
    except Exception:
        return default


def soul_identity_canon(limit: int | None = 12000) -> str:
    """Return the canonical identity block from SOUL.md.

    Presence treats the role content before the Hermes runtime boundary / section 8
    as the identity authority. Profile YAML may describe routing and policy, but it
    must not override this canon.
    """
    text = read_text(HERMES_HOME / "SOUL.md", "", limit=None)
    if not text:
        return ""
    stops = []
    for marker in ("\n## Hermes 微信运行边界", "\n## 8."):
        idx = text.find(marker)
        if idx >= 0:
            stops.append(idx)
    if stops:
        text = text[: min(stops)]
    text = text.rstrip()
    if limit and len(text) > limit:
        return text[:limit] + "\n...[truncated]"
    return text


def load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ[key.strip()] = value.strip().strip("\"").strip("'")


def load_profile_env(profile: dict[str, Any]) -> None:
    manifest = profile.get("manifest") or {}
    llm = manifest.get("llm") or {}
    env_file = llm.get("env_file")
    if not env_file:
        return
    path = Path(str(env_file)).expanduser()
    if not path.is_absolute():
        path = Path(str(profile.get("profile_dir") or "")).expanduser() / path
    load_env_file(path.resolve())


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def redact(text: str) -> str:
    # Lightweight local redaction; Hermes will also redact cron script output.
    import re
    patterns = [
        r"sk-[A-Za-z0-9_-]{12,}",
        r"(?i)(api[_-]?key|token|secret|password)=([^\\s]+)",
        r"(?i)bearer\\s+[A-Za-z0-9._-]+",
    ]
    out = text
    for pat in patterns:
        out = re.sub(pat, lambda m: m.group(0).split("=")[0] + "=***" if "=" in m.group(0) else "***", out)
    return out


def day_key(now: datetime) -> str:
    return now.strftime("%Y-%m-%d")


def event(obj: dict[str, Any], profile: dict[str, Any], run_id: str | None = None) -> dict[str, Any]:
    now = local_now(profile)
    obj.setdefault("profile_id", profile["profile_id"])
    obj.setdefault("created_at", now.isoformat())
    obj.setdefault("config_revision", profile.get("config_revision"))
    if run_id:
        obj.setdefault("run_id", run_id)
    return obj


def load_control() -> dict[str, Any]:
    return read_json(runtime_path("control.json"), {"schema_version": 1, "revision": 1, "override": {}, "operator_feedback": []})


def save_control(control: dict[str, Any]) -> None:
    write_json(runtime_path("control.json"), control)


def load_runtime_state() -> dict[str, Any]:
    return read_json(runtime_path("state.json"), {})


def save_runtime_state(state: dict[str, Any]) -> None:
    write_json(runtime_path("state.json"), state)


def load_intent_state() -> dict[str, Any]:
    return read_json(runtime_path("intent-state.json"), {"schema_version": 1, "topics": {}, "delivery_counters": {}})


def save_intent_state(state: dict[str, Any]) -> None:
    write_json(runtime_path("intent-state.json"), state)


def latest_jsonl(path: Path, limit: int = 50) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    try:
        with path.open("r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    rows.append(json.loads(line))
                except Exception:
                    continue
    except Exception:
        return []
    return rows[-limit:][::-1]


def call_chat_completion(
    *,
    base_url: str,
    api_key: str,
    model: str,
    messages: list[dict[str, str]],
    temperature: float = 0.2,
    max_tokens: int = 1200,
    timeout: float = 120,
    extra_body: dict[str, Any] | None = None,
) -> tuple[str, float]:
    start = time.time()
    body: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if extra_body:
        body.update(extra_body)
    url = base_url.rstrip("/") + "/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": "Hermes-Presence-Kernel/1.0",
        "X-WX-Request-Source": "presence-kernel",
    }
    local_proxy = "127.0.0.1" in base_url.lower() or "localhost" in base_url.lower()
    if local_proxy:
        body["wx_proxy_bypass"] = ["snippets", "sampling", "commands"]
        headers["X-WX-Proxy-Bypass"] = "snippets,sampling,commands"
        if api_key:
            headers["X-WX-Proxy-Upstream-Key"] = api_key
    elif api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    req = urllib.request.Request(
        url,
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            payload = json.loads(resp.read().decode("utf-8", errors="replace"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"LLM HTTP {exc.code}: {redact(detail[:1200])}") from exc
    latency = round((time.time() - start) * 1000)
    content = payload.get("choices", [{}])[0].get("message", {}).get("content", "")
    return str(content), latency


def parse_jsonish(text: str, default: Any) -> Any:
    text = text.strip()
    if not text:
        return default
    if text.startswith("```"):
        text = text.strip("`")
        if "\n" in text:
            text = text.split("\n", 1)[1]
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        text = text[start:end + 1]
    try:
        return json.loads(text)
    except Exception:
        return default


def conversation_context(limit: int = 24, profile: dict[str, Any] | None = None) -> dict[str, Any]:
    """Return a sanitized real-time conversation context for Presence.

    Presence must not read raw cron sessions or script prompts as chat history.
    The sanitized ledger records only user-visible inbound/outbound events.
    """
    try:
        from presence_conversation_ledger import build_context

        if profile is None:
            profile = {"profile_id": os.environ.get("PRESENCE_PROFILE_ID", "linjiang"), "delivery": {"channel": "weixin"}}
        return build_context(profile, limit=limit)
    except Exception as exc:
        return {
            "messages": [],
            "timeline": [],
            "ledger_timeline": [],
            "last_visible_interaction": None,
            "interaction_gap": {"elapsed_minutes": None, "unresolved_open_loops": [], "error": str(exc)[:200]},
            "activity": {"error": str(exc)[:200]},
        }


def _dedupe_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str, str]] = set()
    out: list[dict[str, Any]] = []
    for msg in sorted(messages, key=lambda item: float(item.get("timestamp") or 0), reverse=True):
        role = str(msg.get("role") or msg.get("speaker") or "")
        content = str(msg.get("content") or "").strip()
        key = (str(round(float(msg.get("timestamp") or 0), 3)), role, content)
        if key in seen:
            continue
        seen.add(key)
        if content:
            out.append(msg)
    return out


def _compact_message(message: dict[str, Any], now_ts: float) -> dict[str, Any]:
    ts = float(message.get("timestamp") or 0)
    role = str(message.get("role") or message.get("speaker") or "unknown").lower()
    label = "User" if role in {"user", "human"} else "Lin" if role in {"assistant", "lin", "bot"} else role
    return {
        "timestamp": ts,
        "age_minutes": round((now_ts - ts) / 60, 1) if ts else None,
        "speaker": label,
        "content": str(message.get("content") or "")[:600],
    }


def model_settings(kind: str, profile: dict[str, Any]) -> dict[str, Any]:
    llm = ((profile.get("manifest") or {}).get("llm") or {})
    layers = llm.get("layers") or {}
    layer = layers.get(kind) or (layers.get("decision") if kind == "render" else {}) or {}
    prefix = str(layer.get("env_prefix") or f"PRESENCE_{kind.upper()}")
    return {
        "base_url": os.environ.get(f"{prefix}_BASE_URL", "http://127.0.0.1:8788/v1").rstrip("/"),
        "api_key": os.environ.get(f"{prefix}_API_KEY", ""),
        "model": os.environ.get(f"{prefix}_MODEL", "gpt-5.4-mini"),
        "temperature": float(os.environ.get(f"{prefix}_TEMPERATURE", "0.2")),
        "max_tokens": int(os.environ.get(f"{prefix}_MAX_TOKENS", "1200")),
        "timeout": float(os.environ.get(f"{prefix}_TIMEOUT", "120")),
    }
