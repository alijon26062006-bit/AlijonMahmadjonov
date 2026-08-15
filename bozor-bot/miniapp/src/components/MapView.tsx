/** Обёртка Leaflet без react-leaflet: карта каталога, мини-карта, выбор точки. */
import L from 'leaflet';
import { useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { fmtPrice } from '../api/client';
import type { Card } from '../api/types';

const TILE = (import.meta.env.VITE_TILE_URL as string | undefined)
  ?? 'https://tile.openstreetmap.org/{z}/{x}/{y}.png';
const ATTR = '© OpenStreetMap contributors';

const DEFAULT_CENTER: [number, number] = [38.5598, 68.787]; // Душанбе

function pinIcon(text: string): L.DivIcon {
  return L.divIcon({ className: '', html: `<div class="pin">${text}</div>`, iconAnchor: [20, 14] });
}

export function CatalogMap({ items, onBounds }: {
  items: Card[];
  onBounds?: (b: { min_lon: number; min_lat: number; max_lon: number; max_lat: number }) => void;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const mapRef = useRef<L.Map | null>(null);
  const layerRef = useRef<L.LayerGroup | null>(null);
  const navigate = useNavigate();

  useEffect(() => {
    if (!ref.current || mapRef.current) return;
    const map = L.map(ref.current).setView(DEFAULT_CENTER, 12);
    L.tileLayer(TILE, { attribution: ATTR, maxZoom: 19 }).addTo(map);
    layerRef.current = L.layerGroup().addTo(map);
    mapRef.current = map;
    if (onBounds) {
      let t: ReturnType<typeof setTimeout>;
      map.on('moveend', () => {
        clearTimeout(t);
        t = setTimeout(() => {
          const b = map.getBounds();
          onBounds({ min_lon: b.getWest(), min_lat: b.getSouth(),
                     max_lon: b.getEast(), max_lat: b.getNorth() });
        }, 300);
      });
    }
    setTimeout(() => map.invalidateSize(), 50);
    return () => { map.remove(); mapRef.current = null; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    const layer = layerRef.current;
    if (!layer) return;
    layer.clearLayers();
    for (const item of items) {
      if (item.lat == null || item.lon == null) continue;
      L.marker([item.lat, item.lon], { icon: pinIcon(fmtPrice(item.price, item.currency)) })
        .on('click', () => navigate(`/listing/${item.public_id}`))
        .addTo(layer);
    }
  }, [items, navigate]);

  return <div ref={ref} className="map-wrap" />;
}

export function MiniMap({ lat, lon }: { lat: number; lon: number }) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!ref.current) return;
    const map = L.map(ref.current, {
      dragging: false, scrollWheelZoom: false, zoomControl: false,
    }).setView([lat, lon], 15);
    L.tileLayer(TILE, { attribution: ATTR }).addTo(map);
    L.marker([lat, lon], { icon: pinIcon('📍') }).addTo(map);
    setTimeout(() => map.invalidateSize(), 50);
    return () => { map.remove(); };
  }, [lat, lon]);
  return <div ref={ref} className="map-wrap map-mini" />;
}

export function PickMap({ value, onChange }: {
  value?: { lat: number; lon: number } | null;
  onChange: (p: { lat: number; lon: number }) => void;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const markerRef = useRef<L.Marker | null>(null);
  useEffect(() => {
    if (!ref.current) return;
    const map = L.map(ref.current).setView(
      value ? [value.lat, value.lon] : DEFAULT_CENTER, value ? 15 : 12);
    L.tileLayer(TILE, { attribution: ATTR }).addTo(map);
    if (value) {
      markerRef.current = L.marker([value.lat, value.lon], { icon: pinIcon('📍') }).addTo(map);
    }
    map.on('click', (e: L.LeafletMouseEvent) => {
      markerRef.current?.remove();
      markerRef.current = L.marker(e.latlng, { icon: pinIcon('📍') }).addTo(map);
      onChange({ lat: e.latlng.lat, lon: e.latlng.lng });
    });
    setTimeout(() => map.invalidateSize(), 50);
    return () => { map.remove(); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  return <div ref={ref} className="map-wrap map-mini" />;
}
