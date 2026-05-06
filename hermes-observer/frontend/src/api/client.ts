async function readJson(res: Response, fallbackMessage: string) {
  const contentType = res.headers.get('content-type') || '';
  const text = await res.text();

  if (!contentType.includes('application/json')) {
    const snippet = text.replace(/\s+/g, ' ').trim().slice(0, 240);
    const path = res.url ? new URL(res.url).pathname : 'API request';
    throw new Error(
      `API ${path} returned ${contentType || 'non-JSON'} with status ${res.status}. ` +
        `这通常表示请求命中了前端页面 fallback 或反向代理路由错误。` +
        (snippet ? ` 响应片段：${snippet}` : ''),
    );
  }

  let json: any = null;
  try {
    json = text ? JSON.parse(text) : null;
  } catch (error) {
    const path = res.url ? new URL(res.url).pathname : 'API request';
    throw new Error(`API ${path} returned invalid JSON with status ${res.status}`);
  }

  if (!res.ok) {
    throw new Error(json?.detail || fallbackMessage);
  }
  return json;
}

export async function fetchHealth() {
  const res = await fetch('/api/health');
  return readJson(res, 'Failed to fetch health');
}

export async function fetchStateCurrent() {
  const res = await fetch('/api/state/current');
  return readJson(res, 'Failed to fetch current state');
}

export async function fetchDecisions(limit = 50) {
  const res = await fetch(`/api/decisions?limit=${limit}`);
  return readJson(res, 'Failed to fetch decisions');
}

export async function fetchHeartbeatState() {
  const res = await fetch('/api/heartbeat/state');
  return readJson(res, 'Failed to fetch heartbeat state');
}

export async function fetchProxyStats() {
  const res = await fetch('/api/proxy/stats');
  return readJson(res, 'Failed to fetch proxy stats');
}

export async function fetchProxyCalls(limit = 50) {
  const res = await fetch(`/api/proxy/calls?limit=${limit}`);
  return readJson(res, 'Failed to fetch proxy calls');
}

export async function fetchStateEvents(limit = 50) {
  const res = await fetch(`/api/state/events?limit=${limit}`);
  return readJson(res, 'Failed to fetch state events');
}

export async function fetchHeartbeatControl() {
  const res = await fetch('/api/heartbeat/control');
  return readJson(res, 'Failed to fetch heartbeat control');
}

export async function postHeartbeatControl(data: any) {
  const res = await fetch('/api/heartbeat/control', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(data),
  });
  return readJson(res, 'Failed to update control');
}

export async function postHeartbeatFeedback(data: {target_run_id: string, content: string}) {
  const res = await fetch('/api/heartbeat/feedback', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(data),
  });
  return readJson(res, 'Failed to post feedback');
}

export async function postHeartbeatTrigger() {
  const res = await fetch('/api/heartbeat/trigger', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    }
  });
  return readJson(res, 'Failed to trigger script');
}

export async function postStateTrigger() {
  const res = await fetch('/api/state/trigger', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    }
  });
  return readJson(res, 'Failed to trigger state tick');
}

export async function fetchSettings() {
  const res = await fetch('/api/settings');
  return readJson(res, 'Failed to fetch settings');
}

export async function fetchDecisionPrompt() {
  const res = await fetch('/api/settings/decision-prompt');
  return readJson(res, 'Failed to fetch decision prompt');
}

export async function postDecisionPrompt(data: any) {
  const res = await fetch('/api/settings/decision-prompt', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(data),
  });
  return readJson(res, 'Failed to update prompt');
}

export async function fetchProfiles() {
  const res = await fetch('/api/profiles');
  return readJson(res, 'Failed to fetch profiles');
}

export async function fetchProfileConfig(profileId = 'linjiang') {
  const res = await fetch(`/api/profiles/${profileId}/config`);
  return readJson(res, 'Failed to fetch profile config');
}

export async function postProfileConfig(profileId: string, data: any) {
  const res = await fetch(`/api/profiles/${profileId}/config`, {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(data),
  });
  return readJson(res, 'Failed to save profile config');
}

export async function fetchProfileConfigBackups(profileId: string, kind?: string) {
  const params = new URLSearchParams();
  if (kind) params.set('kind', kind);
  const suffix = params.toString() ? `?${params.toString()}` : '';
  const res = await fetch(`/api/profiles/${profileId}/config/backups${suffix}`);
  return readJson(res, 'Failed to fetch profile config backups');
}

export async function postProfileConfigRollback(profileId: string, data: any) {
  const res = await fetch(`/api/profiles/${profileId}/config/rollback`, {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(data),
  });
  return readJson(res, 'Failed to rollback profile config');
}

export async function postProfileValidate(profileId: string) {
  const res = await fetch(`/api/profiles/${profileId}/validate`, {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
  });
  return readJson(res, 'Failed to validate profile');
}

export async function fetchPresenceEvents(profileId: string, kind: string, limit = 50) {
  const res = await fetch(`/api/profiles/${profileId}/events/${kind}?limit=${limit}`);
  return readJson(res, `Failed to fetch ${kind} events`);
}

export async function fetchPresenceRuntime(profileId: string, kind: string) {
  const res = await fetch(`/api/profiles/${profileId}/runtime/${kind}`);
  return readJson(res, `Failed to fetch ${kind} runtime`);
}

export async function postPreviewFull(data: any) {
  const res = await fetch('/api/preview/full', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(data),
  });
  const json = await readJson(res, 'Failed to start preview');
  if (json?.job_id && ['queued', 'running'].includes(json.status)) {
    return pollPreviewJob(json.job_id);
  }
  return json;
}

export async function fetchPreviewJob(jobId: string) {
  const res = await fetch(`/api/preview/jobs/${encodeURIComponent(jobId)}`);
  return readJson(res, 'Failed to fetch preview job');
}

async function pollPreviewJob(jobId: string) {
  const started = Date.now();
  let delayMs = 1200;
  while (Date.now() - started < 5 * 60 * 1000) {
    await new Promise((resolve) => setTimeout(resolve, delayMs));
    const job = await fetchPreviewJob(jobId);
    if (!['queued', 'running'].includes(job.status)) {
      return job;
    }
    delayMs = Math.min(3000, Math.round(delayMs * 1.25));
  }
  throw new Error(`Preview job ${jobId} 运行超过 5 分钟，已停止前端等待；可稍后刷新链路或查看后台 job 文件。`);
}

export async function fetchTraces(limit = 50, profileId = '') {
  const params = new URLSearchParams({ limit: String(limit) });
  if (profileId) params.set('profile_id', profileId);
  const res = await fetch(`/api/traces?${params.toString()}`);
  return readJson(res, 'Failed to fetch traces');
}

export async function fetchWorldSignals(limit = 100, profileId = '') {
  const params = new URLSearchParams({ limit: String(limit) });
  if (profileId) params.set('profile_id', profileId);
  const res = await fetch(`/api/world-signals?${params.toString()}`);
  return readJson(res, 'Failed to fetch world signals');
}

export async function postWorldSignalReview(signalId: string, data: any) {
  const res = await fetch(`/api/world-signals/${encodeURIComponent(signalId)}/review`, {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(data),
  });
  return readJson(res, 'Failed to review world signal');
}
