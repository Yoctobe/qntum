import type { Dataset, EventInstance, EventTemplate, ModelVersion, Pin, Scenario, SimResult, SystemState } from './types';

async function request<T>(url: string, options?: RequestInit): Promise<T> {
  const res = await fetch(url, options);
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail ?? `${res.status} ${res.statusText}`);
  }
  return res.json();
}

export const fetchState = (dataset: Dataset = 'monthly') =>
  request<SystemState>(`/api/state?dataset=${dataset}`);

export const fetchDatasets = () =>
  request<{ choices: Dataset[]; descriptions: Record<Dataset, string> }>('/api/datasets');

export const fetchLibrary = (dataset: Dataset = 'monthly') =>
  request<EventTemplate[]>(`/api/library?dataset=${dataset}`);

export const simulate = (
  pins: Pin[],
  events: EventInstance[],
  horizon: number,
  nBootstrap: number,
  anticipation = 0,
  replayFrom?: string,
  dynamics: ModelVersion = 'v2',
  dataset: Dataset = 'monthly',
) =>
  request<SimResult>('/api/simulate', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      pins,
      events: events.map((e) => ({
        template: e.template,
        name: e.name,
        date: e.date,
        intensity: e.intensity,
        formation: e.formation,
        tau: e.tau,
      })),
      horizon,
      n_bootstrap: nBootstrap,
      anticipation,
      replay_from: replayFrom ?? null,
      dynamics,
      dataset,
    }),
  });

export const addTemplate = (
  template: Omit<EventTemplate, 'ranges' | 'analogues'>,
  dataset: Dataset = 'monthly',
) =>
  request<EventTemplate[]>('/api/library', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ...template, dataset }),
  });

export const addChannel = (name: string, transform: string, data: { date: string; value: number }[]) =>
  request<{ fit: unknown; state: SystemState }>('/api/channels', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name, transform, data }),
  });

export const setCoupling = (target: string, source: string, weight: number, lagDays: number) =>
  request<SystemState>('/api/matrix', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ target, source, weight, lag_days: lagDays }),
  });

export const removeCoupling = (target: string, source: string) =>
  request<SystemState>(
    `/api/matrix?target=${encodeURIComponent(target)}&source=${encodeURIComponent(source)}`,
    { method: 'DELETE' },
  );

export const fetchScenarios = () => request<Scenario[]>('/api/scenarios');

export const saveScenario = (scenario: Scenario) =>
  request<Scenario[]>('/api/scenarios', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(scenario),
  });

export const deleteScenario = (name: string) =>
  request<Scenario[]>(`/api/scenarios/${encodeURIComponent(name)}`, { method: 'DELETE' });
