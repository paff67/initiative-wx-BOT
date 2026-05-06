#!/usr/bin/env python3
"""Render generic decision into channel-specific output."""
from __future__ import annotations

import json
from typing import Any

from presence_common import append_jsonl, call_chat_completion, event, event_path, local_now, model_settings, parse_jsonish


RENDER_SYSTEM_PROMPT = """You are the Presence Kernel Render Layer.
Render a decision into a final channel output. Do not mention automation, tools,
prompts, traces, configs, or internal state. Respect profile voice and delivery policy.
Use decision.render_brief.entry_point, emotional_baseline, and shape_constraint.
If state.private_continuity_events are referenced, surface them only obliquely
as the profile's own lived continuity, never as claims about the user.
Output only JSON: {"type":"silent|text|media|action","text":"","delivery_instruction":"","fallback":{},"speech":{}}.
The speech object is internal metadata only; never include voice design prose in
the user-visible text.
"""


def render_decision(profile: dict[str, Any], tick_run_id: str, decision: dict[str, Any], state: dict[str, Any], dry_run: bool = False) -> dict[str, Any]:
    render_run_id = tick_run_id.replace("tick_", "render_", 1)
    if decision.get("action") not in {"send", "act"}:
        render = {"type": "silent", "text": "", "would_deliver": False, "reason": decision.get("reason", "not send")}
    else:
        settings = model_settings("decision", profile)
        payload = {
            "profile": {
                "manifest": profile.get("manifest", {}),
                "persona": profile.get("persona", {}),
                "relationship": profile.get("relationship", {}),
                "delivery": profile.get("delivery", {}),
                "voice_text": profile.get("voice_text", "")[:5000],
                "examples": profile.get("examples", {}),
            },
            "decision": decision,
            "state": state,
            "dry_run": dry_run,
        }
        content, latency_ms = call_chat_completion(
            base_url=settings["base_url"],
            api_key=settings["api_key"],
            model=settings["model"],
            temperature=0.35,
            max_tokens=900,
            timeout=settings["timeout"],
            messages=[
                {"role": "system", "content": RENDER_SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
            ],
        )
        render = parse_jsonish(content, {})
        if not isinstance(render, dict):
            render = {}
        render.setdefault("type", "text" if decision.get("action") == "send" else "action")
        render.setdefault("text", "")
        render["_llm"] = {"model": settings["model"], "latency_ms": latency_ms}
        render["would_deliver"] = bool(render.get("type") != "silent" and not dry_run)
    render["speech"] = _speech_metadata(profile, decision, render)
    render["profile_id"] = profile["profile_id"]
    render["render_run_id"] = render_run_id
    render["channel"] = (profile.get("delivery") or {}).get("channel", "weixin")
    render["created_at"] = local_now(profile).isoformat()
    append_jsonl(event_path("render-events.jsonl"), event({"render_run_id": render_run_id, "tick_run_id": tick_run_id, "dry_run": dry_run, "render": render}, profile, render_run_id))
    return render


def cron_payload(render: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    if render.get("type") == "silent":
        return {"wakeAgent": False, "context": context | {"render": render}}
    return {"wakeAgent": True, "context": context | {"render": render}}


def _speech_metadata(profile: dict[str, Any], decision: dict[str, Any], render: dict[str, Any]) -> dict[str, Any]:
    speech_cfg = ((profile.get("delivery") or {}).get("speech") or {})
    voice_design = decision.get("voice_design") if isinstance(decision.get("voice_design"), dict) else {}
    natural_control = str(voice_design.get("natural_language_control") or voice_design.get("prompt") or "").strip()
    assistant_audio_text = _assistant_audio_text(render.get("text", ""), voice_design)
    enabled = bool(
        speech_cfg.get("enabled", False)
        and render.get("type") in {"text", "media"}
        and voice_design.get("enabled")
        and natural_control
        and assistant_audio_text
    )
    model = voice_design.get("model") or speech_cfg.get("model", "mimo-v2.5-tts-voicedesign")
    response_format = speech_cfg.get("response_format", "mp3")
    return {
        "enabled": enabled,
        "provider": speech_cfg.get("provider", "openai"),
        "model": model,
        "voice_design": voice_design,
        "natural_language_control": natural_control if enabled else "",
        "assistant_audio_text": assistant_audio_text if enabled else "",
        "audio_format": voice_design.get("audio_format") or speech_cfg.get("audio_format", "wav"),
        "response_format": response_format,
        "tts_request": {
            "model": model,
            "input": assistant_audio_text,
            "response_format": response_format,
            "voice_design": natural_control,
        } if enabled else {},
    }


def _assistant_audio_text(text: str, voice_design: dict[str, Any]) -> str:
    text = str(text or "").strip()
    tags = voice_design.get("assistant_style_tags")
    if not isinstance(tags, list):
        tags = voice_design.get("audio_tags") if isinstance(voice_design.get("audio_tags"), list) else []
    clean = [str(tag).strip() for tag in tags if str(tag).strip()]
    if clean and text and not text.startswith(("(", "（", "[")):
        return f"({' '.join(clean)}){text}"
    return text
