export async function fetchHealth() {
  const res = await fetch('/api/health');
  if (!res.ok) throw new Error('Network response was not ok');
  return res.json();
}

export async function fetchStateCurrent() {
  const res = await fetch('/api/state/current');
  if (!res.ok) throw new Error('Network response was not ok');
  return res.json();
}

export async function fetchDecisions(limit = 50) {
  const res = await fetch(`/api/decisions?limit=${limit}`);
  if (!res.ok) throw new Error('Network response was not ok');
  return res.json();
}

export async function fetchHeartbeatState() {
  const res = await fetch('/api/heartbeat/state');
  if (!res.ok) throw new Error('Network response was not ok');
  return res.json();
}

export async function fetchProxyStats() {
  const res = await fetch('/api/proxy/stats');
  if (!res.ok) throw new Error('Network response was not ok');
  return res.json();
}

export async function fetchProxyCalls(limit = 50) {
  const res = await fetch(`/api/proxy/calls?limit=${limit}`);
  if (!res.ok) throw new Error('Network response was not ok');
  return res.json();
}

export async function fetchStateEvents(limit = 50) {
  const res = await fetch(`/api/state/events?limit=${limit}`);
  if (!res.ok) throw new Error('Network response was not ok');
  return res.json();
}

export async function fetchHeartbeatControl() {
  const res = await fetch('/api/heartbeat/control');
  if (!res.ok) throw new Error('Network response was not ok');
  return res.json();
}

export async function postHeartbeatControl(data: any) {
  const res = await fetch('/api/heartbeat/control', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(data),
  });
  const json = await res.json();
  if (!res.ok) throw new Error(json.detail || 'Failed to update control');
  return json;
}

export async function postHeartbeatFeedback(data: {target_run_id: string, content: string}) {
  const res = await fetch('/api/heartbeat/feedback', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(data),
  });
  const json = await res.json();
  if (!res.ok) throw new Error(json.detail || 'Failed to post feedback');
  return json;
}

export async function postHeartbeatTrigger() {
  const res = await fetch('/api/heartbeat/trigger', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    }
  });
  const json = await res.json();
  if (!res.ok) throw new Error(json.detail || 'Failed to trigger script');
  return json;
}

export async function postStateTrigger() {
  const res = await fetch('/api/state/trigger', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    }
  });
  const json = await res.json();
  if (!res.ok) throw new Error(json.detail || 'Failed to trigger state tick');
  return json;
}

export async function fetchSettings() {
  const res = await fetch('/api/settings');
  if (!res.ok) throw new Error('Network response was not ok');
  return res.json();
}

export async function fetchDecisionPrompt() {
  const res = await fetch('/api/settings/decision-prompt');
  if (!res.ok) throw new Error('Network response was not ok');
  return res.json();
}

export async function postDecisionPrompt(data: any) {
  const res = await fetch('/api/settings/decision-prompt', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(data),
  });
  const json = await res.json();
  if (!res.ok) throw new Error(json.detail || 'Failed to update prompt');
  return json;
}

export async function fetchProfiles() {
  const res = await fetch('/api/profiles');
  if (!res.ok) throw new Error('Failed to fetch profiles');
  return res.json();
}

export async function fetchProfileConfig(profileId = 'linjiang') {
  const res = await fetch(`/api/profiles/${profileId}/config`);
  if (!res.ok) throw new Error('Failed to fetch profile config');
  return res.json();
}

export async function postProfileConfig(profileId: string, data: any) {
  const res = await fetch(`/api/profiles/${profileId}/config`, {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(data),
  });
  const json = await res.json();
  if (!res.ok) throw new Error(json.detail || 'Failed to save profile config');
  return json;
}

export async function fetchProfileConfigBackups(profileId: string, kind?: string) {
  const params = new URLSearchParams();
  if (kind) params.set('kind', kind);
  const suffix = params.toString() ? `?${params.toString()}` : '';
  const res = await fetch(`/api/profiles/${profileId}/config/backups${suffix}`);
  if (!res.ok) throw new Error('Failed to fetch profile config backups');
  return res.json();
}

export async function postProfileConfigRollback(profileId: string, data: any) {
  const res = await fetch(`/api/profiles/${profileId}/config/rollback`, {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(data),
  });
  const json = await res.json();
  if (!res.ok) throw new Error(json.detail || 'Failed to rollback profile config');
  return json;
}

export async function postProfileValidate(profileId: string) {
  const res = await fetch(`/api/profiles/${profileId}/validate`, {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
  });
  const json = await res.json();
  if (!res.ok) throw new Error(json.detail || 'Failed to validate profile');
  return json;
}

export async function fetchPresenceEvents(profileId: string, kind: string, limit = 50) {
  const res = await fetch(`/api/profiles/${profileId}/events/${kind}?limit=${limit}`);
  if (!res.ok) throw new Error(`Failed to fetch ${kind} events`);
  return res.json();
}

export async function fetchPresenceRuntime(profileId: string, kind: string) {
  const res = await fetch(`/api/profiles/${profileId}/runtime/${kind}`);
  if (!res.ok) throw new Error(`Failed to fetch ${kind} runtime`);
  return res.json();
}

export async function postPreviewFull(data: any) {
  const res = await fetch('/api/preview/full', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(data),
  });
  const json = await res.json();
  if (!res.ok) throw new Error(json.detail || 'Failed to run preview');
  return json;
}

export async function fetchTraces(limit = 50, profileId = '') {
  const params = new URLSearchParams({ limit: String(limit) });
  if (profileId) params.set('profile_id', profileId);
  const res = await fetch(`/api/traces?${params.toString()}`);
  if (!res.ok) throw new Error('Failed to fetch traces');
  return res.json();
}

export async function fetchWorldSignals(limit = 100, profileId = '') {
  const params = new URLSearchParams({ limit: String(limit) });
  if (profileId) params.set('profile_id', profileId);
  const res = await fetch(`/api/world-signals?${params.toString()}`);
  if (!res.ok) throw new Error('Failed to fetch world signals');
  return res.json();
}

export async function postWorldSignalReview(signalId: string, data: any) {
  const res = await fetch(`/api/world-signals/${encodeURIComponent(signalId)}/review`, {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(data),
  });
  const json = await res.json();
  if (!res.ok) throw new Error(json.detail || 'Failed to review world signal');
  return json;
}
