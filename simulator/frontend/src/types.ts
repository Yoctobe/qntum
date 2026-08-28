export interface ChannelInfo {
  name: string;
  transform: string;
  center: number;
  scale: number;
}

export interface Relationship {
  target: string;
  source: string;
  weight: number;
  significance: number;
  lag_days: number;
  manual: boolean;
}

export interface SystemState {
  dates: string[];
  observed: Record<string, number[]>;
  channels: ChannelInfo[];
  alpha: number;
  beta_v1: number;
  beta_v2: number;
  clamp_v1: number;
  max_spectral_radius: number;
  min_corr: number;
  relationships: Relationship[];
  influence_matrix: number[][];
}

export type ModelVersion = 'v1' | 'v2';
export type Dataset = 'monthly' | 'medical' | 'ecosystem';

export interface EventTemplate {
  name: string;
  description: string;
  formation: number;
  tau: number;
  first_hop: Record<string, number>;
  ranges: Record<string, number[]>;
  analogues: string[];
}

export interface Pin {
  channel: string;
  date: string;
  value: number;
}

export interface EventInstance {
  id: string;
  template: string;
  name: string;
  date: string;
  intensity: number;
  formation: number;
  tau: number;
}

export interface SimChannel {
  name: string;
  levels: number[];
  status: number[]; // 1 observed, 2 pinned, 3 simulated
  lower?: number[];
  upper?: number[];
}

export interface SimResult {
  dates: string[];
  sim_start: number;
  channels: SimChannel[];
  events: { name: string; trajectory: number[] }[];
}

export interface Scenario {
  name: string;
  pins: Pin[];
  events: EventInstance[];
  horizon: number;
  anticipation: number;
}

export const OBSERVED = 1;
export const PINNED = 2;
