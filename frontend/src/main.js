import { Map as LeafletMap, tileLayer, featureGroup, marker, divIcon, polyline, geoJSON, circleMarker } from 'leaflet';
import 'leaflet/dist/leaflet.css';
import './style.css';
import { getRoutes, toLeaflet, isCoordinate } from './api.js';
import { dublinNow, departurePayload } from './time.js';

const byId = id => document.getElementById(id);
const apiBase = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/$/, '');
const escapeHTML = value => String(value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
byId('departure').value = dublinNow();

const map = new LeafletMap('map').setView([53.35, -6.26], 12);
tileLayer(import.meta.env.VITE_TILE_URL || 'https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
  maxZoom: 19,
  attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
}).addTo(map);
const routeLayer = featureGroup().addTo(map);
const hospitalLayer = featureGroup().addTo(map);
const routeColours = {fastest:'#3975ff',night:'#f5be53',best_lit:'#f5be53',balanced:'#b57bff',alternative1:'#6dd6b0',alternative2:'#f58dc0'};
const routeTitles = {fastest:'Fastest route',night:'Night route',best_lit:'Best lit route',balanced:'Balanced route',alternative1:'Alternative route',alternative2:'Alternative route 2'};

function recommendedKind(routes) {
  const candidates = routes.filter(route => route.kind !== 'fastest' && Number.isFinite(route.score));
  return candidates.length ? candidates.reduce((best, route) => route.score > best.score ? route : best).kind : null;
}
const markers = {};

function status(message, isError = false) {
  const el = byId('status');
  el.textContent = message || '';
  el.className = isError ? 'error' : '';
}

// Coordinates stay local; named places use the backend's shared rate gate/cache.
async function geocode(query, signal) {
  const match = query.match(/^\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*$/);
  if (match) {
    const point = [Number(match[2]), Number(match[1])];
    if (!isCoordinate(point)) throw new Error('Coordinates must be latitude, longitude.');
    return point;
  }
  const response = await fetch(`${apiBase}/geocode`, { method:'POST', signal,
    headers:{'Content-Type':'application/json'}, body:JSON.stringify({query}), credentials:'omit', cache:'no-store' });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error?.message || 'Place search unavailable. Try latitude, longitude.');
  if (!isCoordinate(data.coordinates)) throw new Error('Place search returned invalid coordinates.');
  return data.coordinates;
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
      <div class="factor-label"><span>${escapeHTML(factor.label)}</span><b>${known ? `${factor.value.toFixed(0)}/100` : 'Unknown'}</b></div>
      <div class="factor-track"><div class="factor-fill ${known ? '' : 'unknown'}" style="width:${known ? pct : 100}%"></div></div>
    </div>`;
}

function routeCard(route, isRecommended = false) {
  const title = routeTitles[route.kind];
  const minutes = (route.duration_s / 60).toFixed(0);
  const km = (route.distance_m / 1000).toFixed(2);
  const confidence = route.confidence ?? 'Unknown';
  const explanation = route.explanations[0] || '';
  const factors = route.score_breakdown.length
    ? route.score_breakdown.map(factorBar).join('')
    : '<p class="muted">No recorded lighting or footfall evidence here.</p>';
  const hospitals = route.nearby_hospitals === null || route.nearby_hospitals === undefined
    ? '<p class="muted">Hospital data unavailable.</p>'
    : route.nearby_hospitals.length
      ? `<ul class="hospital-list">${route.nearby_hospitals.map(h => `<li>${escapeHTML(h.name)} <span>${h.distance_from_route_m} m from route</span></li>`).join('')}</ul>`
      : '<p class="muted">No mapped hospital landmarks within 1 km in this snapshot.</p>';

  return `
    <article class="card ${route.kind}" style="border-top-color:${routeColours[route.kind]}">
      <h2>${title}${isRecommended ? '<span class="recommended" title="Highest recorded evidence score among the non-fastest options; not a safety rating">Recommended</span>' : ''}</h2>
      <div class="stat-row">
        <div class="stat"><b>${minutes}</b><span>min</span></div>
        <div class="stat"><b>${km}</b><span>km</span></div>
      </div>
      <span class="badge ${confidenceClass(confidence)}">${confidence} confidence</span>
      <div class="factors">${factors}</div>
      <p class="muted">Lamp operating status: unknown. Recorded assets do not confirm working lights.</p>
      <p class="explain">${escapeHTML(explanation)}</p>
      <details class="nearby-hospitals"><summary>${route.nearby_hospitals?.length ?? 'Unknown'} nearby mapped hospitals</summary>
        ${hospitals}
        <p class="muted">Within 1 km straight-line of the route, not a walk to an entrance. Opening hours and emergency care are unverified.</p>
      </details>
      <button class="view-route" type="button" data-route="${route.kind}">Show this route on map</button>
      <details class="evidence"><summary>Evidence and limitations</summary>
        <p class="muted">Recorded lighting evidence: ${route.lighting_coverage_pct === null ? 'Unknown' : `${route.lighting_coverage_pct.toFixed(1)}% of route length`}. Walking time is an estimate, not a guarantee.</p>
        <ul>${route.limitations.map(item => `<li>${escapeHTML(item)}</li>`).join('')}</ul>
        <ul>${route.sources.map(source => `<li>${escapeHTML(source.name)} (${escapeHTML(source.date || 'date unknown')}) — ${escapeHTML(source.attribution)}</li>`).join('')}</ul>
      </details>
    </article>`;
}

function render(data) {
  routeLayer.clearLayers();
  hospitalLayer.clearLayers();
  const lines = {};
  // Paint every casing first so an overlapping route cannot hide another's colour.
  const routes = [...data.routes].sort((a, b) => Number(a.kind === 'night') - Number(b.kind === 'night'));
  const paths = routes.map(route => route.geometry.coordinates.map(toLeaflet));
  for (const [color, weight] of [['#ffffff', 15], ['#172229', 11]]) {
    for (const path of paths) {
      polyline(path, { color, weight, opacity: 1, interactive: false }).addTo(routeLayer);
    }
  }
  for (const [index, route] of routes.entries()) {
    const night = route.kind === 'night' || route.kind === 'best_lit';
    lines[route.kind] = polyline(paths[index], {
      color: routeColours[route.kind],
      className: night ? 'route-line-night' : route.kind === 'fastest' ? 'route-line-fastest' : 'route-line-alternative',
      weight: night ? 6 : 8,
      opacity: 1,
      dashArray: night ? '12 12' : route.kind === 'fastest' ? undefined : '2 10',
      interactive: false,
    }).addTo(routeLayer);
  }
  const padding = () => window.innerWidth > 640
    ? {paddingTopLeft:[400,70],paddingBottomRight:[40,40]}
    : {paddingTopLeft:[20,window.innerHeight*.72],paddingBottomRight:[20,35]};
  if (routeLayer.getLayers().length) map.fitBounds(routeLayer.getBounds(), padding());

  byId('sheet-intro').textContent = `${data.routes.length} walking option${data.routes.length === 1 ? '' : 's'} found, within the five-minute detour limit. ${data.routes.length < 3 ? 'Fewer than three distinct candidates were found. ' : ''}Recorded lighting and historical activity are not a safety guarantee. ${data.hospital_context?.attribution ? `${data.hospital_context.attribution}; hospitals fetched ${data.hospital_context.fetched_at_utc.slice(0,10)}.` : ''}`;
  const recommended = recommendedKind(data.routes);
  byId('sheet-body').innerHTML = data.routes.map(route => routeCard(route, route.kind === recommended)).join('');
  for (const button of byId('sheet-body').querySelectorAll('.view-route')) {
    button.addEventListener('click', () => {
      const route = data.routes.find(r=>r.kind===button.dataset.route);
      hospitalLayer.clearLayers();
      for (const [kind,line] of Object.entries(lines)) line.setStyle({opacity:kind===route.kind?1:.25,weight:kind===route.kind?7:4});
      lines[route.kind].bringToFront();
      for (const hospital of route.nearby_hospitals || []) {
        const popup=document.createElement('span');popup.textContent=`${hospital.name}: ${hospital.distance_from_route_m} m straight-line from route. Opening hours and emergency care unverified.`;
        marker(toLeaflet(hospital.coordinates), {icon:divIcon({className:'hospital-icon',html:'H',iconSize:[24,24]}),title:hospital.name})
          .bindPopup(popup).addTo(hospitalLayer);
      }
      map.fitBounds(lines[route.kind].getBounds(),padding());
      for (const card of byId('sheet-body').querySelectorAll('.card')) card.classList.remove('selected');
      button.closest('.card').classList.add('selected');
    });
  }
  byId('sheet').hidden = false;
  byId('sheet-body').querySelector('.view-route')?.click();
  status('');
}

let controller;
let requestVersion = 0;
let nextPin = 'origin';
function invalidate() {
  requestVersion++;
  controller?.abort();
  routeLayer.clearLayers();
  hospitalLayer.clearLayers();
  byId('sheet').hidden = true;
  byId('compare').disabled = false;
  status('');
}
for (const kind of ['origin', 'destination']) {
  byId(`${kind}-input`).addEventListener('focus', () => { nextPin = kind; });
  byId(`${kind}-input`).addEventListener('input', () => { invalidate(); markers[kind]?.remove(); });
}
byId('departure').addEventListener('input', invalidate);
map.on('click', event => {
  invalidate();
  const {lat,lng} = event.latlng;
  byId(`${nextPin}-input`).value = `${lat.toFixed(6)}, ${lng.toFixed(6)}`;
  placePin(nextPin, [lng,lat], nextPin);
  nextPin = nextPin === 'origin' ? 'destination' : 'origin';
});
byId('panel').addEventListener('submit', async event => {
  event.preventDefault();
  controller?.abort();
  controller = new AbortController();
  const requestController = controller;
  const signal = requestController.signal;
  const version = ++requestVersion;
  let timedOut = false;
  const timeout = setTimeout(() => { timedOut = true; requestController.abort(); }, 30000);
  const originQuery = byId('origin-input').value.trim();
  const destinationQuery = byId('destination-input').value.trim();
  if (!originQuery || !destinationQuery) { clearTimeout(timeout); status('Enter both a start and a destination.', true); return; }

  byId('compare').disabled = true;
  byId('sheet').hidden = true;
  routeLayer.clearLayers();
  status('Finding start and destination…');
  try {
    const origin = await geocode(originQuery, signal);
    const destination = await geocode(destinationQuery, signal);
    if (version !== requestVersion) return;
    placePin('origin', origin, originQuery);
    placePin('destination', destination, destinationQuery);

    status('Finding walking routes…');
    const payload = { origin, destination, ...departurePayload(byId('departure').value, 'earlier') };
    const data = await getRoutes(payload, {
      baseUrl: apiBase,
      signal,
    });
    if (version === requestVersion) render(data);
  } catch (error) {
    if (version === requestVersion && timedOut) status('Request timed out. Try map points or coordinates, then retry.', true);
    else if (version === requestVersion && error.name !== 'AbortError') status(`${error.code || 'ERROR'}: ${error.message}`, true);
  } finally {
    clearTimeout(timeout);
    if (version === requestVersion) byId('compare').disabled = false;
  }
});

byId('sheet-close').addEventListener('click', () => { byId('sheet').hidden = true; });

let stopsLayer;
byId('show-stops').addEventListener('change', async event => {
  if (!event.target.checked) { stopsLayer?.remove(); byId('transport-status').textContent = ''; return; }
  byId('transport-status').textContent = 'Loading saved Luas stop locations…';
  try {
    const [response, stateResponse] = await Promise.all([
      fetch(`${apiBase}/transport/stops`, {cache:'no-store'}),
      fetch(`${apiBase}/transport/status`, {cache:'no-store'}),
    ]);
    if (!response.ok) throw new Error('Luas snapshot unavailable; walking routes still work.');
    const data = await response.json();
    const state = stateResponse.ok ? await stateResponse.json() : {status:'unavailable'};
    if (!event.target.checked) return;
    stopsLayer?.remove();
    stopsLayer = geoJSON(data, {
      pointToLayer: (_feature, latlng) => circleMarker(latlng, {radius:4,color:'#ad8dff',weight:2,fillOpacity:0.6}),
      onEachFeature: (feature, layer) => {
        const popup = document.createElement('span');
        popup.textContent = `${feature.properties.stop_name} — static stop/platform; service availability unknown.`;
        layer.bindPopup(popup);
      },
    }).addTo(map);
    const received = state.received_at_unix ? new Date(state.received_at_unix * 1000).toLocaleString('en-IE',{timeZone:'Europe/Dublin'}) : 'none';
    byId('transport-status').textContent = `NTA Luas stops, fetched ${data.metadata.fetched_at_utc.slice(0,10)}. Realtime snapshot at this check: ${state.status}; received ${received} (Ireland time). Locations do not confirm service now.`;
    const link = document.createElement('a'); link.href = 'https://www.transportforireland.ie/transitData/PT_Data.html';
    link.textContent = ' NTA · CC BY 4.0 · provided as is; NTA is not responsible for errors or inaccuracies.';
    byId('transport-status').append(link);
  } catch (error) {
    if (event.target.checked) { byId('transport-status').textContent = error.message; event.target.checked = false; }
  }
});
