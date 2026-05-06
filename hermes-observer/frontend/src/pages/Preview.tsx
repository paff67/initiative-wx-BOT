import { useMutation } from '@tanstack/react-query';
import { Play } from 'lucide-react';
import { postPreviewFull } from '../api/client';
import { EmptyState, KeyValue, PageHeader, Panel, Pill, actionLabel, actionTone, classLabel, compactObject, formatDateTime, shortId } from '../lib/presenceView';

const stepLabels: Record<string, string> = {
  world_collect: '世界采集',
  intent_decay: '意图衰减',
  stochastic_prefilter: '随机预筛',
  state: '状态推演',
  decision: '动作裁决',
  intent_update: '意图更新',
  cooldown: '频控',
  render: '渲染',
  delivery: '投递',
};

export default function Preview({ profileId }: { profileId: string }) {
  const mutation = useMutation({ mutationFn: () => postPreviewFull({ profile_id: profileId, mode: 'full', force_llm: true }) });
  const trace = mutation.data?.trace;
  const render = trace?.render;
  const decision = trace?.decision || {};
  const voiceDesign = render?.speech?.voice_design || decision?.voice_design || {};
  const isSilent = !render || render.type === 'silent';

  return (
    <div className="stack">
      <PageHeader
        title="投递预览"
        description="完整 dry-run 会跑 World、State、Decision 和 Render，但不会触发微信投递。这里展示最终可见效果和关键裁决，不展示整段 JSON。"
        actions={
          <button type="button" onClick={() => mutation.mutate()} disabled={mutation.isPending || !profileId} className="btn btn-primary">
            <Play size={16} /> {mutation.isPending ? '运行中' : '运行完整预览'}
          </button>
        }
      />

      {mutation.error && <Panel><Pill tone="error">{String((mutation.error as Error).message)}</Pill></Panel>}

      {render ? (
        <div className="split-grid">
          <Panel title="微信效果" eyebrow={render.would_deliver ? 'would deliver' : 'dry-run only'}>
            <div className={`message-bubble ${isSilent ? 'is-silent' : ''}`}>
              {render.type === 'text' ? render.text : '[SILENT]'}
            </div>
            <div className="inline-row mt-4">
              <Pill tone={isSilent ? 'muted' : 'success'}>{render.type || 'unknown'}</Pill>
              <Pill tone="neutral">{render.channel || 'weixin'}</Pill>
              <Pill tone={render.would_deliver ? 'warning' : 'muted'}>{render.would_deliver ? '可投递但已隔离' : '不会投递'}</Pill>
            </div>
          </Panel>

          <Panel title="裁决摘要" eyebrow={shortId(decision.decision_run_id, 18)}>
            <div className="kv-stack">
              <KeyValue label="动作" value={<Pill tone={actionTone(decision.action)}>{actionLabel(decision.action)}</Pill>} />
              <KeyValue label="消息类型" value={classLabel(decision.message_class)} />
              <KeyValue label="回复压力" value={decision.reply_pressure || '无'} />
              <KeyValue label="理由" value={decision.reasoning_summary || decision.reason || '暂无'} />
            </div>
          </Panel>
        </div>
      ) : (
        <Panel>
          <EmptyState title="还没有预览结果" description="点击右上角运行完整预览，结果会在这里以微信消息和裁决摘要展示。" />
        </Panel>
      )}

      {decision.render_brief && (
        <Panel title="Render Brief" eyebrow="给最终渲染层的写作约束">
          <div className="kv-stack">
            <KeyValue label="切入点" value={decision.render_brief.entry_point || '无'} />
            <KeyValue label="情绪底色" value={decision.render_brief.emotional_baseline || decision.render_brief.tone || '无'} />
            <KeyValue label="句式限制" value={decision.render_brief.shape_constraint || decision.render_brief.message_shape || '无'} />
          </div>
        </Panel>
      )}

      {(voiceDesign.enabled || voiceDesign.prompt || voiceDesign.natural_language_control) && (
        <Panel title="语音设计" eyebrow="MiMo voice design">
          <div className="kv-stack">
            <KeyValue label="启用" value={<Pill tone={voiceDesign.enabled ? 'success' : 'muted'}>{voiceDesign.enabled ? '候选语音' : '文本优先'}</Pill>} />
            <KeyValue label="控制语句" value={voiceDesign.natural_language_control || voiceDesign.prompt || '无'} />
            <KeyValue label="风格标签" value={(voiceDesign.assistant_style_tags || voiceDesign.audio_tags || []).join('、') || '无'} />
            <KeyValue label="模式" value={voiceDesign.delivery_mode || 'text_only'} />
          </div>
        </Panel>
      )}

      {trace?.steps?.length > 0 && (
        <Panel title="执行链路" eyebrow={`${shortId(trace.tick_run_id || trace.run_id, 18)} · ${formatDateTime(trace.created_at)}`}>
          <div className="pipeline">
            {trace.steps.map((step: any, index: number) => (
              <div key={`${step.name}-${index}`} className="pipeline-row">
                <div className="pipeline-name">
                  <span>{index + 1}</span>
                  <span>{stepLabels[step.name] || step.name}</span>
                </div>
                <div className="pipeline-body">
                  <strong>{step.action ? actionLabel(step.action) : step.result?.reason || step.result?.message_class || step.type || '完成'}</strong>
                  <span>{summarizeStep(step)}</span>
                </div>
              </div>
            ))}
          </div>
        </Panel>
      )}

      {mutation.data && !mutation.data.ok && (
        <Panel title="运行异常" eyebrow={`exit ${mutation.data.exit_code}`}>
          <div className="kv-stack">
            <KeyValue label="stdout" value={compactObject(mutation.data.stdout, 220)} mono />
            <KeyValue label="stderr" value={compactObject(mutation.data.stderr, 220)} mono />
          </div>
        </Panel>
      )}
    </div>
  );
}

function summarizeStep(step: any) {
  if (step.name === 'world_collect') {
    return `${(step.signals || []).length} 个信号，${(step.tool_calls || []).length} 次工具调用`;
  }
  if (step.name === 'stochastic_prefilter') {
    const result = step.result || {};
    return `${result.skip ? '跳过 LLM' : '允许继续'}，概率 ${result.probability ?? '未知'}，rolled ${result.rolled ?? '未知'}`;
  }
  if (step.name === 'intent_update') {
    return step.intent_delta?.reason || compactObject(step.summary, 180);
  }
  if (step.name === 'cooldown') {
    const result = step.result || {};
    return `${result.allowed ? '频控允许' : '频控阻止'}，${result.reason || '无原因'}`;
  }
  if (step.name === 'render') {
    return `render_run_id ${shortId(step.render_run_id, 18)}`;
  }
  return compactObject(step, 180);
}
