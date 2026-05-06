import { useQuery } from '@tanstack/react-query';
import { fetchStateEvents } from '../api/client';
import { Clock, ArrowRight } from 'lucide-react';

export default function StateTimeline() {
  const { data: events, isLoading } = useQuery({ queryKey: ['stateEvents'], queryFn: () => fetchStateEvents(50), refetchInterval: 10000 });

  return (
    <div className="space-y-6 max-w-4xl mx-auto">
      <header className="mb-8 flex justify-between items-end">
        <div>
          <h2 className="text-3xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-white to-gray-400">状态时间线</h2>
          <p className="text-[var(--color-text-secondary)] mt-1">Linjiang 内部心智状态的流转历史纪录</p>
        </div>
      </header>

      <div className="relative border-l border-white/10 ml-4 pl-8 space-y-8 pb-8">
        {isLoading ? (
          <div className="text-[var(--color-text-tertiary)] py-4">正在加载时间线数据...</div>
        ) : !events || events.length === 0 ? (
          <div className="text-[var(--color-text-tertiary)] py-4">当前无状态流转记录。</div>
        ) : (
          events.map((event: any, idx: number) => {
            const time = new Date(event.local_time || event.timestamp * 1000);
            const state = event.state || {};
            const privateEvents = state.private_continuity_events || [];

            return (
              <div key={idx} className="relative group">
                <div className="absolute -left-[41px] top-1.5 w-5 h-5 rounded-full bg-[var(--color-dark-bg)] border-2 border-purple-500 flex items-center justify-center group-hover:bg-purple-500 transition-colors">
                  <div className="w-1.5 h-1.5 rounded-full bg-purple-500 group-hover:bg-white transition-colors" />
                </div>

                <div className="mb-2 flex items-center gap-3">
                  <span className="text-sm font-bold text-white flex items-center gap-1.5">
                    <Clock className="w-4 h-4 text-purple-400" />
                    {time.toLocaleString()}
                  </span>
                  <span className="text-xs px-2 py-0.5 rounded-full bg-white/5 border border-white/10 text-gray-400 font-medium">
                    {state.virtual_day_phase || 'unknown'}
                  </span>
                </div>

                <div className="glass-panel glass-panel-hover rounded-xl p-5">
                  <div className="mb-4">
                    <div className="text-xs text-gray-500 uppercase tracking-wider font-semibold mb-1">私有上下文 (Private Context)</div>
                    <div className="text-sm text-gray-200 leading-relaxed border-l-2 border-purple-500/30 pl-3 py-1">
                      {state.current_private_context || state.persona_projection || '暂无数据'}
                    </div>
                  </div>

                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4 pt-4 border-t border-white/5">
                    <div>
                      <div className="text-[10px] text-gray-500 uppercase tracking-wider font-semibold">情绪 (Mood)</div>
                      <div className="text-sm text-white mt-0.5 capitalize">{state.mood?.replace(/_/g, ' ') || '-'}</div>
                    </div>
                    <div>
                      <div className="text-[10px] text-gray-500 uppercase tracking-wider font-semibold">能量 (Energy)</div>
                      <div className="text-sm text-white mt-0.5">{state.energy || 0} <span className="text-gray-500 text-xs">/100</span></div>
                    </div>
                    <div>
                      <div className="text-[10px] text-gray-500 uppercase tracking-wider font-semibold">专注度 (Attention)</div>
                      <div className="text-sm text-white mt-0.5 capitalize">{state.attention || '-'}</div>
                    </div>
                    <div>
                      <div className="text-[10px] text-gray-500 uppercase tracking-wider font-semibold">关系温度 (Rel. Temp)</div>
                      <div className="text-sm text-white mt-0.5 capitalize truncate" title={state.relationship_temperature || ''}>
                        {state.relationship_temperature?.replace(/_/g, ' ') || (state.interaction_analysis?.had_natural_closure === false ? 'open loop' : '-')}
                      </div>
                    </div>
                  </div>

                  {privateEvents.length > 0 && (
                    <div className="mt-4 pt-4 border-t border-white/5">
                      <div className="text-[10px] text-gray-500 uppercase tracking-wider font-semibold mb-2">连续事件 / 预备意图</div>
                      <div className="flex flex-wrap gap-2">
                        {privateEvents.slice(0, 3).map((item: any, i: number) => (
                          <span key={i} className="text-xs px-2 py-1 rounded bg-blue-500/10 text-blue-300 border border-blue-500/20 flex items-center gap-1 max-w-full truncate" title={item.summary || item.seed || ''}>
                            <ArrowRight className="w-3 h-3 flex-shrink-0" /> {item.event_key || item.intent || item.summary || 'event'}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
