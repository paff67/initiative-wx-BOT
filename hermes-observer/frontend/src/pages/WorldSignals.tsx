import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Ban, Clock } from 'lucide-react';
import { fetchWorldSignals, postWorldSignalReview } from '../api/client';

export default function WorldSignals({ profileId }: { profileId: string }) {
  const queryClient = useQueryClient();
  const { data } = useQuery({ queryKey: ['world-signals', profileId], queryFn: () => fetchWorldSignals(100, profileId), refetchInterval: 10000, enabled: Boolean(profileId) });
  const mutation = useMutation({
    mutationFn: (signalId: string) => postWorldSignalReview(signalId, { action: 'blocked', reason: 'Blocked from Observer' }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['world-signals', profileId] }),
  });
  return (
    <div className="space-y-6">
      <header>
        <h2 className="text-3xl font-bold text-white">World Signals</h2>
        <p className="text-[var(--color-text-secondary)] mt-1">真实世界信号、来源、工具调用与事后纠偏</p>
      </header>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {(data?.signals || []).map((signal: any) => (
          <div key={signal.id} className="glass-panel rounded-lg p-4">
            <div className="flex justify-between gap-3">
              <div>
                <div className="text-white font-semibold">{signal.kind}</div>
                <div className="text-sm text-gray-400 flex items-center gap-1 mt-1"><Clock className="w-3 h-3" /> {signal.fetched_at}</div>
              </div>
              <button onClick={() => mutation.mutate(signal.id)} className="text-red-300 hover:text-red-200"><Ban className="w-4 h-4" /></button>
            </div>
            <p className="mt-3 text-slate-200">{signal.normalized_fact}</p>
            <pre className="text-xs mt-3 bg-black/30 rounded p-3 overflow-auto text-emerald-100">{JSON.stringify(signal.trace || signal.source || {}, null, 2)}</pre>
          </div>
        ))}
      </div>
    </div>
  );
}
