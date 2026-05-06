import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Activity, Clock, ShieldCheck, Heart, Zap, Settings, XCircle, PauseCircle, Eye, AlertTriangle, Play, RefreshCw } from 'lucide-react';
import { fetchHealth, fetchStateCurrent, fetchHeartbeatState, fetchProxyStats, fetchHeartbeatControl, postHeartbeatControl, postHeartbeatTrigger, postStateTrigger } from '../api/client';

export default function Dashboard() {
  const { data: health } = useQuery({ queryKey: ['health'], queryFn: fetchHealth, refetchInterval: 10000 });
  const { data: state } = useQuery({ queryKey: ['stateCurrent'], queryFn: fetchStateCurrent, refetchInterval: 5000 });
  const { data: heartbeat } = useQuery({ queryKey: ['heartbeat'], queryFn: fetchHeartbeatState, refetchInterval: 10000 });
  const { data: proxy } = useQuery({ queryKey: ['proxyStats'], queryFn: fetchProxyStats, refetchInterval: 10000 });
  const { data: decisions } = useQuery({ queryKey: ['decisions'], queryFn: () => fetch('/api/heartbeat/decisions').then(r=>r.json()), refetchInterval: 10000 });

  const lastEvent = decisions?.events?.[0];
  const isCrashed = lastEvent?.action === 'crash';
  const openLoops = state?.interaction_analysis?.unresolved_open_loops || [];

  return (
    <div className="space-y-6">
      <header className="flex justify-between items-end mb-8">
        <div>
          <h2 className="text-3xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-white to-gray-400">总览面板</h2>
          <p className="text-[var(--color-text-secondary)] mt-1">实时遥测数据与当前状态快照</p>
        </div>
        {health?.status === 'ok' && (
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-emerald-500/10 text-emerald-400 text-sm font-medium border border-emerald-500/20 shadow-[0_0_15px_rgba(16,185,129,0.1)]">
            <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
            系统健康运行
          </div>
        )}
      </header>

      {isCrashed && (
        <div className="bg-red-500/20 border border-red-500/50 rounded-xl p-4 flex items-start gap-4 shadow-[0_0_20px_rgba(239,68,68,0.15)]">
          <AlertTriangle className="w-6 h-6 text-red-500 shrink-0 mt-0.5" />
          <div className="flex-1">
            <h3 className="text-red-400 font-bold mb-1">系统严重故障警告</h3>
            <p className="text-sm text-red-300/80">检测到林绛的上一次心跳逻辑发生底层崩溃 (Crash)。目前自动判断流程已被阻断。请立即查看【决策追踪】中的致命错误日志，并在修复代码后手动执行心跳以恢复状态。</p>
          </div>
        </div>
      )}

      {/* Primary Stats Row */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <StatCard
          title="虚拟时间阶段"
          value={state?.virtual_day_phase?.replace('_', ' ') || '未知'}
          icon={<Clock className="w-5 h-5 text-blue-400" />}
          gradient="from-blue-500/20 to-transparent"
        />
        <StatCard
          title="核心能量值"
          value={`${state?.energy || 0}/100`}
          subtitle={`社交能量: ${state?.social_energy || 0}`}
          icon={<Zap className="w-5 h-5 text-amber-400" />}
          gradient="from-amber-500/20 to-transparent"
        />
        <StatCard
          title="当前情绪"
          value={state?.mood?.replace(/_/g, ' ') || '平静'}
          icon={<Heart className="w-5 h-5 text-pink-400" />}
          gradient="from-pink-500/20 to-transparent"
        />
        <StatCard
          title="网关错误率"
          value={`${((proxy?.error_rate || 0) * 100).toFixed(1)}%`}
          subtitle={`近 ${proxy?.total || 0} 次请求`}
          icon={<ShieldCheck className="w-5 h-5 text-emerald-400" />}
          gradient="from-emerald-500/20 to-transparent"
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mt-6">
        {/* Private Context Panel */}
        <div className="glass-panel rounded-2xl p-6">
          <div className="flex items-center gap-3 mb-4">
            <div className="p-2 rounded-lg bg-purple-500/10">
              <Activity className="w-5 h-5 text-purple-400" />
            </div>
            <h3 className="text-lg font-semibold text-white">当前私有上下文 (Private Context)</h3>
          </div>
          <div className="p-4 rounded-xl bg-black/20 border border-[rgba(255,255,255,0.05)] text-[var(--color-text-secondary)] leading-relaxed min-h-[100px]">
            {state?.current_private_context || state?.persona_projection || '暂无上下文信息。'}
          </div>

          <div className="mt-6">
            <h4 className="text-sm font-medium text-[var(--color-text-tertiary)] uppercase tracking-wider mb-3">当前挂起心智 (Open Loops)</h4>
            <div className="space-y-2">
              {openLoops.map((loop: any, i: number) => (
                <div key={i} className="flex gap-3 text-sm p-3 rounded-lg bg-white/5 border border-white/5">
                  <div className="w-1.5 h-1.5 rounded-full bg-purple-400 mt-1.5 flex-shrink-0" />
                  <span className="text-[var(--color-text-primary)]">{typeof loop === 'string' ? loop : (loop.description || loop.id || JSON.stringify(loop))}</span>
                </div>
              ))}
              {openLoops.length === 0 && (
                <div className="text-sm text-[var(--color-text-tertiary)] italic">当前无挂起的心智循环。</div>
              )}
            </div>
          </div>
        </div>

        {/* Heartbeat Status Panel */}
        <div className="glass-panel rounded-2xl p-6">
          <h3 className="text-lg font-semibold text-white mb-4">主动心跳引擎 (Heartbeat)</h3>
          <div className="grid grid-cols-2 gap-4 mb-6">
            <div className="p-4 rounded-xl bg-black/20 border border-white/5">
              <div className="text-sm text-[var(--color-text-tertiary)] mb-1">今日主动发送</div>
              <div className="text-2xl font-bold text-white">
                {heartbeat?.today_initiation_count || 0} <span className="text-sm text-gray-500 font-normal">/ {heartbeat?.daily_limit || 3}</span>
              </div>
            </div>
            <div className="p-4 rounded-xl bg-black/20 border border-white/5">
              <div className="text-sm text-[var(--color-text-tertiary)] mb-1">冷却状态</div>
              <div className={`text-lg font-bold mt-1 ${heartbeat?.in_cooldown ? 'text-amber-400' : 'text-emerald-400'}`}>
                {heartbeat?.in_cooldown ? '休息中 (Cooldown)' : '就绪 (Ready)'}
              </div>
            </div>
          </div>

          <h4 className="text-sm font-medium text-[var(--color-text-tertiary)] uppercase tracking-wider mb-3">文件系统完整性监控</h4>
          <div className="space-y-3">
            {health?.files && Object.entries(health.files).map(([key, file]: [string, any]) => (
              <div key={key} className="flex items-center justify-between text-sm py-2 border-b border-white/5 last:border-0">
                <span className="text-gray-400 font-mono text-xs">{key}</span>
                {file.exists && file.readable ? (
                  <span className="text-emerald-400 flex items-center gap-1">
                    <div className="w-1.5 h-1.5 rounded-full bg-emerald-400" /> 正常
                  </span>
                ) : (
                  <span className="text-red-400">缺失 / 不可读</span>
                )}
              </div>
            ))}
          </div>

          <div className="mt-8 border-t border-white/10 pt-6">
            <SystemDiagnosticsPanel />
          </div>

          <div className="mt-8 border-t border-white/10 pt-6">
            <HeartbeatControlPanel />
          </div>
        </div>
      </div>
    </div>
  );
}

function StatCard({ title, value, subtitle, icon, gradient }: any) {
  return (
    <div className="glass-panel glass-panel-hover rounded-2xl p-5 relative overflow-hidden group">
      <div className={`absolute top-0 right-0 w-32 h-32 bg-gradient-to-bl ${gradient} blur-2xl opacity-50 group-hover:opacity-100 transition-opacity`} />
      <div className="flex justify-between items-start relative z-10">
        <div>
          <h4 className="text-sm font-medium text-[var(--color-text-secondary)]">{title}</h4>
          <div className="text-2xl font-bold text-white mt-1">{value}</div>
          {subtitle && <div className="text-xs text-[var(--color-text-tertiary)] mt-1">{subtitle}</div>}
        </div>
        <div className="p-2 rounded-xl bg-white/5 border border-white/10">
          {icon}
        </div>
      </div>
    </div>
  );
}

function SystemDiagnosticsPanel() {
  const queryClient = useQueryClient();
  const [result, setResult] = useState<any>(null);

  const triggerHeartbeatMutation = useMutation({
    mutationFn: () => postHeartbeatTrigger(),
    onSuccess: (data) => {
      setResult(data);
      queryClient.invalidateQueries({ queryKey: ['decisions'] });
      queryClient.invalidateQueries({ queryKey: ['heartbeat'] });
    },
    onError: (err: any) => {
      setResult({ status: 'error', stderr: err.message, exit_code: -1 });
    }
  });

  const triggerStateMutation = useMutation({
    mutationFn: () => postStateTrigger(),
    onSuccess: (data) => {
      setResult(data);
      queryClient.invalidateQueries({ queryKey: ['stateCurrent'] });
    },
    onError: (err: any) => {
      setResult({ status: 'error', stderr: err.message, exit_code: -1 });
    }
  });

  return (
    <div>
      <h4 className="text-sm font-medium text-[var(--color-text-tertiary)] uppercase tracking-wider mb-4 flex items-center gap-2">
        <Activity className="w-4 h-4" /> 系统诊断与执行器
      </h4>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Heartbeat Trigger */}
        <div className="flex flex-col justify-between p-3 rounded-lg bg-black/20 border border-white/5">
          <div className="mb-3">
            <div className="text-sm text-gray-300 font-medium">手动触发心跳判定</div>
            <div className="text-xs text-gray-500 mt-1">越过 Cron 调度，立刻运行一次后台决策脚本。</div>
          </div>
          <button
            onClick={() => triggerHeartbeatMutation.mutate()}
            disabled={triggerHeartbeatMutation.isPending || triggerStateMutation.isPending}
            className="w-full py-2 bg-emerald-600 hover:bg-emerald-500 text-white rounded text-xs font-semibold flex items-center justify-center gap-2 disabled:opacity-50 transition-colors"
          >
            {triggerHeartbeatMutation.isPending ? <div className="w-3 h-3 border-2 border-white/30 border-t-white rounded-full animate-spin"/> : <Play className="w-3 h-3"/>}
            {triggerHeartbeatMutation.isPending ? '执行中...' : 'Run Heartbeat'}
          </button>
        </div>

        {/* State Tick Trigger */}
        <div className="flex flex-col justify-between p-3 rounded-lg bg-black/20 border border-white/5">
          <div className="mb-3">
            <div className="text-sm text-gray-300 font-medium">手动刷新心智状态</div>
            <div className="text-xs text-gray-500 mt-1">立刻读取最新微信聊天，强制更新内部时间线。</div>
          </div>
          <button
            onClick={() => triggerStateMutation.mutate()}
            disabled={triggerHeartbeatMutation.isPending || triggerStateMutation.isPending}
            className="w-full py-2 bg-blue-600 hover:bg-blue-500 text-white rounded text-xs font-semibold flex items-center justify-center gap-2 disabled:opacity-50 transition-colors"
          >
            {triggerStateMutation.isPending ? <div className="w-3 h-3 border-2 border-white/30 border-t-white rounded-full animate-spin"/> : <RefreshCw className="w-3 h-3"/>}
            {triggerStateMutation.isPending ? '刷新中...' : 'Force State Tick'}
          </button>
        </div>
      </div>

      {result && (
        <div className={`mt-3 p-3 rounded text-xs overflow-x-auto ${result.exit_code === 0 ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-300' : 'bg-red-500/10 border-red-500/20 text-red-300'} border`}>
          <div className="font-bold mb-1">Exit Code: {result.exit_code}</div>
          {result.stderr && <pre className="whitespace-pre-wrap">{result.stderr}</pre>}
          {result.stdout && <pre className="whitespace-pre-wrap mt-2">{result.stdout}</pre>}
        </div>
      )}
    </div>
  );
}

function HeartbeatControlPanel() {
  const queryClient = useQueryClient();
  const { data: control } = useQuery({ queryKey: ['heartbeatControl'], queryFn: fetchHeartbeatControl, refetchInterval: 5000 });

  const override = control?.override || {};
  const isActive = override.mode && !override.consumed;

  const mutation = useMutation({
    mutationFn: (req: any) => postHeartbeatControl({ ...req, expected_revision: control?.revision }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['heartbeatControl'] });
    }
  });

  const handleAction = (action: string, duration_minutes?: number) => {
    if (action !== 'clear' && !window.confirm(`确定要执行 [${action}] 操作吗？这将改变主动心跳的默认行为。`)) return;
    mutation.mutate({ action, duration_minutes });
  };

  return (
    <div>
      <h4 className="text-sm font-medium text-[var(--color-text-tertiary)] uppercase tracking-wider mb-4 flex items-center gap-2">
        <Settings className="w-4 h-4" /> 心跳控制台 (Overrides)
      </h4>

      {isActive && (
        <div className="mb-4 p-3 rounded bg-purple-500/10 border border-purple-500/20 text-sm">
          <div className="flex justify-between items-start">
            <div>
              <span className="text-purple-400 font-bold uppercase mr-2">{override.mode}</span>
              <span className="text-gray-300">{override.reason}</span>
            </div>
          </div>
          {override.expires_at && (
            <div className="text-xs text-gray-500 mt-2">过期时间: {new Date(override.expires_at).toLocaleString()}</div>
          )}
        </div>
      )}

      <div className="flex flex-col gap-3">
        <div className="grid grid-cols-2 gap-2">
          <button
            onClick={() => handleAction('force_silent_next')}
            disabled={mutation.isPending}
            className="px-3 py-2 bg-black/40 hover:bg-white/10 border border-white/5 rounded text-xs text-left flex flex-col gap-1 transition-colors"
          >
            <span className="text-gray-300 font-semibold flex items-center gap-1"><PauseCircle className="w-3 h-3"/> 强制下一次静默</span>
            <span className="text-gray-500 text-[10px]">跳过 LLM 判定直接退出，节省 Token</span>
          </button>

          <button
            onClick={() => handleAction('standby_next')}
            disabled={mutation.isPending}
            className="px-3 py-2 bg-black/40 hover:bg-white/10 border border-white/5 rounded text-xs text-left flex flex-col gap-1 transition-colors"
          >
            <span className="text-blue-400 font-semibold flex items-center gap-1"><Eye className="w-3 h-3"/> 下一次待机观察</span>
            <span className="text-gray-500 text-[10px]">完整跑完决策但不发消息，用于测试</span>
          </button>

          <button
            onClick={() => handleAction('pause_until', 60)}
            disabled={mutation.isPending}
            className="px-3 py-2 bg-black/40 hover:bg-white/10 border border-white/5 rounded text-xs text-left flex flex-col gap-1 transition-colors"
          >
            <span className="text-amber-400 font-semibold flex items-center gap-1"><Clock className="w-3 h-3"/> 暂停心跳 1 小时</span>
            <span className="text-gray-500 text-[10px]">未来一小时内强制拦截所有触发</span>
          </button>

          <button
            onClick={() => handleAction('clear')}
            disabled={!isActive || mutation.isPending}
            className="px-3 py-2 bg-red-500/10 hover:bg-red-500/20 border border-red-500/20 rounded text-xs text-left flex flex-col gap-1 transition-colors disabled:opacity-30"
          >
            <span className="text-red-400 font-semibold flex items-center gap-1"><XCircle className="w-3 h-3"/> 恢复正常清除覆盖</span>
            <span className="text-red-500/50 text-[10px]">清除当前的 Override 状态</span>
          </button>
        </div>

        {mutation.isError && <div className="text-red-400 text-xs mt-2">执行失败: {(mutation.error as any).message}</div>}
      </div>
    </div>
  );
}
