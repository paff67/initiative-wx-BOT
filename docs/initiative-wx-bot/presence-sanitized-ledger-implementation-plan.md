# Presence Sanitized Ledger 与 ST 兼容上下文桥接实现方案

更新时间：2026-05-06 03:08 Asia/Shanghai

落地状态：核心链路已实现并通过 dry-run 验证。gateway/session 层已新增 sanitized ledger 写入与 chat history 合并；Presence State/Decision 已切换到 ledger timeline 与真实本地时间 `interaction_gap`；State/Decision prompt 已替换为“真实时间连续性与互动缺口”版本。Observer 维护端已增加 ledger 读取 API。

目标：把 Presence 主动消息、普通微信 inbound/outbound、Presence State/Decision 看到的最近对话统一到一条干净的时间线里。Presence 发出的消息要能被用户回复，普通聊天模型要知道用户是在回复哪条主动消息；Presence State/Decision 也不能再从 raw cron session 里读到内部 prompt。

当前已落地文件：

```text
/home/hermes/.hermes/hermes-agent/gateway/conversation_ledger.py
/home/hermes/.hermes/profiles/wx/presence/kernel/presence_conversation_ledger.py
/home/hermes/.hermes/profiles/wx/conversation/schemas/ledger-event.schema.json
/home/hermes/.hermes/hermes-agent/gateway/run.py
/home/hermes/.hermes/hermes-agent/gateway/platforms/base.py
/home/hermes/.hermes/hermes-agent/cron/scheduler.py
```

当前已接线位置：

- 普通 inbound：`gateway/run.py` 在模型调用前写入 `role=user` ledger。
- 普通 outbound：`gateway/platforms/base.py` 在文本/附件发送成功后写入 `role=assistant` ledger。
- 流式普通 outbound：`gateway/run.py` 在 `already_sent=true` 时补写 `role=assistant` ledger，避免 streaming 路径绕过 `base.py`。
- cron/Presence delivery：`cron/scheduler.py` 在 delivery 成功后写入 `source=presence|cron_delivery` ledger。
- Presence State/Decision：`presence_common.conversation_context()` 改为读取 sanitized ledger。

## 1. 已修复的问题

改造前存在两条割裂的上下文：

1. 普通微信会话历史：
   `/home/hermes/.hermes/profiles/wx/sessions/20260505_153825_588c7a5d.jsonl`
2. Presence cron session：
   `/home/hermes/.hermes/profiles/wx/sessions/session_cron_presence001_*.json`

普通 inbound chat 的 Prompt 只包含普通会话 `messages`，没有自动包含 Presence 最近发出的用户可见消息。用户回复 Presence 消息时，模型可能回到旧普通会话上下文。

Presence State/Decision 过去通过 `wx-smart-greeting-gate.py` 扫最近消息，能扫到 cron session，但会把 cron 内部 user prompt/script output 也作为对话项混入 timeline。

当前结论：不是“用户不能回复 Presence”，而是 Presence outbound 必须进入一层干净、可审计、可被普通会话读取的事实层。该事实层现在就是 `conversation/ledger.jsonl`。

## 2. 落点

Sanitized Ledger 应落在微信 profile 的 conversation 层，而不是落在 Presence 私有目录或 proxy 内部：

```text
/home/hermes/.hermes/profiles/wx/conversation/
  ledger.jsonl
  indexes/
    latest-by-chat.json
    latest-presence-by-chat.json
  schemas/
    ledger-event.schema.json
```

原因：

- Presence、普通 inbound、普通 outbound、Observer、State/Decision 都要读写它。
- proxy 只适合做 OpenAI/ST 兼容注入，不应成为事实源。
- Presence 私有目录会让普通聊天链路继续感知不到主动消息。
- raw session 文件仍由 Hermes 维护；ledger 是干净、可审计、跨链路的会话事件索引。

## 3. 当前普通会话 Prompt 结构

普通 wx inbound 落盘结构见：

```text
/home/hermes/.hermes/profiles/wx/sessions/session_20260505_153825_588c7a5d.json
```

当前结构：

```text
system_prompt
  = SOUL.md 角色预设
  + Hermes 运行边界
  + memory/skill/tool 指令
  + WeChat channel 指令

tools
  = Hermes tool/function definitions

messages
  = 普通 user/assistant chat history
```

`wx-openai-proxy-v2.py` 已兼容 SillyTavern preset snippet 注入，支持：

- `pre`：插入 chat history 之前。
- `post`：插入最后一条 user message 之前。
- `depth`：按 user turn 深度插入 chat history。

和原版 SillyTavern 的区别：

- 原版 ST 由 Prompt Manager 统一组织 Main Prompt、WorldInfo、角色卡、Scenario、Examples、Chat History、Post-History 等。
- 当前 Hermes 先构造 `system_prompt/tools/messages`，proxy 再把 ST preset snippets 注入 OpenAI messages。
- 当前是 ST preset/OpenAI messages 兼容，不是完整 ST prompt builder。
- Hermes 额外混入 tool/skill/channel 指令，原版 ST 通常没有这么重的工具层。

## 4. Ledger Event Schema

基础字段：

```json
{
  "schema_version": 1,
  "event_id": "conv_20260505_215648_xxx",
  "profile_id": "linjiang",
  "channel": "weixin",
  "chat_id": "o9cq800...",
  "thread_id": "",
  "user_id": "",
  "session_id": "20260505_153825_588c7a5d",
  "conversation_key": "weixin:main:o9cq800DQ7ZiX2Y1UbCXVyDq9dkc@im.wechat",
  "session_epoch_id": "20260505_153825_588c7a5d",
  "persona_revision": "sha256:...",
  "preset_id": "balanced",
  "role": "assistant",
  "source": "presence",
  "content": "今晚先到这儿。晚安。",
  "content_kind": "text",
  "visible_to_user": true,
  "created_at": "2026-05-05T21:56:48+08:00",
  "unix_ts": 1777989408.0,
  "sanitized": true,
  "prompt_visibility": {
    "chat_history": true,
    "state_context": true
  },
  "presence": {
    "tick_run_id": "tick_20260505_215548_4501",
    "render_run_id": "render_20260505_215548_4501",
    "message_class": "closure"
  },
  "delivery": {
    "delivery_event_id": "delivery_20260505_215548_4501",
    "delivery_channel": "weixin",
    "delivery_kind": "text",
    "message_id": ""
  }
}
```

不得写入 ledger 的内容：

- cron system prompt。
- script output 原文。
- LLM traceback。
- decision/state/render 的完整内部推理。
- tool raw secret、cookie、token。
- `reasoning_content`。

可写入 ledger 的内容：

- 用户真正看到的文本。
- 用户发来的文本。
- 用户真正收到的附件描述。
- message class、run id、delivery id 这类审计定位字段。
- 经过摘要和脱敏的 source metadata。

## 5. 写入点

### 5.1 Presence outbound

当前落点：

```text
/home/hermes/.hermes/hermes-agent/cron/scheduler.py
```

Presence Kernel 只负责输出 `render.text` / `MEDIA:` / `silent` payload；真正是否到达用户由 Hermes cron delivery 确认。因此 ledger 写入放在 cron delivery 成功之后，而不是提前放在 kernel 内部。

新增读取侧：

```text
/home/hermes/.hermes/profiles/wx/presence/kernel/presence_conversation_ledger.py
```

当 cron delivery 成功且 job id/name 识别为 Presence 时：

1. 从最终 delivery 内容或 `MEDIA:` 附件生成 sanitized assistant event。
2. 写入 `conversation/ledger.jsonl`。
3. 更新 `indexes/latest-presence-by-chat.json`。
4. `source=presence`，`content_kind=text|audio_attachment|file_attachment`。

注意：只有真正投递成功的内容写入 ledger。`dry_run`、`silent`、`presence_kernel_error` 不写入 chat history，可写 trace 但不写用户可见 ledger。

### 5.2 普通 inbound/outbound

最终落点：Hermes gateway session 层。直接采取“让 gateway 写 ledger”的路线，不把 proxy 作为事实源，也不先做 proxy-only 临时方案。

可复用现有模块：

```text
/home/hermes/.hermes/hermes-agent/gateway/mirror.py
```

该模块本来就声明用于“delivery-mirror record”，但当前 Presence cron 发出的消息没有进入普通会话历史。实现时应扩展或旁路新增：

```text
/home/hermes/.hermes/hermes-agent/gateway/conversation_ledger.py
```

写入规则：

- 普通 inbound 收到用户消息：写 `role=user, source=weixin_inbound`。
- 普通 assistant 回复完成：写 `role=assistant, source=wx_inbound_reply`。
- cron / send_message / media delivery 成功：写 `role=assistant, source=presence|cron_delivery|tool_delivery`。
- streaming 已经把最终回复发给用户时：由 `gateway/run.py` 在跳过普通 final send 前补写 `role=assistant, source=<platform>_streamed_reply`。

gateway 写 ledger 时必须写入归属字段：

```json
{
  "conversation_key": "weixin:main:o9cq800DQ7ZiX2Y1UbCXVyDq9dkc@im.wechat",
  "session_epoch_id": "20260505_153825_588c7a5d",
  "profile_id": "linjiang",
  "persona_revision": "sha256:...",
  "preset_id": "balanced-or-st-preset-id",
  "origin": {
    "platform": "weixin",
    "account_id": "main",
    "chat_id": "o9cq800DQ7ZiX2Y1UbCXVyDq9dkc@im.wechat",
    "thread_id": "",
    "user_id": "o9cq800DQ7ZiX2Y1UbCXVyDq9dkc@im.wechat"
  }
}
```

`conversation_key` 是物理通道归属，`session_epoch_id` 是当前对话连续体归属。后续所有“拼接”都只在同一个 key 和 epoch 内进行。

### 5.3 如何确定拼接哪一条对话

不做模糊匹配，也不按“最近两条任意 session”拼接。普通 inbound prompt 构造时按以下顺序选择 ledger events：

1. **精确 conversation_key**：`platform + account_id + chat_id + thread_id/user_id` 必须一致。
2. **精确 profile/persona scope**：`profile_id` 必须一致；如果支持角色切换，再比较 `persona_revision` 或 `preset_id`。
3. **当前 session_epoch_id**：优先只取当前 Hermes active session 对应 epoch。
4. **Presence outbound 例外**：如果 Presence delivery 发生在同一个 `conversation_key + profile_id`，但 delivery 时没有绑定到普通 session epoch，则仍可作为“同一物理会话中的用户可见 assistant 消息”注入下一轮普通 chat history。
5. **歧义时不注入**：如果同一个 chat 下有多个活跃 session/角色且无法判断当前 epoch，宁可不拼接，只把事件留在 ledger 审计里。

这意味着“拼接哪两个对话”不是由文本相似度决定，而是由 gateway 已知的会话归属决定。

### 5.4 用户切换对话或角色时

用户切换对话有几种情况：

- 切到另一个微信联系人或群：`conversation_key` 变化，不会拼接。
- 同一个微信联系人里 `/new`、重新开一条 Hermes session：`session_epoch_id` 变化，默认不把旧 epoch 的聊天消息作为当前 chat history。
- 同一个联系人切换角色/profile/ST preset：`profile_id/persona_revision/preset_id` 变化，默认创建新 epoch，不把旧角色的 assistant 消息当成当前角色说过的话。
- 用户显式 resume 旧会话：恢复原 `session_epoch_id`，ledger 可继续按该 epoch 合并。

如果需要跨 epoch 提供连续性，只允许注入“摘要型背景”，不允许把旧角色/旧 epoch 的 assistant 消息伪装成当前角色刚说过的话。摘要型背景必须标注来源为 `continuity_summary`，并由当前 profile 决定是否采用。

## 6. 读取与注入

### 6.1 普通 inbound chat

目标：用户回复 Presence 后，普通聊天模型能看到：

```json
{"role": "assistant", "content": "今晚先到这儿。晚安。"}
{"role": "user", "content": "晚安"}
```

实现方式：gateway prompt 构造前合并 ledger。

- 在 Hermes gateway 构造 `messages` 时读取 `ledger.jsonl`。
- 按 `conversation_key + session_epoch_id + profile_id/persona_revision` 过滤。
- 按 `unix_ts` 和现有 session messages 合并。
- 去重规则：`role + content + timestamp window + source`。
- 只注入 `prompt_visibility.chat_history=true` 的 event。
- 不把 `trace/script_output/cron_prompt/internal_error` 注入 ordinary chat history。
- proxy 保持 ST/OpenAI 兼容层职责，只保留采样和 preset snippets 注入。

短回复关联不是靠单独提示，而是靠真实 chat history：Presence outbound 已作为同一 epoch 的 assistant 消息存在，用户后续“晚安/嗯/好”等短回复自然接在它后面。

### 6.2 Presence State/Decision

修改：

```text
/home/hermes/.hermes/profiles/wx/presence/kernel/presence_common.py
```

将 `conversation_context()` 从扫 raw session/cron session 改为读取 sanitized ledger：

```text
ledger.timeline(limit=24, channel="weixin", profile_id="linjiang")
```

过滤规则：

- 只读 `visible_to_user=true`。
- 排除 `source=cron_prompt|script_output|trace|internal_error`。
- 排除 `content="[SILENT]"`。
- 按 `conversation_key + profile_id/persona_revision` 读取当前连续体。

这样 State/Decision 看到的最近几轮聊天将包含 Presence 真正发出的消息，但不会再包含 cron 内部 user prompt。

## 7. 真实时间连续性与互动缺口

所有时间判断都基于真实本地时间，所有互动都属于同一条连续时间线。

删除 `scene_ttl_minutes` 配置项。系统不另设叙事时间，而是判断：

- 上一次互动距今多久。
- 上一次互动是否自然收口。
- 上一次互动是否留下开放动作、情绪、承诺、照看、问题或未完成事项。
- 中间无互动的时间里，profile 自身可能如何自然流动。
- 当前真实本地时间、真实 world signals、个人状态是否改变了表达时机。

### 7.1 互动缺口建模

新增 State 输入：

```json
{
  "last_visible_interaction": {
    "role": "assistant",
    "content": "……那你快去。别弄太久，不然我又睡着了。",
    "created_at": "2026-05-05T15:45:56+08:00",
    "age_minutes": 371
  },
  "interaction_gap": {
    "elapsed_minutes": 371,
    "had_natural_closure": false,
    "unresolved_open_loops": [
      "对方去做热食",
      "她可能又睡着",
      "厨房收拾承诺未闭合"
    ]
  }
}
```

`had_natural_closure` 由 Python 规则和 LLM 共同判断：

- Python 只做结构化检测：是否问句、是否含承诺/待办/动作未闭合、是否存在最近 assistant closure。
- LLM 负责语义判断：这段互动在人类关系里是否“收住了”。

### 7.2 缺口内的个人事件

State LLM 可以在无互动时间段中生成符合 profile 的私有连续事件：

```json
{
  "private_continuity_events": [
    {
      "event_key": "fell_asleep_after_food_wait",
      "time_anchor": "after_last_interaction",
      "summary": "等了一会儿又困过去，醒来时已经晚了。",
      "visibility": "internal_state",
      "can_surface_obliquely": true
    }
  ]
}
```

约束：

- 只能生成 profile 自身的状态、动作、情绪、生活片段。
- 不能生成用户做过的事，除非 ledger 中已有用户消息或真实工具信号。
- 不能生成共同物理事实作为已发生事实，除非 profile 明确允许且不侵犯用户现实。
- 可以作为后续表达的气味和动机，例如“刚醒”“汤的事没接上”“白天那句话还卡着”。
- 这些事件写入 `presence/events/continuity-events.jsonl` 或 `runtime/state.json`，不作为普通 chat history 的 assistant/user 消息。

### 7.3 Decision 使用缺口

Decision 必须把以下内容纳入决策：

- 上一次互动是否没有自然收口。
- 是否存在应该闭合但不应追问的 open loop。
- 是否适合用 `closure`、`micro_send`、`random_share` 或继续 `silent`。
- 无互动缺口中生成的 private continuity events 是否已经形成表达动机。

示例：

- 如果上一轮是“你去弄点吃的”，长时间无互动后，可以形成 `closure` 或 `micro_send`：`睡过去了。`
- 如果上一轮已经明确“晚安”，后续深夜应倾向静默。
- 如果中间有真实 world signal，如下雨、降温、日程变化，可作为随机分享或时机调整，但仍不编造用户行为。

## 8. Prompt 注入策略

普通聊天注入顺序：

```text
system_prompt
ST pre snippets
sanitized ledger assistant/user messages merged into chat history
ST depth snippets
ST post snippets
latest user message
```

短句处理：

- 如果 latest user message 属于 `晚安|早安|睡了|醒了|嗯|好|到了|知道了`，模型应依据同一 ledger 时间线中的上一条可见消息理解它。
- 所有时间锚点使用真实本地时间。
- 不使用“场景已过期/未过期”的二分概念。
- 如果上一条可见互动没有收口，模型可以自然承接；如果已经收口，则保持短、轻、低压。

建议配置：

```yaml
conversation_bridge:
  enabled: true
  ledger_path: /home/hermes/.hermes/profiles/wx/conversation/ledger.jsonl
  max_history_events: 24
  require_exact_conversation_key: true
  require_session_epoch_match: true
  require_profile_scope_match: true
  ambiguous_match_policy: skip_injection
  merge_presence_as_chat_history: true
```

## 9. 语音投递闭环

短期目标：不是原生微信语音条，而是通过 iLink 文件附件发送 mp3。

现有 Weixin gateway 代码已经有文件发送链路：

```text
/home/hermes/.hermes/hermes-agent/gateway/platforms/weixin.py
```

相关事实：

- `ITEM_FILE = 4`，即 iLink `item_list[].type=4` 是文件附件。
- mp3 的 MIME 是 `audio/mpeg`，当前 `_outbound_media_builder()` 会走 `ITEM_FILE`。
- `send_voice()` 已明确使用 file attachment fallback，而不是未验证的原生 voice bubble。

实现：

1. Render 发现 `speech.enabled=true` 且 `delivery_mode=voice_note_preferred|voice_note_candidate`。
2. 调用 `http://127.0.0.1:8787/v1/audio/speech` 生成 mp3。
3. 保存到：

```text
/home/hermes/.hermes/profiles/wx/presence/runtime/audio/
```

4. cron final output 使用 Hermes 支持的 media 语法：

```text
MEDIA:/home/hermes/.hermes/profiles/wx/presence/runtime/audio/presence_....mp3
```

5. Weixin gateway 通过 iLink 上传并发送 `item_list[].type=4` 文件附件。
6. ledger 写入 assistant event：

```json
{
  "role": "assistant",
  "content": "[语音附件] 今晚先到这儿。晚安。",
  "content_kind": "audio_attachment",
  "delivery": {
    "delivery_kind": "mp3_attachment",
    "ilink_item_type": 4,
    "file_path": "/home/hermes/.hermes/profiles/wx/presence/runtime/audio/..."
  }
}
```

注意：

- 不把 voice design prompt 写入用户可见 content。
- mp3 文件应有保留期，例如 7 天，之后清理。
- 如果 mp3 生成失败，fallback 到 `render.text`。

## 10. Observer

新增 API：

```text
GET /api/conversation/ledger
GET /api/conversation/latest
GET /api/conversation/ledger
GET /api/conversation/latest
```

前端新增或扩展：

- Traces：显示 `ledger_event_id`。
- Delivery：显示对应 ledger event。
- Preview：显示“将合并到普通聊天 history 的 ledger 事件”。
- World Signals：区分 world signal 与 conversation ledger，不混用。

## 11. 测试计划

### 11.1 Ledger 写入

- Presence `would_deliver=true` 后，`ledger.jsonl` 出现一条 `source=presence` assistant event。
- `dry_run=true` 不写 ledger。
- `silent` 不写 ledger。
- `presence_kernel_error` 不写 ledger。
- streaming 普通 outbound 已发送时，`gateway/run.py` 补写 assistant ledger，不依赖 `base.py` final send。
- 未绑定 session epoch 的 Presence event 会合并进同一 `conversation_key + profile_id` 的下一轮普通 chat history；其他 session 的普通 event 不会被合并。

### 11.2 普通回复桥接

测试流程：

1. 构造 Presence outbound：`今晚先到这儿。晚安。`
2. 5 分钟内发送用户普通 inbound：`晚安`
3. 抓普通 chat prompt，确认同一 `conversation_key + session_epoch_id` 下包含 Presence assistant event。
4. 模型回复应基于真实本地时间和同一连续时间线，短、轻、低压，不说“下午四点”。

期望回复形状：

```text
嗯。晚安。
别再折腾了，真的。
```

### 11.3 State/Decision

- `conversation_context()` 不再包含 cron 内部 prompt。
- State timeline 包含 Presence 可见 outbound。
- Decision 能识别用户刚回复了 Presence closure，深夜不再补发。

### 11.4 语音附件

- TTS 生成 mp3。
- cron final output 包含 `MEDIA:/abs/path.mp3`。
- Weixin 发送 iLink `item_list[].type=4` 文件附件。
- 失败时 fallback 文本。
- ledger 记录 `content_kind=audio_attachment`。

## 12. 实施顺序

1. 新增 ledger module 与 schema。已完成。
2. gateway 增加 conversation ledger 写入能力。已完成。
3. cron/Presence delivery 成功后写 ledger。已完成。
4. gateway 普通 inbound/outbound 镜像写 ledger。已完成，含 streaming 补写。
5. 普通 chat prompt builder 按 `conversation_key + session_epoch_id + profile scope` 合并 ledger。已完成，Presence 无 epoch 例外已补齐。
6. Presence `conversation_context()` 改读 ledger。已完成。
7. Observer 加 ledger API。已完成基础 API；前端 ledger 详情页仍可继续增强。
8. TTS mp3 生成并通过 `MEDIA:` 发送 iLink type=4 附件。设计已写入，自动闭环待单独落地。
9. 回归测试普通聊天、Presence tick、Preview、Delivery。已完成 dry-run/编译/构建/ledger 冒烟；真实线上投递需等下一次实际 `send` 决策验证。

## 13. 回滚

可单独关闭：

```yaml
conversation_bridge:
  enabled: false
  merge_presence_as_chat_history: false
```

Presence 可继续运行，只是不再把 outbound 注入普通聊天。

Ledger 文件是 append-only，不需要删除。若需要停用，保留文件供审计即可。
