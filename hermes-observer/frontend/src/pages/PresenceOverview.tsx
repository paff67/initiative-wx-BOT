import { useQuery } from '@tanstack/react-query';
import type { ReactNode } from 'react';
import { Activity, Clock, Gauge, Radio } from 'lucide-react';
import { fetchPresenceEvents, fetchPresenceRuntime, fetchProfiles } from '../api/client';

export default function PresenceOverview({ profileId }: { profileId: string }) {
  const { data: profiles } = useQuery({ queryKey: ['profiles'], queryFn: fetchProfiles, refetchInterval: 15000 });
  const { data: state } = useQuery({ queryKey: ['presence-runtime', profileId, 'state'], queryFn: () => fetchPresenceRuntime(profileId, 'state'), refetchInterval: 8000, enabled: Boolean(profileId) });
  const { data: intent } = useQuery({ queryKey: ['presence-runtime', profileId, 'intent'], queryFn: () => fetchPresenceRuntime(profileId, 'intent'), refetchInterval: 8000, enabled: Boolean(profileId) });
  const { data: ticks } = useQuery({ queryKey: ['presence-events', profileId, 'tick'], queryFn: () => fetchPresenceEvents(profileId, 'tick', 10), refetchInterval: 8000, enabled: Boolean(profileId) });
  const activeProfile = profiles?.profiles?.find((p: any) => p.profile_id === profileId);
  const lastTick = ticks?.events?.[0];

  return (
    <div className="space-y-6">
      <header>
        <h2 className="text-3xl font-bold text-white">Presence Kernel</h2>
        <p className="text-[var(--color-text-secondary)] mt-1">通用主动心跳内核运行总览</p>
      </header>
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Metric title="Profile" value={activeProfile?.display_name || profileId} icon={<Radio className="w-5 h-5" />} />
        <Metric title="Attention" value={state?.attention || 'unknown'} icon={<Activity className="w-5 h-5" />} />
        <Metric title="Energy" value={`${state?.energy ?? 0}`} icon={<Gauge className="w-5 h-5" />} />
        <Metric title="Last Tick" value={lastTick?.reason || lastTick?.run_id || 'none'} icon={<Clock className="w-5 h-5" />} />
      </div>
      <section className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Panel title="Runtime State" data={state} />
        <Panel title="Intent Accumulator" data={intent} />
      </section>
    </div>
  );
}

function Metric({ title, value, icon }: { title: string; value: string; icon: ReactNode }) {
  return (
    <div className="glass-panel rounded-lg p-5">
      <div className="flex items-center justify-between text-[var(--color-text-secondary)]">
        <span className="text-sm">{title}</span>
        {icon}
      </div>
      <div className="text-xl font-semibold text-white mt-3 truncate">{value}</div>
    </div>
  );
}

function Panel({ title, data }: { title: string; data: any }) {
  return (
    <div className="glass-panel rounded-lg p-5">
      <h3 className="text-lg font-semibold mb-4">{title}</h3>
      <pre className="text-xs bg-black/30 rounded p-4 overflow-auto max-h-[460px] text-emerald-100">{JSON.stringify(data || {}, null, 2)}</pre>
    </div>
  );
}
