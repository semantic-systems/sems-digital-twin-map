import React, { useEffect, useRef, useState } from 'react';
import L from 'leaflet';
import {
  MapContainer,
  TileLayer,
  ZoomControl,
  GeoJSON,
  useMap,
  useMapEvents,
} from 'react-leaflet';
import { useMapStore } from '../../store/useMapStore';
import { useFilterStore } from '../../store/useFilterStore';
import { useReportStore } from '../../store/useReportStore';
import { useUserStore } from '../../store/useUserStore';
import { fetchLayerGeoJSON } from '../../api/layers';
import { updateLocations, fetchDots } from '../../api/reports';
import { ReportDots } from './ReportDots';
import { ActiveReportPolygons } from './ActiveReportPolygons';
import { OffscreenArrows } from './OffscreenArrows';
import type { LocationEntry } from '../../types';

// ---- PickModeHandler ----
function PickModeHandler(): null {
  const { pickMode, exitPickMode } = useMapStore();
  const { reports, optimisticUpdateLocations, setDots } = useReportStore();
  const { username } = useUserStore();
  const filters = useFilterStore();

  useMapEvents({
    click: async (e) => {
      if (!pickMode || !username) return;

      const { reportId, locIndex, mention } = pickMode;
      const report = reports.find((r) => r.id === reportId);
      if (!report) return;

      const effectiveLocs: LocationEntry[] =
        report.user_state.locations !== undefined && report.user_state.locations !== null
          ? report.user_state.locations
          : [...report.locations];

      const newLoc: LocationEntry = {
        mention: mention ?? undefined,
        lat: e.latlng.lat,
        lon: e.latlng.lng,
        name: `${e.latlng.lat.toFixed(5)}, ${e.latlng.lng.toFixed(5)}`,
      };

      let newLocs: LocationEntry[];
      if (locIndex !== null) {
        newLocs = effectiveLocs.map((l, i) => (i === locIndex ? newLoc : l));
      } else {
        newLocs = [...effectiveLocs, newLoc];
      }

      optimisticUpdateLocations(reportId, newLocs);
      exitPickMode();

      try {
        await updateLocations(reportId, username, newLocs);
        const dotsRes = await fetchDots({
          username,
          loc_filter: filters.locFilter,
          platforms: filters.platforms.length ? filters.platforms : filters.allPlatforms,
          event_types: filters.eventTypes,
          relevances: filters.relevances,
          show_hidden: filters.showHidden,
          show_flagged: filters.showFlagged,
          show_unflagged: filters.showUnflagged,
        });
        setDots(dotsRes.dots);
      } catch (e2) {
        console.error('Failed to update locations via map click:', e2);
      }
    },
  });

  return null;
}

// ---- FitBoundsHandler ----
function FitBoundsHandler(): null {
  const map = useMap();
  const { fitBoundsRequest, clearFitBounds } = useMapStore();

  useEffect(() => {
    if (!fitBoundsRequest) return;
    map.fitBounds(fitBoundsRequest, { padding: [40, 40] });
    clearFitBounds();
  }, [fitBoundsRequest]);

  return null;
}

// ---- LayerRenderer ----
const LAYER_COLORS = ['#6366f1', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#06b6d4', '#f97316', '#84cc16'];

interface LayerData {
  id: number;
  geojson: object | null;
}

function buildPopupHtml(props: Record<string, unknown> | null, layerName: string): string {
  if (!props) return `<div style="font-family:'Inter',sans-serif;font-size:12px;font-weight:600;">${layerName}</div>`;
  const entries = Object.entries(props).filter(([k]) => !k.startsWith('_'));
  if (entries.length === 0) return `<div style="font-family:'Inter',sans-serif;font-size:12px;font-weight:600;">${layerName}</div>`;
  const rows = entries
    .map(([k, v]) => `<tr><td style="padding:2px 8px 2px 0;color:#6b7280;white-space:nowrap;">${k}</td><td style="padding:2px 0;color:#111827;">${v}</td></tr>`)
    .join('');
  return `<div style="font-family:'Inter',sans-serif;font-size:12px;min-width:160px;">
    <div style="font-weight:600;margin-bottom:6px;">${layerName}</div>
    <table style="border-collapse:collapse;width:100%">${rows}</table>
  </div>`;
}

function LayerRenderer(): React.ReactElement {
  const { activeLayers, availableLayers } = useFilterStore();
  const [layerData, setLayerData] = useState<LayerData[]>([]);
  const loadedRef = useRef<Set<number>>(new Set());

  useEffect(() => {
    const toLoad = activeLayers.filter((id) => !loadedRef.current.has(id));
    if (toLoad.length === 0) return;

    Promise.allSettled(toLoad.map((id) => fetchLayerGeoJSON(id).then((geo) => ({ id, geo })))).then(
      (results) => {
        const newData: LayerData[] = [];
        for (const result of results) {
          if (result.status === 'fulfilled') {
            loadedRef.current.add(result.value.id);
            newData.push({ id: result.value.id, geojson: result.value.geo });
          }
        }
        setLayerData((prev) => [...prev.filter((d) => !newData.find((n) => n.id === d.id)), ...newData]);
      },
    );
  }, [activeLayers]);

  const visibleData = layerData.filter((d) => activeLayers.includes(d.id) && d.geojson !== null);

  return (
    <>
      {visibleData.map((d) => {
        const colorIdx = availableLayers.findIndex((l) => l.id === d.id);
        const color = LAYER_COLORS[colorIdx % LAYER_COLORS.length] ?? '#6366f1';
        const layerName = availableLayers.find((l) => l.id === d.id)?.name ?? `Layer ${d.id}`;
        return (
          <GeoJSON
            key={d.id}
            data={d.geojson as GeoJSON.GeoJsonObject}
            style={(feature) => {
              if (feature?.properties?._style) return feature.properties._style;
              return { color, weight: 2, fillColor: color, fillOpacity: 0.15 };
            }}
            pointToLayer={(_feature, latlng) =>
              L.circleMarker(latlng, { radius: 7, color, fillColor: color, fillOpacity: 0.8, weight: 2 })
            }
            onEachFeature={(feature, leafletLayer) => {
              const html = buildPopupHtml(feature.properties as Record<string, unknown> | null, layerName);
              leafletLayer.bindPopup(html, { maxWidth: 320 });
            }}
          />
        );
      })}
    </>
  );
}

// ---- Cursor style for pick mode ----
function PickModeCursor(): null {
  const map = useMap();
  const { pickMode } = useMapStore();

  useEffect(() => {
    const container = map.getContainer();
    if (pickMode) {
      container.style.cursor = 'crosshair';
    } else {
      container.style.cursor = '';
    }
    return () => {
      container.style.cursor = '';
    };
  }, [pickMode, map]);

  return null;
}

// ---- MapView ----
export function MapView(): React.ReactElement {
  return (
    <MapContainer
      center={[53.55, 9.99]}
      zoom={12}
      doubleClickZoom={false}
      zoomControl={false}
      style={{ width: '100%', height: '100%' }}
    >
      {/* OpenStreetMap base */}
      <TileLayer
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
        maxZoom={19}
      />

      {/* Layers */}
      <LayerRenderer />

      {/* Report dots */}
      <ReportDots />

      {/* Active report polygons */}
      <ActiveReportPolygons />

      {/* Offscreen arrows */}
      <OffscreenArrows />

      {/* Handlers */}
      <PickModeHandler />
      <FitBoundsHandler />
      <PickModeCursor />

      {/* Controls */}
      <ZoomControl position="topright" />
    </MapContainer>
  );
}
