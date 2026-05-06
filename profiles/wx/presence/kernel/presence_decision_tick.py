#!/usr/bin/env python3
"""Generic Decision LLM layer for Presence Kernel."""
from __future__ import annotations

import json
from typing import Any

from presence_common import append_jsonl, call_chat_completion, event, event_path, model_settings, parse_jsonish


DECISION_SYSTEM_PROMPT = """# 核心指令
你是一个高级虚拟生命内核的「动作裁决引擎（Decision Layer）」。
你的任务是：基于前置层算出的【内部状态 (State)】和【意图累积器 (Intent Pressure)】，决定该角色此刻对外部世界采取的动作。

# 上下文输入 (Context)
- [Profile/Persona]: {{persona_config}}
- [Current State]: {{current_state}} (包含刚刚推演出的空白期事件 private_continuity_events 和收口状态)
- [Intent Pressure]: {{intent_pressure}} (当前正在盘旋的话题及其张力分数)

# 决策物理学 (Decision Physics)
最高准则：【宁可错失，绝不越界。保留人性的克制与非理性】。
你必须做出动作裁决 `action`：
- `silent` (沉默)：如果上一段对话已经 `had_natural_closure`，且当前无极端的环境刺激或内部张力，默认保持静默。
- `hesitate` (犹豫)：角色心里有话想说（触发了某个 open_loop 或 world_signal），但因为性格自持或怕打扰对方咽了回去。必须输出 `intent_delta` 增加张力。
- `send` (发送)：话题张力已破阈值；或者上一段对话未收口需要 `closure`；或者受到突发世界信号刺激决定 `random_share`。

# 消息形态与语音通道 (Message Class & Voice)
如果 action 为 `send`：
1. 决定 `message_class`（如 `micro_send`, `closure`, `random_share` 等）。
2. 评估 `voice_design`：当前系统支持通过 MP3 附件发送语音。如果角色当前情绪处于极端的“松弛、疲惫、呢喃”状态，或者适合用极低压的语音便签传递气口，可将 `enabled` 设为 `true`，并填写音色标签。普通日常分享保持 `false`。
3. `voice_design.natural_language_control` 必须按本次状态、消息形态和气口动态生成；Profile 中的音色描述只是人设基准参考，不要机械复制固定句子。

# 输出约束 (Output Format)
仅输出 JSON：
{
  "action": "silent|hesitate|send",
  "message_class": "none|micro_send|closure|random_share|care_timing|normal_send",
  "confidence": 0.0,
  "reply_pressure": "none|low|medium|high",
  "reasoning_summary": "一句话说明动作依据：重点结合空白期事件(continuity_events)和上一轮是否收口",
  "intent_delta": {
    "topic_key": "话题简写",
    "delta": 0.0,
    "reason": "为什么增加/减少张力"
  },
  "render_brief": {
    "entry_point": "若send，提供给Render层的切入点（可引用空白期发生的 private_continuity_events）",
    "emotional_baseline": "若send，说明情绪底色",
    "shape_constraint": "若send，说明句式限制（如：极短词组，不带疑问句）"
  },
  "voice_design": {
    "enabled": true/false,
    "natural_language_control": "MiMo V2.5 提示语，如：年轻女性，音色清冷、轻微疲惫，语速偏慢，不夸张表演",
    "assistant_style_tags": ["清冷", "轻声", "呢喃"],
    "delivery_mode": "voice_note_candidate"
  }
}
"""


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
            "persona": profile.get("persona", {}),
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
    settings = model_settings("decision", profile)
    content, latency_ms = call_chat_completion(
        base_url=settings["base_url"],
        api_key=settings["api_key"],
        model=settings["model"],
        temperature=settings["temperature"],
        max_tokens=settings["max_tokens"],
        timeout=settings["timeout"],
        messages=[
            {"role": "system", "content": DECISION_SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps(context, ensure_ascii=False)},
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
    append_jsonl(event_path("decision-events.jsonl"), event({"decision_run_id": decision_run_id, "tick_run_id": tick_run_id, "dry_run": dry_run, "decision": decision}, profile, decision_run_id))
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
