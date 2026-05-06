#!/usr/bin/env python3
"""Generic State LLM layer for Presence Kernel."""
from __future__ import annotations

from typing import Any

from presence_common import (
    HERMES_HOME, append_jsonl, call_chat_completion, conversation_context, event, event_path,
    load_runtime_state, local_now, load_prompt, model_settings, parse_jsonish, read_text, save_runtime_state,
)



def run_state_layer(profile: dict[str, Any], tick_run_id: str, world_signals: list[dict[str, Any]], intent_summary: dict[str, Any], dry_run: bool = False) -> dict[str, Any]:
    now = local_now(profile)
    state_run_id = tick_run_id.replace("tick_", "state_", 1)
    previous = load_runtime_state()
    context = conversation_context(profile=profile)
    user = read_text(HERMES_HOME / "USER.md", "", limit=5000)
    memory = read_text(HERMES_HOME / "MEMORY.md", "", limit=8000)
    payload = {
        "persona_config": _profile_brief(profile) | {"memory_bindings": {"user": user, "memory": memory}},
        "current_time": {"local_time": now.isoformat(), "timezone": profile.get("timezone"), "time_basis": "real_local_time"},
        "world_signals": world_signals,
        "ledger_timeline": context.get("ledger_timeline") or context.get("timeline", []),
        "interaction_gap": context.get("interaction_gap", {}),
        "previous_state": previous,
    }
    system_prompt = load_prompt(profile, "state")
    settings = model_settings("state", profile)
    content, latency_ms = call_chat_completion(
        base_url=settings["base_url"],
        api_key=settings["api_key"],
        model=settings["model"],
        temperature=settings["temperature"],
        max_tokens=settings["max_tokens"],
        timeout=settings["timeout"],
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": __import__("json").dumps(payload, ensure_ascii=False)},
        ],
    )
    state = parse_jsonish(content, {})
    if not isinstance(state, dict):
        state = {}
    state.setdefault("schema_version", 1)
    state["profile_id"] = profile["profile_id"]
    state["state_run_id"] = state_run_id
    state.setdefault("updated_at", now.isoformat())
    if isinstance(state.get("mood"), dict):
        state["mood"] = str(state["mood"].get("label") or state["mood"].get("mood") or "unknown")
    state.setdefault("interaction_analysis", {"had_natural_closure": True, "unresolved_open_loops": []})
    state.setdefault("private_continuity_events", [])
    state.setdefault("usable_world_signals", world_signals[:8])
    state["_llm"] = {"model": settings["model"], "latency_ms": latency_ms}
    if not dry_run:
        save_runtime_state(state)
    append_jsonl(event_path("state-events.jsonl"), event({"state_run_id": state_run_id, "tick_run_id": tick_run_id, "dry_run": dry_run, "state": state}, profile, state_run_id))
    if state.get("private_continuity_events"):
        append_jsonl(
            event_path("continuity-events.jsonl"),
            event(
                {
                    "state_run_id": state_run_id,
                    "tick_run_id": tick_run_id,
                    "dry_run": dry_run,
                    "private_continuity_events": state.get("private_continuity_events", []),
                },
                profile,
                state_run_id,
            ),
        )
    return state


def _profile_brief(profile: dict[str, Any]) -> dict[str, Any]:
    return {
        "profile_id": profile["profile_id"],
        "manifest": profile.get("manifest", {}),
        "profile_metadata": profile.get("profile_metadata", {}),
        "identity_canon": profile.get("identity_canon", ""),
        "relationship": profile.get("relationship", {}),
        "voice_text": profile.get("voice_text", "")[:4000],
    }
