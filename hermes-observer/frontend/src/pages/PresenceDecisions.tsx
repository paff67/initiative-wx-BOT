import { Fragment, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Eye } from 'lucide-react';
import { fetchPresenceEvents } from '../api/client';
import { ConfidenceBar, EmptyState, PageHeader, Panel, Pill, actionLabel, actionTone, classLabel, formatDateTime, modeLabel, shortId } from '../lib/presenceView';

export default function PresenceDecisions({ profileId }: { profileId: string }) {
  const [expanded, setExpanded] = useState<string | null>(null);
  const { data } = useQuery({ queryKey: ['presence-decisions', profileId], queryFn: () => fetchPresenceEvents(profileId, 'decision', 100), refetchInterval: 8000, enabled: Boolean(profileId) });
  const rows = data?.events || [];

  return (
    <div className="stack">
      <PageHeader
        title="动作决策"
        description="Decision Layer 的输出被整理成动作、消息类型、置信度、语音候选和一句话理由。点击 Prompt 可查看该次调用的完整 system/user prompt。"
      />

      <Panel>
        {rows.length === 0 ? (
          <EmptyState title="暂无决策事件" description="decision-events.jsonl 写入后会在这里显示。" />
        ) : (
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>时间</th>
                  <th>Run</th>
                  <th>模式</th>
                  <th>动作</th>
                  <th>类型</th>
                  <th>置信度</th>
                  <th>语音</th>
                  <th>理由与切入点</th>
                  <th>Prompt</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row: any) => {
                  const decision = row.decision || row;
                  const voice = decision.voice_design || {};
                  const rowId = row.decision_run_id || decision.decision_run_id || row.run_id;
                  const isOpen = expanded === rowId;
                  return (
                    <Fragment key={rowId}>
                      <tr key={rowId}>
                        <td>{formatDateTime(row.created_at)}</td>
                        <td className="mono">{shortId(rowId, 18)}</td>
                        <td><Pill tone={row.dry_run ? 'muted' : 'success'}>{modeLabel(row.dry_run)}</Pill></td>
                        <td><Pill tone={actionTone(decision.action)}>{actionLabel(decision.action)}</Pill></td>
                        <td>{classLabel(decision.message_class)}</td>
                        <td><ConfidenceBar value={decision.confidence} /></td>
                        <td><Pill tone={voice.enabled ? 'accent' : 'muted'}>{voice.enabled ? '候选' : '关闭'}</Pill></td>
                        <td>
                          <div className="stack">
                            <span>{decision.reasoning_summary || decision.reason || '无理由摘要'}</span>
                            {decision.render_brief?.entry_point && <span className="text-sm text-[var(--color-muted)]">切入：{decision.render_brief.entry_point}</span>}
                          </div>
                        </td>
                        <td>
                          <button type="button" className="btn btn-secondary" onClick={() => setExpanded(isOpen ? null : rowId)}>
                            <Eye size={15} /> {isOpen ? '收起' : '查看'}
                          </button>
                        </td>
                      </tr>
                      {isOpen && (
                        <tr key={`${rowId}-prompt`}>
                          <td colSpan={9}>
                            <PromptDetails prompt={row.prompt || decision.prompt_snapshot || decision.prompt} decision={decision} />
                          </td>
                        </tr>
                      )}
                    </Fragment>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </Panel>
    </div>
  );
}

function PromptDetails({ prompt, decision }: { prompt: any; decision: any }) {
  if (!prompt) {
    return (
      <div className="detail-band">
        <Pill tone="warning">历史事件未记录完整 prompt</Pill>
        <p className="mt-3 text-sm leading-6 text-[var(--color-muted)]">
          已更新 Decision Kernel，新的 decision-events 会保存 prompt snapshot。当前历史事件只能展示 LLM 输出摘要。
        </p>
        <details className="raw-details">
          <summary>查看本次 Decision 输出</summary>
          <pre className="raw-block">{JSON.stringify(decision, null, 2)}</pre>
        </details>
      </div>
    );
  }
  return (
    <div className="detail-band">
      <div className="inline-row">
        <Pill tone="accent">完整 Prompt</Pill>
        {prompt.messages?.length && <Pill tone="neutral">{prompt.messages.length} messages</Pill>}
      </div>
      <details className="raw-details" open>
        <summary>System Prompt</summary>
        <pre className="raw-block">{prompt.system || prompt.messages?.find((item: any) => item.role === 'system')?.content || '无'}</pre>
      </details>
      <details className="raw-details">
        <summary>User Payload</summary>
        <pre className="raw-block">{prompt.user || prompt.messages?.find((item: any) => item.role === 'user')?.content || '无'}</pre>
      </details>
    </div>
  );
}
