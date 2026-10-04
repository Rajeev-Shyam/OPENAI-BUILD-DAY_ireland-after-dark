import { Map as LeafletMap, tileLayer, featureGroup, marker, divIcon, polyline } from 'leaflet';
import 'leaflet/dist/leaflet.css';
import './style.css';
import { getRoutes, toLeaflet } from './api.js';
import { dublinNow, departurePayload } from './time.js';

const byId = id => document.getElementById(id);

const map = new LeafletMap('map').setView([53.35, -6.26], 12);
tileLayer(import.meta.env.VITE_TILE_URL || 'https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
  maxZoom: 19,
  attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
}).addTo(map);
const routeLayer = featureGroup().addTo(map);
const markers = {};

function status(message, isError = false) {
  const el = byId('status');
  el.textContent = message || '';
  el.className = isError ? 'error' : '';
}

// Single lookup per submit (not autocomplete-as-you-type), biased to Ireland.
// See https://operations.osmfoundation.org/policies/nominatim/.
async function geocode(query, signal) {
  const url = `https://nominatim.openstreetmap.org/search?format=json&countrycodes=ie&limit=1&q=${encodeURIComponent(query)}`;
  const response = await fetch(url, { signal, headers: { Accept: 'application/json' } });
  if (!response.ok) throw new Error('Place search is unavailable right now.');
  const [match] = await response.json();
  if (!match) throw new Error(`Could not find "${query}" in Ireland.`);
  return [Number(match.lon), Number(match.lat)];
}

function placePin(kind, point, label) {
  markers[kind]?.remove();
  markers[kind] = marker(toLeaflet(point), {
    icon: divIcon({ className: 'endpoint-icon', html: kind === 'origin' ? 'A' : 'B', iconSize: [26, 26] }),
    title: label,
  }).addTo(map);
}

function confidenceClass(confidence) {
  return confidence === 'High' ? 'high' : confidence === 'Medium' ? 'medium' : 'low';
}

function factorBar(factor) {
  const known = factor.value !== null;
  const pct = known ? Math.max(0, Math.min(100, factor.value)) : 0;
  return `
    <div class="factor">
      <div class="factor-label"><span>${factor.label}</span><b>${known ? `${factor.value.toFixed(0)}%` : 'Unknown'}</b></div>
      <div class="factor-track"><div class="factor-fill ${known ? '' : 'unknown'}" style="width:${known ? pct : 100}%"></div></div>
    </div>`;
}

function routeCard(route) {
  const night = route.kind === 'night';
  const title = night ? 'Night route' : 'Fastest route';
  const minutes = (route.duration_s / 60).toFixed(0);
  const km = (route.distance_m / 1000).toFixed(2);
  const confidence = route.confidence ?? 'Unknown';
  const explanation = route.explanations[0] || '';
  const factors = route.score_breakdown.length
    ? route.score_breakdown.map(factorBar).join('')
    : '<p class="muted">No recorded lighting or footfall evidence here.</p>';

  return `
    <article class="card ${route.kind}">
      <h2>${title}</h2>
      <div class="stat-row">
        <div class="stat"><b>${minutes}</b><span>min</span></div>
        <div class="stat"><b>${km}</b><span>km</span></div>
      </div>
      <span class="badge ${confidenceClass(confidence)}">${confidence} confidence</span>
      <div class="factors">${factors}</div>
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

  byId('sheet-intro').textContent = 'Compared using recorded street lighting and historical footfall activity. No crime data is used.';
  byId('sheet-body').innerHTML = data.routes.map(routeCard).join('');
  byId('sheet').hidden = false;
  status('');
}

let controller;
byId('panel').addEventListener('submit', async event => {
  event.preventDefault();
  controller?.abort();
  controller = new AbortController();
  const originQuery = byId('origin-input').value.trim();
  const destinationQuery = byId('destination-input').value.trim();
  if (!originQuery || !destinationQuery) { status('Enter both a start and a destination.', true); return; }

  byId('compare').disabled = true;
  byId('sheet').hidden = true;
  status('Finding start and destination…');
  try {
    const [origin, destination] = await Promise.all([
      geocode(originQuery, controller.signal),
      geocode(destinationQuery, controller.signal),
    ]);
    placePin('origin', origin, originQuery);
    placePin('destination', destination, destinationQuery);

    status('Finding walking routes…');
    const payload = { origin, destination, ...departurePayload(dublinNow(), 'earlier') };
    const data = await getRoutes(payload, {
      baseUrl: import.meta.env.VITE_API_BASE_URL || '',
      signal: controller.signal,
    });
    render(data);
  } catch (error) {
    if (error.name !== 'AbortError') status(`${error.code || 'ERROR'}: ${error.message}`, true);
  } finally {
    byId('compare').disabled = false;
  }
});

byId('sheet-close').addEventListener('click', () => { byId('sheet').hidden = true; });
