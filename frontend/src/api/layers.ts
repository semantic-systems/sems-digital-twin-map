import { apiFetch } from './client';
import type { LayersResponse, ScenariosResponse } from '../types';

export async function fetchLayers(): Promise<LayersResponse> {
  return apiFetch<LayersResponse>('/layers');
}

export async function fetchLayerGeoJSON(id: number): Promise<object> {
  return apiFetch<object>(`/layers/${id}/geojson`);
}

export async function fetchScenarios(): Promise<ScenariosResponse> {
  return apiFetch<ScenariosResponse>('/scenarios');
}

export async function fetchScenarioGeoJSON(id: number): Promise<object> {
  return apiFetch<object>(`/scenarios/${id}/geojson`);
}
