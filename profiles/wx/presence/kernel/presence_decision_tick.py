#!/usr/bin/env python3
"""Generic Decision LLM layer for Presence Kernel."""
from __future__ import annotations

import json
from typing import Any

from presence_common import append_jsonl, call_chat_completion, event, event_path, load_prompt, model_settings, parse_jsonish



def run_decision_layer(
    profile: dict[str, Any],
    tick_run_id: str,
    state: dict[str, Any],
    intent_summary: dict[str, Any],
    world_signals: list[dict[str, Any]],
    dry_run: bool = False,
) -> dict[str, Any]:
    decision_run_id = tick_run_id.replace("tick_", "decision_", 1)
    context = {
        "persona_config": {
            "manifest": profile.get("manifest", {}),
            "profile_metadata": profile.get("profile_metadata", {}),
            "identity_canon": profile.get("identity_canon", ""),
            "relationship": profile.get("relationship", {}),
            "proactive_policy": profile.get("proactive_policy", {}),
            "permission_policy": profile.get("permission_policy", {}),
            "delivery": profile.get("delivery", {}),
            "speech": (profile.get("delivery", {}) or {}).get("speech", {}),
            "voice_text": profile.get("voice_text", "")[:4000],
        },
        "current_state": state,
        "intent_pressure": intent_summary,
    }
    system_prompt = load_prompt(profile, "decision")
    settings = model_settings("decision", profile)
    user_prompt = json.dumps(context, ensure_ascii=False)
    content, latency_ms = call_chat_completion(
        base_url=settings["base_url"],
        api_key=settings["api_key"],
        model=settings["model"],
        temperature=settings["temperature"],
        max_tokens=settings["max_tokens"],
        timeout=settings["timeout"],
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )
    decision = parse_jsonish(content, {})
    if not isinstance(decision, dict):
        decision = {}
    decision = normalize_decision(decision, profile)
    decision["profile_id"] = profile["profile_id"]
    decision["decision_run_id"] = decision_run_id
    decision["used_inputs"] = {
        "state_run_id": state.get("state_run_id"),
        "world_signal_ids": [s.get("id") for s in world_signals[:8]],
        "intent_topic_keys": [t.get("topic_key") for t in intent_summary.get("topics", [])],
    }
    decision["_llm"] = {"model": settings["model"], "latency_ms": latency_ms}
    append_jsonl(
        event_path("decision-events.jsonl"),
        event(
            {
                "decision_run_id": decision_run_id,
                "tick_run_id": tick_run_id,
                "dry_run": dry_run,
                "prompt": {
                    "system": system_prompt,
                    "user": user_prompt,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                },
                "decision": decision,
            },
            profile,
            decision_run_id,
        ),
    )
    return decision


def normalize_decision(decision: dict[str, Any], profile: dict[str, Any] | None = None) -> dict[str, Any]:
    action = str(decision.get("action") or "silent").strip().lower()
    if action == "act":
        action = "send"
    if action not in {"silent", "hesitate", "send"}:
        action = "silent"
    msg_class = str(decision.get("message_class") or ("none" if action in {"silent", "hesitate"} else "normal_send")).strip()
    allowed_classes = {"none", "micro_send", "closure", "random_share", "care_timing", "normal_send", "media"}
    if msg_class not in allowed_classes:
        msg_class = "none" if action in {"silent", "hesitate"} else "normal_send"
    try:
        confidence = max(0.0, min(1.0, float(decision.get("confidence", 0))))
    except Exception:
        confidence = 0.0
    delta = decision.get("intent_delta") if isinstance(decision.get("intent_delta"), dict) else {}
    try:
        delta["delta"] = max(0.0, min(1.0, float(delta.get("delta", 0))))
    except Exception:
        delta["delta"] = 0.0
    return {
        "action": action,
        "message_class": msg_class,
        "confidence": confidence,
        "reply_pressure": str(decision.get("reply_pressure") or "low"),
        "reasoning_summary": str(decision.get("reasoning_summary") or decision.get("_thought_process") or "")[:1000],
        "reason": str(decision.get("reason") or "")[:240],
        "intent_delta": delta,
        "render_brief": normalize_render_brief(decision.get("render_brief")),
        "voice_design": normalize_voice_design(decision.get("voice_design"), action, msg_class, profile or {}),
        "planned_actions": decision.get("planned_actions") if isinstance(decision.get("planned_actions"), list) else [],
    }


def normalize_render_brief(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raw = {}
    entry_point = str(raw.get("entry_point") or "")[:500]
    emotional_baseline = str(raw.get("emotional_baseline") or raw.get("tone") or "")[:500]
    shape_constraint = str(raw.get("shape_constraint") or raw.get("message_shape") or "")[:500]
    avoid = raw.get("avoid") if isinstance(raw.get("avoid"), list) else []
    return {
        "entry_point": entry_point,
        "emotional_baseline": emotional_baseline,
        "shape_constraint": shape_constraint,
        "tone": emotional_baseline,
        "message_shape": shape_constraint,
        "avoid": [str(item)[:160] for item in avoid[:6]],
    }


def normalize_voice_design(raw: Any, action: str, message_class: str, profile: dict[str, Any]) -> dict[str, Any]:
    if isinstance(raw, str):
        raw = {"natural_language_control": raw}
    if not isinstance(raw, dict):
        raw = {}
    speech_cfg = ((profile.get("delivery") or {}).get("speech") or {})
    natural_control = str(
        raw.get("natural_language_control")
        or raw.get("prompt")
        or raw.get("description")
        or ""
    )[:1200].strip()
    enabled_raw = raw.get("enabled")
    requested_enabled = bool(enabled_raw) if enabled_raw is not None else False
    enabled = bool(action == "send" and requested_enabled and natural_control)
    tags = raw.get("assistant_style_tags")
    if not isinstance(tags, list):
        tags = raw.get("audio_tags") if isinstance(raw.get("audio_tags"), list) else []
    tag_policy = speech_cfg.get("audio_tag_policy") if isinstance(speech_cfg.get("audio_tag_policy"), dict) else {}
    allowed = {str(tag).strip() for tag in tag_policy.get("allowed", []) or []}
    max_tags = int(tag_policy.get("max_tags_per_message") or 2)
    clean_tags: list[str] = []
    for tag in tags if enabled else []:
        text = str(tag).strip()[:40]
        if not text:
            continue
        if allowed and text not in allowed:
            continue
        clean_tags.append(text)
        if len(clean_tags) >= max_tags:
            break
    audio_format = str(raw.get("audio_format") or "wav").strip().lower()
    if audio_format not in {"wav", "pcm16"}:
        audio_format = "wav"
    delivery_mode = str(raw.get("delivery_mode") or ("voice_note_candidate" if enabled else "text_only")).strip()
    if delivery_mode not in {"text_only", "voice_note_candidate", "voice_note_preferred"}:
        delivery_mode = "text_only"
    if not enabled:
        delivery_mode = "text_only"
    reason = str(raw.get("reason") or "")[:240]
    if action == "send" and requested_enabled and not natural_control:
        reason = reason or "voice_design enabled was requested but no natural_language_control was provided"
    return {
        "enabled": enabled,
        "model": str(raw.get("model") or speech_cfg.get("model") or "mimo-v2.5-tts-voicedesign"),
        "natural_language_control": natural_control if enabled else "",
        "prompt": natural_control if enabled else "",
        "assistant_style_tags": clean_tags,
        "audio_tags": clean_tags,
        "audio_format": audio_format,
        "delivery_mode": delivery_mode,
        "reason": reason,
    }
