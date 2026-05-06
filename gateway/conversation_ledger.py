"""
Sanitized conversation ledger for gateway-visible chat events.

The ledger is a sidecar fact layer: it records only user-visible inbound and
outbound events so Presence and ordinary chat history can share one clean,
real-time timeline without reading raw cron/session internals.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from hermes_cli.config import get_hermes_home

logger = logging.getLogger(__name__)

SCHEMA_VERSION = 1
RECENT_WINDOW_SECONDS = 4.0
DEFAULT_PROFILE_ID = "linjiang"
MAX_CONTENT_CHARS = 2000
MEMORY_CONTEXT_REPLY_PREFIX = "🧠 Memory context:"
MEMORY_CONTEXT_BLOCK_RE = re.compile(r"(?is)<memory-context\b[^>]*>.*?</memory-context>")


def ledger_dir() -> Path:
    return get_hermes_home() / "conversation"


def ledger_path() -> Path:
    return ledger_dir() / "ledger.jsonl"


def indexes_dir() -> Path:
    return ledger_dir() / "indexes"


def default_profile_id() -> str:
    path = get_hermes_home() / "presence" / "config.yaml"
    if path.exists():
        try:
            import yaml

            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            value = str(data.get("default_profile_id") or "").strip()
            if value:
                return value
        except Exception:
            pass
    return os.environ.get("PRESENCE_PROFILE_ID", DEFAULT_PROFILE_ID) or DEFAULT_PROFILE_ID


def profile_revision(profile_id: Optional[str] = None) -> str:
    profile_id = profile_id or default_profile_id()
    home = get_hermes_home()
    pieces: list[str] = []
    for path in (
        home / "SOUL.md",
        home / "USER.md",
        home / "MEMORY.md",
        home / "presence" / "profiles" / profile_id / "manifest.yaml",
        home / "presence" / "profiles" / profile_id / "profile_metadata.yaml",
        home / "presence" / "profiles" / profile_id / "voice.md",
        home / "presence" / "profiles" / profile_id / "relationship.yaml",
    ):
        try:
            if path.exists():
                pieces.append(path.read_text(encoding="utf-8", errors="replace"))
        except Exception:
            continue
    digest = hashlib.sha256("\n---\n".join(pieces).encode("utf-8")).hexdigest()
    return f"sha256:{digest[:16]}"


def preset_id() -> str:
    return os.environ.get("WX_ST_PRESET_ID") or os.environ.get("ST_PRESET_ID") or "default"


def _profile_env_value(name: str) -> str:
    """Read a value from the active profile .env without leaking global state.

    Gateway processes may inherit ~/.hermes/.env while the active profile has
    its own ~/.hermes/profiles/<id>/.env.  For the conversation ledger, the
    profile-local value is the stable identity for this profile's timeline.
    """
    path = get_hermes_home() / ".env"
    if not path.exists():
        return ""
    try:
        for raw_line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            if key.strip() == name:
                return value.strip().strip('"').strip("'")
    except Exception:
        return ""
    return ""


def conversation_key_from_parts(
    *,
    platform: str,
    chat_id: str,
    thread_id: str | None = None,
    account_id: str | None = None,
) -> str:
    platform = str(platform or "unknown").lower()
    if platform == "weixin":
        account_id = (
            account_id
            or _profile_env_value("WEIXIN_ACCOUNT_ID")
            or os.environ.get("WEIXIN_ACCOUNT_ID")
            or "main"
        )
    else:
        account_id = account_id or "main"
    return f"{platform}:{account_id}:{chat_id}:{thread_id or ''}"


def _conversation_key_matches(event: dict[str, Any], conversation_key: str) -> bool:
    """Match exact keys, with a Weixin fallback for legacy mixed account IDs."""
    event_key = str(event.get("conversation_key") or "")
    if event_key == conversation_key:
        return True

    try:
        platform, _account, chat_id, thread_id = conversation_key.split(":", 3)
        event_platform, _event_account, event_chat_id, event_thread_id = event_key.split(":", 3)
    except ValueError:
        return False

    return (
        platform == "weixin"
        and event_platform == "weixin"
        and event_chat_id == chat_id
        and event_thread_id == thread_id
    )


def conversation_key_from_source(source: Any) -> str:
    platform = getattr(getattr(source, "platform", None), "value", None) or getattr(source, "platform", None) or "unknown"
    return conversation_key_from_parts(
        platform=str(platform),
        chat_id=str(getattr(source, "chat_id", "") or ""),
        thread_id=str(getattr(source, "thread_id", "") or "") or None,
    )


def find_session_id(platform: str, chat_id: str, thread_id: str | None = None, user_id: str | None = None) -> str:
    sessions_index = get_hermes_home() / "sessions" / "sessions.json"
    if not sessions_index.exists():
        return ""
    try:
        data = json.loads(sessions_index.read_text(encoding="utf-8"))
    except Exception:
        return ""

    platform_lower = str(platform or "").lower()
    candidates: list[dict[str, Any]] = []
    for entry in data.values():
        if not isinstance(entry, dict):
            continue
        origin = entry.get("origin") or {}
        entry_platform = str(origin.get("platform") or entry.get("platform") or "").lower()
        if entry_platform != platform_lower:
            continue
        if str(origin.get("chat_id") or "") != str(chat_id):
            continue
        if thread_id is not None and str(origin.get("thread_id") or "") != str(thread_id):
            continue
        candidates.append(entry)

    if not candidates:
        return ""
    if user_id:
        exact = [entry for entry in candidates if str((entry.get("origin") or {}).get("user_id") or "") == str(user_id)]
        if exact:
            candidates = exact
        elif len(candidates) > 1:
            return ""
    elif len(candidates) > 1:
        distinct_users = {
            str((entry.get("origin") or {}).get("user_id") or "").strip()
            for entry in candidates
            if str((entry.get("origin") or {}).get("user_id") or "").strip()
        }
        if len(distinct_users) > 1:
            return ""
    best = max(candidates, key=lambda entry: entry.get("updated_at", ""))
    return str(best.get("session_id") or "")


def write_event_from_source(
    *,
    source: Any,
    role: str,
    content: str,
    source_label: str,
    session_id: str | None = None,
    content_kind: str = "text",
    message_id: str | None = None,
    delivery: dict[str, Any] | None = None,
    presence: dict[str, Any] | None = None,
) -> str:
    platform = getattr(getattr(source, "platform", None), "value", None) or getattr(source, "platform", None) or ""
    chat_id = str(getattr(source, "chat_id", "") or "")
    thread_id = str(getattr(source, "thread_id", "") or "")
    user_id = str(getattr(source, "user_id", "") or "")
    if not session_id:
        session_id = find_session_id(str(platform), chat_id, thread_id or None, user_id or None)
    return write_visible_event(
        platform=str(platform),
        chat_id=chat_id,
        thread_id=thread_id,
        user_id=user_id,
        session_id=session_id or "",
        role=role,
        source_label=source_label,
        content=content,
        content_kind=content_kind,
        message_id=message_id,
        delivery=delivery,
        presence=presence,
    )


def write_delivery_event(
    *,
    platform: str,
    chat_id: str,
    content: str,
    source_label: str,
    thread_id: str | None = None,
    user_id: str | None = None,
    session_id: str | None = None,
    content_kind: str = "text",
    message_id: str | None = None,
    delivery: dict[str, Any] | None = None,
    presence: dict[str, Any] | None = None,
) -> str:
    if not session_id:
        session_id = find_session_id(platform, chat_id, thread_id, user_id)
    return write_visible_event(
        platform=platform,
        chat_id=chat_id,
        thread_id=thread_id or "",
        user_id=user_id or "",
        session_id=session_id or "",
        role="assistant",
        source_label=source_label,
        content=content,
        content_kind=content_kind,
        message_id=message_id,
        delivery=delivery,
        presence=presence,
    )


def write_visible_event(
    *,
    platform: str,
    chat_id: str,
    role: str,
    source_label: str,
    content: str,
    session_id: str = "",
    thread_id: str = "",
    user_id: str = "",
    content_kind: str = "text",
    profile_id: str | None = None,
    message_id: str | None = None,
    delivery: dict[str, Any] | None = None,
    presence: dict[str, Any] | None = None,
) -> str:
    clean = sanitize_content(content)
    if not clean or clean.upper() == "[SILENT]":
        return ""
    profile_id = profile_id or default_profile_id()
    now = datetime.now().astimezone()
    role_norm = "assistant" if str(role).lower() == "assistant" else "user"
    conversation_key = conversation_key_from_parts(
        platform=str(platform or ""),
        chat_id=str(chat_id or ""),
        thread_id=str(thread_id or "") or None,
    )
    duplicate_id = _find_duplicate_visible_event(
        conversation_key=conversation_key,
        role=role_norm,
        source_label=str(source_label or "unknown"),
        content=clean,
        message_id=message_id,
        now_ts=now.timestamp(),
    )
    if duplicate_id:
        return duplicate_id
    event_id = f"conv_{now.strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
    event = {
        "schema_version": SCHEMA_VERSION,
        "event_id": event_id,
        "profile_id": profile_id,
        "channel": str(platform or "").lower(),
        "chat_id": str(chat_id or ""),
        "thread_id": str(thread_id or ""),
        "user_id": str(user_id or ""),
        "session_id": str(session_id or ""),
        "conversation_key": conversation_key,
        "session_epoch_id": str(session_id or ""),
        "persona_revision": profile_revision(profile_id),
        "preset_id": preset_id(),
        "role": role_norm,
        "source": str(source_label or "unknown"),
        "content": clean[:MAX_CONTENT_CHARS],
        "content_kind": content_kind,
        "visible_to_user": True,
        "created_at": now.isoformat(),
        "unix_ts": time.time(),
        "sanitized": True,
        "prompt_visibility": {"chat_history": True, "state_context": True},
    }
    if message_id:
        event["message_id"] = message_id
    if delivery:
        event["delivery"] = delivery
    if presence:
        event["presence"] = presence
    _append_jsonl(ledger_path(), event)
    _update_indexes(event)
    return event_id


def read_visible_events_for_source(
    *,
    source: Any,
    session_id: str,
    profile_id: str | None = None,
    limit: int = 24,
) -> list[dict[str, Any]]:
    return read_visible_events(
        conversation_key=conversation_key_from_source(source),
        session_epoch_id=session_id,
        profile_id=profile_id or default_profile_id(),
        limit=limit,
    )


def read_visible_events(
    *,
    conversation_key: str,
    session_epoch_id: str | None = None,
    profile_id: str | None = None,
    limit: int = 24,
) -> list[dict[str, Any]]:
    profile_id = profile_id or default_profile_id()
    rows: list[dict[str, Any]] = []
    path = ledger_path()
    if not path.exists():
        return []
    try:
        with path.open("r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                try:
                    event = json.loads(line)
                except Exception:
                    continue
                if not event.get("visible_to_user"):
                    continue
                if event.get("profile_id") != profile_id:
                    continue
                if not _conversation_key_matches(event, conversation_key):
                    continue
                if session_epoch_id and event.get("session_epoch_id") != session_epoch_id:
                    # Presence cron delivery may happen outside an ordinary
                    # inbound session and therefore has no session epoch to
                    # bind to. It is still visible in the same chat and should
                    # enter the next ordinary chat prompt.
                    if not (
                        event.get("source") == "presence"
                        and not str(event.get("session_epoch_id") or "").strip()
                    ):
                        continue
                if not (event.get("prompt_visibility") or {}).get("chat_history", True):
                    continue
                rows.append(event)
    except Exception as exc:
        logger.debug("conversation ledger read failed: %s", exc)
        return []
    rows.sort(key=lambda item: float(item.get("unix_ts") or 0))
    return rows[-limit:]


def merge_ledger_into_history(
    history: list[dict[str, Any]],
    *,
    source: Any,
    session_id: str,
    limit: int = 24,
) -> list[dict[str, Any]]:
    events = read_visible_events_for_source(source=source, session_id=session_id, limit=limit)
    if not events:
        return history
    out = list(history or [])
    for event in events:
        content = sanitize_content(str(event.get("content") or ""))
        if not content:
            continue
        msg = {
            "role": "assistant" if event.get("role") == "assistant" else "user",
            "content": content,
            "timestamp": event.get("created_at"),
            "ledger_event_id": event.get("event_id"),
            "ledger_source": event.get("source"),
        }
        if not msg["content"] or _has_duplicate_message(out, msg):
            continue
        _insert_chronological(out, msg)
    return out


def recent_ledger_system_message(
    *,
    source: Any,
    session_id: str,
    profile_id: str | None = None,
    limit: int = 12,
) -> str:
    """Build a compact system note from the recent user-visible ledger.

    This is intentionally redundant with ``merge_ledger_into_history``: the
    history merge keeps role continuity, while this note gives models with
    aggressive history truncation an unmistakable bridge across ordinary chat
    and Presence cron deliveries.
    """
    events = read_visible_events_for_source(
        source=source,
        session_id=session_id,
        profile_id=profile_id or default_profile_id(),
        limit=limit,
    )
    if not events:
        return ""
    lines = [
        "[Recent visible conversation ledger]",
        "These are only user-visible chat events. They exclude cron prompts, scripts, traces, tool logs, and internal notices.",
    ]
    for event in events[-limit:]:
        role = "assistant" if event.get("role") == "assistant" else "user"
        src = str(event.get("source") or "").strip()
        label = role
        if role == "assistant" and src == "presence":
            label = f"assistant({src})"
        created = _format_time_for_ledger_note(event.get("created_at"), event.get("unix_ts"))
        content = sanitize_content(str(event.get("content") or "")).replace("\n", " ").strip()
        if len(content) > 360:
            content = content[:357] + "..."
        if content:
            lines.append(f"{created} {label}: {content}")
    return "\n".join(lines) if len(lines) > 2 else ""


def sanitize_content(content: str) -> str:
    text = str(content or "").strip()
    text = MEMORY_CONTEXT_BLOCK_RE.sub("", text).strip()
    if re.match(r"(?i)^presence\s+location(?:\s+|$)", text):
        return ""
    if re.match(r"(?i)^proxy\s+memory(?:-context|\s+context|\s+show|\s+clear)?(?:\s+|$)", text):
        return ""
    if text.startswith("📍 Presence location:"):
        return ""
    if text.startswith(MEMORY_CONTEXT_REPLY_PREFIX):
        return ""
    text = re.sub(r"MEDIA:\s*\S+", "", text)
    text = text.replace("[[audio_as_voice]]", "").strip()
    text = re.sub(r"<\|[^>]{1,80}\|>", "", text).strip()
    text = text.replace("</null>", "").strip()
    text = re.sub(r"(?i)(api[_-]?key|token|secret|password)=\S+", r"\1=***", text)
    text = re.sub(r"(?i)bearer\s+[A-Za-z0-9._-]+", "Bearer ***", text)
    if re.match(
        r"^(Operation interrupted|Interrupting current task|Gateway code was updated|⟳ Gateway code was updated|◐ Session automatically reset)\b",
        text,
        flags=re.IGNORECASE,
    ):
        return ""
    return text


def _find_duplicate_visible_event(
    *,
    conversation_key: str,
    role: str,
    source_label: str,
    content: str,
    message_id: str | None,
    now_ts: float,
) -> str:
    path = ledger_path()
    if not path.exists():
        return ""
    clean = sanitize_content(content)
    found = ""
    try:
        with path.open("r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                try:
                    event = json.loads(line)
                except Exception:
                    continue
                if not event.get("visible_to_user"):
                    continue
                if not _conversation_key_matches(event, conversation_key):
                    continue
                if str(event.get("role") or "") != role:
                    continue
                if str(event.get("source") or "") != source_label:
                    continue
                if message_id:
                    if str(event.get("message_id") or "") == str(message_id):
                        found = str(event.get("event_id") or "")
                    continue
                if sanitize_content(str(event.get("content") or "")) != clean:
                    continue
                event_ts = event.get("unix_ts")
                try:
                    event_ts = float(event_ts)
                except Exception:
                    event_ts = None
                if event_ts is None or abs(now_ts - event_ts) <= RECENT_WINDOW_SECONDS:
                    found = str(event.get("event_id") or "")
    except Exception as exc:
        logger.debug("conversation ledger duplicate check failed: %s", exc)
        return ""
    return found


def _format_time_for_ledger_note(created_at: Any, unix_ts: Any) -> str:
    try:
        if created_at:
            dt = datetime.fromisoformat(str(created_at))
        else:
            dt = datetime.fromtimestamp(float(unix_ts)).astimezone()
        return dt.strftime("%H:%M")
    except Exception:
        return "??:??"


def _append_jsonl(path: Path, obj: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(obj, ensure_ascii=False) + "\n")


def _update_indexes(event: dict[str, Any]) -> None:
    indexes_dir().mkdir(parents=True, exist_ok=True)
    _update_index(indexes_dir() / "latest-by-chat.json", event)
    if event.get("source") == "presence":
        _update_index(indexes_dir() / "latest-presence-by-chat.json", event)


def _update_index(path: Path, event: dict[str, Any]) -> None:
    try:
        data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    except Exception:
        data = {}
    data[event["conversation_key"]] = {
        "event_id": event["event_id"],
        "profile_id": event["profile_id"],
        "session_epoch_id": event.get("session_epoch_id", ""),
        "role": event.get("role"),
        "source": event.get("source"),
        "content": event.get("content", "")[:200],
        "created_at": event.get("created_at"),
        "unix_ts": event.get("unix_ts"),
    }
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def _has_duplicate_message(messages: list[dict[str, Any]], candidate: dict[str, Any]) -> bool:
    candidate_role = str(candidate.get("role") or "")
    candidate_content = sanitize_content(str(candidate.get("content") or ""))
    candidate_ts = _message_ts(candidate)
    for message in messages:
        if not isinstance(message, dict):
            continue
        if str(message.get("role") or "") != candidate_role:
            continue
        if sanitize_content(str(message.get("content") or "")) != candidate_content:
            continue
        other_ts = _message_ts(message)
        if candidate_ts is None or other_ts is None:
            return True
        if abs(candidate_ts - other_ts) <= RECENT_WINDOW_SECONDS:
            return True
    return False


def _insert_chronological(messages: list[dict[str, Any]], message: dict[str, Any]) -> None:
    ts = _message_ts(message)
    if ts is None:
        messages.append(message)
        return
    start = 1 if messages and messages[0].get("role") == "session_meta" else 0
    for idx in range(start, len(messages)):
        other_ts = _message_ts(messages[idx])
        if other_ts is not None and other_ts > ts + RECENT_WINDOW_SECONDS:
            messages.insert(idx, message)
            return
    messages.append(message)


def _message_ts(message: dict[str, Any]) -> float | None:
    value = message.get("unix_ts") or message.get("timestamp") or message.get("created_at")
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return datetime.fromisoformat(str(value)).timestamp()
    except Exception:
        return None
