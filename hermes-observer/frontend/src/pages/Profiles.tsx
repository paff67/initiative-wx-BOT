import { useEffect, useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { CheckCircle2, RotateCcw, Save } from 'lucide-react';
import {
  fetchProfileConfig,
  fetchProfileConfigBackups,
  fetchProfiles,
  postProfileConfig,
  postProfileConfigRollback,
  postProfileValidate,
} from '../api/client';

const kinds = ['manifest', 'persona', 'relationship', 'proactive_policy', 'world_policy', 'permission_policy', 'delivery', 'examples', 'voice'];

export default function Profiles({ profileId, onProfileChange }: { profileId: string; onProfileChange: (profileId: string) => void }) {
  const queryClient = useQueryClient();
  const [kind, setKind] = useState('proactive_policy');
  const [content, setContent] = useState('');
  const [confirm, setConfirm] = useState(false);
  const [backupFilename, setBackupFilename] = useState('');
  const [rollbackConfirm, setRollbackConfirm] = useState(false);
  const { data: profiles } = useQuery({ queryKey: ['profiles'], queryFn: fetchProfiles });
  const { data: config } = useQuery({ queryKey: ['profile-config', profileId], queryFn: () => fetchProfileConfig(profileId), enabled: Boolean(profileId) });
  const { data: backups } = useQuery({
    queryKey: ['profile-config-backups', profileId, kind],
    queryFn: () => fetchProfileConfigBackups(profileId, kind),
    enabled: Boolean(profileId && kind),
  });
  const selected = useMemo(() => config?.files?.[kind], [config, kind]);
  const backupList = backups?.backups || [];

  useEffect(() => {
    setContent(selected?.content || '');
    setConfirm(false);
    setBackupFilename('');
    setRollbackConfirm(false);
  }, [selected?.sha256, selected?.content]);

  const mutation = useMutation({
    mutationFn: () => postProfileConfig(profileId, { kind, content, expected_sha256: selected?.sha256 || '', confirm_write: confirm }),
    onSuccess: (data) => {
      if (data.status === 'diff_required') setConfirm(true);
      else {
        setConfirm(false);
        queryClient.invalidateQueries({ queryKey: ['profile-config', profileId] });
      }
    },
  });
  const validateMutation = useMutation({ mutationFn: () => postProfileValidate(profileId) });
  const rollbackMutation = useMutation({
    mutationFn: () => postProfileConfigRollback(profileId, {
      kind,
      backup_filename: backupFilename,
      expected_current_sha256: selected?.sha256 || '',
      confirm_rollback: rollbackConfirm,
    }),
    onSuccess: () => {
      setRollbackConfirm(false);
      setBackupFilename('');
      queryClient.invalidateQueries({ queryKey: ['profile-config', profileId] });
      queryClient.invalidateQueries({ queryKey: ['profile-config-backups', profileId, kind] });
    },
  });

  return (
    <div className="space-y-6">
      <header>
        <h2 className="text-3xl font-bold text-white">Profiles</h2>
        <p className="text-[var(--color-text-secondary)] mt-1">配置编辑、diff 预确认、自动备份与 rollback 基础</p>
      </header>
      <div className="glass-panel rounded-lg p-5 flex flex-wrap gap-3 items-center">
        <select className="bg-black/40 border border-white/10 rounded px-3 py-2" value={profileId} onChange={(event) => onProfileChange(event.target.value)}>
          {(profiles?.profiles || [{ profile_id: profileId, display_name: profileId }]).map((p: any) => (
            <option key={p.profile_id} value={p.profile_id}>{p.display_name || p.profile_id}</option>
          ))}
        </select>
        <select className="bg-black/40 border border-white/10 rounded px-3 py-2" value={kind} onChange={(e) => setKind(e.target.value)}>
          {kinds.map((item) => <option key={item} value={item}>{item}</option>)}
        </select>
        <button onClick={() => mutation.mutate()} className="inline-flex items-center gap-2 bg-blue-600 hover:bg-blue-500 rounded px-4 py-2 text-white">
          <Save className="w-4 h-4" /> {confirm ? 'Confirm Save' : 'Save'}
        </button>
        <button onClick={() => validateMutation.mutate()} className="inline-flex items-center gap-2 bg-slate-700 hover:bg-slate-600 rounded px-4 py-2 text-white">
          <CheckCircle2 className="w-4 h-4" /> Validate
        </button>
        <select className="bg-black/40 border border-white/10 rounded px-3 py-2 min-w-[280px]" value={backupFilename} onChange={(e) => { setBackupFilename(e.target.value); setRollbackConfirm(false); }}>
          <option value="">Select backup...</option>
          {backupList.map((backup: any) => (
            <option key={backup.filename} value={backup.filename}>{backup.mtime} · {backup.filename}</option>
          ))}
        </select>
        <button
          onClick={() => {
            if (!rollbackConfirm) setRollbackConfirm(true);
            else rollbackMutation.mutate();
          }}
          disabled={!backupFilename || rollbackMutation.isPending}
          className="inline-flex items-center gap-2 bg-amber-700 hover:bg-amber-600 disabled:opacity-50 rounded px-4 py-2 text-white"
        >
          <RotateCcw className="w-4 h-4" /> {rollbackConfirm ? 'Confirm Rollback' : 'Rollback'}
        </button>
        {mutation.error && <span className="text-red-400 text-sm">{String((mutation.error as Error).message)}</span>}
        {rollbackMutation.error && <span className="text-red-400 text-sm">{String((rollbackMutation.error as Error).message)}</span>}
        {validateMutation.data && <span className={validateMutation.data.ok ? 'text-emerald-300 text-sm' : 'text-red-300 text-sm'}>{validateMutation.data.ok ? 'Valid' : JSON.stringify(validateMutation.data)}</span>}
        {confirm && <span className="text-amber-300 text-sm">Diff ready. Click Confirm Save to write.</span>}
        {rollbackConfirm && <span className="text-amber-300 text-sm">Rollback selected backup? Click Confirm Rollback.</span>}
      </div>
      <textarea className="w-full h-[620px] bg-black/40 border border-white/10 rounded-lg p-4 font-mono text-sm text-slate-100" value={content} onChange={(e) => setContent(e.target.value)} />
    </div>
  );
}
