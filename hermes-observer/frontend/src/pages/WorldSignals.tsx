import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Ban, Clock, Database } from 'lucide-react';
import { fetchWorldSignals, postWorldSignalReview } from '../api/client';
import { EmptyState, KeyValue, PageHeader, Panel, Pill, compactObject, formatDateTime, shortId } from '../lib/presenceView';

export default function WorldSignals({ profileId }: { profileId: string }) {
  const queryClient = useQueryClient();
  const { data } = useQuery({ queryKey: ['world-signals', profileId], queryFn: () => fetchWorldSignals(100, profileId), refetchInterval: 10000, enabled: Boolean(profileId) });
  const mutation = useMutation({
    mutationFn: (signalId: string) => postWorldSignalReview(signalId, { action: 'blocked', reason: 'Blocked from Observer' }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['world-signals', profileId] }),
  });
  const signals = data?.signals || [];
  const toolCallsById = new Map<string, any>();
  for (const event of data?.events || []) {
    for (const call of event.tool_calls || []) {
      if (call.tool_call_id) toolCallsById.set(call.tool_call_id, call);
    }
  }

  return (
    <div className="stack">
      <PageHeader
        title="世界信号"
        description="展示 MCP、脚本和缓存采集到的真实世界信号。这里重点看来源、用途、过期时间和是否需要人工阻断。"
      />

      {signals.length === 0 ? (
        <Panel>
          <EmptyState title="暂无世界信号" description="collector 写入 world-signal-events.jsonl 后会在这里出现。" />
        </Panel>
      ) : (
        <div className="split-grid">
          {signals.map((signal: any) => (
            <Panel
              key={signal.id}
              title={signal.kind || 'signal'}
              eyebrow={shortId(signal.id, 22)}
              action={
                <button type="button" onClick={() => mutation.mutate(signal.id)} disabled={mutation.isPending} className="btn btn-danger" title="阻断此信号">
                  <Ban size={15} /> 阻断
                </button>
              }
            >
              <div className="stack">
                <p className="text-base leading-7">{compactObject(signal.normalized_fact || signal.raw_summary, 260)}</p>
                <div className="inline-row">
                  <Pill tone="accent"><Database size={13} /> {signal.source?.name || signal.source?.type || 'unknown'}</Pill>
                  <Pill tone={signal.policy_decision === 'auto_allow' ? 'success' : 'warning'}>{signal.policy_decision || '未定'}</Pill>
                  <Pill tone="neutral">{signal.allowed_use || '未指定用途'}</Pill>
                  <Pill tone={signal.operator_review === 'blocked' ? 'error' : 'muted'}>{signal.operator_review || 'unreviewed'}</Pill>
                </div>

                <div className="kv-stack">
                  <KeyValue label="采集时间" value={formatDateTime(signal.fetched_at)} />
                  <KeyValue label="过期时间" value={formatDateTime(signal.expires_at)} />
                  <KeyValue label="敏感度" value={signal.sensitivity || 'public'} />
                  <KeyValue label="置信度" value={signal.confidence ?? '无'} />
                  <KeyValue label="工具" value={toolSummary(signal)} mono />
                </div>

                <RawSignalDetails signal={signal} toolCallsById={toolCallsById} />
              </div>
            </Panel>
          ))}
        </div>
      )}

      {(data?.events || []).length > 0 && (
        <Panel title="采集批次" eyebrow="collector runs">
          <div className="pipeline">
            {(data.events || []).slice(0, 8).map((event: any) => (
              <div key={event.run_id || event.collector_run_id || event.created_at} className="pipeline-row">
                <div className="pipeline-name">
                  <Clock size={15} />
                  <span>{shortId(event.run_id || event.collector_run_id, 20)}</span>
                </div>
                <div className="pipeline-body">
                  <strong>{(event.signals || []).length} 个信号，{(event.tool_calls || []).length} 次工具调用</strong>
                  <span>{formatDateTime(event.created_at)} · profile {event.profile_id || profileId}</span>
                </div>
              </div>
            ))}
          </div>
        </Panel>
      )}
    </div>
  );
}

function toolSummary(signal: any) {
  const source = signal.source || {};
  const calls = signal.trace?.tool_calls || [];
  if (source.server || source.tool) return `${source.server || source.type || 'source'} / ${source.tool || 'tool'}${source.cached ? ' · cached' : ''}`;
  if (calls.length) return calls.join('、');
  return source.type || '无';
}

function RawSignalDetails({ signal, toolCallsById }: { signal: any; toolCallsById: Map<string, any> }) {
  const callIds = signal.trace?.tool_calls || [];
  const calls = callIds.map((id: string) => toolCallsById.get(id)).filter(Boolean);
  const raw = {
    raw_summary: signal.raw_summary,
    source: signal.source,
    trace: signal.trace,
    matched_tool_calls: calls,
  };
  return (
    <details className="raw-details">
      <summary>查看完整原文与工具回执</summary>
      <pre className="raw-block">{JSON.stringify(raw, null, 2)}</pre>
    </details>
  );
}
