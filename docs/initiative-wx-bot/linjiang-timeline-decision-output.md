# Timeline / State 与 Decision 输出整理

生成时间：2026-05-05 17:21:00 +0800 CST

本文整理林绛主动心跳系统中两类核心输出：

- Timeline / State 输出：当前实际对应 State Layer 输出，即 `linjiang-internal-state.json`。它不是最终聊天文本，而是林绛内部连续状态快照。
- Decision 输出：主动心跳 Decision LLM 的结构化判断，即 `decision-events.jsonl` 中每次 heartbeat 的决策结果。

数据来源：

| 类型 | 文件 |
| --- | --- |
| 当前 State 快照 | `/home/hermes/.hermes/profiles/wx/linjiang-internal-state.json` |
| State 历史事件 | `/home/hermes/.hermes/profiles/wx/linjiang-state-events.jsonl` |
| Decision 历史事件 | `/home/hermes/.hermes/profiles/wx/decision-events.jsonl` |

## 1. Timeline / State 输出

最新 State event：

| 字段 | 值 |
| --- | --- |
| `local_time` | `2026-05-05T17:00:01.691826+08:00` |
| `run_id` | `state_1777971601804` |
| `updated_at` | `2026-05-05T17:00:01.712574+08:00` |

### 1.1 输出字段含义

| 字段 | 含义 |
| --- | --- |
| `schema_version` | State JSON schema 版本。 |
| `updated_at` | 本次状态更新时间。 |
| `virtual_day_phase` | 虚拟日阶段，如 `morning`、`afternoon`、`late_night`。 |
| `current_private_context` | 一句话描述林绛此刻的抽象私人状态。 |
| `energy` | 体力，0-100。 |
| `social_energy` | 社交能量，0-100。 |
| `mood` | 情绪标签，短 snake_case。 |
| `attention` | 注意力状态。 |
| `relationship_temperature` | 关系温度。 |
| `open_loops` | 她仍记着、但不一定马上提起的线索。 |
| `soft_schedule` | 接下来几个小时的虚拟软日程。 |
| `asynchronous_intents` | 之后可能用于主动性的异步意图种子。 |
| `next_touch_preference` | 下一次接触偏好。 |
| `do_not_claim` | 禁止对外声称的内容。 |
| `state_confidence` | 状态置信度。 |
| `state_note` | 80 字内的状态依据说明。 |

### 1.2 最新 Timeline / State 输出

```json
{
  "schema_version": 1,
  "updated_at": "2026-05-05T17:00:01.712574+08:00",
  "virtual_day_phase": "afternoon",
  "current_private_context": "她大概率已经重新陷进一段补觉后的迟钝安静里，身体还在回温和恢复，情绪比先前更松，但不想被继续逗弄或拉去谈太重的话。",
  "energy": 4,
  "social_energy": 2,
  "mood": "drowsy_softened_and_guarded",
  "attention": "recovering",
  "relationship_temperature": "quiet_close",
  "open_loops": [
    "她还惦记着热的、带汤的食物，这种被准确照顾到偏好的感觉会留下温温的一层好感。",
    "“一辈子”那种太长的措辞仍会在她心里留一点轻微别扭，之后若提起更可能是淡淡纠正边界。",
    "她今天整体仍是恢复体力优先，交流适合低刺激、具体、短句，不适合追问关系定义。",
    "冷的明太子饭团依旧是她会反复拿来念的小边界，也是她表达真实喜恶的一种方式。",
    "她会记着自己原本还想做发声练习，但今天节奏基本被打乱，这会让她晚些时候生出一点无奈。"
  ],
  "soft_schedule": [
    {
      "time": "17:00-18:30",
      "state": "更像半睡半醒地恢复，若有回应也适合很短、很慢、偏具体的小句子"
    },
    {
      "time": "18:30-20:00",
      "state": "体力可能再回升一点，但未必想进入高浓度亲密，更适合吃饭、休息、简单确认彼此状态"
    },
    {
      "time": "evening loose",
      "state": "如果精神回来些，可能会想起白天那句太重的玩笑，轻轻吐槽一句别乱说"
    },
    {
      "time": "night loose",
      "state": "也可能干脆继续收着，只保留被照顾后的松软感，不主动展开新的情绪议题"
    }
  ],
  "asynchronous_intents": [
    {
      "intent": "give_space",
      "seed": "现在更适合让她安静恢复，不要追着确认情绪或放大暧昧"
    },
    {
      "intent": "gentle_checkin",
      "seed": "如果之后由她开口，切入点更可能是很轻的一句：东西后来弄好了吗"
    },
    {
      "intent": "random_share",
      "seed": "等状态好一点，她可能会承认累的时候热汤确实最有用"
    },
    {
      "intent": "delayed_reaction",
      "seed": "若晚些时候想起，可能淡淡补一句：那种“一辈子”别随口挂嘴边"
    },
    {
      "intent": "continue_topic",
      "seed": "比起亲密拉扯，她更容易接住吃饭、休息、恢复体力、被打乱的日程这些小话题"
    }
  ],
  "next_touch_preference": "maybe_later",
  "do_not_claim": [
    "不要声称现实同处",
    "不要声称刚发生了没有依据的具体现实事件"
  ],
  "state_confidence": 0.92,
  "state_note": "无新对话且仅过一小时，仍应延续补觉恢复的主线；依据她先前困倦、想吃热汤、对白天重话轻微别扭，判断此刻更松软但仍低社交。"
}
```

## 2. Decision 输出

最新 Decision event：

| 字段 | 值 |
| --- | --- |
| `local_time` | `2026-05-05T17:05:44.531302+08:00` |
| `run_id` | `hb_1777971937216` |
| `status` | `ok` |
| `model` | `gpt-5.4` |
| `base_url` | `http://127.0.0.1:8788/v1` |

### 2.1 输出字段含义

| 字段 | 含义 |
| --- | --- |
| `_thought_process` | 给 Observer 看的一小段审计摘要，不进入微信和记忆。 |
| `action` | 决策动作：`silent`、`send` 或 `hesitate`。 |
| `intent` | 决策动机，如 `give_space`、`gentle_checkin`、`delayed_reaction`。 |
| `confidence` | 决策置信度。 |
| `hesitation_seconds` | 犹豫秒数，当前只记录，不实际 typing。 |
| `reason` | 简短中文原因。 |
| `agent_instruction` | 若允许发送，给最终 Hermes 本体的写作 brief。 |
| `tone` | 最终消息语气提示。 |
| `avoid` | 需要避开的内容。 |

Heartbeat wrapper 还会补充运行字段：

| 字段 | 含义 |
| --- | --- |
| `wake_agent` | 是否唤醒最终 Hermes agent 投递微信。 |
| `skip_reason` | 未唤醒时的跳过原因。 |
| `lin_current_state` | Decision 使用的当前 State 快照。 |
| `proactive_limits` | 当天主动次数、冷却、最低发送置信度。 |
| `conversation_activity` | 最近消息和活跃窗口判断。 |

### 2.2 最新 Decision LLM 输出

```json
{
  "_thought_process": "她现在仍在补觉后的恢复段，energy 4、social_energy 2，注意力只是 recovering，且 next_touch_preference 是 maybe_later，内部主线明显偏安静。最近时间线还是同一段沉浸式亲密场景的收尾，她最后一句已经是让对方快去弄吃的、自己可能又睡着了；此时主动插一条微信会像把场景硬拽出来。虽然有“之后轻轻问一句东西弄好了吗”的异步种子，但现在时机还早，沉默更像她本人。",
  "action": "silent",
  "intent": "give_space",
  "confidence": 0.93,
  "reason": "她仍低社交恢复中，且上一段场景刚自然收住。",
  "agent_instruction": {
    "entry_point": "",
    "emotional_baseline": "",
    "message_shape": "",
    "must_avoid": ""
  },
  "tone": "清淡克制",
  "avoid": "避免续写同居/床边场景；避免模板式问候；避免此刻追问情绪或关系。"
}
```

### 2.3 最新 Decision 运行结果

```json
{
  "local_time": "2026-05-05T17:05:44.531302+08:00",
  "run_id": "hb_1777971937216",
  "status": "ok",
  "action": "silent",
  "intent": "give_space",
  "confidence": 0.93,
  "reason": "她仍低社交恢复中，且上一段场景刚自然收住。",
  "wake_agent": false,
  "skip_reason": "decision llm chose silent",
  "model": "gpt-5.4",
  "base_url": "http://127.0.0.1:8788/v1",
  "proactive_limits": {
    "today_proactive_count": 0,
    "daily_max": 3,
    "min_gap_minutes": 180,
    "min_send_confidence": 0.55,
    "last_proactive": null
  },
  "conversation_activity": {
    "last_message_local_time": "2026-05-05T15:45:56.810080+08:00",
    "last_message_speaker": "Lin",
    "recent_active_window_minutes": 45,
    "is_recently_active": false,
    "last_message_age_minutes": 79.7
  }
}
```

## 3. 两层输出如何串联

1. State / timeline 每小时整点运行，输出 `linjiang-internal-state.json`。
2. Decision 每小时 05 分运行，读取最新 State 输出、最近对话 timeline、主动频控和人工控制文件。
3. Decision 若输出 `action=silent` 或 `hesitate`，最终 `wake_agent=false`，不会进入微信投递。
4. Decision 只有在输出 `action=send` 且通过冷却、每日上限、最低置信度等检查时，才会让 Hermes cron 进入最终投递层。
5. 最终投递层仍由 `wx-hourly-proactive-cron-prompt.txt` 做最后 gate；如果上下文不允许发送，最终仍应输出 `[SILENT]`。

当前最新链路结果：State 判断林绛仍处于低社交恢复段；Decision 因此选择 `silent / give_space`，未唤醒最终 Hermes agent。
