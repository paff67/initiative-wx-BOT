import { useState } from 'react';
import { useQuery, useMutation } from '@tanstack/react-query';
import { fetchDecisions, postHeartbeatFeedback } from '../api/client';
import { Bot, EyeOff, AlertTriangle, Send, ChevronDown, ChevronRight, CheckCircle2, Clock, Code } from 'lucide-react';

export default function Decisions() {
  const { data: decisions, isLoading } = useQuery({ queryKey: ['decisions'], queryFn: () => fetchDecisions(100), refetchInterval: 5000 });
  const [expandedRow, setExpandedRow] = useState<number | null>(null);

  return (
    <div className="space-y-6 max-w-5xl mx-auto">
      <header className="mb-8">
        <h2 className="text-3xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-white to-gray-400">决策引擎历史</h2>
        <p className="text-[var(--color-text-secondary)] mt-1">主动心跳触发的 LLM 内部决策日志</p>
      </header>

      <div className="glass-panel rounded-2xl overflow-hidden">
        {isLoading ? (
          <div className="p-8 text-center text-[var(--color-text-tertiary)]">正在加载决策日志...</div>
        ) : !decisions || decisions.length === 0 ? (
          <div className="p-8 text-center text-[var(--color-text-tertiary)]">当前无决策事件记录。</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full data-table">
              <thead>
                <tr>
                  <th>时间</th>
                  <th>动作</th>
                  <th>意图 / 理由</th>
                  <th>置信度</th>
                  <th>唤醒状态</th>
                </tr>
              </thead>
              <tbody>
                {decisions.map((d: any, i: number) => {
                  const isExpanded = expandedRow === i;
                  return (
                    <DecisionRow
                      key={i}
                      d={d}
                      isExpanded={isExpanded}
                      onToggle={() => setExpandedRow(isExpanded ? null : i)}
                    />
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}

function ActionBadge({ action, override }: { action: string, override?: string }) {
  if (override) return <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-medium bg-purple-500/10 text-purple-400 border border-purple-500/20"><Bot className="w-3 h-3" /> {override.toUpperCase()} 拦截</span>;
  if (action === 'send') return <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"><Send className="w-3 h-3" /> 发送发言</span>;
  if (action === 'silent' || action === 'hesitate') return <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-medium bg-gray-500/10 text-gray-400 border border-gray-500/20"><EyeOff className="w-3 h-3" /> 静默待机</span>;
  if (action === 'standby') return <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-medium bg-blue-500/10 text-blue-400 border border-blue-500/20"><Clock className="w-3 h-3" /> 观察测试</span>;
  if (action === 'error' || action === 'skip_error') return <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-medium bg-red-500/10 text-red-400 border border-red-500/20"><AlertTriangle className="w-3 h-3" /> 发生错误</span>;
  return <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-medium bg-blue-500/10 text-blue-400 border border-blue-500/20"><Bot className="w-3 h-3" /> {action.toUpperCase()}</span>;
}

function DecisionRow({ d, isExpanded, onToggle }: { d: any, isExpanded: boolean, onToggle: () => void }) {
  return (
    <>
      <tr onClick={onToggle} className="cursor-pointer hover:bg-white/5 transition-colors">
        <td className="whitespace-nowrap font-mono text-xs text-gray-400 flex items-center gap-2">
          {isExpanded ? <ChevronDown className="w-4 h-4 text-white" /> : <ChevronRight className="w-4 h-4" />}
          {new Date(d.local_time).toLocaleTimeString()}
        </td>
        <td>
          <ActionBadge action={d.action} override={d.override} />
        </td>
        <td className="max-w-md">
          {d.intent && <div className="text-sm font-medium text-white mb-1">{d.intent}</div>}
          <div className="text-xs text-gray-400 truncate" title={d.reason}>{d.reason || d.skip_reason || '未提供具体推理理由'}</div>
        </td>
        <td>
          {d.confidence ? (
            <div className="flex items-center gap-2">
              <div className="w-16 h-1.5 bg-gray-800 rounded-full overflow-hidden">
                <div
                  className={`h-full ${d.confidence > 0.8 ? 'bg-emerald-500' : d.confidence > 0.5 ? 'bg-amber-500' : 'bg-red-500'}`}
                  style={{ width: `${d.confidence * 100}%` }}
                />
              </div>
              <span className="text-xs font-mono text-gray-400">{d.confidence.toFixed(2)}</span>
            </div>
          ) : (
            <span className="text-xs text-gray-600">-</span>
          )}
        </td>
        <td>
          {d.wake_agent ? (
            <span className="px-2 py-1 rounded text-xs font-medium bg-blue-500/10 text-blue-400 border border-blue-500/20">WAKED 唤醒</span>
          ) : (
            <span className="text-xs text-gray-600">SLEEP 睡眠</span>
          )}
        </td>
      </tr>
      {isExpanded && (
        <tr>
          <td colSpan={5} className="p-0 border-b border-white/5 bg-black/40">
            <div className="p-6 space-y-6">
              {d._thought_process && (
                <div>
                  <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2 flex items-center gap-2">
                    <Bot className="w-4 h-4" /> 内部思维过程 (_thought_process)
                  </h4>
                  <div className="bg-white/5 border border-white/10 rounded-lg p-4 text-sm text-gray-300 leading-relaxed whitespace-pre-wrap">
                    {d._thought_process}
                  </div>
                  {/* Crash Traceback Viewer */}
                  {d.action === 'crash' && d.error && (
                    <div className="bg-red-500/10 border border-red-500/20 rounded-lg p-4 mt-4">
                      <h4 className="text-sm font-semibold text-red-400 mb-3 flex items-center gap-2">
                        <Code className="w-4 h-4" /> 致命错误 (System Crash Log)
                      </h4>
                      <pre className="text-xs text-red-300 font-mono overflow-x-auto p-4 bg-black/60 rounded">
                        {d.error}
                      </pre>
                    </div>
                  )}
                </div>
              )}

              {d.action !== 'crash' && (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  <div>
                    <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">执行状态</h4>
                    <div className="bg-white/5 rounded-lg p-4 space-y-2 text-sm">
                      <div className="flex justify-between"><span className="text-gray-400">调用模型:</span> <span className="font-mono text-white">{d.model || 'N/A'}</span></div>
                      <div className="flex justify-between"><span className="text-gray-400">网关耗时:</span> <span className="font-mono text-emerald-400">{d.latency_ms ? `${d.latency_ms} ms` : 'N/A'}</span></div>
                      <div className="flex justify-between"><span className="text-gray-400">时间戳:</span> <span className="font-mono text-gray-300">{d.timestamp}</span></div>
                      {d.override && <div className="flex justify-between"><span className="text-gray-400">被控拦截:</span> <span className="font-mono text-purple-400">{d.override}</span></div>}
                      {d.injected_feedback && <div className="flex justify-between"><span className="text-gray-400">被注入反馈:</span> <span className="text-amber-400">是 ({d.injected_feedback.length} 条)</span></div>}
                    </div>
                  </div>

                  {d.lin_current_state && (
                    <div>
                      <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">当时的内部心智</h4>
                      <div className="bg-white/5 rounded-lg p-4 space-y-2 text-sm">
                        <div className="flex justify-between"><span className="text-gray-400">能量:</span> <span>{d.lin_current_state.energy}</span></div>
                        <div className="flex justify-between"><span className="text-gray-400">情绪:</span> <span>{d.lin_current_state.mood}</span></div>
                        <div className="flex justify-between"><span className="text-gray-400">专注:</span> <span>{d.lin_current_state.attention}</span></div>
                        {d.lin_current_state.interaction_analysis?.unresolved_open_loops && (
                          <div className="mt-2 text-xs text-gray-500 truncate" title={(d.lin_current_state.interaction_analysis?.unresolved_open_loops || []).map((x: any)=>x.description || x).join(', ')}>
                            挂起事件: {(d.lin_current_state.interaction_analysis?.unresolved_open_loops || []).length} 个
                          </div>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              )}

              <div className="space-y-4">
                 <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wider flex items-center gap-2">
                   <ChevronRight className="w-4 h-4" /> 人类反馈注入 (Steering)
                 </h4>
                 <FeedbackForm targetRunId={`decision_${d.timestamp}`} />
              </div>

              {d.raw_json && (
                <details className="text-sm">
                  <summary className="text-gray-500 cursor-pointer hover:text-white transition-colors">查看原生大模型返回 (Raw JSON Output)</summary>
                  <pre className="mt-4 p-4 bg-black rounded border border-white/10 text-emerald-400/80 overflow-x-auto text-xs font-mono">
                    {d.raw_json}
                  </pre>
                </details>
              )}
            </div>
          </td>
        </tr>
      )}
    </>
  );
}

function FeedbackForm({ targetRunId }: { targetRunId: string }) {
  const [content, setContent] = useState('');
  const mutation = useMutation({
    mutationFn: (text: string) => postHeartbeatFeedback({ target_run_id: targetRunId, content: text }),
    onSuccess: () => {
      setContent('');
    }
  });

  return (
    <div className="bg-amber-500/10 border border-amber-500/20 rounded-lg p-4 flex flex-col gap-3">
      <p className="text-xs text-amber-500/80">如果你对刚才的决策不满意，可以在此输入指导意见，它会在下一次主动心跳时被注入给大模型纠偏。</p>
      <textarea
        className="w-full bg-black/50 border border-amber-500/30 rounded p-2 text-sm text-amber-100 placeholder-amber-700/50 focus:outline-none focus:border-amber-500"
        rows={2}
        placeholder="例如：刚才的回复太生硬了，下次遇到同类话题请先保持沉默。"
        value={content}
        onChange={(e) => setContent(e.target.value)}
      />
      <div className="flex gap-2 items-center">
        <button
          className="px-4 py-1.5 bg-amber-600 hover:bg-amber-500 text-white text-xs font-medium rounded transition-colors disabled:opacity-50 flex items-center gap-2"
          disabled={!content.trim() || mutation.isPending || mutation.isSuccess}
          onClick={() => mutation.mutate(content)}
        >
          {mutation.isPending ? '发送中...' : mutation.isSuccess ? <><CheckCircle2 className="w-3 h-3"/> 已提交</> : '注入反馈'}
        </button>
      </div>
      {mutation.isError && <div className="text-red-400 text-xs mt-2">错误: {(mutation.error as any).message}</div>}
    </div>
  );
}
