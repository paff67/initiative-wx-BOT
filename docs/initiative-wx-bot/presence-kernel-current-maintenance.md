# Hermes Presence Kernel 当前系统维护文档

更新时间：2026-05-06 16:35 Asia/Shanghai
维护范围：`/home/hermes/.hermes/profiles/wx`、`/home/hermes/hermes-observer`、相关 systemd 服务、Hermes cron、MiMo TTS 代理。

本文档描述的是当前机器上的真实状态。敏感 key、token、cookie、OAuth 凭据均不在本文档展开。

## 1. 当前结论

当前系统不是单纯本地测试状态。新 `Proactive Presence Kernel` 已经接入 Hermes cron，任务为：

- Job ID：`presence001`
- Job name：`presence-kernel-linjiang`
- 频率：每 15 分钟
- 状态：enabled
- 投递通道：`weixin`
- 当前 profile：`linjiang`
- 最近状态：`last_status=ok`
- 配置文件：`/home/hermes/.hermes/profiles/wx/cron/jobs.json`

2026-05-06 已完成一次 Presence Kernel 落地修复：

1. `presence_tick.py` 的 `_age_minutes()` 已修复，stochastic prefilter 能正确读取 `state_age_minutes`。
2. 旧用户 crontab 的 `wx-linjiang-state-tick.sh` 已备份并注释，不再每小时更新旧 state。
3. Preview dry-run 已隔离到 `preview-events.jsonl` 和 `preview-last-trace.json`，不再污染生产 `decision/trace` latest。
4. `presence_world_collector.py` 已接入现有 stdio MCP adapter，并将 tool call 与 world signal 写入 `world-signal-events.jsonl` 和 trace。
5. `voice_design` 已按 MiMo-V2.5-TTS-VoiceDesign 语义拆成 `natural_language_control` 与 `assistant_style_tags`，本地 TTS 代理测试通过；当前策略为 Decision LLM 动态生成，不再由代码把 profile 默认 prompt 硬填进每次 decision。
6. `counts_toward_normal_send` 已在 Python cooldown 层生效。
7. State/Decision prompt 已更新为“真实时间连续性与互动缺口”版本：State 输出 `interaction_analysis/private_continuity_events`，Decision 输出 `render_brief/voice_design`。
8. Sanitized Ledger 核心链路已落地：普通 inbound/outbound、streaming outbound、cron/Presence delivery 可写入 `/home/hermes/.hermes/profiles/wx/conversation/ledger.jsonl`，Presence `conversation_context()` 已改读该 ledger。
9. gateway 普通聊天在加载 transcript 后会合并同一 `conversation_key + session_epoch_id + profile_id` 的 ledger 可见事件；未绑定 session epoch 的 Presence 主动消息也会在同一 `conversation_key + profile_id` 下进入后续普通聊天 history。
10. 本轮 Prompt First 改造后已验证：State 输出 `interaction_analysis/private_continuity_events`，Decision 输出 `render_brief/voice_design`，dry-run 不写用户可见 ledger。
11. wx proxy 已支持无斜杠 Presence 地点控制命令：`presence location set 上海`、`presence location show`、`presence location clear`。命令写入 `presence/runtime/location-context.json`，不会作为普通聊天内容进入上游模型；ledger 清洗层会丢弃该控制命令及其 proxy 回执。

仍需注意：

1. Observer 已经切换到 Presence Kernel 控制台，但仍保留部分旧 API/旧 Dashboard 代码，维护时要区分新旧页面与新旧事件源。
2. 普通微信 inbound chat 与 Presence cron session 的上下文割裂已完成核心修复；当前还没有新的真实 `send` 投递事件写入 ledger，后续重点是观察下一次真实投递后的 ledger 事件质量，以及补充前端 ledger 详情页。
3. 当前微信会话的 `gateway_voice_mode.json` 显示 voice mode 为 `off`；`speech` metadata 和 TTS 请求体已就绪。短期语音闭环方案改为走 iLink 文件附件：`item_list[].type=4`，发送 mp3 附件，不追求原生语音条。
4. `/etc/logrotate.d/linjiang-heartbeat` 是 root-owned；当前用户无免密 sudo，presence events logrotate 尚未写入系统配置。

## 2. 总体架构

当前运行链路：

```text
Hermes gateway wx service
  -> Hermes cron scheduler
  -> cron job presence001 / presence-kernel-linjiang
  -> script: /home/hermes/.hermes/profiles/wx/scripts/presence_tick.py
  -> kernel: /home/hermes/.hermes/profiles/wx/presence/kernel/presence_tick.py
  -> world collector
  -> intent decay
  -> stochastic prefilter
  -> State LLM
  -> Decision LLM
  -> Python intent accumulator update
  -> Python message-class cooldown enforcement
  -> Render LLM
  -> JSON payload: wakeAgent true/false
  -> Hermes cron delivery gate
  -> Weixin delivery or skip
  -> sanitized conversation ledger
```

普通微信会话与 Presence 上下文桥接目标链路：

```text
Presence delivery / normal inbound / normal outbound
  -> /home/hermes/.hermes/profiles/wx/conversation/ledger.jsonl
  -> gateway prompt builder
  -> ST-compatible chat history merge
  -> model reply
  -> normal session + ledger append

Presence State/Decision
  -> sanitized ledger timeline
  -> no raw cron prompt/script output
```

Observer 控制台链路：

```text
browser / Cloudflare Access
  -> http://127.0.0.1:8790
  -> linjiang-observer-backend.service
  -> FastAPI /api/*
  -> React frontend dist
  -> presence runtime / events / profile config
```

模型代理链路：

```text
Presence State/Decision/Render
  -> http://127.0.0.1:8788/v1/chat/completions
  -> wx-openai-proxy.service
  -> upstream model

Hermes TTS / test TTS
  -> http://127.0.0.1:8787/v1/audio/speech
  -> mimo-tts-proxy.service
  -> Xiaomi MiMo API
  -> mp3
```

## 3. 关键路径

### 3.1 Hermes wx profile

```text
/home/hermes/.hermes/profiles/wx
```

关键文件：

| 路径 | 用途 |
| --- | --- |
| `config.yaml` | Hermes wx profile 主配置，包含模型、TTS、MCP、cron.wrap_response 等。权限当前为 `600`。 |
| `.env` | Hermes wx 服务环境变量，权限当前为 `600`。 |
| `linjiang-llm.env` | Presence State/Decision/Render 使用的 LLM 环境变量，权限当前为 `600`。 |
| `cron/jobs.json` | Hermes cron 当前任务表，权限当前为 `600`。 |
| `cron/output/presence001/*.md` | Presence cron 每次运行输出。 |
| `cron/output/e1a5cda0d909/*.md` | 旧 hourly proactive job 历史输出。 |
| `state.db` | Hermes 会话/消息状态数据库。 |
| `proxy-requests.jsonl` | wx 模型代理请求日志。 |
| `gateway_voice_mode.json` | 微信 voice mode 状态，当前目标会话为 `off`。 |

### 3.1.1 Conversation Ledger（已落地核心链路）

方案文档：

```text
/home/hermes/presence-sanitized-ledger-implementation-plan.md
```

目标路径：

```text
/home/hermes/.hermes/profiles/wx/conversation
```

已落地/计划文件：

| 路径 | 用途 |
| --- | --- |
| `conversation/ledger.jsonl` | 干净会话事件事实源。只保存用户可见 inbound/outbound，不保存 cron prompt、script output、trace、reasoning。 |
| `conversation/indexes/latest-by-chat.json` | 每个 chat 最近普通/主动事件索引。 |
| `conversation/indexes/latest-presence-by-chat.json` | 每个 chat 最近 Presence outbound 索引。 |
| `conversation/schemas/ledger-event.schema.json` | ledger event schema。 |
| `presence/runtime/location-context.json` | wx proxy 手动设置的当前地点上下文，供 MCP 参数模板解析使用。 |
| `presence/events/location-context-events.jsonl` | 地点 set/clear 审计事件。 |
| `presence/runtime/memory-context-latest.json` | wx proxy 最近一次捕获到的 Hindsight `<memory-context>` 快照，仅供本地 `proxy memory context` 查看。 |
| `presence/events/memory-context-events.jsonl` | memory-context 捕获审计；只记录长度、hash、时间，不保存正文。 |

维护判断：

- Ledger 应落在 wx profile 的 conversation 层，不落在 Presence 私有目录，也不以 proxy 日志作为事实源。
- proxy 只作为 ST/OpenAI 兼容注入器；ledger 的写入和普通 chat history 合并应落在 gateway/session 层。
- Presence State/Decision 已改读 sanitized ledger timeline，不再扫 raw cron session。
- `presence location ...` 是 wx proxy 控制命令，不属于用户可见对话事实；proxy 会在转发上游前移除历史中的该命令与回执，ledger `sanitize_content()` 也会过滤它们。
- `proxy memory context` 是 wx proxy 本地调试命令，用于显式查看当前/最近一次 Hindsight `<memory-context>`；该命令与 `🧠 Memory context:` 回执会被 proxy 和 ledger 过滤，不进入 Presence State/Decision、sanitized ledger 或 MCP 参数。
- `<memory-context>` 只能作为 Hindsight 给普通会话模型的内部上下文存在；任何 proxy 命令参数、ledger 内容、Presence runtime、world signal trace 都必须剥离它。

当前写入点：

| 写入点 | 文件 | 内容 |
| --- | --- | --- |
| 普通用户输入 | `.hermes/hermes-agent/gateway/run.py` | `_prepare_inbound_message_text()` 后写 `role=user`。 |
| 普通助手回复 | `.hermes/hermes-agent/gateway/platforms/base.py` | 文本/附件发送成功后写 `role=assistant`。 |
| cron / Presence 投递 | `.hermes/hermes-agent/cron/scheduler.py` | `_deliver_result()` 成功后写 `source=presence` 或 `cron_delivery`。 |
| 流式助手回复 | `.hermes/hermes-agent/gateway/run.py` | `already_sent=true` 时补写 `source=<platform>_streamed_reply`。 |
| Presence 读取 | `presence/kernel/presence_common.py` | `conversation_context()` 读取 ledger 并计算 `interaction_gap`。 |

验证命令：

```bash
tail -n 20 /home/hermes/.hermes/profiles/wx/conversation/ledger.jsonl
curl -s http://127.0.0.1:8790/api/conversation/latest
```

如果 `ledger.jsonl` 尚不存在，通常表示改造完成后还没有发生真实用户可见 inbound/outbound 或 Presence send；dry-run 和 silent 不会创建该文件。

### 3.2 Presence Kernel

```text
/home/hermes/.hermes/profiles/wx/presence
```

目录：

| 路径 | 用途 |
| --- | --- |
| `kernel/` | 通用主动心跳内核代码。 |
| `profiles/linjiang/` | 林绛 profile 配置实例。 |
| `runtime/` | 当前 runtime state、intent state、last trace。 |
| `events/` | JSONL 事件流水。 |
| `schemas/` | schema 草案。 |
| `backups/config/` | Observer profile config 自动备份与 rollback 文件。 |
| `config.yaml` | Presence 默认 profile 配置，目前 `default_profile_id: linjiang`。 |

核心脚本：

| 脚本 | 责任 |
| --- | --- |
| `kernel/presence_tick.py` | 唯一 Presence tick 主入口。负责调度 world/state/decision/render。 |
| `kernel/presence_common.py` | 路径、配置、LLM 调用、JSONL、conversation context、model settings。 |
| `kernel/presence_world_collector.py` | 非 LLM 真实世界信号采集。当前只采本地时间和 command sources。 |
| `kernel/presence_state_tick.py` | Generic State LLM 层。 |
| `kernel/presence_decision_tick.py` | Generic Decision LLM 层，包含 `voice_design` 字段规范。 |
| `kernel/presence_intent.py` | Python 层 intent accumulator 与 cooldown enforcement。 |
| `kernel/presence_render.py` | Render LLM 层与 cron payload 生成。 |
| `kernel/presence_preview.py` | dry-run preview 包装入口。 |
| `scripts/presence_tick.py` | Hermes cron-safe wrapper，读取 default profile 后运行 kernel。 |

### 3.3 林绛 profile 配置

```text
/home/hermes/.hermes/profiles/wx/presence/profiles/linjiang
```

| 文件 | 用途 |
| --- | --- |
| `manifest.yaml` | profile 元信息、timezone、llm env file、各层 env prefix。 |
| `profile_metadata.yaml` | 仅保留 `name`、`language`、`channel` 等 UI 显示和路由字段，不承载人设。 |
| `../../../SOUL.md` 前七部分 | 角色身份、边界、语气、亲密度和主动性的权威来源。 |
| `voice.md` | 文字语气与 voice design 基准参考，不作为独立人设来源。 |
| `relationship.yaml` | 关系距离、边界、消息形状。 |
| `proactive_policy.yaml` | cadence、prefilter、intent、cooldown、decision policy。 |
| `world_policy.yaml` | world signal 采集与表达策略。 |
| `permission_policy.yaml` | 权限模式、继承 MCP/skills/action tools、trace 策略。 |
| `delivery_weixin.yaml` | 微信投递能力、wrap_response、speech/VoiceDesign 配置。 |
| `examples.yaml` | 好/坏输出示例。 |

当前 profile validate 结果：`ok=true`，没有 missing 和 YAML error。

### 3.4 Observer

```text
/home/hermes/hermes-observer
```

| 路径 | 用途 |
| --- | --- |
| `backend/app/main.py` | FastAPI 应用入口。 |
| `backend/app/config.py` | Observer 读取的路径与功能开关。 |
| `backend/app/routers/api.py` | API 路由，含 profile config edit/rollback/preview/traces。 |
| `frontend/src/App.tsx` | 新 Presence Console 导航。 |
| `frontend/src/pages/Profiles.tsx` | 配置编辑、validate、backup、rollback。 |
| `frontend/src/pages/Preview.tsx` | Full preview，强制 dry-run，不投递。 |
| `frontend/src/pages/Traces.tsx` | World -> State -> Intent -> Decision -> Render -> Delivery trace。 |
| `frontend/src/pages/WorldSignals.tsx` | world signal 查看与事后 review。 |
| `frontend/src/pages/PresenceDecisions.tsx` | 新 decision events。 |
| `frontend/src/pages/Delivery.tsx` | delivery events。 |
| `frontend/dist/` | 已构建的前端静态文件。 |

当前 backend systemd：

- 服务名：`linjiang-observer-backend.service`
- 监听：`127.0.0.1:8790`
- PATH 要包含 `/home/hermes/.local/bin`，否则 Observer 触发的 Presence Preview 里 Node-based MCP 会找不到 `node`。
- `OBSERVER_ENABLE_WRITES=1`
- `OBSERVER_ENABLE_HUMAN_FEEDBACK=1`
- `OBSERVER_ENABLE_PROMPT_EDIT=0`
- 鉴权：代码内 token check 已移除，注释说明由 Cloudflare Access 处理。

## 4. systemd 服务与端口

当前相关服务均为 active/running：

| 服务 | 端口/作用 | 维护命令 |
| --- | --- | --- |
| `hermes-gateway-wx.service` | Hermes wx gateway，负责微信、cron、MCP。 | `systemctl status hermes-gateway-wx.service -l --no-pager` |
| `wx-openai-proxy.service` | `127.0.0.1:8788`，wx LLM OpenAI-compatible 代理。 | `systemctl status wx-openai-proxy.service -l --no-pager` |
| `mimo-tts-proxy.service` | `127.0.0.1:8787`，MiMo TTS OpenAI-compatible 代理。 | `systemctl status mimo-tts-proxy.service -l --no-pager` |
| `linjiang-observer-backend.service` | `127.0.0.1:8790`，Observer FastAPI + frontend。 | `systemctl status linjiang-observer-backend.service -l --no-pager` |
| `hermes-dashboard.service` | `127.0.0.1:9119`，Hermes dashboard。 | `systemctl status hermes-dashboard.service -l --no-pager` |
| `hermes-gateway-wx-friend.service` | wx-friend gateway。 | `systemctl status hermes-gateway-wx-friend.service -l --no-pager` |
| `wx-openai-proxy-friend.service` | `127.0.0.1:8789`，friend 聊天模型代理。 | `systemctl status wx-openai-proxy-friend.service -l --no-pager` |

端口快查：

```bash
ss -ltnp | rg '(:8787|:8788|:8789|:8790|:9119)'
```

重启常用命令：

```bash
systemctl restart linjiang-observer-backend.service
systemctl restart hermes-gateway-wx.service
systemctl restart wx-openai-proxy.service
systemctl restart mimo-tts-proxy.service
```

Observer PATH drop-in：

```bash
sudo mkdir -p /etc/systemd/system/linjiang-observer-backend.service.d
sudo tee /etc/systemd/system/linjiang-observer-backend.service.d/10-path.conf >/dev/null <<'EOF'
[Service]
Environment=PATH=/home/hermes/.local/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:/snap/bin
EOF
sudo systemctl daemon-reload
sudo systemctl restart linjiang-observer-backend.service
```

当前代码也会在执行 Presence Preview 子进程时显式补同样的 PATH，避免 systemd 环境未更新时 MCP 直接失效；但 systemd drop-in 仍建议保留，便于排查和环境一致性。

日志：

```bash
journalctl -u linjiang-observer-backend.service -n 100 -o cat --no-pager
journalctl -u hermes-gateway-wx.service -n 100 -o cat --no-pager
journalctl -u wx-openai-proxy.service -n 100 -o cat --no-pager
journalctl -u mimo-tts-proxy.service -n 100 -o cat --no-pager
```

wx proxy 当前还承载 Presence 控制命令。微信里直接发送，不带斜杠：

```text
presence location set 上海
presence location set 30.2741,120.1551 杭州
presence location show
presence location clear
proxy memory context
proxy memory clear
```

这些命令由 `/home/hermes/.local/bin/wx-openai-proxy-v2.py` 本地处理，正常返回 OpenAI-compatible fake response，不转发上游 LLM。

命令隔离规则：

- proxy 命令解析只读取剥离 `<memory-context>` 后的第一条真实命令行。
- `presence location set ...` 的地点 label 上限 80 字符，拒绝换行、尖括号、`memory-context`、`Hindsight Memory`、`System note` 等内部标记。
- `proxy memory context` 会显示本次请求捕获到的 Hindsight block；若本次没有则读取 `presence/runtime/memory-context-latest.json`。
- `proxy memory context` 的正文只展示给用户，不写入 sanitized ledger，也不会进入 Presence Decision/Render。

## 5. Cron 与调度

### 5.1 当前 Hermes cron job

当前 `cron/jobs.json` 只有一个启用 job：

```json
{
  "id": "presence001",
  "name": "presence-kernel-linjiang",
  "script": "presence_tick.py",
  "schedule": {"kind": "interval", "minutes": 15, "display": "every 15m"},
  "enabled": true,
  "deliver": "weixin"
}
```

最近状态以 `cron/jobs.json` 为准。2026-05-06 03:00 前后检查时：

- `created_at`: `2026-05-05T19:03:55+08:00`
- `repeat.completed`: `30`
- `last_status`: `ok`
- `deliver`: `weixin`

查看：

```bash
cat /home/hermes/.hermes/profiles/wx/cron/jobs.json | python3 -m json.tool
```

Presence cron 输出：

```bash
ls -lh /home/hermes/.hermes/profiles/wx/cron/output/presence001
tail -n 80 /home/hermes/.hermes/profiles/wx/cron/output/presence001/*.md
```

最近一次 cron 输出显示：

```text
Script gate returned wakeAgent=false - agent skipped.
```

这表示 kernel 本轮判断不投递，Hermes cron 没有进入用户可见最终消息。

### 5.2 当前 Hermes cron delivery gate

当前 job prompt 是 Presence Kernel delivery gate：

```text
Use only the script-provided context.

If no script context exists, or context.render.type is "silent", or context.dry_run is true, output exactly:
[SILENT]

If context.render.type is "text", output only context.render.text.

If context.render.type is "media" or "action", follow context.render.delivery_instruction only if it is directly supported by this delivery channel; otherwise output exactly:
[SILENT]

Do not mention or describe automation, cron, scripts, LLMs, prompts, decisions, traces, tools, context, internal state, or this protocol.
```

`/home/hermes/.hermes/profiles/wx/config.yaml` 中：

```yaml
cron:
  wrap_response: false
```

因此正常情况下不会再向微信输出 `Cronjob Response` 包装文本。

### 5.3 遗留 crontab

系统用户 crontab 中旧 state tick 已被注释禁用：

```cron
# disabled by presence-kernel implementation 20260506-011016: 0 * * * * cd /home/hermes/.hermes/hermes-agent && HERMES_HOME=$HOME/.hermes/profiles/wx /home/hermes/.hermes/profiles/wx/wx-linjiang-state-tick.sh >> $HOME/.hermes/profiles/wx/linjiang-state-tick.log 2>&1
```

它会每小时更新旧文件：

```text
/home/hermes/.hermes/profiles/wx/linjiang-internal-state.json
/home/hermes/.hermes/profiles/wx/linjiang-state-events.jsonl
/home/hermes/.hermes/profiles/wx/linjiang-state-tick.log
```

新 Presence Kernel 不依赖这个旧 state 文件；Observer 的新 Overview 使用 `presence/runtime/state.json`。但旧 `/api/state/current` 和旧 Dashboard 仍读取 `linjiang-internal-state.json`，所以维护时不要混淆。

如果要检查或进一步清理旧 state tick，需要编辑用户 crontab：

```bash
crontab -e
```

删除或注释上述 `wx-linjiang-state-tick.sh` 行。修改前先保存当前 crontab：

```bash
crontab -l > /home/hermes/crontab.backup.$(date +%Y%m%d-%H%M%S)
```

## 6. Presence Tick 运行流程

`presence_tick.py --profile linjiang` 当前固定顺序：

1. `ensure_dirs()`
2. `load_profile(profile_id)`
3. `load_profile_env(profile)`，读取 `manifest.yaml` 中 `../../../linjiang-llm.env`
4. `collect_world_signals()`
5. `load_and_decay()`，Python 层 intent decay
6. `compute_stochastic_prefilter()`
7. 如果 skip：写 `tick-events.jsonl`、`trace-events.jsonl`，打印 `wakeAgent=false`，退出
8. `run_state_layer()`
9. `run_decision_layer()`
10. `apply_intent_delta()`，Python 层 intent 加分
11. `cooldown_status()`，Python 层 message class 独立冷却
12. `render_decision()`
13. 如果 would_deliver：`record_delivery()`
14. 写 `last-trace.json`、`trace-events.jsonl`
15. 打印 cron payload

直接 dry-run：

```bash
cd /home/hermes/.hermes/profiles/wx/presence/kernel
python3 presence_tick.py --profile linjiang --dry-run --force-llm
```

通过 Hermes wrapper dry-run：

```bash
python3 /home/hermes/.hermes/profiles/wx/scripts/presence_tick.py --dry-run --force-llm
```

注意：dry-run 会恢复 `state.json` 和 `intent-state.json`，事件写入 `preview-events.jsonl`，trace 写入 `runtime/preview-last-trace.json`，不会覆盖生产 `runtime/last-trace.json`。

## 7. Stochastic Prefilter

配置位置：

```text
/home/hermes/.hermes/profiles/wx/presence/profiles/linjiang/proactive_policy.yaml
```

当前配置：

```yaml
cadence:
  schedule: "every 15m"
  stochastic_prefilter:
    enabled: true
    base_wake_probability: 0.22
    min_probability: 0.04
    max_probability: 0.65
    skip_before_llm: true
    jitter_not_before_minutes:
      min: 12
      max: 45
    force_llm_after_state_age_minutes: 180
```

设计逻辑：

- base 概率：`0.22`
- 最近活跃：概率乘 `0.4`
- 有非 time 且 auto_allow 的 world signal：每个加 `0.05`，最高加 `0.2`
- intent pressure 接近阈值：加 `0.15`
- state age 超过 `180` 分钟：强制通过
- 最终 clamp 到 `0.04 - 0.65`

已修复问题：

```python
def _age_minutes(value: Any, now) -> float | None:
    if not value:
        return None
```

解析时间的代码被错误放进了 `restore_runtime_for_dry_run()` 后部，导致 `_age_minutes()` 对任何已有时间也返回 `None`。于是：

```python
if state_age is None or state_age >= force_age:
    return {"skip": False, "reason": "state_age_force_llm", ...}
```

过去会在每次 tick 强制通过，形成每 15 分钟完整 LLM 链路。当前已修正为正常解析 ISO 时间。

当前实现：

```python
def _age_minutes(value: Any, now) -> float | None:
    if not value:
        return None
    try:
        from datetime import datetime
        dt = datetime.fromisoformat(str(value))
        return round((now - dt).total_seconds() / 60, 1)
    except Exception:
        return None
```

同时从 `restore_runtime_for_dry_run()` 移除误放的 `value/now` 解析代码。

验证：

```bash
for i in $(seq 1 20); do
  python3 /home/hermes/.hermes/profiles/wx/scripts/presence_tick.py --dry-run | tail -n 1
done | rg 'stochastic_skip_before_llm|wakeAgent'
```

预期：20 次里应出现若干 `stochastic_skip_before_llm`，且 skip 时不产生 State/Decision LLM 请求。此前已验证出现 skip 分布。

## 8. Intent Accumulator

代码：

```text
/home/hermes/.hermes/profiles/wx/presence/kernel/presence_intent.py
```

runtime：

```text
/home/hermes/.hermes/profiles/wx/presence/runtime/intent-state.json
```

事件：

```text
/home/hermes/.hermes/profiles/wx/presence/events/intent-events.jsonl
```

当前配置：

```yaml
intent_accumulator:
  enabled: true
  score_min: 0
  score_max: 3
  send_pressure_threshold: 2.0
  hourly_decay: 0.2
  hesitate_delta_default: 0.7
  silent_with_open_loop_delta: 0.2
  world_signal_delta_max: 0.5
  expire_after_hours: 12
  clear_after_delivery: true
```

当前 runtime 快照：

- topic：`repair_quiet_closure`
- score：约 `1.1`
- threshold：`2.0`
- delivery counters：空
- 结论：尚未达到强制发送压力阈值。

职责边界：

- LLM 只输出 `intent_delta`。
- Python 负责 score 加分、时间衰减、过期、evidence 合并、delivery 后清理。
- 下一轮 LLM 只能看到 Python 计算后的 pressure summary。

常用检查：

```bash
cat /home/hermes/.hermes/profiles/wx/presence/runtime/intent-state.json | python3 -m json.tool
tail -n 20 /home/hermes/.hermes/profiles/wx/presence/events/intent-events.jsonl
```

## 9. Message Class 冷却

配置位置：

```text
/home/hermes/.hermes/profiles/wx/presence/profiles/linjiang/proactive_policy.yaml
```

当前 message class 独立冷却：

| message_class | min_gap | daily_cap | 是否计入 normal |
| --- | ---: | ---: | --- |
| `micro_send` | 15 min | 6 | false |
| `closure` | 30 min | 4 | false |
| `random_share` | 120 min | 2 | true |
| `care_timing` | 120 min | 2 | true |
| `normal_send` | 120 min | 5 | true |
| `media` | 180 min | 1 | true |

当前 `counts_toward_normal_send` 已在 Python 层实现：

- `micro_send` / `closure` 不写入 normal aggregate，不阻塞 `normal_send`。
- `random_share` / `care_timing` / `media` / `normal_send` 会同时计入 `_normal_send_aggregate`。
- `cooldown_status()` 同时检查自身 bucket 和 normal aggregate bucket。

## 10. State / Decision / Render Prompt 边界

Prompt 已从 Python 代码中解耦。Kernel 代码只调用 `load_prompt(profile, layer)`，实际 prompt 文件位置：

```text
/home/hermes/.hermes/profiles/wx/presence/prompts/state-system.md
/home/hermes/.hermes/profiles/wx/presence/prompts/decision-system.md
/home/hermes/.hermes/profiles/wx/presence/prompts/render-system.md
```

支持 profile 覆盖，优先级高于通用 prompt：

```text
/home/hermes/.hermes/profiles/wx/presence/profiles/<profile_id>/prompts/state-system.md
/home/hermes/.hermes/profiles/wx/presence/profiles/<profile_id>/prompts/decision-system.md
/home/hermes/.hermes/profiles/wx/presence/profiles/<profile_id>/prompts/render-system.md
```

维护规则：

- 修改 prompt 只编辑 markdown 文件，不改 `presence_*_tick.py`。
- prompt 文件内容已纳入 `config_revision`，改 prompt 后新的事件 revision 会变化。
- `decision-events.jsonl` 仍会记录当次实际使用的 `prompt.system` 和 `prompt.user`，便于审计。

### 10.1 State Layer

代码文件：

```text
/home/hermes/.hermes/profiles/wx/presence/kernel/presence_state_tick.py
```

Prompt 文件：

```text
/home/hermes/.hermes/profiles/wx/presence/prompts/state-system.md
```

System prompt 是通用的：

- 不作为最终用户可见说话者
- 不硬编码具体人设
- `identity_canon` 由 `SOUL.md` 前七部分注入，是人设权威
- `profile_metadata` 只提供名称、语言、通道等 UI / 路由字段
- voice 作为文字语气和 voice design 参考注入
- 输出 JSON

输入包括：

- `persona_config`
- `current_time`
- world signals
- sanitized ledger timeline
- interaction gap
- previous runtime state
- SOUL / USER / MEMORY 绑定

输出进入：

```text
presence/runtime/state.json
presence/events/state-events.jsonl
```

### 10.2 Decision Layer

代码文件：

```text
/home/hermes/.hermes/profiles/wx/presence/kernel/presence_decision_tick.py
```

Prompt 文件：

```text
/home/hermes/.hermes/profiles/wx/presence/prompts/decision-system.md
```

Decision 输出 schema：

```json
{
  "action": "silent|hesitate|send",
  "message_class": "none|micro_send|closure|random_share|care_timing|normal_send",
  "confidence": 0.0,
  "reply_pressure": "none|low|medium|high",
  "reasoning_summary": "结合空白期事件和上一轮是否收口的一句话依据",
  "intent_delta": {
    "topic_key": "short_key",
    "delta": 0.0,
    "reason": "why"
  },
  "render_brief": {
    "entry_point": "",
    "emotional_baseline": "",
    "shape_constraint": ""
  },
  "voice_design": {
    "enabled": false,
    "natural_language_control": "",
    "assistant_style_tags": [],
    "delivery_mode": "voice_note_candidate"
  }
}
```

`voice_design` 是内部 delivery metadata，不应出现在用户可见文本里。

### 10.3 Render Layer

代码文件：

```text
/home/hermes/.hermes/profiles/wx/presence/kernel/presence_render.py
```

Prompt 文件：

```text
/home/hermes/.hermes/profiles/wx/presence/prompts/render-system.md
```

Render 输出：

```json
{
  "type": "silent|text|media|action",
  "text": "",
  "delivery_instruction": "",
  "fallback": {},
  "speech": {}
}
```

当前 `speech` 只作为 metadata 写入 trace/render event。Cron final gate 目前只输出 `render.text`，所以语音投递尚未自动闭环。

## 11. World Signals 与 MCP

### 11.1 当前 Presence world collector

代码：

```text
/home/hermes/.hermes/profiles/wx/presence/kernel/presence_world_collector.py
```

当前 collector 行为：

- 总是采集本地时间。
- 读取 `world_policy.command_sources`。
- `command_sources` 当前为空。
- 读取 `world_policy.mcp_sources`，通过 `presence_mcp_adapter.py` 调用已配置 MCP。
- MCP source 的 `arguments` 支持 `${location.label}`、`${location.country_code}`、`${location.latitude}`、`${location.longitude}` 模板。
- 当前地点优先读取 `presence/runtime/location-context.json`；未设置时回退 `world_policy.location_resolution.default_anchor`。
- 地点模板解析前会再次清洗 runtime label；无效地点会回退默认 anchor，防止 `<memory-context>`、换行、超长文本进入天气/Google Maps 参数。
- 当前启用 time、weather、Google Maps、RSS、fetch、filesystem audit、browser snapshot 等 source；是否真实成功取决于对应 MCP server 是否启用、key 是否配置、缓存是否命中。
- 不调用 LLM。
- 将 signals 与 tool calls 写入 `world-signal-events.jsonl` 和 trace。

当前 `world_policy.yaml`：

```yaml
collection:
  default_enabled: true
  prefilter_phase_must_be_non_llm: true
location_resolution:
  enabled: true
  default_anchor:
    label: Shanghai
    country_code: CN
    latitude: 31.2304
    longitude: 121.4737
    confidence: 0.7
  render_visibility_default: oblique_only
signals:
  time_context:
    enabled: true
command_sources: []
mcp_sources:
  - name: shanghai_current_weather
    enabled: true
    phase: prefilter
    server: weather_openmeteo
    tool: get_current_weather
    arguments:
      location: ${location.label}
      country_code: ${location.country_code}
      units: metric
    kind: weather
    sensitivity: public
    policy_decision: auto_allow
    allowed_use: mood_and_share
    cache_ttl_minutes: 45
  - name: shanghai_public_places
    server: google_maps
    tool: maps_search_places
    arguments:
      query: bookstores cafes parks in ${location.label}
      location:
        latitude: ${location.latitude}
        longitude: ${location.longitude}
      radius: 5000
expression_policy:
  public_read_only: may_share_obliquely
  personal_read_only: mood_only
  user_adjacent: timing_only
  actionful: policy_controlled
```

### 11.2 当前 Hermes gateway 已加载的 MCP

`/home/hermes/.hermes/profiles/wx/config.yaml` 中存在并已被 gateway 加载的 MCP：

| server | 当前状态 | 作用 |
| --- | --- | --- |
| `time` | 已加载 | 时间与时区 |
| `fetch` | 已加载 | URL fetch |
| `weather_openmeteo` | 已加载 | 天气 |
| `filesystem_presence` | 已加载 | `/home/hermes` 文件系统 |
| `playwright_browser` | 已加载 | 浏览器/网页交互 |
| `rss_reader` | 已加载 | RSS |

配置中存在但 disabled：

| server | 状态 | 说明 |
| --- | --- | --- |
| `google_maps` | `enabled: false` | 需要 `GOOGLE_MAPS_API_KEY` |
| `google_calendar` | `enabled: false` | 需要 Google OAuth credentials |
| `gmail` | `enabled: false` | 需要 Gmail OAuth 授权 |

Gateway service 的进程树显示已启动：

```text
mcp-server-time
mcp-server-fetch
@cynosure-mcp/weather
@modelcontextprotocol/server-filesystem /home/hermes
@playwright/mcp@latest
@missionsquad/mcp-rss
```

维护注意：

- Hermes 能使用这些 MCP 工具，不代表 Presence Kernel 会自动使用所有 MCP；Presence 只消费 `world_policy.mcp_sources` 中显式启用的 source。
- 当前 Presence Kernel 已有第一版 MCP collector adapter，prefilter 前可采集非 LLM world signal。
- 当前 Observer World Signals 查看的是 collector 写入的 events，不等价于 Hermes gateway 全部 MCP 调用审计。
- 如果只执行 `presence location set 杭州`，天气 MCP 会使用 `location=杭州`；Google Maps 的 query 会变成 `bookstores cafes parks in 杭州`，但经纬度字段会被模板解析器移除。
- 如果执行 `presence location set 30.2741,120.1551 杭州`，Google Maps 会同时获得文本地点和经纬度。
- `location_context` 会写入 MCP tool call 和 world signal trace，便于在 Observer/JSONL 中审计“这次天气/地图信号用了哪个地点”。
- 2026-05-06 已清理一次历史污染：`location-context.json` 被恢复为 `浙江省绍兴市越城区`，相关 runtime/events 原文件备份到 `presence/backups/memory-context-scrub-20260506-172101/`。

## 12. Presence 与 Hindsight

### 12.1 推荐桥接方案

目标：Presence 主动发出的用户可见消息也进入 Hindsight，但不让 cron prompt、decision JSON、trace、tool call、voice design 等内部内容污染长期记忆。

推荐实现点：

1. 以 `conversation/ledger.jsonl` 为唯一输入源，只读取 `source=presence`、`role=assistant`、`visible_to_user=true`、`prompt_visibility.chat_history=true` 的记录。
2. 在 cron successful delivery 后触发一个轻量 ingest worker，或由定时 worker 扫描 ledger 中未 ingest 的 Presence 事件。
3. worker 写入 `conversation/indexes/hindsight-ingested-presence.json`，用 `event_id` 做幂等，避免重启后重复入库。
4. Hindsight 入库内容只包含：真实发送文本、发送时间、conversation_key、message_class、delivery channel；不包含 state/decision/render prompt 和 MCP 原始结果。
5. 入库文案建议压成一条事实：`On <time>, assistant proactively sent to user: "<text>" (class=<message_class>).`
6. 如果 Presence 投递的是 mp3 附件，只入库对应的可见文本或附件说明，不入库 voice design prompt。

建议落点：

```text
/home/hermes/.hermes/hermes-agent/cron/scheduler.py
/home/hermes/.hermes/hermes-agent/gateway/conversation_ledger.py
/home/hermes/.hermes/profiles/wx/presence/runtime/hindsight-presence-ingest-state.json
```

不要把这个桥接放在 `wx-openai-proxy-v2.py`：proxy 只看 OpenAI-compatible 请求，不可靠地知道 Presence 投递是否真的成功；cron/gateway delivery 层才知道“已经对用户可见”。

## 13. TTS / VoiceDesign

### 13.1 当前服务

systemd：

```text
/etc/systemd/system/mimo-tts-proxy.service
```

代理脚本：

```text
/home/hermes/.local/bin/mimo-openai-tts-proxy.py
```

监听：

```text
http://127.0.0.1:8787/v1
```

Hermes 全局配置：

```yaml
tts:
  provider: openai
  openai:
    model: mimo-v2.5-tts-voicedesign
    voice: mimo_default
    base_url: http://127.0.0.1:8787/v1
    response_format: mp3
    voice_compatible: true
    voice_design:
      prompt: 年轻女性中文声线，音色清冷、干净、轻微疲惫但温柔。语速偏慢，停顿自然，句尾轻轻落下，不夸张表演，不客服腔。
```

说明：这里的 `tts.openai.voice_design.prompt` 是 Hermes 通用 TTS 工具的兜底音色，不是 Presence Decision 的动态 `voice_design`。Presence 主动链路以 `delivery_weixin.yaml` 的 `style_reference` 作为参考，由 Decision LLM 每次生成本轮 `natural_language_control`；代码不会再把这个固定 prompt 自动写入 `silent/hesitate` 或空白 voice design。

Linjiang profile delivery speech 配置：

```yaml
speech:
  enabled: true
  provider: openai
  model: mimo-v2.5-tts-voicedesign
  base_url: http://127.0.0.1:8787/v1
  response_format: mp3
  proxy_mode: openai_audio_speech
  voice_design:
    strategy: decision_llm_dynamic
    style_reference: 年轻女性中文声线，音色清冷、干净、轻微疲惫但温柔。语速偏慢，停顿自然，句尾轻轻落下，不夸张表演，不客服腔。
```

### 13.2 代理实现要点

代理接收：

```text
POST /v1/audio/speech
```

对 `mimo-v2.5-tts-voicedesign`：

- 上游使用 `model: mimo-v2.5-tts-voicedesign`
- `audio.format` 使用 `wav` 或 `pcm16`
- 第一条 message 是 voice design prompt
- 第二条 assistant message 是要合成的文本
- 如果调用方要求 `mp3`，代理用 ffmpeg 转码

对普通 `mimo-v2.5-tts`：

- 使用固定 `voice`
- `instructions/style_prompt` 作为朗读风格

### 13.3 当前验证结果

2026-05-05 21:11 手动测试成功：

```bash
curl -sS http://127.0.0.1:8787/v1/audio/speech \
  -H 'Content-Type: application/json' \
  -d '{"model":"mimo-v2.5-tts-voicedesign","voice":"mimo_default","input":"维护测试。","response_format":"mp3","voice_design":"年轻女性中文声线，清冷自然，短句轻声。"}' \
  --output /tmp/presence-maintenance-tts-test.mp3
```

输出为 24 kHz mono mp3。临时测试文件已删除。

### 13.4 当前语音投递边界

当前：

```json
{
  "weixin:o9cq800DQ7ZiX2Y1UbCXVyDq9dkc@im.wechat": "off"
}
```

即 gateway voice mode 对目标会话为 off。

Presence Decision 能输出 `voice_design`，Render 能写 `speech` metadata，但 cron gate 当前只把文本投递给微信。短期不走 gateway voice mode，也不追求原生微信语音条。

新约定：

1. Render 发现 `speech.enabled=true` 且 `delivery_mode=voice_note_candidate|voice_note_preferred`。
2. Presence 调用 `http://127.0.0.1:8787/v1/audio/speech` 生成 mp3。
3. mp3 落盘到 `presence/runtime/audio/`。
4. cron final output 使用 Hermes media 语法：`MEDIA:/absolute/path/to/audio.mp3`。
5. Weixin gateway 通过 iLink 文件附件发送。当前代码里 `ITEM_FILE=4`，mp3 MIME 为 `audio/mpeg` 时 `_outbound_media_builder()` 会构造 `item_list[].type=4` 的文件附件。
6. 失败时 fallback 到 `render.text`。

维护时不要误以为 `speech.enabled=true` 就已经会自动发语音；当前闭环目标是“mp3 附件”，不是原生 voice bubble。

### 13.5 Conversation Ledger 与语音记录

语音附件投递后，后续 `Sanitized Ledger` 应写入一条 assistant event：

```json
{
  "role": "assistant",
  "source": "presence",
  "content": "[语音附件] 今晚先到这儿。晚安。",
  "content_kind": "audio_attachment",
  "delivery": {
    "delivery_kind": "mp3_attachment",
    "ilink_item_type": 4,
    "file_path": "/home/hermes/.hermes/profiles/wx/presence/runtime/audio/..."
  }
}
```

`voice_design` prompt 只进入 TTS 请求和 trace，不进入用户可见 content。

## 14. Observer API

当前核心 API：

| API | 用途 |
| --- | --- |
| `GET /api/health` | Observer 与关键文件健康检查。 |
| `GET /api/profiles` | profile 列表。 |
| `GET /api/profiles/{profile_id}/config` | 读取 profile 配置。 |
| `POST /api/profiles/{profile_id}/config` | 保存 profile 配置，支持 expected sha 和 confirm write。 |
| `GET /api/profiles/{profile_id}/config/backups` | 配置备份列表。 |
| `POST /api/profiles/{profile_id}/config/rollback` | 配置 rollback。 |
| `POST /api/profiles/{profile_id}/validate` | YAML/profile 文件存在性校验。 |
| `GET /api/profiles/{profile_id}/events/{kind}` | 读取 world/tick/state/intent/decision/render/delivery/trace events。 |
| `GET /api/profiles/{profile_id}/runtime/{kind}` | 读取 state/intent/control/trace runtime。 |
| `POST /api/preview/full` | 创建 full dry-run preview 后台 job，不投递，立即返回 `job_id`。 |
| `GET /api/preview/jobs/{job_id}` | 查询 preview job 状态、结果和 trace。 |
| `GET /api/traces` | trace 列表。 |
| `GET /api/traces/{run_id}` | 单个 trace。 |
| `GET /api/world-signals` | world signal 列表。 |
| `POST /api/world-signals/{id}/review` | 事后 review，当前只是写入 review log。 |
| `POST /api/runtime/control` | Presence runtime control。 |
| `GET /api/conversation/ledger` | 读取 sanitized conversation ledger，默认返回最近事件。 |
| `GET /api/conversation/latest` | 读取每个 chat 的最近 ledger 索引。 |

旧 API 仍存在：

- `/api/state/current`
- `/api/state/events`
- `/api/heartbeat/state`
- `/api/heartbeat/control`
- `/api/settings/decision-prompt`

这些读取的是旧文件或旧 prompt，维护时不要用于判断新 Presence Kernel 的实际 decision 状态。

## 15. Config Edit / Backup / Rollback

### 15.1 保存流程

Observer `Profiles` 页面保存配置分两步：

1. 第一次点击 `Save`：后端返回 `diff_required`，给出 old/new sha。
2. 第二次点击 `Confirm Save`：写入文件，并在 `presence/backups/config/` 创建旧版本备份。

后端 endpoint：

```text
POST /api/profiles/{profile_id}/config
```

请求字段：

```json
{
  "kind": "voice",
  "content": "...",
  "expected_sha256": "...",
  "confirm_write": true
}
```

支持 kind：

```text
manifest
persona
relationship
proactive_policy
world_policy
permission_policy
delivery
examples
voice
```

### 15.2 备份命名

备份路径：

```text
/home/hermes/.hermes/profiles/wx/presence/backups/config
```

命名模式：

```text
{profile_id}.{kind}.{timestamp}.{old_sha8}.{ext}
{profile_id}.{kind}.pre-rollback.{timestamp}.{current_sha8}.{ext}
```

当前已有 voice 备份：

```text
linjiang.voice.20260505_205429.ea3a9557.md
linjiang.voice.pre-rollback.20260505_205429.ea3a9557.md
```

### 15.3 Rollback 行为

后端 endpoint：

```text
POST /api/profiles/{profile_id}/config/rollback
```

请求字段：

```json
{
  "kind": "voice",
  "backup_filename": "linjiang.voice.20260505_205429.ea3a9557.md",
  "expected_current_sha256": "...",
  "confirm_rollback": true
}
```

行为：

- 校验 kind 支持。
- 校验 backup filename 不允许路径穿越。
- 校验 backup 属于当前 profile/kind。
- 校验 YAML 或 voice text 格式。
- 如果提供 expected current sha，不一致则 409。
- rollback 前创建 `pre-rollback` 当前文件备份。
- 原子写入目标配置。
- 写入 `observer-control-events.jsonl` audit event。

### 15.4 Curl 示例

读取配置：

```bash
curl -sS http://127.0.0.1:8790/api/profiles/linjiang/config | python3 -m json.tool
```

列出 voice 备份：

```bash
curl -sS 'http://127.0.0.1:8790/api/profiles/linjiang/config/backups?kind=voice' | python3 -m json.tool
```

校验 profile：

```bash
curl -sS -X POST http://127.0.0.1:8790/api/profiles/linjiang/validate | python3 -m json.tool
```

## 16. 事件与 Runtime 文件

Runtime：

| 文件 | 用途 |
| --- | --- |
| `presence/runtime/state.json` | 新 State 当前快照。 |
| `presence/runtime/intent-state.json` | intent accumulator 与 delivery counters。 |
| `presence/runtime/last-trace.json` | 最近生产 trace。Preview dry-run 使用 `preview-last-trace.json`。 |
| `presence/runtime/control.json` | Presence runtime control，如果创建。 |
| `presence/runtime/world-signal-reviews.jsonl` | World signal review 记录，如果创建。 |

Conversation ledger：

| 文件 | 用途 |
| --- | --- |
| `conversation/ledger.jsonl` | 用户可见 inbound/outbound 的 append-only 事实层；dry-run/silent/internal prompt 不写入。 |
| `conversation/indexes/latest-by-chat.json` | 每个 chat 最近 ledger event 索引。 |
| `conversation/indexes/latest-presence-by-chat.json` | 每个 chat 最近 Presence delivery 索引。 |
| `conversation/schemas/ledger-event.schema.json` | ledger event schema。 |

Events：

| 文件 | 用途 |
| --- | --- |
| `world-signal-events.jsonl` | world collector 每次采集。 |
| `tick-events.jsonl` | tick/prefilter 事件。 |
| `state-events.jsonl` | State LLM 输出。 |
| `continuity-events.jsonl` | State 生成的 private continuity events。 |
| `intent-events.jsonl` | intent decay/update。 |
| `decision-events.jsonl` | Decision LLM 输出。 |
| `render-events.jsonl` | Render 输出。 |
| `delivery-events.jsonl` | 实际 would_deliver 后记录。当前未看到有效 delivery event。 |
| `trace-events.jsonl` | 全链路 trace。 |

查看最近事件：

```bash
tail -n 5 /home/hermes/.hermes/profiles/wx/presence/events/tick-events.jsonl
tail -n 3 /home/hermes/.hermes/profiles/wx/presence/events/decision-events.jsonl
tail -n 3 /home/hermes/.hermes/profiles/wx/presence/events/render-events.jsonl
tail -n 3 /home/hermes/.hermes/profiles/wx/presence/events/trace-events.jsonl
```

## 17. 备份

### 17.1 一步到位重构前备份

本轮 Prompt First + Sanitized Ledger 改造前备份：

```text
/home/hermes/.hermes/backups/presence-ledger-prompt-first-20260506-024440
```

覆盖：

- `/home/hermes/.hermes/profiles/wx/`（排除递归 wx backups）
- `/home/hermes/.hermes/hermes-agent/gateway/`
- `/home/hermes/hermes-observer/`
- 当前维护/方案文档
- `SHA256SUMS`

当前完整备份：

```text
/home/hermes/.hermes/profiles/wx/backups/presence-kernel-direct-20260505-190355
```

包含：

- `profile-wx/`
- `hermes-observer/`
- `linjiang-heartbeat-improvement-feasibility-assessment.md`
- `SHA256SUMS`

`SHA256SUMS` 存在：

```text
/home/hermes/.hermes/profiles/wx/backups/presence-kernel-direct-20260505-190355/SHA256SUMS
```

校验：

```bash
cd /home/hermes/.hermes/profiles/wx/backups/presence-kernel-direct-20260505-190355
sha256sum -c SHA256SUMS
```

### 17.2 创建新的全量维护备份

建议命令：

```bash
export BACKUP_ROOT="/home/hermes/.hermes/profiles/wx/backups/presence-maintenance-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$BACKUP_ROOT"
rsync -a /home/hermes/.hermes/profiles/wx/ "$BACKUP_ROOT/profile-wx/"
rsync -a --exclude node_modules /home/hermes/hermes-observer/ "$BACKUP_ROOT/hermes-observer/"
cp /home/hermes/presence-kernel-current-maintenance.md "$BACKUP_ROOT/"
find "$BACKUP_ROOT" -type f -print0 | sort -z | xargs -0 sha256sum > "$BACKUP_ROOT/SHA256SUMS"
```

## 18. 日志轮转与存储

当前 `/etc/logrotate.d/linjiang-heartbeat` 覆盖：

```text
/home/hermes/.hermes/profiles/wx/proxy-requests.jsonl
/home/hermes/.hermes/profiles/wx/decision-events.jsonl
/home/hermes/.hermes/profiles/wx/linjiang-state-events.jsonl
/home/hermes/.hermes/profiles/wx/observer-control-events.jsonl
/home/hermes/.hermes/profiles/wx/linjiang-state-tick.log
```

策略：

- daily
- rotate 14
- compress
- copytruncate
- create 0640 hermes hermes

当前未覆盖 Presence Kernel 新事件：

```text
/home/hermes/.hermes/profiles/wx/presence/events/*.jsonl
```

建议新增 logrotate 覆盖 presence events，否则 `trace-events.jsonl`、`state-events.jsonl` 会持续增长。

## 19. 安全与权限

当前敏感配置权限：

| 文件 | 权限 |
| --- | --- |
| `config.yaml` | `600 hermes:hermes` |
| `.env` | `600 hermes:hermes` |
| `linjiang-llm.env` | `600 hermes:hermes` |
| `cron/jobs.json` | `600 hermes:hermes` |

维护原则：

- 不把 `config.yaml`、`.env`、`linjiang-llm.env` 内容完整粘贴到聊天或文档。
- `config.yaml` 当前 `security.redact_secrets=false`，如果希望更稳，应评估改为 `true`。
- Observer 写入已开启，公网访问必须依赖 Cloudflare Access 或等效保护。
- MCP `filesystem_presence` 当前根目录是 `/home/hermes`，能力很大；如果要更精细，应收窄到 Presence 相关目录。

## 20. 常用巡检

服务状态：

```bash
systemctl status hermes-gateway-wx.service wx-openai-proxy.service mimo-tts-proxy.service linjiang-observer-backend.service --no-pager -l
```

端口：

```bash
ss -ltnp | rg '(:8787|:8788|:8789|:8790|:9119)'
```

Observer health：

```bash
curl -sS http://127.0.0.1:8790/api/health | python3 -m json.tool
```

Profile validate：

```bash
curl -sS -X POST http://127.0.0.1:8790/api/profiles/linjiang/validate | python3 -m json.tool
```

Preview：

```bash
JOB_ID="$(curl -sS -X POST http://127.0.0.1:8790/api/preview/full \
  -H 'Content-Type: application/json' \
  -d '{"profile_id":"linjiang","mode":"full","force_llm":true}' \
  | python3 -c 'import json,sys; print(json.load(sys.stdin)["job_id"])')"

curl -sS "http://127.0.0.1:8790/api/preview/jobs/${JOB_ID}" | python3 -m json.tool
```

如需本机同步调试，可以临时加 `"sync": true`。不要通过公网 Cloudflare 页面使用同步模式，否则长请求仍可能触发 524：

```bash
curl -sS -X POST http://127.0.0.1:8790/api/preview/full \
  -H 'Content-Type: application/json' \
  -d '{"profile_id":"linjiang","mode":"full","force_llm":true,"sync":true}' | python3 -m json.tool
```

Presence direct dry-run：

```bash
python3 /home/hermes/.hermes/profiles/wx/scripts/presence_tick.py --dry-run --force-llm
```

MCP gateway 进程：

```bash
systemctl status hermes-gateway-wx.service -l --no-pager | rg 'mcp|weather|filesystem|playwright|rss|fetch|time'
```

LLM proxy stats：

```bash
curl -sS http://127.0.0.1:8790/api/proxy/stats | python3 -m json.tool
```

TTS 代理测试：

```bash
curl -sS http://127.0.0.1:8787/v1/audio/speech \
  -H 'Content-Type: application/json' \
  -d '{"model":"mimo-v2.5-tts-voicedesign","voice":"mimo_default","input":"测试一下语音合成。","response_format":"mp3","voice_design":"年轻女性中文声线，清冷自然，短句轻声。"}' \
  --output /tmp/mimo-test.mp3
ls -lh /tmp/mimo-test.mp3
file /tmp/mimo-test.mp3
```

Frontend build：

```bash
cd /home/hermes/hermes-observer/frontend
npm run build
systemctl restart linjiang-observer-backend.service
```

Python compile：

```bash
python3 -m compileall -q /home/hermes/.hermes/profiles/wx/presence/kernel /home/hermes/hermes-observer/backend/app
```

## 21. 当前验证记录

本次维护文档生成前完成的检查：

| 项目 | 结果 |
| --- | --- |
| `linjiang-observer-backend.service` | active/running |
| `hermes-gateway-wx.service` | active/running |
| `wx-openai-proxy.service` | active/running |
| `mimo-tts-proxy.service` | active/running |
| Observer `/api/health` | ok |
| `GET /api/profiles` | 返回 `linjiang` |
| `POST /api/profiles/linjiang/validate` | ok |
| `presence_tick.py --dry-run --force-llm` | 成功，结果 silent |
| State prompt 输出字段 | 包含 `interaction_analysis`、`private_continuity_events` |
| Decision prompt 输出字段 | 包含 `render_brief`、`voice_design` |
| Sanitized ledger 冒烟 | unbound Presence event 可合并进同一 chat 的普通 history；其他 session event 不串入 |
| ledger 污染检查 | 未发现 `Cronjob Response`、script output、State/Decision prompt 泄漏到 ledger/runtime |
| Python compileall | ok |
| Observer frontend `npm run build` | ok，有 chunk size warning |
| MiMo TTS VoiceDesign curl 测试 | 成功生成 mp3 |

Frontend build warning：

```text
Some chunks are larger than 500 kB after minification.
```

这只是构建体积提示，不影响当前运行。

## 22. 已知问题与建议优先级

### P0：修复 stochastic prefilter（已完成）

问题：

- `_age_minutes()` 没有正确解析时间。
- 所有 tick 都可能走 `state_age_force_llm`。
- 造成 token 成本和行为确定性上升。

处理：

- 修正 `_age_minutes()`。
- 移除 `restore_runtime_for_dry_run()` 尾部误放代码。
- 已验证 20 次 prefilter 计算出现 skip 分布，示例结果：13 skip / 7 pass。

### P1：清理旧 crontab state tick（已完成）

问题：

- 用户 crontab 仍每小时跑旧 `wx-linjiang-state-tick.sh`。
- 这会更新旧 state 文件，干扰旧 API/旧 Dashboard 判断。

处理：

- 备份 crontab。
- 注释旧行。
- 观察 `linjiang-state-tick.log` 不再增长。

### P1：完善 Preview dry-run 隔离（已完成）

问题：

- dry-run 曾经会追加事件并覆盖 `last-trace.json`。
- Observer 如果显示 latest trace，可能混入 preview。

处理：

- runtime snapshot 覆盖 `last-trace.json`。
- dry-run trace 写入 `preview-events.jsonl`，runtime trace 写入 `preview-last-trace.json`。
- 所有 latest API 默认过滤 dry-run。

### P1：打通语音投递闭环（部分完成）

问题：

- TTS 代理和 `voice_design` metadata 已可用。
- 当前 cron gate 只输出文本，不会自动变成语音或媒体附件。

处理：

- Decision/Render 已输出 MiMo VoiceDesign 结构化字段：`natural_language_control`、`assistant_style_tags`、`tts_request`。`delivery_weixin.yaml` 中的 `style_reference` 只是动态设计参考，不再作为 normalization fallback 写入 silent/hesitate trace。
- 本地 `mimo-tts-proxy.service` 已验证可用 `voice_design` 生成 mp3。
- 新闭环方案：Presence 直接生成 mp3，并让 cron final output 追加 `MEDIA:/abs/path.mp3`。
- Weixin iLink 发送走文件附件：`item_list[].type=4`。不要求原生语音条。
- 待实现 mp3 文件生成、保留期清理、fallback 文本、ledger delivery 记录。
- Observer Preview 增加音频试听。

### P1：打通 Presence outbound 与普通微信会话上下文（核心链路已完成）

问题：

- Presence cron 发出的用户可见消息当前落在 cron session。
- 普通 inbound chat 的 `messages` 不自动包含最近 Presence outbound。
- 用户回复主动消息时，模型可能只看到旧普通会话上下文。
- Presence State/Decision 通过 raw session 扫描能看到 cron session，但会混入 cron 内部 prompt/script output。

处理方案：

- 方案文档：`/home/hermes/presence-sanitized-ledger-implementation-plan.md`。
- 新增 wx profile conversation 层：`/home/hermes/.hermes/profiles/wx/conversation/ledger.jsonl`。
- cron / Presence delivery 成功后由 `cron/scheduler.py` 写入 sanitized assistant event。
- 普通 inbound/outbound 由 gateway 写入同一 ledger。
- streaming 普通 outbound 已补写 ledger，避免流式发送绕过 `base.py`。
- 普通 chat prompt 由 gateway 按 `conversation_key + session_epoch_id + profile scope` 合并 ledger；未绑定 epoch 的 Presence event 允许在同一 `conversation_key + profile_id` 下进入下一轮普通 chat history。
- Presence `conversation_context()` 已改读 sanitized ledger，不再读 raw cron session。
- 所有时间判断基于真实本地时间；不再设置 `scene_ttl_minutes`，由 State/Decision 判断互动缺口、未收口 open loop 和缺口内 profile 私有连续事件。

### P2：Presence world collector 接入 MCP（已完成第一版）

问题：

- Hermes gateway 已加载 MCP。
- Presence collector 仍只采本地时间。

处理：

- 新增 MCP collector adapter。
- 将 tool call、参数摘要、结果摘要写入 `trace-events.jsonl` 和 `world-signal-events.jsonl`。
- `world_policy.yaml` 已启用 `weather_openmeteo.get_current_weather`，并带 TTL 缓存。
- Observer World Signals 可通过事件查看完整调用链和使用位置。

### P2：实现 `counts_toward_normal_send`（已完成）

问题：

- 配置已有该字段。
- Python cooldown 当前未聚合 normal_send 计数。

处理：

- `record_delivery()` 写入 class counter 后，如 `counts_toward_normal_send=true` 同时写入 normal bucket 或 aggregate view。
- `cooldown_status()` 同时检查自身 bucket 和 aggregate bucket。

### P2：新增 Presence event logrotate（待 root 权限）

问题：

- `/presence/events/*.jsonl` 当前未纳入 `/etc/logrotate.d/linjiang-heartbeat`。

处理：

- 增加 presence events 文件匹配。
- 保持 daily/rotate 14/copytruncate。
- 当前 `/etc/logrotate.d/linjiang-heartbeat` 为 root-owned，当前用户无免密 sudo，尚未写入。

### P2：修正 Observer 手动触发入口（已完成）

问题：

- `POST /api/heartbeat/trigger` 当前查找 `/home/hermes/.hermes/profiles/wx/scripts/presence_tick.py`。
- 该文件存在，但权限是 `664`，不是 executable。
- API 里有 `os.access(script_path, os.X_OK)` 检查，即使后续用 `python3 script_path` 执行，也会先返回 “not executable”。
- `POST /api/state/trigger` 没有这个 executable 检查，所以行为不一致。

处理：

- 已删除 `/api/heartbeat/trigger` 的 `X_OK` 检查，只检查文件存在与可读。
- 旧命名 `heartbeat/state trigger` 后续可再统一改成 Presence 语义，避免误导。

### P3：Observer 旧页面/API 去噪

问题：

- 旧 Dashboard 仍引用旧接口与旧文件。
- 新导航未暴露旧 Dashboard，但代码仍在。

处理：

- 移除旧 Dashboard 或明确标记 Legacy。
- 旧 API 返回时增加 `legacy: true`。

## 23. 新建测试 profile 流程

目标是验证 kernel 与特定人设解耦。

复制林绛 profile：

```bash
cp -a /home/hermes/.hermes/profiles/wx/presence/profiles/linjiang \
  /home/hermes/.hermes/profiles/wx/presence/profiles/testprofile
```

修改：

```text
manifest.yaml: profile_id/display_name
profile_metadata.yaml: name/language/channel
SOUL.md 前七部分：角色身份权威内容
voice.md
relationship.yaml
examples.yaml
delivery_weixin.yaml
```

validate：

```bash
curl -sS -X POST http://127.0.0.1:8790/api/profiles/testprofile/validate | python3 -m json.tool
```

preview：

```bash
JOB_ID="$(curl -sS -X POST http://127.0.0.1:8790/api/preview/full \
  -H 'Content-Type: application/json' \
  -d '{"profile_id":"testprofile","mode":"full","force_llm":true}' \
  | python3 -c 'import json,sys; print(json.load(sys.stdin)["job_id"])')"

curl -sS "http://127.0.0.1:8790/api/preview/jobs/${JOB_ID}" | python3 -m json.tool
```

不要直接把测试 profile 加入 cron，除非已经确认 delivery 通道和 profile 目标不会误投递。

## 24. 故障排查速查

### Cron 没跑

检查：

```bash
systemctl status hermes-gateway-wx.service -l --no-pager
cat /home/hermes/.hermes/profiles/wx/cron/jobs.json | python3 -m json.tool
ls -lt /home/hermes/.hermes/profiles/wx/cron/output/presence001 | head
```

### Cron 跑了但不投递

检查：

```bash
tail -n 20 /home/hermes/.hermes/profiles/wx/presence/events/render-events.jsonl
tail -n 20 /home/hermes/.hermes/profiles/wx/presence/events/decision-events.jsonl
```

如果 `render.type=silent` 或 `wakeAgent=false`，这是正常 skip。

### 每 15 分钟都在烧 LLM

检查：

```bash
tail -n 20 /home/hermes/.hermes/profiles/wx/presence/events/tick-events.jsonl | rg 'state_age_force_llm|stochastic_skip'
```

如果持续 `state_age_force_llm` 且 `state_age_minutes=null`，就是 `_age_minutes()` bug。

### Observer 页面不更新

检查：

```bash
curl -sS http://127.0.0.1:8790/api/health | python3 -m json.tool
journalctl -u linjiang-observer-backend.service -n 80 -o cat --no-pager
cd /home/hermes/hermes-observer/frontend && npm run build
systemctl restart linjiang-observer-backend.service
```

### Config 保存失败

常见原因：

- YAML 语法错误。
- expected sha 冲突。
- `confirm_write=false` 只返回 diff_required，不会写入。

处理：

```bash
curl -sS -X POST http://127.0.0.1:8790/api/profiles/linjiang/validate | python3 -m json.tool
```

### TTS 不工作

检查：

```bash
systemctl status mimo-tts-proxy.service -l --no-pager
journalctl -u mimo-tts-proxy.service -n 100 -o cat --no-pager
ss -ltnp | rg ':8787'
```

直接 curl 测试 `/v1/audio/speech`。

### MCP 不加载

检查：

```bash
systemctl restart hermes-gateway-wx.service
journalctl -u hermes-gateway-wx.service -n 150 -o cat --no-pager | rg 'mcp|MCP|weather|filesystem|playwright|rss|fetch|time'
```

Hermes 运行中修改 MCP 配置后，优先用 Hermes 自身 `/reload-mcp` 能力；如果没有交互入口，则重启 gateway。

## 25. 维护原则

1. 先备份，再改配置或 cron。
2. 不把 profile 配置和 runtime 混为一谈：`profiles/linjiang` 是配置，`runtime/` 是当前状态，`events/` 是审计流水。
3. 不用旧 `linjiang-internal-state.json` 判断新 Presence Kernel。
4. Preview 永远 dry-run，不应投递。
5. 真正投递只看 Hermes cron `presence001` 和 `render.type`。
6. 修复 prefilter 前，谨慎增加任何高频 collector 或外部工具调用。
7. 语音功能按“VoiceDesign metadata + mp3 附件闭环”维护：短期走 iLink `item_list[].type=4` 文件附件，不承诺原生语音条。
8. 普通聊天与 Presence 的共享上下文以后以 sanitized ledger 为准；不要把 raw cron session prompt/script output 当作聊天历史。
9. MCP 工具权限当前很大，新增真实世界 collector 时必须把调用链写入 trace，方便 Observer 审计。
