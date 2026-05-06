import { useQuery } from '@tanstack/react-query';
import { CheckCircle2, CircleDashed, XCircle } from 'lucide-react';
import { fetchTraces } from '../api/client';
import { EmptyState, PageHeader, Panel, Pill, actionLabel, actionTone, classLabel, compactObject, formatDateTime, shortId } from '../lib/presenceView';

const stepLabels: Record<string, string> = {
  world_collect: 'World',
  intent_decay: 'Intent Decay',
  stochastic_prefilter: 'Prefilter',
  state: 'State',
  decision: 'Decision',
  intent_update: 'Intent Update',
  cooldown: 'Cooldown',
  render: 'Render',
  delivery: 'Delivery',
};

export default function Traces({ profileId }: { profileId: string }) {
  const { data } = useQuery({ queryKey: ['traces', profileId], queryFn: () => fetchTraces(80, profileId), refetchInterval: 8000, enabled: Boolean(profileId) });
  const traces = data?.traces || [];

  return (
    <div className="stack">
      <PageHeader
        title="链路追踪"
        description="按运行顺序展示 World、State、Intent、Decision、Render 和 Delivery。每条记录只保留关键结论、输入数量和异常摘要。"
      />

      {traces.length === 0 ? (
        <Panel>
          <EmptyState title="暂无 trace" description="Presence Kernel 运行后会写入 trace-events.jsonl，并在这里显示。" />
        </Panel>
      ) : (
        traces.map((trace: any) => (
          <Panel
            key={trace.tick_run_id || trace.run_id}
            title={shortId(trace.tick_run_id || trace.run_id, 26)}
            eyebrow={formatDateTime(trace.created_at)}
            action={
              <div className="inline-row">
                <Pill tone={trace.dry_run ? 'muted' : 'success'}>{trace.dry_run ? 'dry-run' : '正式'}</Pill>
                {trace.decision?.action && <Pill tone={actionTone(trace.decision.action)}>{actionLabel(trace.decision.action)}</Pill>}
                {trace.decision?.message_class && <Pill tone="neutral">{classLabel(trace.decision.message_class)}</Pill>}
                {trace.render?.type && <Pill tone={trace.render.type === 'silent' ? 'muted' : 'accent'}>{trace.render.type}</Pill>}
              </div>
            }
          >
            <div className="pipeline">
              {(trace.steps || []).map((step: any, index: number) => (
                <div key={`${trace.tick_run_id || trace.run_id}-${step.name}-${index}`} className="pipeline-row">
                  <div className="pipeline-name">
                    {stepIcon(step)}
                    <span>{stepLabels[step.name] || step.name}</span>
                  </div>
                  <div className="pipeline-body">
                    <strong>{stepTitle(step)}</strong>
                    <span>{stepSummary(step)}</span>
                    <details className="raw-details step-details">
                      <summary>查看该部分详细内容</summary>
                      <pre className="raw-block">{JSON.stringify(step, null, 2)}</pre>
                    </details>
                  </div>
                </div>
              ))}
            </div>
          </Panel>
        ))
      )}
    </div>
  );
}

function stepIcon(step: any) {
  if (step.error || step.result?.allowed === false) return <XCircle size={15} />;
  if (step.result?.skip) return <CircleDashed size={15} />;
  return <CheckCircle2 size={15} />;
}

function stepTitle(step: any) {
  if (step.name === 'decision') return actionLabel(step.action);
  if (step.name === 'cooldown') return step.result?.allowed ? '频控通过' : '频控阻止';
  if (step.name === 'stochastic_prefilter') return step.result?.skip ? '跳过 LLM' : '继续执行';
  if (step.name === 'render') return step.type || 'render complete';
  return '完成';
}

function stepSummary(step: any) {
  if (step.name === 'world_collect') return `${(step.signals || []).length} 个信号，${(step.tool_calls || []).length} 次工具调用`;
  if (step.name === 'intent_decay') return `max_score ${step.summary?.max_score ?? 0}，threshold ${step.summary?.threshold ?? '未知'}`;
  if (step.name === 'stochastic_prefilter') return `reason ${step.result?.reason || '无'}，probability ${step.result?.probability ?? '未知'}，rolled ${step.result?.rolled ?? '未知'}`;
  if (step.name === 'state') return `state_run_id ${shortId(step.state_run_id, 18)}`;
  if (step.name === 'decision') return `decision_run_id ${shortId(step.decision_run_id, 18)}`;
  if (step.name === 'intent_update') return step.intent_delta?.reason || compactObject(step.summary, 180);
  if (step.name === 'cooldown') return `${step.result?.message_class || 'none'}，${step.result?.reason || '无原因'}`;
  if (step.name === 'render') return `render_run_id ${shortId(step.render_run_id, 18)}`;
  return compactObject(step, 180);
}
