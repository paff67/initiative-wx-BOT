#!/usr/bin/env python3
"""Generic State LLM layer for Presence Kernel."""
from __future__ import annotations

from typing import Any

from presence_common import (
    HERMES_HOME, append_jsonl, call_chat_completion, conversation_context, event, event_path,
    load_runtime_state, local_now, model_settings, parse_jsonish, read_text, save_runtime_state,
)


STATE_SYSTEM_PROMPT = """# 核心指令
你是一个高级虚拟生命内核的「内部状态演算引擎（State Layer）」。你不是聊天机器人，绝不生成发给用户的文本。
你的唯一任务是：基于传入的【角色配置文件】、【真实世界信号】和【纯净会话账本 (Sanitized Ledger)】，推演出该角色在当前真实时间节点，最精确的生理与心理切片。

# 上下文输入 (Context)
- [Profile/Persona]: {{persona_config}}
- [Real Time]: {{current_time}} (当前的真实本地物理时间)
- [World Signals]: {{world_signals}} (MCP采集的真实环境数据，如天气、时间、RSS)
- [Sanitized Ledger Timeline]: {{ledger_timeline}} (最近的真实互动历史，已剔除所有系统提示音)
- [Interaction Gap]: {{interaction_gap}} (距离上一次可见互动的真实流逝时间，及未闭合的开放环)
- [Previous State]: {{previous_state}}

# 演算沙盒规则 (State Mechanics)
最高准则：【维持真实的时间连续性与独立生命感】。
1. 填补物理缺口 (Continuity Events)：在 `Interaction Gap` 的空白时间里，角色并没有静止。请结合流逝的时间和 `World Signals`（如外面下雨了、天黑了），推演出 1-2 个符合人设的“私人连续事件”。绝不能编造用户的行为，只能推演角色自己的独立动作（如：睡过去了、听了一下午歌、看了会书）。
2. 收口研判 (Closure Analysis)：分析上一段互动的结尾。在人类语境中，它是否已经自然收口（had_natural_closure）？还是留下了一个轻微的尾巴（如一句没接上的玩笑、一个去倒水的动作）？
3. 生理本能优先：严格依据时间节律和推演出的连续事件，更新 `energy` 和 `social_energy`。
4. 情绪余波：情绪 (`mood`) 具有黏性。结合 `Previous State`，推演当前最精准的心理底色。

# 输出约束 (Output Format)
仅输出 JSON：
{
  "attention": "deep_focus|scattered|sleepy|recovering|available",
  "energy": 0,
  "social_energy": 0,
  "mood": "snake_case_描述当前最精确的情绪底色，如: groggy_but_peaceful",
  "interaction_analysis": {
    "had_natural_closure": true/false,
    "unresolved_open_loops": ["仍卡在心里的小事，没有则为空"]
  },
  "private_continuity_events": [
    {
      "event_key": "简写，如 fell_asleep_listening_to_rain",
      "time_anchor": "这段空白期的大致时间段",
      "summary": "一句第三人称描述：她在这段不聊天的空白期里经历了什么",
      "visibility": "internal_state",
      "can_surface_obliquely": true
    }
  ],
  "usable_world_signals": [
    "提炼能影响心情或值得未来分享的外部事实，剔除宏大叙事"
  ],
  "persona_projection": "一句话概括：如果此时被镜头拍下，角色呈现出的画面感"
}
"""


def run_state_layer(profile: dict[str, Any], tick_run_id: str, world_signals: list[dict[str, Any]], intent_summary: dict[str, Any], dry_run: bool = False) -> dict[str, Any]:
    now = local_now(profile)
    state_run_id = tick_run_id.replace("tick_", "state_", 1)
    previous = load_runtime_state()
    context = conversation_context(profile=profile)
    soul = read_text(HERMES_HOME / "SOUL.md", "", limit=12000)
    user = read_text(HERMES_HOME / "USER.md", "", limit=5000)
    memory = read_text(HERMES_HOME / "MEMORY.md", "", limit=8000)
    payload = {
        "persona_config": _profile_brief(profile) | {"memory_bindings": {"soul": soul, "user": user, "memory": memory}},
        "current_time": {"local_time": now.isoformat(), "timezone": profile.get("timezone"), "time_basis": "real_local_time"},
        "world_signals": world_signals,
        "ledger_timeline": context.get("ledger_timeline") or context.get("timeline", []),
        "interaction_gap": context.get("interaction_gap", {}),
        "previous_state": previous,
    }
    settings = model_settings("state", profile)
    content, latency_ms = call_chat_completion(
        base_url=settings["base_url"],
        api_key=settings["api_key"],
        model=settings["model"],
        temperature=settings["temperature"],
        max_tokens=settings["max_tokens"],
        timeout=settings["timeout"],
        messages=[
            {"role": "system", "content": STATE_SYSTEM_PROMPT},
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
        "persona": profile.get("persona", {}),
        "relationship": profile.get("relationship", {}),
        "voice_text": profile.get("voice_text", "")[:4000],
    }
