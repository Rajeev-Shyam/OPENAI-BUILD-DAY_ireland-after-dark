import { fixture } from './fixtures.js';
export const isCoordinate = point => Array.isArray(point) && point.length === 2 && point.every(Number.isFinite) && Math.abs(point[0]) <= 180 && Math.abs(point[1]) <= 90;
export const toLeaflet = point => [point[1], point[0]];
export class RouteError extends Error { constructor(code, message) { super(message); this.code = code; } }
const optionalNumber = (value, maximum = Infinity) => value === null || (Number.isFinite(value) && value >= 0 && value <= maximum);
export function validateResponse(data) {
  const fail = () => { throw new RouteError('INVALID_RESPONSE', 'The API response does not match the proposed contract.'); };
  if (data?.mode !== 'walking' || !Array.isArray(data.routes) || data.routes.length !== 2 || !data.coverage || typeof data.coverage.description !== 'string') fail();
  const bounds = data.coverage.bounds;
  if (bounds !== null && (!Array.isArray(bounds) || bounds.length !== 4 || !isCoordinate(bounds.slice(0,2)) || !isCoordinate(bounds.slice(2)) || bounds[0] >= bounds[2] || bounds[1] >= bounds[3])) fail();
  for (const kind of ['fastest','night']) {
    const route = data.routes.find(candidate => candidate.kind === kind);
    if (!route || route.geometry?.type !== 'LineString' || !Array.isArray(route.geometry.coordinates) || route.geometry.coordinates.length < 2 || !route.geometry.coordinates.every(isCoordinate)) fail();
    if (!Number.isFinite(route.distance_m) || route.distance_m < 0 || !Number.isFinite(route.duration_s) || route.duration_s < 0 || !optionalNumber(route.lighting_coverage_pct,100) || !optionalNumber(route.score,100)) fail();
    if (!['Low','Medium','High',null].includes(route.confidence)) fail();
    if (route.historical_activity !== null && (!optionalNumber(route.historical_activity?.value) || route.historical_activity.value === null || typeof route.historical_activity.unit !== 'string')) fail();
    if (route.waiting !== null && (!optionalNumber(route.waiting?.seconds) || route.waiting.seconds === null || typeof route.waiting.meaning !== 'string')) fail();
    for (const key of ['limitations','explanations']) if (!Array.isArray(route[key]) || !route[key].every(value => typeof value === 'string')) fail();
    if (!Array.isArray(route.score_breakdown) || !route.score_breakdown.every(factor => typeof factor.label === 'string' && optionalNumber(factor.value, factor.max ?? Infinity) && (factor.max === null || (Number.isFinite(factor.max) && factor.max > 0)))) fail();
    if (!Array.isArray(route.sources) || !route.sources.every(source => typeof source.name === 'string' && (source.date === null || typeof source.date === 'string') && typeof source.attribution === 'string')) fail();
  }
  return data;
}
export function normalizePhase1Response(data) {
  const levels = { low:'Low', medium:'Medium', high:'High' };
  const textList = value => Array.isArray(value) && value.every(item => typeof item === 'string');
  if (!data?.routes?.fastest || !data.routes.night || !levels[data.data_confidence?.level]
      || !textList(data.data_confidence.reasons) || !textList(data.explanation) || !textList(data.warnings)
      || !data.score_breakdown || typeof data.score_breakdown !== 'object' || Array.isArray(data.score_breakdown)
      || !Object.values(data.score_breakdown).every(value => optionalNumber(value,100))) {
    throw new RouteError('INVALID_RESPONSE','The API response does not match docs/api-contract.md.');
  }
  return {
    mode:'walking',
    coverage:{bounds:null,description:'This API contract does not provide graph bounds. An Ireland map does not establish routing support.'},
    routes:['fastest','night'].map(kind => {
      const route = data.routes[kind];
      return {kind,geometry:route.geometry,distance_m:route.distance_metres,duration_s:Number.isFinite(route.duration_minutes) ? route.duration_minutes * 60 : NaN,
        lighting_coverage_pct:null,historical_activity:null,waiting:null,score:route.route_score,
        score_breakdown:kind === 'night' ? Object.entries(data.score_breakdown).map(([label,value]) => ({label,value,max:100})) : [],
        confidence:levels[data.data_confidence.level],
        limitations:[...data.data_confidence.reasons,...data.warnings,'Confidence is supplied for the overall comparison. Measured lighting coverage, activity values and source dates are not supplied by this API contract; factor scores are not substituted for these metrics.'],
        explanations:kind === 'night' ? data.explanation : [],sources:[]};
    })
  };
}
export async function getRoutes(payload, { mode, scenario, baseUrl = '', contract = 'phase1', fetcher = fetch, signal } = {}) {
  let data;
  if (mode === 'mock') data = fixture(scenario);
  else {
    if (!['phase1','development'].includes(contract)) throw new RouteError('INVALID_CONFIGURATION','Choose the phase1 or development API contract.');
    const body = contract === 'phase1' ? {
      origin:{lat:payload.origin[1],lng:payload.origin[0]},
      destination:{lat:payload.destination[1],lng:payload.destination[0]},
      departure_time:payload.departure_time
    } : payload;
    let response;
    try { response = await fetcher(`${baseUrl.replace(/\/$/,'')}/route`, { method: 'POST', headers: { 'Content-Type':'application/json' }, body: JSON.stringify(body), signal, credentials: 'omit', cache: 'no-store' }); }
    catch (error) { if (error.name === 'AbortError') throw error; throw new RouteError('NETWORK_ERROR','Cannot reach the API. Check its address and CORS settings. Demo mode has not been enabled.'); }
    try { data = await response.json(); } catch { throw new RouteError('INVALID_RESPONSE','The API did not return JSON.'); }
    if (!response.ok && !data?.error) throw new RouteError('API_ERROR',`API request failed (${response.status}).`);
    if (data?.error?.code === 'OUT_OF_AREA') data.error.code = 'UNSUPPORTED_AREA';
    if (!data?.error && contract === 'phase1') data = normalizePhase1Response(data);
  }
  if (data?.error) throw new RouteError(data.error.code || 'API_ERROR', String(data.error.message || 'The request failed.'));
  return validateResponse(data);
}
