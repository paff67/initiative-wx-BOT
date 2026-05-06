import { useQuery } from '@tanstack/react-query';
import { fetchPresenceEvents } from '../api/client';

export default function PresenceDecisions({ profileId }: { profileId: string }) {
  const { data } = useQuery({ queryKey: ['presence-decisions', profileId], queryFn: () => fetchPresenceEvents(profileId, 'decision', 100), refetchInterval: 8000, enabled: Boolean(profileId) });
  return (
    <div className="space-y-6">
      <header>
        <h2 className="text-3xl font-bold text-white">Decisions</h2>
        <p className="text-[var(--color-text-secondary)] mt-1">新 Presence Kernel 决策事件</p>
      </header>
      <div className="glass-panel rounded-lg overflow-hidden">
        <table className="w-full data-table">
          <thead><tr><th>Run</th><th>Mode</th><th>Action</th><th>Class</th><th>Confidence</th><th>Reason</th></tr></thead>
          <tbody>
            {(data?.events || []).map((row: any) => {
              const d = row.decision || {};
              return <tr key={row.decision_run_id || row.run_id}><td className="font-mono text-xs">{row.decision_run_id}</td><td>{row.dry_run ? 'dry-run' : 'live'}</td><td>{d.action}</td><td>{d.message_class}</td><td>{d.confidence}</td><td>{d.reason}</td></tr>;
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
