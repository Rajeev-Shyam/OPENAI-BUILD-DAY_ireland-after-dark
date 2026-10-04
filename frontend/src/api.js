export const isCoordinate = point => Array.isArray(point) && point.length === 2 && point.every(Number.isFinite) && Math.abs(point[0]) <= 180 && Math.abs(point[1]) <= 90;
export const toLeaflet = point => [point[1], point[0]];
export class RouteError extends Error { constructor(code, message) { super(message); this.code = code; } }
const optionalNumber = (value, maximum = Infinity) => value === null || (Number.isFinite(value) && value >= 0 && value <= maximum);

export function validateResponse(data) {
  const fail = () => { throw new RouteError('INVALID_RESPONSE', 'The API response does not match the agreed contract.'); };
  if (data?.mode !== 'walking' || !Array.isArray(data.routes) || data.routes.length < 1 || data.routes.length > 3 || !data.coverage || typeof data.coverage.description !== 'string') fail();
  if (data.routes[0].kind !== 'fastest' || new Set(data.routes.map(r=>r.kind)).size !== data.routes.length) fail();
  const bounds = data.coverage.bounds;
  if (bounds !== null && (!Array.isArray(bounds) || bounds.length !== 4 || !isCoordinate(bounds.slice(0,2)) || !isCoordinate(bounds.slice(2)) || bounds[0] >= bounds[2] || bounds[1] >= bounds[3])) fail();
  for (const route of data.routes) {
    if (!['fastest','night','best_lit','balanced','alternative1','alternative2'].includes(route.kind)) fail();
    if (!route || route.geometry?.type !== 'LineString' || !Array.isArray(route.geometry.coordinates) || route.geometry.coordinates.length < 2 || !route.geometry.coordinates.every(isCoordinate)) fail();
    if (!Number.isFinite(route.distance_m) || route.distance_m < 0 || !Number.isFinite(route.duration_s) || route.duration_s < 0 || !optionalNumber(route.lighting_coverage_pct,100) || !optionalNumber(route.score,100)) fail();
    if (!['Low','Medium','High',null].includes(route.confidence)) fail();
    if (route.historical_activity !== null && (!optionalNumber(route.historical_activity?.value) || route.historical_activity.value === null || typeof route.historical_activity.unit !== 'string')) fail();
    if (route.waiting !== null && (!optionalNumber(route.waiting?.seconds) || route.waiting.seconds === null || typeof route.waiting.meaning !== 'string')) fail();
    for (const key of ['limitations','explanations']) if (!Array.isArray(route[key]) || !route[key].every(value => typeof value === 'string')) fail();
    if (!Array.isArray(route.score_breakdown) || !route.score_breakdown.every(factor => typeof factor.label === 'string' && optionalNumber(factor.value, factor.max ?? Infinity) && (factor.max === null || (Number.isFinite(factor.max) && factor.max > 0)))) fail();
    if (!Array.isArray(route.sources) || !route.sources.every(source => typeof source.name === 'string' && (source.date === null || typeof source.date === 'string') && typeof source.attribution === 'string')) fail();
    if (route.nearby_hospitals !== undefined && route.nearby_hospitals !== null &&
        (!Array.isArray(route.nearby_hospitals) || !route.nearby_hospitals.every(h => typeof h.name === 'string' && isCoordinate(h.coordinates) && Number.isFinite(h.distance_from_route_m) && h.distance_from_route_m >= 0))) fail();
  }
  return data;
}

export async function getRoutes(payload, { baseUrl = '', fetcher = fetch, signal } = {}) {
  let response;
  try {
    response = await fetcher(`${baseUrl.replace(/\/$/,'')}/route`, { method: 'POST', headers: { 'Content-Type':'application/json' }, body: JSON.stringify(payload), signal, credentials: 'omit', cache: 'no-store' });
  } catch (error) {
    if (error.name === 'AbortError') throw error;
    throw new RouteError('NETWORK_ERROR','Cannot reach the API. Check its address and CORS settings.');
  }
  let data;
  try { data = await response.json(); } catch { throw new RouteError('INVALID_RESPONSE','The API did not return JSON.'); }
  if (!response.ok && !data?.error) throw new RouteError('API_ERROR',`API request failed (${response.status}).`);
  if (data?.error) throw new RouteError(data.error.code || 'API_ERROR', String(data.error.message || 'The request failed.'));
  return validateResponse(data);
}
