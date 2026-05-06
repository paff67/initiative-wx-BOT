# 通用主动心跳系统一步到位方案评估

生成时间：2026-05-05

评估对象：从当前 wx / 林绛主动心跳实现，升级为人设解耦、配置驱动、具备真实世界交互和 Observer 全链路审计能力的通用 Proactive Presence System。

评估依据：当前生产代码、wx profile 配置、Hermes 本地随代码文档、Hermes 官方线上文档，以及现有 Observer 代码。

## 0. 总结

最终方向应当不是继续给“林绛”打补丁，而是抽出一个通用的主动心跳内核：

```text
Proactive Presence Kernel
  不绑定某个角色
  不硬编码某个人设
  不人为限制 Hermes runtime permissions
  通过 profile / persona / relationship / policy 配置注入个性
  通过 Observer 查看、编辑、预览、回放完整链路
```

林绛只是第一个 profile instance。后续任何人设、任何关系模式、任何投递渠道，都应该通过配置文件接入同一套内核。

核心判断：

1. 当前 State / Decision / Final Gate 的分层是有价值的，但命名、字段、prompt 和 Observer 都太林绛专属。
2. 一步到位方案应重构为通用 `presence-kernel`，而不是继续叠加 `linjiang-*` 文件。
3. 个性化内容应从代码和 prompt 中剥离，放入 profile 配置包。
4. Hermes 的 web / browser / MCP / skills / cron / gateway 能力应完整进入系统，不在主动心跳层做硬权限阉割。
5. Observer 不应是单纯监控面板，而应成为配置编辑器、链路审计器、dry-run 预览器和运行回放器。

一句话结论：要做的不是“让林绛更主动”，而是做一个通用的主动存在系统；林绛的人格、语气、关系边界和微信投递只是这个系统的一组配置。

## 1. 现状边界

当前实现仍然强绑定 wx / 林绛：

- State tick：`/home/hermes/.hermes/profiles/wx/wx-linjiang-state-tick.py`
- State prompt：`/home/hermes/.hermes/profiles/wx/wx-linjiang-state-prompt.md`
- State output：`/home/hermes/.hermes/profiles/wx/linjiang-internal-state.json`
- Decision script：`/home/hermes/.hermes/profiles/wx/wx-proactive-heartbeat.py`
- Decision prompt：`/home/hermes/.hermes/profiles/wx/wx-proactive-decision-prompt.md`
- Delivery prompt：`/home/hermes/.hermes/profiles/wx/wx-hourly-proactive-cron-prompt.txt`
- Decision log：`/home/hermes/.hermes/profiles/wx/decision-events.jsonl`
- Runtime state：`/home/hermes/.hermes/profiles/wx/proactive_heartbeat_state.json`

现有 Observer 也强绑定这套路径：

- Backend config：`/home/hermes/hermes-observer/backend/app/config.py`
- Backend API：`/home/hermes/hermes-observer/backend/app/routers/api.py`
- Frontend tabs：`/home/hermes/hermes-observer/frontend/src/App.tsx`

当前 Hermes 能力基础是足够的：

- Cron 支持 interval、cron expression、one-shot、script context 和 delivery。
- MCP 支持 stdio / HTTP server、工具自动发现、per-server tool filtering、动态工具发现。
- Hermes toolsets 支持 web search、browser、file、memory、skills、gateway 等能力。
- Observer 已有 health、state、decisions、control、feedback、prompt editor、proxy monitor 的基础形态。

必须先修的实际投递问题仍然成立：

```yaml
cron:
  wrap_response: true
```

wx profile 当前这个配置会让主动消息带上 `Cronjob Response` 包装。通用内核应把 delivery profile 的默认值设为：

```yaml
cron:
  wrap_response: false
```

参考代码：

- [scheduler.py](/home/hermes/.hermes/hermes-agent/cron/scheduler.py:355)
- [scheduler.py](/home/hermes/.hermes/hermes-agent/cron/scheduler.py:365)

## 2. 一步到位目标架构

推荐一次性实现为 `presence-kernel`，由多个配置文件驱动：

```text
Presence Kernel
  Scheduler Layer
    cron / stochastic wakeup / dynamic wake hints

  World Layer
    web / browser / MCP / skills / local scripts / gateway context

  Timeline Layer
    conversation timeline / session search / recent delivery / world events

  State Layer
    persona-neutral internal state schema

  Intent Layer
    open loops / hesitation accumulator / topic pressure / wake hints

  Decision Layer
    silent / hesitate / send / act / multimodal

  Render Layer
    persona voice renderer / delivery-channel renderer / final guard

  Delivery & Action Layer
    text / media / gateway delivery / Hermes tools / MCP actions

  Observer Layer
    config edit / preview / audit / replay / override / trace search
```

建议目录形态：

```text
.hermes/profiles/wx/
  presence/
    kernel/
      presence_state_tick.py
      presence_decision_tick.py
      presence_world_collector.py
      presence_render_prompt.md
      presence_state_prompt.md
      presence_decision_prompt.md
      schemas/
        presence_profile.schema.json
        world_signal.schema.json
        decision_event.schema.json
        preview_request.schema.json
    profiles/
      linjiang/
        persona.yaml
        voice.md
        relationship.yaml
        memory_bindings.yaml
        proactive_policy.yaml
        world_policy.yaml
        delivery_weixin.yaml
        examples.yaml
    runtime/
      state.json
      intent-state.json
      world-signal-state.json
      control.json
    events/
      state-events.jsonl
      decision-events.jsonl
      world-signal-events.jsonl
      delivery-events.jsonl
      trace-events.jsonl
```

兼容迁移期可以保留旧文件名，但新代码不应继续写死 `linjiang`。

## 3. 配置驱动的人设注入

个性化不进核心代码。核心只认识通用字段，具体人设通过 profile 注入。

### 3.1 Profile Manifest

```yaml
profile_id: linjiang
display_name: 林绛
version: 1
channel: weixin
locale: zh-CN
timezone: Asia/Shanghai

persona_files:
  soul: SOUL.md
  voice: presence/profiles/linjiang/voice.md
  relationship: presence/profiles/linjiang/relationship.yaml
  proactive_policy: presence/profiles/linjiang/proactive_policy.yaml
  world_policy: presence/profiles/linjiang/world_policy.yaml
  delivery: presence/profiles/linjiang/delivery_weixin.yaml

memory_bindings:
  user: USER.md
  memory: MEMORY.md
  session_db: state.db
```

### 3.2 Persona Config

```yaml
identity:
  name: 林绛
  role: intimate_companion
  language: zh-CN

voice:
  temperature_style: cold_soft
  brevity: high
  directness: medium
  humor: dry
  avoids:
    - 解释系统
    - 客服腔
    - 过度撒娇
    - 编造共同物理空间

relationship:
  default_distance: close_but_self-contained
  reply_pressure: low
  asks_for_immediate_reply: false

proactive_style:
  can_micro_send_when_low_energy: true
  closure_messages: true
  random_shares: true
  world_signal_shares: true
```

### 3.3 Policy Config

策略是配置，不是人设代码：

```yaml
cadence:
  schedule: "every 15m"
  stochastic_gate: true
  min_send_gap_minutes: 180
  daily_send_soft_cap: 3
  micro_send_daily_cap: 1

decision:
  min_send_confidence: 0.55
  allow_hesitate: true
  allow_action: true
  allow_media: true

permissions:
  mode: full_runtime
  inherit_hermes_profile_tools: true
  mcp_servers: "*"
  toolsets: "*"
  action_execution: enabled

observer:
  log_every_tool_call: true
  log_prompt_context_digest: true
  log_render_preview: true
  allow_config_edit: true
  allow_dry_run_preview: true
```

这里的重点是：主动系统不做硬编码权限限制。它继承 Hermes profile 的 runtime permissions，并把每次调用、判断和投递完整记录下来。是否启用某些 MCP server、toolset 或 action 能力，由 Hermes profile / MCP config / persona policy 决定，而不是写死在林绛脚本里。

## 4. 真实世界交互层

真实世界交互应是通用 World Layer，而不是“虚拟微环境”。

World Collector 默认运行，读取当前 profile 允许的全部 Hermes 能力：

- web search
- browser automation
- MCP servers
- skills
- local scripts
- gateway/session context
- external APIs
- smart home / calendar / email / music / map 等工具

信号 schema：

```json
{
  "id": "ws_20260505_1732_weather_001",
  "profile_id": "linjiang",
  "run_id": "world_20260505_173200",
  "kind": "weather|calendar|email|music|browser|smart_home|custom_mcp|local_device|news",
  "source": {
    "type": "web|browser|mcp|skill|script|gateway",
    "name": "mcp_weather_get_forecast",
    "query": "current rain near configured city",
    "url": "https://example.source/item"
  },
  "raw_summary": "source-returned summary, never injected verbatim into final render",
  "normalized_fact": "未来 30 分钟可能下雨",
  "fetched_at": "2026-05-05T17:32:00+08:00",
  "expires_at": "2026-05-05T18:10:00+08:00",
  "confidence": 0.82,
  "sensitivity": "public|personal|user_adjacent|private|actionful",
  "policy_decision": "auto_allow|manual_required|blocked",
  "allowed_use": "internal_only|mood_only|may_share_obliquely|may_cite_directly|may_execute",
  "operator_review": "unreviewed|reviewed|redacted|blocked",
  "trace": {
    "tool_calls": ["mcp_weather_get_forecast"],
    "state_run_id": null,
    "decision_run_id": null,
    "render_run_id": null,
    "delivery_event_id": null
  }
}
```

默认策略应改成这样：

| 等级 | 例子 | 默认运行策略 | 默认表达/执行策略 |
| --- | --- | --- | --- |
| public read-only | 天气、公开新闻、节气、公开演出信息 | 自动采集、入库、进入 State / Decision | 可含蓄分享 |
| personal read-only | 日历、邮件摘要、位置、设备状态 | 自动采集、入库、进入 State / Decision | 按 profile 策略表达，默认不暴露工具来源 |
| user-adjacent | 用户行程、住址附近天气、聊天对象状态 | 自动采集、入库、主要影响时机 | 不说“我看到你...”，转译成低压关怀 |
| actionful | 发邮件、改日历、控制智能家居、下单 | 允许进入 Action Planner | 是否自动执行由 profile policy 决定，全链路留痕 |

这里不再写“actionful 必须人工批准”。通用系统不限制运行权限。它只做三件事：

1. 读取 Hermes profile 暴露给它的能力。
2. 按配置决定是否执行、预览、延迟或仅记录 proposal。
3. 把完整调用链路交给 Observer 查看和纠偏。

## 5. 通用 State / Intent / Decision

State schema 必须去人设化：

```json
{
  "profile_id": "linjiang",
  "state_run_id": "state_20260505_170000",
  "time": {
    "now": "2026-05-05T17:00:00+08:00",
    "timezone": "Asia/Shanghai"
  },
  "attention": "available|focused|sleepy|recovering|offline|unknown",
  "energy": 0,
  "social_energy": 0,
  "mood": {
    "label": "drowsy_softened",
    "valence": 0.2,
    "arousal": 0.1
  },
  "open_loops": [],
  "usable_world_signals": [],
  "private_micro_events": [],
  "soft_wake_hints": [],
  "persona_projection": {
    "voice_brief": "render layer should inject this, not core logic"
  }
}
```

Intent state 通用化：

```json
{
  "profile_id": "linjiang",
  "hesitation_accumulator": {
    "topic_key": {
      "seed": "想补一句汤喝了",
      "score": 1.4,
      "first_seen": "2026-05-05T15:05:00+08:00",
      "last_seen": "2026-05-05T17:05:00+08:00",
      "evidence": [
        {"type": "state_open_loop", "id": "loop_hot_soup"},
        {"type": "world_signal", "id": "ws_weather_001"}
      ],
      "expires_at": "2026-05-05T23:00:00+08:00"
    }
  },
  "next_decision_not_before": "2026-05-05T17:31:00+08:00",
  "delivery_counters": {}
}
```

Decision output 通用化：

```json
{
  "profile_id": "linjiang",
  "decision_run_id": "decision_20260505_173200",
  "action": "silent|hesitate|send|act",
  "message_class": "none|micro_send|closure|random_share|care_timing|normal_send|media|tool_action",
  "confidence": 0.72,
  "reply_pressure": "none|low|medium|high",
  "reasoning_summary": "brief audit-safe explanation",
  "used_inputs": {
    "state_run_id": "state_20260505_170000",
    "world_signal_ids": ["ws_20260505_1732_weather_001"],
    "intent_topic_keys": ["hot_soup_closure"]
  },
  "render_brief": {
    "voice_profile": "linjiang",
    "tone": "sleepy, restrained",
    "message_shape": "one short fragment",
    "avoid": ["tool/source mention", "asking for reply"]
  },
  "planned_actions": []
}
```

## 6. Render 与 Delivery 解耦

Final Gate 不应承担决策，也不应发明动作协议。它只做渲染：

```text
Render input:
  decision output
  persona voice config
  delivery channel config
  recent conversation style
  world signal redaction policy

Render output:
  text message
  media reference
  action call envelope
  or [SILENT]
```

微信只是一个 delivery adapter：

```yaml
delivery:
  channel: weixin
  wrap_response: false
  max_text_chars: 80
  supports:
    text: true
    media: true
    typing: adapter_dependent
    native_sticker: adapter_dependent
    nudge: adapter_dependent
```

如果 Hermes / Weixin adapter 暂时不支持 native nudge，内核也不应该把 `[ACTION: NUDGE]` 当文本发出去。正确做法是输出结构化 action envelope，由 delivery layer 判断：

```json
{
  "type": "action",
  "action": "nudge",
  "fallback": {
    "type": "silent"
  }
}
```

## 7. 权限模型：不在心跳层硬限制

用户的要求是“不限制它的运行权限”。因此通用系统的权限原则应是：

1. Presence Kernel 不硬编码禁用某类工具。
2. Kernel 继承 Hermes profile 当前可用的 tools、toolsets、MCP servers、skills 和 gateway 能力。
3. 是否允许自动执行 actionful tool，由 profile policy 决定。
4. Observer 记录每次工具选择、参数摘要、返回摘要、模型判断、执行结果。
5. 可以配置 dry-run、preview、human-confirm，但它们是 policy 选项，不是核心限制。

建议配置：

```yaml
permissions:
  mode: full_runtime
  inherit_hermes_tools: true
  inherit_mcp_servers: true
  inherit_skills: true
  action_execution:
    default: enabled
    dry_run: false
    require_confirmation_for: []
  observability:
    log_tool_args: summarized
    log_tool_results: summarized
    redact_secrets: true
    trace_retention_days: 30
```

风险缓解不靠“不能做”，而靠：

- profile-level policy
- Hermes 自身权限和 MCP 配置
- secret redaction
- trace replay
- kill switch
- post-hoc blocklist
- preview / dry-run 可选开关

## 8. Observer 应升级为控制台

Observer 不只是看状态。它应该支持四类能力。

### 8.1 配置编辑

可编辑配置：

- profile manifest
- persona / voice
- relationship policy
- proactive cadence
- world policy
- permission policy
- delivery channel config
- render examples
- prompt templates

API 建议：

```text
GET  /api/profiles
GET  /api/profiles/{profile_id}/config
POST /api/profiles/{profile_id}/config
GET  /api/profiles/{profile_id}/files/{kind}
POST /api/profiles/{profile_id}/files/{kind}
POST /api/profiles/{profile_id}/validate
```

写入必须有：

- sha256 / revision 冲突检测
- diff preview
- 自动备份
- schema validation
- rollback

现有 prompt editor 可以泛化成 profile config editor。

### 8.2 最终效果预览

这是一步到位方案的关键。Observer 应支持“改配置后预览最终微信效果”，而不是只能等下一次 cron。

Preview pipeline：

```text
选择 profile
选择输入场景
选择 world signal / conversation fixture
运行 State preview
运行 Decision preview
运行 Render preview
显示最终用户可见消息
显示 full trace
不投递
```

API 建议：

```text
POST /api/preview/state
POST /api/preview/decision
POST /api/preview/render
POST /api/preview/full
```

Preview request：

```json
{
  "profile_id": "linjiang",
  "mode": "full",
  "dry_run": true,
  "fixtures": {
    "conversation": "latest|custom",
    "state": "latest|custom",
    "world_signals": "latest|custom",
    "intent_state": "latest|custom"
  },
  "config_overrides": {
    "voice.brevity": "high"
  }
}
```

Preview response：

```json
{
  "state_preview": {},
  "decision_preview": {},
  "render_preview": {
    "channel": "weixin",
    "text": "一会儿可能下雨，别硬撑。",
    "would_deliver": true
  },
  "trace": {
    "prompts": [],
    "tool_calls": [],
    "used_config_files": [],
    "used_world_signals": []
  }
}
```

### 8.3 链路审计

Observer 应能从任意最终消息反查：

```text
delivery event
  -> render run
  -> decision run
  -> state run
  -> intent state
  -> world signals
  -> tool calls / MCP calls / browser actions
  -> config version
  -> prompt version
```

必须展示：

- 每一步输入摘要
- 每一步输出摘要
- 模型名和 base_url
- token / latency / status
- tool call 参数摘要
- tool result 摘要
- redaction 结果
- 最终用户可见内容

### 8.4 操作回放与纠偏

Observer 应支持：

- replay 某次 decision
- replay 某次 render
- 用新配置重跑历史 fixture
- 标记某次输出“好 / 坏 / 太多 / 太少 / 越界”
- 将反馈写回 profile examples 或 operator feedback
- block 某类 signal
- 调整 policy 后预览差异

## 9. 一步到位实施范围

这不是分阶段补丁，而是一轮目标架构实现。建议一次性交付以下范围：

1. 通用目录与配置 schema
   - `presence/kernel`
   - `presence/profiles/{profile_id}`
   - `presence/runtime`
   - `presence/events`

2. 通用运行脚本
   - `presence_world_collector.py`
   - `presence_state_tick.py`
   - `presence_decision_tick.py`
   - `presence_render.py`
   - 旧 `wx-linjiang-*` 只作为 wrapper 或迁移入口。

3. 通用事件与 trace
   - `world-signal-events.jsonl`
   - `state-events.jsonl`
   - `decision-events.jsonl`
   - `render-events.jsonl`
   - `delivery-events.jsonl`
   - `trace-events.jsonl`

4. 权限继承
   - 继承 Hermes 当前 profile 能力。
   - 不在内核硬编码禁用 MCP / skills / browser / action tools。
   - 通过配置决定 dry-run、auto-execute、preview-only。

5. Observer 控制台
   - profile selector
   - config editor
   - schema validation
   - diff / backup / rollback
   - preview final message
   - trace replay
   - world signal view
   - decision graph
   - delivery audit

6. 林绛迁移为配置实例
   - 把当前 SOUL / USER / MEMORY / prompt 里的林绛特定内容拆进 `presence/profiles/linjiang/`。
   - 通用 prompt 只描述任务和 schema。
   - voice / relationship / examples 由 profile 注入。

7. Cron 与 delivery
   - schedule 改为 `every 15m` 或 `*/15 * * * *`。
   - stochastic gate 是通用能力。
   - `cron.wrap_response: false`。
   - delivery prompt 使用通用 render output，不含林绛硬编码。

## 10. 迁移策略

为了不打断当前系统，可以采用兼容迁移：

```text
旧 wx-linjiang-state-tick.py
  -> 调用 presence_state_tick.py --profile linjiang

旧 wx-proactive-heartbeat.py
  -> 调用 presence_decision_tick.py --profile linjiang

旧 wx-hourly-proactive-cron-prompt.txt
  -> 逐步替换为 presence_render_prompt.md + profile voice config
```

迁移后的林绛 profile：

```text
presence/profiles/linjiang/
  persona.yaml
  voice.md
  relationship.yaml
  proactive_policy.yaml
  world_policy.yaml
  permission_policy.yaml
  delivery_weixin.yaml
  examples.yaml
```

这样“林绛”不再是系统结构，而只是一个 profile。

## 11. 关键验收标准

通用性验收：

- 新建另一个 profile，不改 Python 代码，只改配置，即可跑完整 State / Decision / Render / Delivery。
- Observer 可以在 profile 间切换。
- 事件文件包含 `profile_id`。

权限验收：

- Presence Kernel 能看到 Hermes profile 暴露的 web / browser / MCP / skills。
- actionful tool 是否自动执行由配置决定，而不是内核硬限制。
- 每次工具调用都有 trace。

预览验收：

- 修改 voice / policy 后，可以在 Observer 立即预览最终微信消息。
- Preview 不投递。
- Preview 能显示 State、Decision、Render 三层输出。

审计验收：

- 任意一条最终消息可以反查完整链路。
- 任意 world signal 可以看到来源、工具调用、使用位置、是否影响发送。
- 任意配置变更可以看到 diff、作者、时间、备份和 rollback。

人格解耦验收：

- 通用 prompt 中不出现“林绛”。
- 林绛相关词只出现在 `presence/profiles/linjiang/` 和历史兼容 wrapper。
- Decision 逻辑不再写死“清冷、疲惫、自持”等特质，而是读取 profile voice / relationship policy。

## 12. 最终建议

建议把后续工作定义为：

```text
Build a generic Hermes Proactive Presence Kernel,
then migrate Linjiang into it as the first profile.
```

不要继续做“林绛主动心跳补丁”。一步到位的正确边界是：

- 核心系统通用。
- 运行权限继承 Hermes，不在心跳层阉割。
- 个性通过配置注入。
- Observer 可以编辑配置、预览最终效果、回放完整链路。
- 林绛只是 profile，不是架构。

这样做完后，系统释放的不只是“林绛的活人感”，而是 Hermes profile 都可以拥有的、可配置、可观察、可预览、可行动的主动存在能力。
