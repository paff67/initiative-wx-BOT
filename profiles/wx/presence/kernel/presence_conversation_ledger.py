#!/usr/bin/env python3
"""Read the sanitized conversation ledger for Presence context."""
from __future__ import annotations

import json
import os
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any


HERMES_HOME = Path(os.environ.get("HERMES_HOME", str(Path.home() / ".hermes" / "profiles" / "wx"))).expanduser()
LEDGER_PATH = HERMES_HOME / "conversation" / "ledger.jsonl"


def conversation_key_for_profile(profile: dict[str, Any]) -> str:
    delivery = profile.get("delivery") or {}
    channel = str(delivery.get("channel") or profile.get("manifest", {}).get("channel") or "weixin").lower()
    chat_id = (
        os.environ.get("PRESENCE_CONVERSATION_CHAT_ID")
        or os.environ.get("WEIXIN_HOME_CHANNEL")
        or _profile_env_value("WEIXIN_HOME_CHANNEL")
        or ""
    )
    account_id = os.environ.get("WEIXIN_ACCOUNT_ID") or _profile_env_value("WEIXIN_ACCOUNT_ID") or "main"
    if channel == "weixin":
        return f"{channel}:{account_id}:{chat_id}:"
    return f"{channel}:main:{chat_id}:"


def _profile_env_value(key: str) -> str:
    path = HERMES_HOME / ".env"
    if not path.exists():
        return ""
    try:
        for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            name, value = line.split("=", 1)
            if name.strip() == key:
                return value.strip().strip('"').strip("'")
    except Exception:
        return ""
    return ""


def read_timeline(profile: dict[str, Any], limit: int = 24) -> list[dict[str, Any]]:
    profile_id = str(profile.get("profile_id") or "")
    key = conversation_key_for_profile(profile)
    rows: list[dict[str, Any]] = []
    if not LEDGER_PATH.exists():
        return []
    try:
        with LEDGER_PATH.open("r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                try:
                    event = json.loads(line)
                except Exception:
                    continue
                if not event.get("visible_to_user"):
                    continue
                if profile_id and event.get("profile_id") != profile_id:
                    continue
                if key and event.get("conversation_key") != key:
                    continue
                if not (event.get("prompt_visibility") or {}).get("state_context", True):
                    continue
                content = str(event.get("content") or "").strip()
                if not content or content.upper() == "[SILENT]":
                    continue
                rows.append(event)
    except Exception:
        return []
    rows.sort(key=lambda item: float(item.get("unix_ts") or 0))
    return rows[-limit:]


def build_context(profile: dict[str, Any], limit: int = 24) -> dict[str, Any]:
    now_ts = time.time()
    events = read_timeline(profile, limit=limit)
    timeline = [_compact_event(event, now_ts) for event in events]
    last_event = events[-1] if events else None
    last_visible = _compact_event(last_event, now_ts) if last_event else None
    age_minutes = last_visible.get("age_minutes") if last_visible else None
    interaction_gap = {
        "elapsed_minutes": age_minutes,
        "last_visible_interaction": last_visible,
        "unresolved_open_loops": _python_open_loop_hints(timeline[-6:]),
        "python_had_likely_closure": _looks_like_closure(last_visible),
        "time_basis": "real_local_time",
    }
    return {
        "messages": timeline,
        "timeline": timeline,
        "ledger_timeline": timeline,
        "last_visible_interaction": last_visible,
        "interaction_gap": interaction_gap,
        "activity": {
            "last_message_age_minutes": age_minutes,
            "is_recently_active": bool(age_minutes is not None and age_minutes < 45),
            "recent_active_window_minutes": 45,
            "conversation_key": conversation_key_for_profile(profile),
        },
    }


def _compact_event(event: dict[str, Any] | None, now_ts: float) -> dict[str, Any]:
    if not event:
        return {}
    ts = float(event.get("unix_ts") or 0)
    role = str(event.get("role") or "unknown").lower()
    return {
        "event_id": event.get("event_id"),
        "timestamp": ts,
        "created_at": event.get("created_at"),
        "age_minutes": round((now_ts - ts) / 60, 1) if ts else None,
        "role": role,
        "speaker": "User" if role == "user" else "Assistant" if role == "assistant" else role,
        "source": event.get("source"),
        "content_kind": event.get("content_kind", "text"),
        "content": str(event.get("content") or "")[:600],
    }


def _python_open_loop_hints(timeline: list[dict[str, Any]]) -> list[str]:
    if not timeline:
        return []
    hints: list[str] = []
    last = timeline[-1]
    content = str(last.get("content") or "")
    if "?" in content or "？" in content:
        hints.append("last_visible_message_contains_question")
    if re.search(r"(等|回来|一会|待会|去|弄|吃|喝|睡|醒|记得|别忘|晚点|等下)", content):
        hints.append("last_visible_message_may_leave_action_or_care_loop")
    if last.get("role") == "assistant" and not _looks_like_closure(last):
        hints.append("assistant_last_message_without_clear_closure")
    return hints[:4]


def _looks_like_closure(message: dict[str, Any] | None) -> bool:
    if not message:
        return True
    content = str(message.get("content") or "").strip()
    if not content:
        return True
    if re.search(r"(晚安|早安|睡吧|去睡|先这样|到这儿|明天再说|不用回|别回了|收住|结束)", content):
        return True
    if content.endswith(("。", ".", "…", "！", "!")) and not re.search(r"(吗|呢|吧|？|\\?)", content):
        return True
    return False
