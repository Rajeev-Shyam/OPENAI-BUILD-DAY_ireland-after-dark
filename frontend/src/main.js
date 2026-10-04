import { Map as LeafletMap, tileLayer, featureGroup, marker, divIcon, polyline } from 'leaflet';
import 'leaflet/dist/leaflet.css';
import './style.css';
import { getRoutes, toLeaflet } from './api.js';
import { dublinNow, departurePayload } from './time.js';

const byId = id => document.getElementById(id);

const map = new LeafletMap('map').setView([53.4, -8], 7);
tileLayer(import.meta.env.VITE_TILE_URL || 'https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
  maxZoom: 19,
  attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
}).addTo(map);
const routeLayer = featureGroup().addTo(map);

const endpoints = { origin: null, destination: null };
const markers = {};
let controller;

function pinIcon(label) {
  return divIcon({ className: 'endpoint-icon', html: label, iconSize: [26, 26] });
}

function status(message, isError = false) {
  const el = byId('status');
  el.textContent = message || '';
  el.className = isError ? 'error' : '';
}

function setHint() {
  if (!endpoints.origin) byId('hint').innerHTML = 'Click the map to set your <b>start</b>.';
  else if (!endpoints.destination) byId('hint').innerHTML = 'Now click the map to set your <b>destination</b>.';
  else byId('hint').innerHTML = 'Ready — press <b>Compare routes</b>.';
}

function reset() {
  endpoints.origin = null;
  endpoints.destination = null;
  markers.origin?.remove();
  markers.destination?.remove();
  routeLayer.clearLayers();
  byId('pins').hidden = true;
  byId('reset').hidden = true;
  byId('compare').disabled = true;
  byId('sheet').hidden = true;
  status('');
  setHint();
}

function placePoint(kind, point) {
  endpoints[kind] = point;
  markers[kind]?.remove();
  markers[kind] = marker(toLeaflet(point), { icon: pinIcon(kind === 'origin' ? 'A' : 'B') }).addTo(map);
  if (endpoints.origin && endpoints.destination) {
    byId('pins').hidden = false;
    byId('reset').hidden = false;
    byId('compare').disabled = false;
  }
  setHint();
}

map.on('click', event => {
  if (endpoints.origin && endpoints.destination) return;
  placePoint(endpoints.origin ? 'destination' : 'origin', [event.latlng.lng, event.latlng.lat]);
});

byId('reset').addEventListener('click', reset);
byId('sheet-close').addEventListener('click', () => { byId('sheet').hidden = true; });

function confidenceClass(confidence) {
  return confidence === 'High' ? 'high' : confidence === 'Medium' ? 'medium' : 'low';
}

function routeCard(route) {
  const night = route.kind === 'night';
  const title = night ? 'Night route' : 'Fastest route';
  const minutes = (route.duration_s / 60).toFixed(0);
  const km = (route.distance_m / 1000).toFixed(2);
  const lighting = route.lighting_coverage_pct === null ? 'Unknown' : `${route.lighting_coverage_pct.toFixed(0)}%`;
  const confidence = route.confidence ?? 'Unknown';
  const explanation = route.explanations[0] || '';

  return `
    <article class="card ${route.kind}">
      <h2>${title}</h2>
      <div class="stat-row">
        <div class="stat"><b>${minutes}</b><span>min</span></div>
        <div class="stat"><b>${km}</b><span>km</span></div>
        <div class="stat"><b>${lighting}</b><span>lit</span></div>
      </div>
      <span class="badge ${confidenceClass(confidence)}">${confidence} confidence</span>
      <p class="explain">${explanation}</p>
    </article>`;
}

function render(data) {
  routeLayer.clearLayers();
  for (const route of data.routes) {
    const night = route.kind === 'night';
    polyline(route.geometry.coordinates.map(toLeaflet), {
      color: night ? '#f5be53' : '#7ea2ff',
      weight: night ? 5 : 7,
      dashArray: night ? '2 10' : undefined,
    }).addTo(routeLayer);
  }
  if (routeLayer.getLayers().length) map.fitBounds(routeLayer.getBounds(), { padding: [60, 60] });

  byId('sheet-body').innerHTML = data.routes.map(routeCard).join('');
  byId('sheet').hidden = false;
  status('');
}

byId('compare').addEventListener('click', async () => {
  controller?.abort();
  controller = new AbortController();
  const payload = {
    origin: endpoints.origin,
    destination: endpoints.destination,
    ...departurePayload(dublinNow(), 'earlier'),
  };
  byId('compare').disabled = true;
  byId('sheet').hidden = true;
  status('Finding walking routes…');
  try {
    const data = await getRoutes(payload, {
      mode: 'api',
      baseUrl: import.meta.env.VITE_API_BASE_URL || '',
      signal: controller.signal,
    });
    render(data);
  } catch (error) {
    status(`${error.code || 'REQUEST_ERROR'}: ${error.message}`, true);
  } finally {
    byId('compare').disabled = false;
  }
});

setHint();
