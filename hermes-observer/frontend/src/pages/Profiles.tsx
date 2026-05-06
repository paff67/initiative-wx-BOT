import { useEffect, useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { CheckCircle2, Plus, RotateCcw, Save, Trash2 } from 'lucide-react';
import YAML from 'yaml';
import {
  fetchProfileConfig,
  fetchProfileConfigBackups,
  fetchProfiles,
  postProfileConfig,
  postProfileConfigRollback,
  postProfileValidate,
} from '../api/client';
import { EmptyState, KeyValue, PageHeader, Panel, Pill, formatDateTime, shortId } from '../lib/presenceView';

const kinds = ['manifest', 'profile_metadata', 'relationship', 'proactive_policy', 'world_policy', 'permission_policy', 'delivery', 'examples', 'voice'];

const kindLabels: Record<string, string> = {
  manifest: '清单',
  profile_metadata: '元数据',
  relationship: '关系',
  proactive_policy: '主动策略',
  world_policy: '世界信号',
  permission_policy: '权限',
  delivery: '投递',
  examples: '示例',
  voice: '文字语气',
};

type PathPart = string | number;
type VoiceSection = { id: string; level: number; title: string; body: string };

const exactPurpose: Record<string, string> = {
  'name': 'Profile 的人类可读名称，只用于界面显示和日志辨认。真正的人设细节仍以 SOUL.md 前七部分为准。',
  'language': '该 profile 默认使用的语言。比如 zh-CN 会让界面和消息默认按中文语境处理，但不改变角色设定。',
  'display_name': '显示在 Observer、日志和 profile 选择器里的名称。改成“测试人格”后，运行链路仍相同，但操作台会用新名称区分实例。',
  'channel': '指定路由和投递通道。比如 weixin 表示 Render 生成微信适配输出；改成其他通道需要对应 Delivery adapter 支持。',
  'timezone': '真实本地时间、互动间隔和昼夜节律都按这里计算。比如从 Asia/Shanghai 改成 America/New_York 后，凌晨静默和午后疲惫判断会整体换时区。',
  'cadence.schedule': 'cron 入口的基础频率。比如 every 15m 表示每 15 分钟进入一次轻量 tick，但是否跑 LLM 还要看随机预筛。',
  'cadence.stochastic_prefilter.enabled': '启用后，每个 tick 会先掷骰子决定是否进入 State/Decision LLM；关闭后更像机械巡检，token 成本和主动性都会上升。',
  'cadence.stochastic_prefilter.base_wake_probability': '基础唤醒概率。0.22 表示普通 tick 大约 22% 机会继续跑 LLM，调到 0.5 会明显更频繁地思考和产生日志。',
  'cadence.stochastic_prefilter.min_probability': '唤醒概率下限。即使最近很安静或刚活跃过，也不会低于这个值；调高会减少“长时间懒得醒”的情况。',
  'cadence.stochastic_prefilter.max_probability': '唤醒概率上限。即使有世界信号或意图张力，也不会超过这里；调低可避免密集触发。',
  'cadence.stochastic_prefilter.skip_before_llm': '为 true 时，随机跳过会发生在任何 LLM 调用前。改成 false 会保留更多推演，但会增加 token 和延迟。',
  'cadence.stochastic_prefilter.jitter_not_before_minutes.min': '随机通过后写入 next_decision_not_before 的最短等待。比如 12 表示至少 12 分钟内不再把下一次主动决策看作自然时机。',
  'cadence.stochastic_prefilter.jitter_not_before_minutes.max': '随机通过后写入 next_decision_not_before 的最长等待。比如 45 表示这次醒来后，下一次自然醒不会被安排到 45 分钟之后更晚；调大能让节奏更松散，调小会更密集。',
  'cadence.stochastic_prefilter.force_llm_after_state_age_minutes': '状态超过这个分钟数没刷新时强制跑 LLM。比如 180 表示最多 3 小时会重新推演一次状态，避免 runtime state 过旧。',
  'decision.min_send_confidence': 'Decision 低于该置信度时即使建议 send 也更容易被后续保护层挡住。调高会更克制，调低会更敢发。',
  'decision.allow_hesitate': '允许 Decision 输出 hesitate 并向意图累积器加压。关闭后“欲言又止”不会发酵，系统会更二元地发送或沉默。',
  'decision.allow_action': '允许 Decision 规划文本以外动作。当前通道能力有限时仍会被 Render 或 Delivery fallback 处理。',
  'decision.allow_media': '允许 media 类消息候选。关闭后即使适合发图片或附件，也会退回文本或静默。',
  'intent_accumulator.enabled': '启用后 hesitate 和 open loop 会变成可衰减分数。关闭后每次 tick 都重新判断，话题不会“越想越想发”。',
  'intent_accumulator.score_min': '话题张力最低值。通常保持 0，避免衰减后出现负分导致某类话题被长期压制。',
  'intent_accumulator.score_max': '单个话题张力上限。比如 3 表示再多次犹豫也不会无限叠加，避免某个 open loop 永久支配决策。',
  'intent_accumulator.send_pressure_threshold': '发送压力阈值。比如 2.0 表示话题分数接近 2 时，Decision 会更认真考虑把它转成 send。',
  'intent_accumulator.hourly_decay': '每小时衰减多少张力。0.2 表示 2.0 的话题大约 10 小时自然归零；调高会更快放下，调低会更念旧。',
  'intent_accumulator.hesitate_delta_default': 'LLM 输出 hesitate 但没给 delta 时的默认加分。0.7 表示三次左右犹豫就可能接近发送阈值。',
  'intent_accumulator.silent_with_open_loop_delta': '沉默但仍有 open loop 时的轻微加分。调高会让未收口话题更容易在后续冒出来。',
  'intent_accumulator.world_signal_delta_max': '单个世界信号最多能增加的意图压力。调高后天气、地点、新闻等外部刺激更容易触发分享。',
  'intent_accumulator.expire_after_hours': '话题最长保留小时数。比如 12 表示半天后未处理的话题自动过期，避免隔天翻旧账。',
  'intent_accumulator.clear_after_delivery': '发送成功后是否清理对应话题。为 true 可避免刚收口的话题继续驱动下一轮发送。',
  'cooldowns.by_message_class.micro_send.min_gap_minutes': '微消息最小间隔。比如 30 表示发过“困”这类短句后，半小时内不会再发 micro_send，但不阻塞 normal_send。',
  'cooldowns.by_message_class.normal_send.min_gap_minutes': '普通主动消息最小间隔。比如 180 表示一次普通主动消息后 3 小时内不会再发同类消息。',
  'cooldowns.by_message_class.closure.min_gap_minutes': '收口消息最小间隔。比如 60 表示上一条收口后至少一小时才允许再用 closure 补尾巴。',
  'cooldowns.by_message_class.random_share.min_gap_minutes': '随机分享的最小间隔。调高会减少“看到什么都想分享”的感觉。',
  'cooldowns.by_message_class.care_timing.min_gap_minutes': '关心时机类消息的最小间隔。调低会更频繁提醒吃饭、休息，调高会更克制。',
  'cooldowns.by_message_class.media.min_gap_minutes': '媒体或附件候选的最小间隔。调高可避免连续发图、发音频或附件。',
  'speech.enabled': '是否允许 Render 生成语音附件候选。关闭后 Decision 即使给 voice_design，也只会投递文本。',
  'speech.provider': 'TTS provider 类型。当前是 openai，表示 Hermes 用 OpenAI-compatible 接口调用本地 MiMo 代理。',
  'speech.model': 'TTS 模型名称。使用 mimo-v2.5-tts-voicedesign 时，Decision 生成的 natural_language_control 会作为音色设计提示。',
  'speech.base_url': '本地 TTS 代理地址。改错会导致语音合成失败，但文本投递仍可 fallback。',
  'speech.response_format': '最终希望 Hermes 收到的音频格式。当前 mp3 适合通过 iLink type=4 作为附件发送。',
  'speech.voice_design.strategy': '音色设计策略。decision_llm_dynamic 表示由 Decision 根据当次状态动态写 natural_language_control。',
  'speech.voice_design.style_reference': '给 Decision 的音色基准参考，不是固定输出。比如这里写“轻微疲惫”，Decision 会在适合语音便签时借用这种气口。',
  'speech.voice_design.message_class_references.micro_send': 'micro_send 的音色参考。影响“困”“醒了”这类极短语音是否更轻、更慢。',
  'speech.voice_design.message_class_references.closure': 'closure 的音色参考。影响“晚安”“先到这儿”这类收口语音是否更低压。',
  'speech.voice_design.message_class_references.random_share': 'random_share 的音色参考。影响生活分享语音是否更自然、少客服腔。',
  'speech.audio_tag_policy.max_tags_per_message': '每条语音最多允许几个风格标签。比如 2 会阻止 LLM 堆满“轻声、疲惫、叹气、停顿”。',
  'speech.audio_tag_policy.allowed': '允许进入 TTS 请求的风格标签白名单。列表外标签会被清洗，避免模型收到不受控的表演指令。',
  'mcp_sources': 'World Collector 会按这里调用真实世界来源。新增 weather、maps、rss 等条目后，世界信号页会出现对应采集结果。',
  'collection.default_enabled': 'World Collector 总开关。关闭后只会保留极少本地信号，State 更难利用天气、地点、网页等真实世界信息。',
  'collection.prefilter_phase_must_be_non_llm': '要求 prefilter 阶段不得调用 LLM。保持 true 可以确保随机预筛前的采集轻量、可控、低成本。',
  'signals.time_context.enabled': '是否生成本地时间信号。关闭后 State 仍知道 current_time，但世界信号列表不会展示本地时间事件。',
  'expression_policy.public_read_only': '公开只读信息的表达策略。may_share_obliquely 表示可以旁侧提到天气、公开地点或新闻，不像播报。',
  'expression_policy.personal_read_only': '个人只读信息的表达策略。mood_only 表示它只影响状态，不直接在消息里说出来源内容。',
  'expression_policy.user_adjacent': '与用户相邻的信息策略。timing_only 表示只影响时机，不直接暴露用户位置或行程细节。',
  'expression_policy.actionful': '可能触发动作的信息策略。policy_controlled 表示必须受权限和审计策略约束。',
  'permissions.mode': '权限运行模式。full_runtime 表示按 Hermes 当前暴露能力运行，适合你现在的一步到位方案。',
  'permissions.inherit_hermes_tools': '是否继承 Hermes 工具。关闭后 Presence 能力会变窄，真实世界交互和工具调用会减少。',
  'permissions.inherit_mcp_servers': '是否继承 MCP server。关闭后 world_policy 里的 MCP 来源即使配置了也无法调用。',
  'permissions.inherit_skills': '是否继承 skills。关闭后依赖 skill 的动作或工具指导不会进入运行环境。',
  'permissions.action_execution.default': '动作执行默认策略。enabled 表示允许执行配置范围内的动作，改成 disabled 会更像只预览。',
  'permissions.action_execution.dry_run': '是否强制动作 dry-run。true 时不会真实投递或执行外部动作，适合测试。',
  'permissions.action_execution.require_confirmation_for': '需要人工确认的动作列表。加入 media 或 external_post 后，对应动作会进入确认流程而不是自动执行。',
  'permissions.observability.log_tool_args': '工具参数记录粒度。summarized 会保存摘要，既能审计又避免把完整敏感参数铺进日志。',
  'permissions.observability.log_tool_results': '工具结果记录粒度。summarized 会展示结果摘要，完整原文可按需折叠查看。',
  'permissions.observability.redact_secrets': '是否脱敏密钥。关闭后日志可能出现 token、API key 等敏感内容，不建议关闭。',
  'permissions.observability.trace_retention_days': 'trace 保留天数。调大方便长期回看，但事件文件会增长。',
};

const keyPurpose: Record<string, string> = {
  enabled: '开关当前段落。比如某个 mcp source 的 enabled 改为 false 后，该来源不会再出现在 world-signal-events。',
  name: '给条目起一个稳定名称。这个名称会出现在世界信号、trace 和错误排查里。',
  phase: '决定调用发生在随机预筛前还是之后。prefilter 适合便宜信号，post_prefilter 适合更慢或更贵的网页、RSS、浏览器调用。',
  server: 'MCP server 名称。改错后 Collector 会找不到对应 server，并在 trace 里记录调用失败。',
  tool: 'MCP tool 名称。比如 get_current_weather 会拿当前天气，换成 forecast 类工具会改变返回内容和延迟。',
  arguments: '传给工具的参数。比如把 location 从 Shanghai 改成 Hangzhou，天气和地点信号就会按杭州采集。',
  kind: '信号分类。State 会用 kind 判断这是天气、时间、地点还是本地审计信息。',
  model: '调用的模型或工具模型名称。改模型会影响输出风格、延迟、成本和字段遵循能力。',
  base_url: '请求发送到的兼容 API 地址。改到错误端口会导致模型或 TTS 调用失败。',
  api_key: '本地或远端服务的访问密钥。填错会导致 401 或代理拒绝请求。',
  temperature: '控制 LLM 输出随机性。调高会更有变化但更难稳定遵守 JSON，调低会更稳但更机械。',
  max_tokens: '限制单次模型输出长度。太小会截断 JSON，太大则增加成本和等待时间。',
  timeout_seconds: '工具或模型请求超时时间。太短会频繁 timeout，太长会拖慢 tick。',
  cache_ttl_minutes: '同一来源结果缓存多久。调大可减少 MCP 调用，代价是世界信号可能不够新。',
  signal_ttl_minutes: '信号在系统里被认为有效多久。过期后不会再作为当前世界事实影响 State。',
  max_result_chars: '写入日志和传给后续层的结果长度上限。调小更清爽，调大更利于排查但会增加 prompt 体积。',
  confidence: '该来源的可信度。较低时 State 和 Decision 会更谨慎地使用这条信号。',
  daily_cap: '该类别每天最多允许发生的次数。比如 normal_send 为 3 时，当天第 4 次普通主动消息会被频控阻止。',
  min_gap_minutes: '同类消息的最小间隔。比如 120 表示两小时内不会再发同一 message_class。',
  counts_toward_normal_send: '是否同时占用 normal_send 冷却。micro_send 设 false 时，发一个短句不会阻塞后续正常主动消息。',
  allowed_use: '该信号允许怎么用。mood_only 只影响心情，mood_and_share 可成为轻量分享素材，state_only 只进内部状态。',
  sensitivity: '敏感等级。public 可以展示得更直接，personal_readonly 默认只影响内部状态和审计。',
  policy_decision: '采集策略结果。auto_allow 会自动进入链路，internal_only 会只供内部推演和审计。',
  source: '数据来源。会显示在 world signal 和 trace 中，方便判断这条事实来自脚本、MCP 还是缓存。',
  examples: '给 LLM 的示例。例子越具体，输出越容易贴近 profile，但过多会增加 prompt 体积。',
  avoid: '需要避开的表达或行为。比如加入“不要追问”后，Render 会更倾向陈述句。',
};

export default function Profiles({ profileId, onProfileChange }: { profileId: string; onProfileChange: (profileId: string) => void }) {
  const queryClient = useQueryClient();
  const [kind, setKind] = useState('proactive_policy');
  const [draft, setDraft] = useState<any>({});
  const [parseError, setParseError] = useState('');
  const [confirm, setConfirm] = useState(false);
  const [backupFilename, setBackupFilename] = useState('');
  const [rollbackConfirm, setRollbackConfirm] = useState(false);
  const { data: profiles } = useQuery({ queryKey: ['profiles'], queryFn: fetchProfiles });
  const { data: config } = useQuery({ queryKey: ['profile-config', profileId], queryFn: () => fetchProfileConfig(profileId), enabled: Boolean(profileId) });
  const { data: backups } = useQuery({
    queryKey: ['profile-config-backups', profileId, kind],
    queryFn: () => fetchProfileConfigBackups(profileId, kind),
    enabled: Boolean(profileId && kind),
  });
  const selected = useMemo(() => config?.files?.[kind], [config, kind]);
  const backupList = backups?.backups || [];
  const selectedBackup = backupList.find((backup: any) => backup.filename === backupFilename);
  const serializedContent = useMemo(() => serializeDraft(kind, draft), [kind, draft]);

  useEffect(() => {
    const parsed = parseContent(kind, selected?.content || '');
    setDraft(parsed.value);
    setParseError(parsed.error);
    setConfirm(false);
    setBackupFilename('');
    setRollbackConfirm(false);
  }, [kind, selected?.sha256, selected?.content]);

  const mutation = useMutation({
    mutationFn: () => postProfileConfig(profileId, { kind, content: serializedContent, expected_sha256: selected?.sha256 || '', confirm_write: confirm }),
    onSuccess: (data) => {
      if (data.status === 'diff_required') setConfirm(true);
      else {
        setConfirm(false);
        queryClient.invalidateQueries({ queryKey: ['profile-config', profileId] });
        queryClient.invalidateQueries({ queryKey: ['profile-config-backups', profileId, kind] });
      }
    },
  });
  const validateMutation = useMutation({ mutationFn: () => postProfileValidate(profileId) });
  const rollbackMutation = useMutation({
    mutationFn: () => postProfileConfigRollback(profileId, {
      kind,
      backup_filename: backupFilename,
      expected_current_sha256: selected?.sha256 || '',
      confirm_rollback: rollbackConfirm,
    }),
    onSuccess: () => {
      setRollbackConfirm(false);
      setBackupFilename('');
      queryClient.invalidateQueries({ queryKey: ['profile-config', profileId] });
      queryClient.invalidateQueries({ queryKey: ['profile-config-backups', profileId, kind] });
    },
  });

  return (
    <div className="stack">
      <PageHeader
        title="配置中心"
        description="配置文件被拆成可交互字段。右侧编辑字段值，左侧实时渲染最终会写入的配置内容。"
        actions={
          <>
            <button type="button" onClick={() => validateMutation.mutate()} disabled={!profileId || validateMutation.isPending} className="btn btn-secondary">
              <CheckCircle2 size={16} /> 校验
            </button>
            <button type="button" onClick={() => mutation.mutate()} disabled={!profileId || mutation.isPending || Boolean(parseError)} className="btn btn-primary">
              <Save size={16} /> {confirm ? '确认写入' : '保存'}
            </button>
          </>
        }
      />

      <Panel title="编辑目标" eyebrow="profile config">
        <div className="three-grid">
          <label className="stack">
            <span className="text-sm text-[var(--color-muted)]">Profile</span>
            <select className="control" value={profileId} onChange={(event) => onProfileChange(event.target.value)}>
              {(profiles?.profiles || [{ profile_id: profileId, display_name: profileId }]).map((profile: any) => (
                <option key={profile.profile_id} value={profile.profile_id}>{profile.display_name || profile.profile_id}</option>
              ))}
            </select>
          </label>
          <label className="stack">
            <span className="text-sm text-[var(--color-muted)]">配置文件</span>
            <select className="control" value={kind} onChange={(event) => setKind(event.target.value)}>
              {kinds.map((item) => <option key={item} value={item}>{kindLabels[item] || item}</option>)}
            </select>
          </label>
          <div className="kv-stack">
            <KeyValue label="当前 SHA" value={shortId(selected?.sha256, 14)} mono />
            <KeyValue label="修改时间" value={formatDateTime(selected?.mtime)} />
          </div>
        </div>

        <div className="inline-row mt-4">
          {parseError && <Pill tone="error">{parseError}</Pill>}
          {confirm && <Pill tone="warning">已生成 diff，再点一次确认写入</Pill>}
          {mutation.data?.status === 'success' && <Pill tone="success">保存成功</Pill>}
          {mutation.error && <Pill tone="error">{String((mutation.error as Error).message)}</Pill>}
          {validateMutation.data && <Pill tone={validateMutation.data.ok ? 'success' : 'error'}>{validateMutation.data.ok ? '校验通过' : '校验失败'}</Pill>}
        </div>

        {validateMutation.data && !validateMutation.data.ok && (
          <div className="detail-band mt-4">
            {(validateMutation.data.missing || []).length > 0 && <p>缺失文件：{validateMutation.data.missing.join('、')}</p>}
            {(validateMutation.data.errors || []).map((item: any) => (
              <p key={item.kind}>{kindLabels[item.kind] || item.kind}: {item.error}</p>
            ))}
          </div>
        )}
      </Panel>

      <div className="config-editor-grid">
        <Panel title="实时渲染" eyebrow={selected?.path || 'profile file'}>
          <pre className="config-preview">{serializedContent || '空配置'}</pre>
        </Panel>

        <Panel title="字段编辑" eyebrow={`${kindLabels[kind] || kind} · structured inputs`}>
          {kind === 'voice' && (
            <div className="detail-band mb-4">
              <Pill tone="info">voice.md 不是 TTS 模型开关</Pill>
              <p className="mt-3 text-sm leading-6 text-[var(--color-muted)]">
                当前语音合成已经走 MiMo voice design；这里的 voice.md 仍作为“文字语气与音色基准”注入 State、Decision 和 Render。
                Decision 会参考它生成当次 voice_design.natural_language_control，但不会机械复制它。真正的 TTS 开关和模型在“投递”配置里的 speech 段。
              </p>
            </div>
          )}
          {kind === 'voice' ? (
            <VoiceEditor sections={Array.isArray(draft) ? draft : []} onChange={setDraft} />
          ) : (
            <ConfigNode value={draft} path={[]} onChange={setDraft} />
          )}
        </Panel>
      </div>

      <Panel title="备份与回滚" eyebrow="rollback">
        <div className="three-grid">
          <select
            className="control"
            value={backupFilename}
            onChange={(event) => {
              setBackupFilename(event.target.value);
              setRollbackConfirm(false);
            }}
          >
            <option value="">选择备份...</option>
            {backupList.map((backup: any) => (
              <option key={backup.filename} value={backup.filename}>{formatDateTime(backup.mtime)} · {backup.filename}</option>
            ))}
          </select>

          {selectedBackup ? (
            <div className="kv-stack">
              <KeyValue label="备份 SHA" value={shortId(selectedBackup.sha256, 14)} mono />
              <KeyValue label="大小" value={`${selectedBackup.size_bytes || 0} bytes`} />
            </div>
          ) : (
            <EmptyState title="未选择备份" description="选择备份后可二次确认回滚。" />
          )}

          <div className="stack">
            <button
              type="button"
              onClick={() => {
                if (!rollbackConfirm) setRollbackConfirm(true);
                else rollbackMutation.mutate();
              }}
              disabled={!backupFilename || rollbackMutation.isPending}
              className="btn btn-warning"
            >
              <RotateCcw size={16} /> {rollbackConfirm ? '确认回滚' : '回滚到备份'}
            </button>
            {rollbackConfirm && <Pill tone="warning">再次点击会覆盖当前配置，并保存 pre-rollback 备份</Pill>}
            {rollbackMutation.data?.status === 'success' && <Pill tone="success">回滚成功</Pill>}
            {rollbackMutation.error && <Pill tone="error">{String((rollbackMutation.error as Error).message)}</Pill>}
          </div>
        </div>
      </Panel>
    </div>
  );
}

function ConfigNode({ value, path, onChange }: { value: any; path: PathPart[]; onChange: (next: any) => void }) {
  if (Array.isArray(value)) {
    return (
      <div className="form-tree">
        {value.length === 0 && <EmptyState title="空列表" description="当前数组没有条目，可以新增一个空字符串条目后继续编辑。" />}
        {value.map((item, index) => (
          <details key={index} className="field-group" open>
            <summary>
              <span>{labelFor([...path, index])}</span>
              <button type="button" className="icon-btn" onClick={(event) => { event.preventDefault(); onChange(removeArrayIndex(value, index)); }} title="删除该项">
                <Trash2 size={14} />
              </button>
            </summary>
            <ConfigNode value={item} path={[...path, index]} onChange={(next) => onChange(replaceArrayIndex(value, index, next))} />
          </details>
        ))}
        <button type="button" className="btn btn-secondary" onClick={() => onChange([...value, defaultArrayItem(value)])}>
          <Plus size={15} /> 新增条目
        </button>
      </div>
    );
  }
  if (isPlainObject(value)) {
    const entries = Object.entries(value);
    if (entries.length === 0) {
      return <EmptyState title="空对象" description="这个配置段当前没有字段。" />;
    }
    return (
      <div className="form-tree">
        {entries.map(([key, child]) => {
          const nextPath = [...path, key];
          if (isPlainObject(child) || Array.isArray(child)) {
            return (
              <details key={key} className="field-group" open={path.length < 1}>
                <summary>
                  <span>{key}</span>
                  <small>{purposeFor(nextPath, child)}</small>
                </summary>
                <ConfigNode value={child} path={nextPath} onChange={(next) => onChange({ ...value, [key]: next })} />
              </details>
            );
          }
          return <LeafField key={key} label={key} value={child} path={nextPath} onChange={(next) => onChange({ ...value, [key]: next })} />;
        })}
      </div>
    );
  }
  return <LeafField label={labelFor(path)} value={value} path={path} onChange={onChange} />;
}

function LeafField({ label, value, path, onChange }: { label: string; value: any; path: PathPart[]; onChange: (next: any) => void }) {
  const purpose = purposeFor(path, value);
  const id = `field-${path.join('-')}`;
  if (typeof value === 'boolean') {
    return (
      <label className="field-card" htmlFor={id}>
        <span className="field-label">{label}</span>
        <span className="field-purpose">{purpose}</span>
        <select id={id} className="control" value={String(value)} onChange={(event) => onChange(event.target.value === 'true')} title={purpose}>
          <option value="true">启用 / true</option>
          <option value="false">关闭 / false</option>
        </select>
      </label>
    );
  }
  if (typeof value === 'number') {
    return (
      <label className="field-card" htmlFor={id}>
        <span className="field-label">{label}</span>
        <span className="field-purpose">{purpose}</span>
        <input id={id} className="control" type="number" value={value} placeholder={purpose} title={purpose} onChange={(event) => onChange(Number(event.target.value))} />
      </label>
    );
  }
  const text = value === null || value === undefined ? '' : String(value);
  const multiline = text.length > 80 || text.includes('\n');
  return (
    <label className="field-card" htmlFor={id}>
      <span className="field-label">{label}</span>
      <span className="field-purpose">{purpose}</span>
      {multiline ? (
        <textarea id={id} className="control field-textarea" value={text} placeholder={purpose} title={purpose} onChange={(event) => onChange(event.target.value)} />
      ) : (
        <input id={id} className="control" type="text" value={text} placeholder={purpose} title={purpose} onChange={(event) => onChange(event.target.value)} />
      )}
    </label>
  );
}

function VoiceEditor({ sections, onChange }: { sections: VoiceSection[]; onChange: (next: VoiceSection[]) => void }) {
  if (!sections.length) return <EmptyState title="文字语气基准为空" description="新增一个段落后可编辑 voice.md。它会作为文本语气和 voice design 的参考，不是最终音频模型。" />;
  return (
    <div className="form-tree">
      {sections.map((section, index) => (
        <div key={section.id} className="field-group voice-section">
          <LeafField label="段落标题" value={section.title} path={['voice', index, 'title']} onChange={(title) => onChange(replaceArrayIndex(sections, index, { ...section, title }))} />
          <label className="field-card">
            <span className="field-label">段落内容</span>
            <span className="field-purpose">定义该段文字语气和音色基准。比如写“短句、清冷、低压”，Render 会更少长篇解释，Decision 生成 voice_design 时也会借用这种气口。</span>
            <textarea className="control field-textarea voice-textarea" value={section.body} onChange={(event) => onChange(replaceArrayIndex(sections, index, { ...section, body: event.target.value }))} />
          </label>
        </div>
      ))}
      <button type="button" className="btn btn-secondary" onClick={() => onChange([...sections, { id: `new-${Date.now()}`, level: 2, title: '新段落', body: '' }])}>
        <Plus size={15} /> 新增段落
      </button>
    </div>
  );
}

function parseContent(kind: string, content: string): { value: any; error: string } {
  if (kind === 'voice') return { value: parseVoice(content), error: '' };
  try {
    return { value: YAML.parse(content || '{}') ?? {}, error: '' };
  } catch (error) {
    return { value: {}, error: `YAML 解析失败：${String((error as Error).message || error)}` };
  }
}

function serializeDraft(kind: string, draft: any) {
  if (kind === 'voice') return serializeVoice(Array.isArray(draft) ? draft : []);
  try {
    return YAML.stringify(draft ?? {}, { indent: 2, lineWidth: 120 });
  } catch {
    return '';
  }
}

function parseVoice(content: string): VoiceSection[] {
  const lines = content.split(/\r?\n/);
  const sections: VoiceSection[] = [];
  let current: VoiceSection | null = null;
  for (const line of lines) {
    const match = /^(#{1,6})\s+(.+?)\s*$/.exec(line);
    if (match) {
      if (current) sections.push(current);
      current = { id: `${sections.length}-${match[2]}`, level: match[1].length, title: match[2], body: '' };
    } else if (current) {
      current.body += `${line}\n`;
    } else if (line.trim()) {
      current = { id: 'intro', level: 2, title: '开头说明', body: `${line}\n` };
    }
  }
  if (current) sections.push({ ...current, body: current.body.replace(/\n$/, '') });
  return sections.length ? sections : [{ id: 'empty', level: 2, title: '语气说明', body: '' }];
}

function serializeVoice(sections: VoiceSection[]) {
  return sections.map((section) => `${'#'.repeat(section.level || 2)} ${section.title || '未命名段落'}\n${section.body || ''}`.trimEnd()).join('\n\n') + '\n';
}

function purposeFor(path: PathPart[], value: any) {
  const normalized = path.filter((part) => typeof part === 'string').join('.');
  const key = String(path[path.length - 1] || '');
  if (exactPurpose[normalized]) return exactPurpose[normalized];
  if (keyPurpose[key]) return keyPurpose[key];
  return inferredPurpose(normalized, key, value);
}

function inferredPurpose(normalized: string, key: string, value: any) {
  if (Array.isArray(value)) {
    if (normalized.includes('mcp_sources')) return '这一组来源会逐条尝试采集。列表越长，世界信号越丰富，但 tick 延迟和失败点也会增加。';
    if (normalized.includes('allowed') || normalized.includes('require_confirmation_for')) return '这里是白名单或确认名单。新增条目会放开对应能力，删除条目会让相关动作被清洗或拦截。';
    return '这一组条目会按顺序传给后续层。把更重要的示例或规则放前面，LLM 更容易优先遵守。';
  }
  if (isPlainObject(value)) {
    if (normalized.includes('cooldowns.by_message_class')) return '这里定义某一类消息的独立频控。比如 micro_send 和 normal_send 分开后，短句不会吃掉普通消息窗口。';
    if (normalized.includes('mcp_sources.arguments')) return '这里是工具调用参数。改动后下一次采集会拿到不同城市、URL、半径或文件路径的结果。';
    if (normalized.includes('voice_design')) return '这里是 MiMo voice design 的提示参考。它会帮助 Decision 写出当次音色设计，而不是直接作为固定音频输出。';
    return '这个配置段会把相关字段组合成一个决策条件。展开后改具体字段，能看到它是影响时机、信号、权限还是投递。';
  }
  if (normalized.includes('jitter_not_before_minutes')) return '这个数值会改变下一次自然醒来的随机等待区间。数值越大，系统越不容易连续醒来。';
  if (normalized.includes('probability')) return '这个数值参与随机预筛。调高会更频繁进入 LLM，调低会更常记录 skip 并保持安静。';
  if (normalized.includes('minutes')) return '这是分钟级时间窗口。调大通常会让系统更慢、更克制；调小会让下一次动作更快出现。';
  if (normalized.includes('hours')) return '这是小时级保留或过期窗口。调大更容易保留旧话题，调小会更快放下。';
  if (normalized.includes('url')) return '这是公开网页或接口地址。换 URL 后，世界信号会从新页面取摘要，失败时会在 trace 里显示 fetch 错误。';
  if (normalized.includes('location')) return '这是地点参数。改城市或经纬度后，天气、地图和附近地点会按新位置生成。';
  if (normalized.includes('query')) return '这是搜索词。比如从 bookstores cafes parks 改成 livehouse exhibitions 后，地图信号会偏向演出和展览场所。';
  if (normalized.includes('radius')) return '这是搜索半径。数值越大，地点结果范围越广，但也更容易出现不贴近日常场景的地点。';
  if (typeof value === 'boolean') return `这个开关控制 ${key} 是否参与当前链路。关闭后相关步骤通常不会产生事件或候选输出。`;
  if (typeof value === 'number') return `这个数值会作为 ${key} 的阈值或上限。调大通常放宽范围或延长等待，调小通常更严格或更快触发。`;
  return `这里会作为 ${key} 的实际文本值写入配置。比如改名称、提示词或路径后，下一次预览和 trace 会直接显示新值。`;
}

function labelFor(path: PathPart[]) {
  const last = path[path.length - 1];
  if (typeof last === 'number') return `第 ${last + 1} 项`;
  return String(last || '值');
}

function isPlainObject(value: any) {
  return value !== null && typeof value === 'object' && !Array.isArray(value);
}

function replaceArrayIndex<T>(items: T[], index: number, next: T) {
  return items.map((item, itemIndex) => (itemIndex === index ? next : item));
}

function removeArrayIndex<T>(items: T[], index: number) {
  return items.filter((_, itemIndex) => itemIndex !== index);
}

function defaultArrayItem(items: any[]) {
  const first = items[0];
  if (isPlainObject(first)) return {};
  if (typeof first === 'number') return 0;
  if (typeof first === 'boolean') return false;
  return '';
}
