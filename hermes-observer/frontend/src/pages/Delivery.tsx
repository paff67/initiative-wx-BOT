import { useQuery } from '@tanstack/react-query';
import { fetchPresenceEvents } from '../api/client';

export default function Delivery({ profileId }: { profileId: string }) {
  const { data } = useQuery({ queryKey: ['presence-delivery', profileId], queryFn: () => fetchPresenceEvents(profileId, 'delivery', 80), refetchInterval: 10000, enabled: Boolean(profileId) });
  return (
    <div className="space-y-6">
      <header>
        <h2 className="text-3xl font-bold text-white">Delivery</h2>
        <p className="text-[var(--color-text-secondary)] mt-1">最终投递、fallback 与媒体/action 状态</p>
      </header>
      <div className="space-y-3">
        {(data?.events || []).map((event: any) => (
          <div key={event.delivery_event_id || event.run_id} className="glass-panel rounded-lg p-4">
            <div className="text-sm text-gray-400">{event.delivery_event_id}</div>
            <div className="text-lg text-white mt-2">{event.render?.text || event.render?.type}</div>
            <pre className="text-xs mt-3 bg-black/30 rounded p-3 overflow-auto text-emerald-100">{JSON.stringify(event, null, 2)}</pre>
          </div>
        ))}
      </div>
    </div>
  );
}
