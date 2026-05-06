#!/usr/bin/env python3
"""Python-owned intent accumulator and cooldown enforcement."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from presence_common import day_key, load_intent_state, local_now, save_intent_state


def decay_intents(intent_state: dict[str, Any], profile: dict[str, Any], now: datetime | None = None) -> dict[str, Any]:
    now = now or local_now(profile)
    policy = ((profile.get("proactive_policy") or {}).get("intent_accumulator") or {})
    hourly_decay = float(policy.get("hourly_decay", 0.2))
    score_min = float(policy.get("score_min", 0))
    topics = intent_state.setdefault("topics", {})
    for key in list(topics.keys()):
        topic = topics[key]
        last_decay = _parse_time(topic.get("last_decay_at")) or _parse_time(topic.get("last_seen")) or now
        hours = max(0.0, (now - last_decay).total_seconds() / 3600)
        topic["score"] = max(score_min, round(float(topic.get("score", 0)) - hourly_decay * hours, 3))
        topic["last_decay_at"] = now.isoformat()
        expires_at = _parse_time(topic.get("expires_at"))
        if topic["score"] <= score_min or (expires_at and expires_at <= now):
            topics.pop(key, None)
    intent_state["updated_at"] = now.isoformat()
    return intent_state


def apply_intent_delta(
    intent_state: dict[str, Any],
    profile: dict[str, Any],
    delta: dict[str, Any] | None,
    evidence: list[dict[str, Any]] | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    if not delta:
        return intent_state
    now = now or local_now(profile)
    policy = ((profile.get("proactive_policy") or {}).get("intent_accumulator") or {})
    score_max = float(policy.get("score_max", 3))
    expire_hours = float(policy.get("expire_after_hours", 12))
    key = str(delta.get("topic_key") or "general").strip()[:80] or "general"
    amount = float(delta.get("delta") or 0)
    topics = intent_state.setdefault("topics", {})
    topic = topics.setdefault(key, {
        "topic_key": key,
        "seed": str(delta.get("reason") or key)[:240],
        "score": 0,
        "first_seen": now.isoformat(),
        "evidence": [],
    })
    topic["score"] = min(score_max, round(float(topic.get("score", 0)) + amount, 3))
    topic["last_seen"] = now.isoformat()
    topic["last_decay_at"] = now.isoformat()
    topic["last_delta"] = amount
    topic["last_reason"] = str(delta.get("reason") or "")[:240]
    expires_in = delta.get("expires_in_minutes")
    if expires_in is not None:
        topic["expires_at"] = (now + timedelta(minutes=float(expires_in))).isoformat()
    else:
        topic["expires_at"] = (now + timedelta(hours=expire_hours)).isoformat()
    if evidence:
        topic.setdefault("evidence", [])
        topic["evidence"] = (topic["evidence"] + evidence)[-20:]
    return intent_state


def pressure_summary(intent_state: dict[str, Any], profile: dict[str, Any]) -> dict[str, Any]:
    policy = ((profile.get("proactive_policy") or {}).get("intent_accumulator") or {})
    threshold = float(policy.get("send_pressure_threshold", 2.0))
    topics = sorted(
        intent_state.get("topics", {}).values(),
        key=lambda item: float(item.get("score", 0)),
        reverse=True,
    )
    top = topics[0] if topics else None
    return {
        "threshold": threshold,
        "top_topic": top,
        "max_score": float(top.get("score", 0)) if top else 0,
        "near_threshold": bool(top and float(top.get("score", 0)) >= threshold * 0.75),
        "topics": topics[:5],
    }


def cooldown_status(intent_state: dict[str, Any], profile: dict[str, Any], message_class: str, now: datetime | None = None) -> dict[str, Any]:
    now = now or local_now(profile)
    policy = ((profile.get("proactive_policy") or {}).get("cooldowns") or {}).get("by_message_class", {})
    cfg = policy.get(message_class) or policy.get("normal_send") or {"min_gap_minutes": 180, "daily_cap": 3}
    own = _cooldown_bucket_status(intent_state, message_class, cfg, now)
    if not own.get("allowed"):
        return own
    if cfg.get("counts_toward_normal_send", False):
        normal_cfg = policy.get("normal_send") or {"min_gap_minutes": 180, "daily_cap": 3}
        aggregate = _cooldown_bucket_status(intent_state, "_normal_send_aggregate", normal_cfg, now)
        if not aggregate.get("allowed"):
            aggregate["message_class"] = message_class
            aggregate["aggregate_bucket"] = "_normal_send_aggregate"
            return aggregate
    return {"allowed": True, "reason": "ok", "message_class": message_class}


def _cooldown_bucket_status(intent_state: dict[str, Any], bucket: str, cfg: dict[str, Any], now: datetime) -> dict[str, Any]:
    counters = intent_state.setdefault("delivery_counters", {})
    cls_counter = counters.setdefault(bucket, {"events": []})
    events = [e for e in cls_counter.get("events", []) if e.get("day") == day_key(now)]
    cls_counter["events"] = events
    last = events[-1] if events else None
    min_gap = float(cfg.get("min_gap_minutes", 180))
    daily_cap = int(cfg.get("daily_cap", 3))
    if len(events) >= daily_cap:
        return {"allowed": False, "reason": "daily_cap", "message_class": bucket, "daily_cap": daily_cap}
    if last:
        last_at = _parse_time(last.get("created_at"))
        if last_at:
            age = (now - last_at).total_seconds() / 60
            if age < min_gap:
                return {"allowed": False, "reason": "min_gap", "message_class": bucket, "remaining_minutes": round(min_gap - age, 1)}
    return {"allowed": True, "reason": "ok", "message_class": bucket}


def record_delivery(intent_state: dict[str, Any], profile: dict[str, Any], message_class: str, delivery_event: dict[str, Any], now: datetime | None = None) -> dict[str, Any]:
    now = now or local_now(profile)
    counters = intent_state.setdefault("delivery_counters", {})
    event_record = {
        "day": day_key(now),
        "created_at": now.isoformat(),
        "delivery_event_id": delivery_event.get("delivery_event_id"),
    }
    cls_counter = counters.setdefault(message_class, {"events": []})
    cls_counter.setdefault("events", []).append(event_record)
    cooldowns = ((profile.get("proactive_policy") or {}).get("cooldowns") or {}).get("by_message_class", {})
    cfg = cooldowns.get(message_class) or cooldowns.get("normal_send") or {}
    if cfg.get("counts_toward_normal_send", False):
        aggregate = counters.setdefault("_normal_send_aggregate", {"events": []})
        aggregate.setdefault("events", []).append(event_record | {"source_message_class": message_class})
    policy = ((profile.get("proactive_policy") or {}).get("intent_accumulator") or {})
    if policy.get("clear_after_delivery", True):
        intent_state["topics"] = {}
    save_intent_state(intent_state)
    return intent_state


def load_and_decay(profile: dict[str, Any]) -> dict[str, Any]:
    state = load_intent_state()
    return decay_intents(state, profile)


def _parse_time(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value))
    except Exception:
        return None
