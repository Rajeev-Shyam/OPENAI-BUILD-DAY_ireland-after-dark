import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import './style.css';
import { getRoutes, isCoordinate, toLeaflet } from './api.js';
import { dublinNow, departurePayload } from './time.js';
import { searchPlaces } from './places.js';

const byId = id => document.getElementById(id);
const node = (tag, text, className) => { const element = document.createElement(tag); if (text !== undefined) element.textContent = text; if (className) element.className = className; return element; };
const map = L.map('map').setView([53.4,-8],7);
L.tileLayer(import.meta.env.VITE_TILE_URL || 'https://tile.openstreetmap.org/{z}/{x}/{y}.png', { maxZoom:19, attribution:'&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors' }).on('tileerror', () => { byId('map-status').textContent = 'Map tiles unavailable. Coordinate entry and route comparisons still work.'; }).addTo(map);
const routeLayer = L.featureGroup().addTo(map);
const coverageLayer = L.layerGroup().addTo(map);
const endpoints = { origin:null, destination:null };
const markers = {};
let selecting = null;
let controller;
let revision = 0;
const unknownCoverage = 'Backend-supported bounds: unknown. An Ireland map does not establish routing coverage.';
function status(message, error = false) { byId('status').textContent = message; byId('status').className = error ? 'error' : ''; }
function invalidate() {
  revision += 1;
  controller?.abort();
  byId('compare').disabled = false;
  byId('results').replaceChildren();
  byId('results-empty').hidden = false;
  byId('night-legend').textContent = 'Night';
  routeLayer.clearLayers();
  coverageLayer.clearLayers();
  byId('coverage').textContent = unknownCoverage;
  status('Journey changed. Compare routes to update results.');
}
function selectPoint(kind, label, point) {
  invalidate();
  endpoints[kind] = point;
  byId(`${kind}-selected`).textContent = `${kind === 'origin' ? 'A' : 'B'} · ${label} · ${point[1].toFixed(5)}, ${point[0].toFixed(5)}`;
  byId(`${kind}-lat`).value = point[1].toFixed(5);
  byId(`${kind}-lon`).value = point[0].toFixed(5);
  markers[kind]?.remove();
  markers[kind] = L.marker(toLeaflet(point), { icon:L.divIcon({ className:'endpoint-icon', html:kind === 'origin' ? 'A' : 'B', iconSize:[28,28] }), title:kind === 'origin' ? 'Origin A' : 'Destination B' }).addTo(map).bindTooltip(node('span', `${kind}: ${label}`));
}
for (const kind of ['origin','destination']) {
  const title = kind === 'origin' ? 'Origin' : 'Destination';
  const section = node('section');
  const form = node('form');
  const label = node('label',`${title} place search`);
  const input = node('input'); input.id = `${kind}-search`; input.type = 'search'; input.placeholder = 'e.g. Dublin, Cork, Galway'; label.htmlFor = input.id;
  label.append(input); form.append(label);
  const searchButton = node('button', 'Search directory', 'secondary'); searchButton.type = 'submit'; form.append(searchButton);
  const results = node('div', undefined, 'search-results'); results.setAttribute('aria-live','polite');
  form.addEventListener('submit', event => {
    event.preventDefault(); results.replaceChildren();
    const matches = searchPlaces(input.value);
    if (!matches.length) results.append(node('p','No directory match. Select on the map or enter coordinates.'));
    for (const [name,longitude,latitude] of matches) {
      const choice = node('button',`${name} (approximate centre)`,'secondary'); choice.type = 'button';
      choice.addEventListener('click', () => { selectPoint(kind,name,[longitude,latitude]); results.replaceChildren(); byId(`${kind}-map`).focus(); }); results.append(choice);
    }
  });
  input.addEventListener('input', () => {
    invalidate(); endpoints[kind] = null; markers[kind]?.remove();
    byId(`${kind}-selected`).textContent = 'No location selected. Choose a search result.';
    byId(`${kind}-lat`).value = ''; byId(`${kind}-lon`).value = ''; results.replaceChildren();
  });
  const mapButton = node('button',`Choose ${title.toLowerCase()} on map`,'secondary'); mapButton.id = `${kind}-map`; mapButton.type = 'button';
  mapButton.addEventListener('click', () => { selecting = kind; status(`Click the map to select ${title.toLowerCase()}. Keyboard users can enter coordinates below.`); });
  const selected = node('p','No location selected.','selected'); selected.id = `${kind}-selected`;
  const coordinates = node('details'); coordinates.append(node('summary', `${title} coordinates (keyboard alternative)`));
  for (const [suffix,caption,min,max] of [['lat','Latitude',-90,90],['lon','Longitude',-180,180]]) {
    const coordinateLabel = node('label',`${title} ${caption.toLowerCase()}`); const field = node('input'); field.id = `${kind}-${suffix}`; field.type = 'number'; field.step = 'any'; field.min = min; field.max = max; coordinateLabel.append(field); coordinates.append(coordinateLabel);
    field.addEventListener('input', () => { invalidate(); endpoints[kind] = null; markers[kind]?.remove(); selected.textContent = 'Coordinates edited. Press Use coordinates to confirm.'; });
  }
  const use = node('button','Use coordinates','secondary'); use.type = 'button';
  use.addEventListener('click', () => {
    const longitude = byId(`${kind}-lon`).value; const latitude = byId(`${kind}-lat`).value;
    const point = [Number(longitude),Number(latitude)];
    if (!longitude || !latitude || !isCoordinate(point)) { status('Enter latitude between −90 and 90 and longitude between −180 and 180.',true); return; }
    selectPoint(kind,'Selected coordinates',point);
  }); coordinates.append(use);
  section.append(form,results,mapButton,selected,coordinates); byId('locations').append(section);
}
map.on('click', event => { if (!selecting) return; selectPoint(selecting,'Map selection',[event.latlng.lng,event.latlng.lat]); selecting = null; status('Location selected. Compare routes when ready.'); });
byId('departure').value = dublinNow();
for (const id of ['departure','occurrence','scenario']) byId(id).addEventListener('change',invalidate);
byId('mode').addEventListener('change', () => {
  invalidate();
  const mock = byId('mode').value === 'mock';
  byId('demo-banner').hidden = !mock; byId('scenario-label').hidden = !mock;
  byId('mode-note').textContent = mock ? 'Demo uses a fixed illustrative Dublin journey, regardless of selected endpoints.' : 'Real API mode · routing and evidence come from the configured backend. No automatic demo fallback.';
});
byId('fit').addEventListener('click', () => { if (routeLayer.getLayers().length) map.fitBounds(routeLayer.getBounds(),{padding:[25,25]}); else status('Compare routes first to show their extent.'); });
function list(title, values, fallback) { const section = node('section'); section.append(node('h3',title)); const items = node('ul'); for (const text of values.length ? values : [fallback]) items.append(node('li',text)); section.append(items); return section; }
function render(data, mock) {
  byId('results-empty').hidden = true;
  byId('night-legend').textContent = data.comparison_status === 'baseline_only' ? 'Night unavailable' : 'Night';
  const bounds = data.coverage.bounds;
  byId('coverage').textContent = `${mock ? 'Synthetic demo' : 'Backend-supported'} bounds: ${bounds ? bounds.join(', ') + ' (west, south, east, north)' : 'unknown'}. ${data.coverage.description}`;
  if (bounds) L.rectangle([[bounds[1],bounds[0]],[bounds[3],bounds[2]]],{color:'#526469',weight:2,dashArray:'4 6',fill:false,interactive:false}).addTo(coverageLayer);
  for (const route of data.routes) {
    const night = route.kind === 'night'; const title = night ? (data.comparison_status === 'baseline_only' ? 'Night route unavailable' : 'Night route') : 'Fastest route';
    if (!(night && data.comparison_status === 'baseline_only')) L.polyline(route.geometry.coordinates.map(toLeaflet),{color:night ? '#ba7100' : '#375cb5',weight:night ? 4 : 8,dashArray:night ? '9 8' : undefined}).bindTooltip(node('span',title)).addTo(routeLayer);
    const card = node('article',undefined,`card ${route.kind}-card`); card.append(node('h2',title));
    if (mock) card.append(node('p','Synthetic fixture · not calculated for your endpoints','muted'));
    card.append(node('p',`Data Confidence: ${route.confidence ?? 'Unknown'}`,'badge'));
    if (route.confidence === 'Low' || route.confidence === null) card.append(node('p',`${route.confidence === 'Low' ? 'Low' : 'Unknown'} data confidence. ${route.limitations.join(' ') || 'Coverage details were not supplied.'} Missing evidence limits this comparison; it does not establish safety.`,'warning'));
    const metrics = node('dl');
    const entries = [
      ['Estimated walking time',`${(route.duration_s / 60).toFixed(1)} min`], ['Distance',`${(route.distance_m / 1000).toFixed(2)} km`],
      ['Recorded lighting coverage',route.lighting_coverage_pct === null ? 'Unknown' : `${route.lighting_coverage_pct}%`],
      ['Historical pedestrian activity',route.historical_activity === null ? 'Unknown' : `${route.historical_activity.value} ${route.historical_activity.unit}`],
      ['Waiting',route.waiting === null ? 'Not applicable (walking only)' : `${route.waiting.seconds} seconds · ${route.waiting.meaning}`],
      ['Route preference score',route.score === null ? 'Unknown' : `${route.score} / 100`]
    ];
    for (const [label,value] of entries) metrics.append(node('dt',label),node('dd',value)); card.append(metrics);
    card.append(list('Why this route',route.explanations,'No explanation available.'));
    if (night) card.append(list('Night Route Score factors',route.score_breakdown.map(factor => `${factor.label}: ${factor.value === null ? 'Unknown' : factor.value}${factor.max === null ? '' : ` / ${factor.max}`}`),'Not available.'));
    card.append(list('Coverage limitations',route.limitations,'No limitations supplied.'));
    card.append(list('Sources and dates',route.sources.map(source => `${source.name} · ${source.date ?? 'date unknown'} · ${source.attribution}`),'Not available.'));
    byId('results').append(card);
  }
  const identical = JSON.stringify(data.routes[0].geometry) === JSON.stringify(data.routes[1].geometry);
  status(data.comparison_status === 'baseline_only' ? 'Baseline only: showing the fastest path. No evidence-based Night alternative is available.' : identical ? 'Both options follow the same route. This is a valid result.' : 'Two walking routes returned. Use Show routes to adjust the map.');
}
byId('compare').addEventListener('click', async () => {
  invalidate();
  let payload;
  try {
    if (!isCoordinate(endpoints.origin) || !isCoordinate(endpoints.destination)) throw new Error('Select both origin and destination using a search result, map point or coordinates.');
    payload = { origin:endpoints.origin, destination:endpoints.destination, ...departurePayload(byId('departure').value,byId('occurrence').value) };
  } catch (error) { status(error.message,true); return; }
  const current = revision; const mock = byId('mode').value === 'mock';
  controller = new AbortController(); const activeController = controller;
  const timeout = setTimeout(() => activeController.abort('timeout'),15000);
  byId('compare').disabled = true; status(mock ? 'Loading synthetic demo routes…' : 'Finding walking routes…');
  try {
    const data = await getRoutes(payload,{mode:mock ? 'mock' : 'api',scenario:byId('scenario').value,baseUrl:import.meta.env.VITE_API_BASE_URL || '',signal:activeController.signal});
    if (current === revision) render(data,mock);
  } catch (error) {
    if (current === revision) status(activeController.signal.reason === 'timeout' ? 'The API request timed out. Demo mode has not been enabled.' : `${error.code || 'REQUEST_ERROR'}: ${error.message}`,true);
  } finally { clearTimeout(timeout); if (current === revision) byId('compare').disabled = false; }
});
