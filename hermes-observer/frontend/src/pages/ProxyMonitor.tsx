import { Fragment, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { fetchProxyCalls, fetchProxyStats } from '../api/client';
import { Activity, ServerCrash } from 'lucide-react';
import { ResponsiveContainer, AreaChart, Area, XAxis, YAxis, Tooltip, CartesianGrid } from 'recharts';

const outcomeClass: Record<string, string> = {
  success: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/20',
  client_closed: 'bg-yellow-500/15 text-yellow-300 border-yellow-500/20',
  client_cancelled: 'bg-yellow-500/15 text-yellow-300 border-yellow-500/20',
  retry_exhausted: 'bg-red-500/15 text-red-300 border-red-500/20',
  stream_error: 'bg-orange-500/15 text-orange-300 border-orange-500/20',
  proxy_error: 'bg-red-500/15 text-red-300 border-red-500/20',
};

export default function ProxyMonitor() {
  const { data: stats } = useQuery({ queryKey: ['proxyStats'], queryFn: fetchProxyStats, refetchInterval: 5000 });
  const { data: calls, isLoading: callsLoading } = useQuery({ queryKey: ['proxyCalls'], queryFn: () => fetchProxyCalls(50), refetchInterval: 5000 });
  const [expanded, setExpanded] = useState<string | null>(null);

  const chartData = calls ? [...calls].reverse().map((c: any, i: number) => ({
    index: i,
    time: new Date(c.ts).toLocaleTimeString([], { hour12: false }),
    latency: c.latency_ms,
    status: c.client_status || c.upstream_status
  })) : [];

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      <header className="mb-8">
        <h2 className="text-3xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-white to-gray-400">网关监控</h2>
        <p className="text-[var(--color-text-secondary)] mt-1">wx-openai-proxy v2 请求结果、重试、断流和 Decision/State 关联观测</p>
      </header>

      <div className="grid grid-cols-1 md:grid-cols-3 xl:grid-cols-6 gap-4">
        <MetricCard label="样本总请求数" value={stats?.total || 0} accent="bg-blue-500/10" />
        <MetricCard label="聊天补全请求数" value={stats?.chat_total ?? stats?.chat_completions ?? 0} accent="bg-amber-500/10" />
        <div className="glass-panel rounded-2xl p-5 relative overflow-hidden">
          <div className="text-sm font-medium text-[var(--color-text-secondary)]">聊天补全错误率</div>
          <div className={`text-3xl font-bold mt-1 ${((stats?.chat_error_rate || stats?.error_rate || 0) > 0.05) ? 'text-red-400' : 'text-emerald-400'}`}>
            {((stats?.chat_error_rate || stats?.error_rate || 0) * 100).toFixed(1)}%
          </div>
          <div className="text-xs text-gray-500 mt-1">探测错误: {stats?.model_probe_errors || 0}</div>
          <div className="absolute -right-4 -bottom-4 w-24 h-24 bg-emerald-500/10 rounded-full blur-xl" />
        </div>
        <MetricCard label="平均延迟" value={`${stats?.avg_latency_ms || 0}`} suffix="毫秒" accent="bg-purple-500/10" />
        <MetricCard label="client closed 数" value={stats?.client_closed || 0} accent="bg-yellow-500/10" />
        <MetricCard label="retry exhausted 数" value={stats?.retry_exhausted || 0} accent="bg-red-500/10" />
      </div>

      <div className="glass-panel rounded-2xl p-6">
        <h3 className="text-lg font-semibold text-white mb-6 flex items-center gap-2">
          <Activity className="w-5 h-5 text-blue-400" />
          近期延迟走势
        </h3>
        <div className="h-64 w-full">
          {callsLoading ? (
            <div className="w-full h-full flex items-center justify-center text-gray-500">加载图表数据中...</div>
          ) : (
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={chartData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                <defs>
                  <linearGradient id="colorLatency" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.3} />
                    <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" vertical={false} />
                <XAxis dataKey="time" stroke="rgba(255,255,255,0.2)" fontSize={11} tickMargin={10} minTickGap={30} />
                <YAxis stroke="rgba(255,255,255,0.2)" fontSize={11} tickFormatter={(val) => `${val}ms`} />
                <Tooltip
                  contentStyle={{ backgroundColor: 'rgba(24, 24, 27, 0.9)', borderColor: 'rgba(255,255,255,0.1)', borderRadius: '8px' }}
                  itemStyle={{ color: '#fff' }}
                />
                <Area type="monotone" dataKey="latency" stroke="#3b82f6" strokeWidth={2} fillOpacity={1} fill="url(#colorLatency)" isAnimationActive={false} />
              </AreaChart>
            </ResponsiveContainer>
          )}
        </div>
      </div>

      <div className="glass-panel rounded-2xl overflow-hidden">
        <div className="p-5 border-b border-white/5 flex justify-between items-center bg-black/20">
          <h3 className="font-semibold text-white">最新请求记录</h3>
          <span className="text-xs text-gray-500">点击行展开 request_id / run_id / error / attempts 详情</span>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full data-table">
            <thead>
              <tr>
                <th>时间</th>
                <th>方法 / 路径</th>
                <th>模型</th>
                <th>Outcome</th>
                <th>状态码</th>
                <th>Request ID</th>
                <th>Source</th>
                <th>Attempts</th>
                <th>Error</th>
                <th>延迟</th>
              </tr>
            </thead>
            <tbody>
              {callsLoading ? (
                <tr><td colSpan={10} className="text-center py-8 text-gray-500">加载记录中...</td></tr>
              ) : !calls || calls.length === 0 ? (
                <tr><td colSpan={10} className="text-center py-8 text-gray-500">无代理请求记录。</td></tr>
              ) : (
                calls.map((c: any, i: number) => {
                  const key = c.request_id || `${c.ts}-${i}`;
                  const isOpen = expanded === key;
                  return (
                    <Fragment key={key}>
                      <tr className="cursor-pointer hover:bg-white/[0.03]" onClick={() => setExpanded(isOpen ? null : key)}>
                        <td className="whitespace-nowrap font-mono text-xs text-gray-400">
                          {new Date(c.ts).toLocaleTimeString([], { hour12: false })}
                        </td>
                        <td>
                          <div className="flex items-center gap-2">
                            <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded ${c.method === 'POST' ? 'bg-blue-500/20 text-blue-400' : 'bg-gray-500/20 text-gray-400'}`}>
                              {c.method}
                            </span>
                            <span className="font-mono text-xs text-gray-300 truncate max-w-[180px]" title={c.path}>
                              {c.path}
                            </span>
                          </div>
                        </td>
                        <td>
                          <span className="text-xs px-2 py-0.5 rounded-full bg-white/5 border border-white/10 text-gray-300">
                            {c.model || 'unknown'}
                          </span>
                        </td>
                        <td><OutcomeBadge outcome={c.outcome} /></td>
                        <td><StatusBadge status={c.client_status || c.upstream_status} /></td>
                        <td className="font-mono text-[11px] text-gray-400 max-w-[130px] truncate" title={c.request_id}>{c.request_id || '-'}</td>
                        <td className="text-xs text-gray-300 max-w-[130px] truncate" title={c.source || c.run_id}>{c.source || '-'}</td>
                        <td className="font-mono text-xs text-gray-400">{c.attempt_count ?? (c.attempts?.length || 0)}</td>
                        <td className="text-xs text-red-300 max-w-[180px] truncate" title={c.error || c.error_type}>{c.error || c.error_type || '-'}</td>
                        <td className="font-mono text-xs text-gray-400 whitespace-nowrap">{c.latency_ms} <span className="text-gray-600">ms</span></td>
                      </tr>
                      {isOpen && (
                        <tr>
                          <td colSpan={10} className="bg-black/30 p-4">
                            <ProxyDetails call={c} />
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
      </div>
    </div>
  );
}

function MetricCard({ label, value, suffix, accent }: { label: string; value: string | number; suffix?: string; accent: string }) {
  return (
    <div className="glass-panel rounded-2xl p-5 relative overflow-hidden">
      <div className="text-sm font-medium text-[var(--color-text-secondary)]">{label}</div>
      <div className="text-3xl font-bold text-white mt-1">{value} {suffix && <span className="text-lg text-gray-500 font-normal">{suffix}</span>}</div>
      <div className={`absolute -right-4 -bottom-4 w-24 h-24 ${accent} rounded-full blur-xl`} />
    </div>
  );
}

function OutcomeBadge({ outcome }: { outcome?: string }) {
  const value = outcome || 'legacy';
  const klass = outcomeClass[value] || 'bg-gray-500/15 text-gray-300 border-gray-500/20';
  return <span className={`text-[11px] font-semibold px-2 py-0.5 rounded-full border ${klass}`}>{value}</span>;
}

function StatusBadge({ status }: { status: number }) {
  if (!status) return <span className="text-gray-500">-</span>;
  if (status >= 200 && status < 300) return <span className="text-emerald-400 font-mono text-xs font-medium">{status}</span>;
  if (status >= 400 && status < 500) return <span className="text-amber-400 font-mono text-xs font-medium">{status}</span>;
  return <span className="text-red-400 font-mono text-xs font-medium flex items-center gap-1"><ServerCrash className="w-3 h-3" /> {status}</span>;
}

function ProxyDetails({ call }: { call: any }) {
  const details = {
    request_id: call.request_id,
    run_id: call.run_id,
    source: call.source,
    outcome: call.outcome,
    error_type: call.error_type,
    error: call.error,
    attempts: call.attempts || [],
    response_started: call.response_started,
    ts: call.ts,
    ts_local: call.ts ? new Date(call.ts).toLocaleString() : undefined,
  };
  return (
    <pre className="text-xs text-gray-300 whitespace-pre-wrap break-words font-mono leading-relaxed">
      {JSON.stringify(details, null, 2)}
    </pre>
  );
}
