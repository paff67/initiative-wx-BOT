import { useMutation } from '@tanstack/react-query';
import { Play } from 'lucide-react';
import { postPreviewFull } from '../api/client';

export default function Preview({ profileId }: { profileId: string }) {
  const mutation = useMutation({ mutationFn: () => postPreviewFull({ profile_id: profileId, mode: 'full', force_llm: true }) });
  const render = mutation.data?.trace?.render;
  const speech = render?.speech;
  return (
    <div className="space-y-6">
      <header>
        <h2 className="text-3xl font-bold text-white">Preview</h2>
        <p className="text-[var(--color-text-secondary)] mt-1">完整 dry-run：State → Decision → Render，不投递</p>
      </header>
      <button onClick={() => mutation.mutate()} disabled={mutation.isPending || !profileId} className="inline-flex items-center gap-2 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 rounded px-4 py-2 text-white">
        <Play className="w-4 h-4" /> {mutation.isPending ? 'Running...' : 'Run Full Preview'}
      </button>
      {mutation.error && <div className="text-red-400">{String((mutation.error as Error).message)}</div>}
      {render && (
        <div className="glass-panel rounded-lg p-5">
          <h3 className="text-lg font-semibold mb-3">Final Weixin Preview</h3>
          <div className="bg-black/30 rounded p-4 text-xl">{render.type === 'text' ? render.text : '[SILENT]'}</div>
          {speech?.voice_design?.prompt && (
            <div className="mt-4 bg-black/20 border border-white/10 rounded p-3 text-sm text-slate-200">
              <div className="text-slate-400 mb-1">Voice Design</div>
              <div>{speech.voice_design.prompt}</div>
              <div className="text-slate-500 mt-2">mode: {speech.voice_design.delivery_mode} · audio: {speech.audio_format}</div>
            </div>
          )}
        </div>
      )}
      {mutation.data && (
        <pre className="text-xs bg-black/40 border border-white/10 rounded-lg p-4 overflow-auto max-h-[620px] text-emerald-100">{JSON.stringify(mutation.data, null, 2)}</pre>
      )}
    </div>
  );
}
