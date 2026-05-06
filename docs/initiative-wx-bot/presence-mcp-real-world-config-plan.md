# Presence Kernel 真实世界 MCP 配置方案

更新时间：2026-05-05

## 已落到 wx profile 的 MCP

配置位置：`/home/hermes/.hermes/profiles/wx/config.yaml`

当前已加入这些默认可启动的 MCP server：

| server | 用途 | 配置状态 |
| --- | --- | --- |
| `time` | 时区、墙钟时间、节律判断 | enabled |
| `fetch` | 抓取公开网页、RSS 页面、轻量信息源 | enabled |
| `weather_openmeteo` | Open-Meteo 天气，免 API key | enabled |
| `filesystem_presence` | 读取/编辑本机文件、Presence 配置、审计材料 | enabled |
| `playwright_browser` | 浏览器级页面观察、复杂网页、截图式审计 | enabled |
| `rss_reader` | RSS/Atom 信息流、公开新闻订阅 | enabled |

这些 server 会在 Hermes wx gateway 启动或 MCP reload 时注册成工具，工具名按 Hermes 规则变成：

```text
mcp_{server_name}_{tool_name}
```

例如 `time` server 的工具会以 `mcp_time_*` 前缀出现。

## 需要凭据后启用的 MCP

以下配置也已写入 `config.yaml`，但默认 `enabled: false`，避免缺凭据时启动失败。

| server | 价值 | 启用前准备 |
| --- | --- | --- |
| `google_maps` | 地点、距离、路线、周边 POI | 设置 `GOOGLE_MAPS_API_KEY` |
| `google_calendar` | 日程、空闲时间、日历事件 | 准备 Google Calendar OAuth desktop credentials |
| `gmail` | 邮件摘要、提醒、收件箱线索 | 完成 Gmail OAuth autoauth |

启用方式是在 Observer 的 Profiles 里编辑 wx `config.yaml`，或直接改文件，将对应 server 的 `enabled: false` 改为 `true`。重启 `hermes-gateway-wx.service` 或等待 Hermes MCP reload。

## Presence Kernel 使用原则

这些 MCP 不作为林绛补丁存在，而是 Hermes profile 能力。Presence Kernel 只读取 profile 配置和 trace，不在通用 Python kernel 里硬编码某个人设。

建议的真实世界信号分层：

| 信号 | 首选 MCP | Presence 用法 |
| --- | --- | --- |
| 当前时间、节气、时区 | `time` | 影响节律、疲惫、是否适合 micro_send |
| 天气 | `weather_openmeteo` | 作为生活锚点，可进入 World Signals |
| 公开网页/新闻/RSS | `fetch`, `rss_reader` | 产生可审计的 public signal |
| 复杂网页/动态页面 | `playwright_browser` | 截图、页面交互、公开信息核验 |
| 本机配置和日志 | `filesystem_presence` | Observer 审计、配置编辑、回滚辅助 |
| 位置/路线/地点 | `google_maps` | 只在配置授权后作为时机或生活信号 |
| 日历/邮件 | `google_calendar`, `gmail` | 默认进入审计 trace，是否外显由 profile policy 决定 |

## 审计要求

所有真实世界交互都应该进入 Observer 的 trace：

```text
World -> State -> Intent -> Decision -> Render -> Delivery
```

后续如果把 MCP 调用接进 `presence_world_collector.py`，不要让 State/Decision 直接吞掉工具调用。每个 call 至少记录：

```json
{
  "tool": "mcp_weather_openmeteo_get_current_weather",
  "args_summary": "...",
  "result_summary": "...",
  "used_by": ["state", "decision", "render"],
  "sensitivity": "public|personal|user_adjacent",
  "policy_decision": "auto_allow|internal_only|blocked"
}
```

## Config Rollback

Config rollback 是 Observer 的配置回滚功能：每次保存 profile 配置前，后端会把旧版本写进 `presence/backups/config/`。现在 Profiles 页面可以选择某个备份并执行二次确认回滚。

回滚动作会：

1. 校验备份属于当前 `profile_id + kind`。
2. 校验备份内容仍是合法 YAML/Markdown。
3. 校验当前 SHA，避免覆盖别人刚保存的新版本。
4. 回滚前再备份一次当前版本。
5. 写入 audit event，方便后续在 Observer 查看。
