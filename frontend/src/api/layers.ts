import { apiFetch } from './client';
import type { LayersResponse, ScenariosResponse } from '../types';

// Trailing slashes on purpose: both routes are declared as "/" under their
// prefix, so requesting them without one costs a 307 redirect -- which the
// browser may not follow at all if it lands on a different scheme/origin.
export async function fetchLayers(): Promise<LayersResponse> {
  return apiFetch<LayersResponse>('/layers/');
}

export async function fetchLayerGeoJSON(id: number): Promise<object> {
  return apiFetch<object>(`/layers/${id}/geojson`);
}

export async function fetchScenarios(): Promise<ScenariosResponse> {
  return apiFetch<ScenariosResponse>('/scenarios/');
}

export async function fetchScenarioGeoJSON(id: number): Promise<object> {
  return apiFetch<object>(`/scenarios/${id}/geojson`);
}
