import { useQuery } from '@tanstack/react-query';
import { fetchTraces } from '../api/client';

export default function Traces({ profileId }: { profileId: string }) {
  const { data } = useQuery({ queryKey: ['traces', profileId], queryFn: () => fetchTraces(80, profileId), refetchInterval: 8000, enabled: Boolean(profileId) });
  return (
    <div className="space-y-6">
      <header>
        <h2 className="text-3xl font-bold text-white">Traces</h2>
        <p className="text-[var(--color-text-secondary)] mt-1">World → State → Intent → Decision → Render → Delivery 全链路</p>
      </header>
      <div className="space-y-3">
        {(data?.traces || []).map((trace: any) => (
          <details key={trace.tick_run_id || trace.run_id} className="glass-panel rounded-lg p-4">
            <summary className="cursor-pointer text-white">{trace.tick_run_id || trace.run_id} <span className="text-gray-500">{trace.final || trace.render?.type}</span></summary>
            <pre className="text-xs mt-4 bg-black/30 rounded p-4 overflow-auto text-emerald-100">{JSON.stringify(trace, null, 2)}</pre>
          </details>
        ))}
      </div>
    </div>
  );
}
