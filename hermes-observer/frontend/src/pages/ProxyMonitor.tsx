import { Fragment, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { fetchProxyCalls, fetchProxyStats } from '../api/client';
import { ServerCrash } from 'lucide-react';
import { ResponsiveContainer, AreaChart, Area, XAxis, YAxis, Tooltip, CartesianGrid } from 'recharts';
import { EmptyState, KeyValue, MetricCard, PageHeader, Panel, Pill, compactObject, formatDateTime, shortId } from '../lib/presenceView';

const outcomeTone: Record<string, 'success' | 'warning' | 'error' | 'neutral'> = {
  success: 'success',
  client_closed: 'warning',
  client_cancelled: 'warning',
  retry_exhausted: 'error',
  stream_error: 'warning',
  proxy_error: 'error',
};

export default function ProxyMonitor() {
  const { data: stats } = useQuery({ queryKey: ['proxyStats'], queryFn: fetchProxyStats, refetchInterval: 5000 });
  const { data: calls, isLoading: callsLoading } = useQuery({ queryKey: ['proxyCalls'], queryFn: () => fetchProxyCalls(50), refetchInterval: 5000 });
  const [expanded, setExpanded] = useState<string | null>(null);

  const chartData = calls ? [...calls].reverse().map((call: any, index: number) => ({
    index,
    time: new Date(call.ts).toLocaleTimeString('zh-CN', { hour12: false }),
    latency: call.latency_ms || 0,
  })) : [];
  const chatErrorRate = Number(stats?.chat_error_rate || stats?.error_rate || 0);

  return (
    <div className="stack">
      <PageHeader
        title="代理监控"
        description="wx-openai-proxy 请求结果、重试、断流和 Decision/State 关联观测。重点看聊天请求错误率，而不是模型探测噪声。"
      />

      <div className="metric-grid">
        <MetricCard label="样本请求" value={stats?.total || 0} detail="最近 200 条" tone="accent" />
        <MetricCard label="聊天补全" value={stats?.chat_total ?? stats?.chat_completions ?? 0} detail="chat/completions" tone="info" />
        <MetricCard label="聊天错误率" value={`${(chatErrorRate * 100).toFixed(1)}%`} detail={`探测错误 ${stats?.model_probe_errors || 0}`} tone={chatErrorRate > 0.05 ? 'error' : 'success'} />
        <MetricCard label="平均延迟" value={`${stats?.avg_latency_ms || 0} ms`} detail="所有样本平均" tone="warning" />
      </div>

      <div className="metric-grid">
        <MetricCard label="client closed" value={stats?.client_closed || 0} detail="客户端主动关闭" tone="muted" />
        <MetricCard label="retry exhausted" value={stats?.retry_exhausted || 0} detail="重试耗尽" tone={(stats?.retry_exhausted || 0) > 0 ? 'error' : 'success'} />
        <MetricCard label="全部错误率" value={`${(Number(stats?.all_error_rate || 0) * 100).toFixed(1)}%`} detail="含非聊天请求" tone="neutral" />
        <MetricCard label="Outcome 种类" value={Object.keys(stats?.outcome_distribution || {}).length} detail="请求结果分布" tone="neutral" />
      </div>

      <Panel title="近期延迟走势" eyebrow="latency">
        <div className="h-64 w-full">
          {callsLoading ? (
            <EmptyState title="加载图表数据中" />
          ) : (
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={chartData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="oklch(0.872 0.012 105)" vertical={false} />
                <XAxis dataKey="time" stroke="oklch(0.50 0.025 245)" fontSize={11} tickMargin={10} minTickGap={30} />
                <YAxis stroke="oklch(0.50 0.025 245)" fontSize={11} tickFormatter={(val) => `${val}ms`} />
                <Tooltip
                  contentStyle={{
                    background: 'oklch(0.992 0.004 105)',
                    border: '1px solid oklch(0.872 0.012 105)',
                    borderRadius: '12px',
                    color: 'oklch(0.245 0.018 245)',
                    boxShadow: '0 16px 34px oklch(0.35 0.02 105 / 0.12)',
                  }}
                  itemStyle={{ color: 'oklch(0.245 0.018 245)' }}
                />
                <Area type="monotone" dataKey="latency" stroke="oklch(0.56 0.12 174)" strokeWidth={2} fill="oklch(0.91 0.055 174 / 0.48)" isAnimationActive={false} />
              </AreaChart>
            </ResponsiveContainer>
          )}
        </div>
      </Panel>

      <Panel title="最新请求记录" eyebrow="点击行展开关键字段">
        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>时间</th>
                <th>方法 / 路径</th>
                <th>模型</th>
                <th>结果</th>
                <th>状态码</th>
                <th>Request ID</th>
                <th>来源</th>
                <th>次数</th>
                <th>错误</th>
                <th>延迟</th>
              </tr>
            </thead>
            <tbody>
              {callsLoading ? (
                <tr><td colSpan={10}>加载记录中...</td></tr>
              ) : !calls || calls.length === 0 ? (
                <tr><td colSpan={10}>无代理请求记录。</td></tr>
              ) : (
                calls.map((call: any, index: number) => {
                  const key = call.request_id || `${call.ts}-${index}`;
                  const isOpen = expanded === key;
                  return (
                    <Fragment key={key}>
                      <tr className="cursor-pointer" onClick={() => setExpanded(isOpen ? null : key)}>
                        <td className="mono">{formatDateTime(call.ts)}</td>
                        <td>
                          <div className="inline-row">
                            <Pill tone={call.method === 'POST' ? 'accent' : 'neutral'}>{call.method || 'GET'}</Pill>
                            <span className="mono">{compactObject(call.path, 72)}</span>
                          </div>
                        </td>
                        <td><Pill tone="neutral">{call.model || 'unknown'}</Pill></td>
                        <td><OutcomeBadge outcome={call.outcome} /></td>
                        <td><StatusBadge status={call.client_status || call.upstream_status} /></td>
                        <td className="mono">{shortId(call.request_id, 14)}</td>
                        <td>{call.source || call.run_id || '-'}</td>
                        <td className="mono">{call.attempt_count ?? (call.attempts?.length || 0)}</td>
                        <td>{call.error || call.error_type || '-'}</td>
                        <td className="mono">{call.latency_ms || 0} ms</td>
                      </tr>
                      {isOpen && (
                        <tr>
                          <td colSpan={10}>
                            <ProxyDetails call={call} />
                          </td>
                        </tr>
                      )}
                    </Fragment>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </Panel>
    </div>
  );
}

function OutcomeBadge({ outcome }: { outcome?: string }) {
  const value = outcome || 'legacy';
  return <Pill tone={outcomeTone[value] || 'neutral'}>{value}</Pill>;
}

function StatusBadge({ status }: { status?: number }) {
  if (!status) return <span className="text-[var(--color-muted)]">-</span>;
  if (status >= 200 && status < 300) return <Pill tone="success">{status}</Pill>;
  if (status >= 400 && status < 500) return <Pill tone="warning">{status}</Pill>;
  return <Pill tone="error"><ServerCrash size={13} /> {status}</Pill>;
}

function ProxyDetails({ call }: { call: any }) {
  return (
    <div className="detail-band">
      <div className="split-grid">
        <div className="kv-stack">
          <KeyValue label="request_id" value={call.request_id || '-'} mono />
          <KeyValue label="run_id" value={call.run_id || '-'} mono />
          <KeyValue label="source" value={call.source || '-'} />
          <KeyValue label="response_started" value={String(Boolean(call.response_started))} />
        </div>
        <div className="kv-stack">
          <KeyValue label="outcome" value={call.outcome || '-'} />
          <KeyValue label="error_type" value={call.error_type || '-'} />
          <KeyValue label="error" value={call.error || '-'} />
          <KeyValue label="attempts" value={attemptSummary(call.attempts)} />
        </div>
      </div>
    </div>
  );
}

function attemptSummary(attempts?: any[]) {
  if (!attempts?.length) return '无';
  return attempts.map((attempt, index) => `#${index + 1} ${attempt.status || attempt.error || 'unknown'}`).join('；');
}
