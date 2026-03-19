import { apiFetch } from './client';
import type { DemoStatus } from '../types';

export async function fetchDemoStatus(): Promise<DemoStatus> {
  return apiFetch<DemoStatus>('/demo/status');
}

export async function resetDemo(): Promise<{ ok: boolean; total: number; interval_seconds: number }> {
  return apiFetch('/demo/reset', { method: 'POST' });
}
