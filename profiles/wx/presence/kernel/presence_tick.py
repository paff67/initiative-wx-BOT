#!/usr/bin/env python3
"""Single cron entrypoint for the generic Presence Kernel."""
from __future__ import annotations

import argparse
import json
import os
import random
from datetime import datetime, timedelta
from typing import Any

from presence_common import (
    append_jsonl, clamp, conversation_context, ensure_dirs, event, event_path,
    load_profile, load_profile_env, load_runtime_state, local_now, make_run_id,
    runtime_path, save_intent_state, write_json,
)
from presence_decision_tick import run_decision_layer
from presence_intent import apply_intent_delta, cooldown_status, decay_intents, load_and_decay, pressure_summary, record_delivery
from presence_render import cron_payload, render_decision
from presence_state_tick import run_state_layer
from presence_world_collector import collect_world_signals


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", default=os.environ.get("PRESENCE_PROFILE_ID"))
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force-llm", action="store_true")
    args = parser.parse_args()

    ensure_dirs()
    if not args.profile:
        raise SystemExit("presence_tick requires --profile or PRESENCE_PROFILE_ID")
    profile = load_profile(args.profile)
    load_profile_env(profile)
    now = local_now(profile)
    tick_run_id = make_run_id("tick", now)
    if args.dry_run:
        os.environ["PRESENCE_EVENT_STREAM"] = "preview"
        os.environ["PRESENCE_PREVIEW_RUN_ID"] = tick_run_id
    trace: dict[str, Any] = {"tick_run_id": tick_run_id, "profile_id": args.profile, "steps": [], "dry_run": args.dry_run}
    dry_run_snapshot = snapshot_runtime_for_dry_run() if args.dry_run else None

    world_signals, tool_calls = collect_world_signals(profile, tick_run_id, phase="prefilter")
    trace["steps"].append({"name": "world_collect", "signals": [s.get("id") for s in world_signals], "tool_calls": tool_calls})

    intent_state = load_and_decay(profile)
    if not args.dry_run:
        save_intent_state(intent_state)
    intent_summary = pressure_summary(intent_state, profile)
    append_jsonl(event_path("intent-events.jsonl"), event({"tick_run_id": tick_run_id, "phase": "decay", "intent_summary": intent_summary}, profile, tick_run_id))
    trace["steps"].append({"name": "intent_decay", "summary": intent_summary})

    prefilter = compute_stochastic_prefilter(profile, intent_summary, world_signals, args.force_llm)
    trace["steps"].append({"name": "stochastic_prefilter", "result": prefilter})
    append_jsonl(event_path("tick-events.jsonl"), event({"tick_run_id": tick_run_id, **prefilter}, profile, tick_run_id))
    if prefilter.get("skip"):
        write_trace(profile, trace, args.dry_run)
        append_jsonl(event_path("trace-events.jsonl"), event(trace | {"final": "stochastic_skip_before_llm"}, profile, tick_run_id))
        out = {
            "wakeAgent": False,
            "context": {
                "profile_id": args.profile,
                "tick_run_id": tick_run_id,
                "skip_reason": "stochastic_skip_before_llm",
                "prefilter": prefilter,
            },
        }
        restore_runtime_for_dry_run(dry_run_snapshot)
        print(json.dumps(out, ensure_ascii=False))
        return

    try:
        post_signals, post_tool_calls = collect_world_signals(profile, tick_run_id, phase="post_prefilter")
        if post_signals or post_tool_calls:
            world_signals.extend(post_signals)
            tool_calls.extend(post_tool_calls)
            trace["steps"].append({"name": "world_collect_post_prefilter", "signals": [s.get("id") for s in post_signals], "tool_calls": post_tool_calls})

        state = run_state_layer(profile, tick_run_id, world_signals, intent_summary, dry_run=args.dry_run)
        trace["steps"].append({"name": "state", "state_run_id": state.get("state_run_id")})

        decision = run_decision_layer(profile, tick_run_id, state, intent_summary, world_signals, dry_run=args.dry_run)
        trace["steps"].append({"name": "decision", "decision_run_id": decision.get("decision_run_id"), "action": decision.get("action")})

        evidence = [{"type": "decision", "id": decision.get("decision_run_id")}]
        intent_state = apply_intent_delta(intent_state, profile, decision.get("intent_delta"), evidence=evidence)
        if not args.dry_run:
            save_intent_state(intent_state)
        updated_intent_summary = pressure_summary(intent_state, profile)
        append_jsonl(event_path("intent-events.jsonl"), event({"tick_run_id": tick_run_id, "phase": "update", "intent_delta": decision.get("intent_delta"), "intent_summary": updated_intent_summary}, profile, tick_run_id))
        trace["steps"].append({"name": "intent_update", "intent_delta": decision.get("intent_delta"), "summary": updated_intent_summary})

        if decision.get("action") in {"send", "act"}:
            cd = cooldown_status(intent_state, profile, decision.get("message_class") or "normal_send")
            trace["steps"].append({"name": "cooldown", "result": cd})
            if not cd.get("allowed"):
                decision["action"] = "silent"
                decision["cooldown_block"] = cd
                decision["reason"] = f"cooldown blocked: {cd.get('reason')}"

        render = render_decision(profile, tick_run_id, decision, state, dry_run=args.dry_run)
        trace["steps"].append({"name": "render", "render_run_id": render.get("render_run_id"), "type": render.get("type")})

        if render.get("would_deliver"):
            delivery_event = {"delivery_event_id": tick_run_id.replace("tick_", "delivery_", 1), "message_class": decision.get("message_class"), "render_run_id": render.get("render_run_id")}
            record_delivery(intent_state, profile, decision.get("message_class") or "normal_send", delivery_event)
            append_jsonl(event_path("delivery-events.jsonl"), event(delivery_event | {"render": render}, profile, delivery_event["delivery_event_id"]))
    except Exception as exc:
        decision = {"action": "silent", "message_class": "none", "reason": "presence kernel error"}
        state = load_runtime_state()
        render = {"type": "silent", "text": "", "would_deliver": False, "reason": "presence_kernel_error"}
        trace["error"] = str(exc)[:1200]
        append_jsonl(event_path("trace-events.jsonl"), event(trace | {"final": "presence_kernel_error"}, profile, tick_run_id))
        write_trace(profile, trace, args.dry_run)
        restore_runtime_for_dry_run(dry_run_snapshot)
        print(json.dumps({"wakeAgent": False, "context": {"profile_id": args.profile, "tick_run_id": tick_run_id, "skip_reason": "presence_kernel_error", "error": str(exc)[:500]}}, ensure_ascii=False))
        return

    trace["render"] = render
    trace["decision"] = decision
    write_trace(profile, trace, args.dry_run)
    append_jsonl(event_path("trace-events.jsonl"), event(trace, profile, tick_run_id))

    payload = cron_payload(render, {"profile_id": args.profile, "tick_run_id": tick_run_id, "decision": decision, "state": state})
    if args.dry_run:
        payload["wakeAgent"] = False
        payload["context"]["dry_run"] = True
    restore_runtime_for_dry_run(dry_run_snapshot)
    print(json.dumps(payload, ensure_ascii=False))


def compute_stochastic_prefilter(profile: dict[str, Any], intent_summary: dict[str, Any], world_signals: list[dict[str, Any]], force_llm: bool = False) -> dict[str, Any]:
    now = local_now(profile)
    policy = ((profile.get("proactive_policy") or {}).get("cadence") or {}).get("stochastic_prefilter", {})
    if force_llm or not policy.get("enabled", True):
        return {"skip": False, "reason": "forced_or_disabled", "probability": 1.0, "rolled": 0.0}

    runtime_state = load_runtime_state()
    updated_at = runtime_state.get("updated_at") or runtime_state.get("state", {}).get("updated_at")
    state_age = _age_minutes(updated_at, now)
    force_age = float(policy.get("force_llm_after_state_age_minutes", 180))
    if state_age is None or state_age >= force_age:
        return {"skip": False, "reason": "state_age_force_llm", "probability": 1.0, "rolled": 0.0, "state_age_minutes": state_age}

    base = float(policy.get("base_wake_probability", 0.22))
    probability = base
    activity = conversation_context(profile=profile).get("activity", {})
    if activity.get("is_recently_active"):
        probability *= 0.4
    usable_signals = [
        signal for signal in world_signals
        if signal.get("kind") != "time" and signal.get("policy_decision") == "auto_allow"
    ]
    if usable_signals:
        probability += min(0.2, 0.05 * len(usable_signals))
    threshold = float(intent_summary.get("threshold") or 2.0)
    if float(intent_summary.get("max_score") or 0) >= threshold * 0.75:
        probability += 0.15
    probability = clamp(probability, float(policy.get("min_probability", 0.04)), float(policy.get("max_probability", 0.65)))
    rolled = random.random()
    jitter = policy.get("jitter_not_before_minutes", {}) or {}
    next_not_before = now + timedelta(minutes=random.randint(int(jitter.get("min", 12)), int(jitter.get("max", 45))))
    return {
        "skip": rolled > probability,
        "reason": "stochastic_skip_before_llm" if rolled > probability else "stochastic_pass",
        "probability": round(probability, 4),
        "rolled": round(rolled, 4),
        "next_decision_not_before": next_not_before.isoformat(),
        "state_age_minutes": state_age,
        "usable_world_signal_count": len(usable_signals),
    }


def _age_minutes(value: Any, now) -> float | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value))
        if dt.tzinfo is None and getattr(now, "tzinfo", None) is not None:
            dt = dt.replace(tzinfo=now.tzinfo)
        return round((now - dt).total_seconds() / 60, 1)
    except Exception:
        return None


def write_trace(profile: dict[str, Any], trace: dict[str, Any], dry_run: bool) -> None:
    name = "preview-last-trace.json" if dry_run else "last-trace.json"
    write_json(runtime_path(name), event(dict(trace), profile, trace.get("tick_run_id")))


def snapshot_runtime_for_dry_run() -> dict[str, tuple[bool, str]]:
    snapshot: dict[str, tuple[bool, str]] = {}
    for name in ("state.json", "intent-state.json", "last-trace.json"):
        path = runtime_path(name)
        snapshot[name] = (path.exists(), path.read_text(encoding="utf-8") if path.exists() else "")
    return snapshot


def restore_runtime_for_dry_run(snapshot: dict[str, tuple[bool, str]] | None) -> None:
    if not snapshot:
        return
    for name, (existed, content) in snapshot.items():
        path = runtime_path(name)
        if existed:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        elif path.exists():
            path.unlink()


if __name__ == "__main__":
    main()
