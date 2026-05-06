import { useQuery } from '@tanstack/react-query';
import { Activity, Clock, Gauge, Radio } from 'lucide-react';
import { fetchPresenceEvents, fetchPresenceRuntime, fetchProfiles } from '../api/client';
import { EmptyState, KeyValue, MetricCard, PageHeader, Panel, Pill, TextList, formatDateTime, latestEvent, shortId } from '../lib/presenceView';

export default function PresenceOverview({ profileId }: { profileId: string }) {
  const { data: profiles } = useQuery({ queryKey: ['profiles'], queryFn: fetchProfiles, refetchInterval: 15000 });
  const { data: state } = useQuery({ queryKey: ['presence-runtime', profileId, 'state'], queryFn: () => fetchPresenceRuntime(profileId, 'state'), refetchInterval: 8000, enabled: Boolean(profileId) });
  const { data: intent } = useQuery({ queryKey: ['presence-runtime', profileId, 'intent'], queryFn: () => fetchPresenceRuntime(profileId, 'intent'), refetchInterval: 8000, enabled: Boolean(profileId) });
  const { data: ticks } = useQuery({ queryKey: ['presence-events', profileId, 'tick'], queryFn: () => fetchPresenceEvents(profileId, 'tick', 10), refetchInterval: 8000, enabled: Boolean(profileId) });
  const activeProfile = profiles?.profiles?.find((p: any) => p.profile_id === profileId);
  const lastTick = latestEvent(ticks);
  const openLoops = state?.interaction_analysis?.unresolved_open_loops || [];
  const continuityEvents = state?.private_continuity_events || [];
  const topics = Object.values(intent?.topics || {})
    .sort((a: any, b: any) => Number(b.score || 0) - Number(a.score || 0))
    .slice(0, 5) as any[];
  const counters = Object.entries(intent?.delivery_counters || {}) as Array<[string, any]>;

  return (
    <div className="stack">
      <PageHeader
        title="运行总览"
        description="把 State、Intent 和最近 Tick 拆成可读摘要，先看系统此刻怎么理解自己，再看它为什么醒来或跳过。"
      />

      <div className="metric-grid">
        <MetricCard label="Profile" value={activeProfile?.display_name || profileId || '未选择'} detail={activeProfile?.timezone || '默认时区'} icon={<Radio size={18} />} tone="accent" />
        <MetricCard label="注意力" value={state?.attention || 'unknown'} detail={state?.mood || '暂无 mood'} icon={<Activity size={18} />} tone="info" />
        <MetricCard label="能量" value={`${state?.energy ?? 0} / ${state?.social_energy ?? 0}`} detail="energy / social_energy" icon={<Gauge size={18} />} tone="warning" />
        <MetricCard label="最近 Tick" value={lastTick?.reason || shortId(lastTick?.tick_run_id || lastTick?.run_id)} detail={formatDateTime(lastTick?.created_at)} icon={<Clock size={18} />} tone={lastTick?.wakeAgent === false ? 'muted' : 'success'} />
      </div>

      <div className="split-grid">
        <Panel title="内部状态切片" eyebrow={state?.state_run_id ? shortId(state.state_run_id, 18) : 'runtime state'}>
          <div className="kv-stack">
            <KeyValue label="更新时间" value={formatDateTime(state?.updated_at)} />
            <KeyValue label="情绪底色" value={state?.mood || '暂无'} />
            <KeyValue label="自然收口" value={state?.interaction_analysis?.had_natural_closure ? <Pill tone="success">已收口</Pill> : <Pill tone="warning">仍有尾巴</Pill>} />
            <KeyValue label="画面感" value={state?.persona_projection || '暂无'} />
          </div>
        </Panel>

        <Panel title="意图累积器" eyebrow={`updated ${formatDateTime(intent?.updated_at)}`}>
          {topics.length ? (
            <div className="stack">
              {topics.map((topic) => (
                <div key={topic.topic_key} className="detail-band">
                  <div className="inline-row">
                    <Pill tone={Number(topic.score || 0) >= 2 ? 'warning' : 'accent'}>{topic.topic_key}</Pill>
                    <span className="mono">score {Number(topic.score || 0).toFixed(2)}</span>
                  </div>
                  <p className="mt-2 text-sm leading-6 text-[var(--color-muted)]">{topic.last_reason || topic.seed || '暂无张力说明'}</p>
                </div>
              ))}
            </div>
          ) : (
            <EmptyState title="当前没有盘旋话题" description="Intent Accumulator 已衰减为空，下一次 Decision 会按新状态重新判断。" />
          )}
        </Panel>
      </div>

      <div className="split-grid">
        <Panel title="未闭合互动" eyebrow="Interaction Gap">
          <TextList items={openLoops} empty="上一轮互动没有记录到明显尾巴" />
        </Panel>

        <Panel title="私人连续事件" eyebrow="Continuity Events">
          {continuityEvents.length ? (
            <div className="stack">
              {continuityEvents.map((event: any) => (
                <div key={event.event_key || event.summary} className="detail-band">
                  <div className="inline-row">
                    <Pill tone={event.can_surface_obliquely ? 'success' : 'muted'}>{event.can_surface_obliquely ? '可旁侧浮现' : '仅内部'}</Pill>
                    <span className="mono">{event.time_anchor || '无时间锚点'}</span>
                  </div>
                  <strong className="block mt-2">{event.event_key || 'continuity_event'}</strong>
                  <p className="mt-1 text-sm leading-6 text-[var(--color-muted)]">{event.summary || '暂无摘要'}</p>
                </div>
              ))}
            </div>
          ) : (
            <EmptyState title="还没有连续事件" description="State Layer 下次命中 LLM 后会补齐真实时间空白。" />
          )}
        </Panel>
      </div>

      <Panel title="可用世界信号" eyebrow="World Signals">
        <TextList items={state?.usable_world_signals} empty="本轮 State 没有提炼可用外部事实" />
      </Panel>

      {counters.length > 0 && (
        <Panel title="投递计数" eyebrow="message class cooldown">
          <div className="inline-row">
            {counters.map(([name, counter]) => (
              <Pill key={name} tone="neutral">
                {name}: {(counter?.events || []).length}
              </Pill>
            ))}
          </div>
        </Panel>
      )}
    </div>
  );
}
