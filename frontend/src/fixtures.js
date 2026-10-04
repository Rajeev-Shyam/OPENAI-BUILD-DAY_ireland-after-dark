const fastest = {
  kind: 'fastest', geometry: { type: 'LineString', coordinates: [[-6.2603,53.3498],[-6.257,53.348],[-6.252,53.347],[-6.248,53.348]] },
  distance_m: 950, duration_s: 720, lighting_coverage_pct: 60,
  historical_activity: { value: 120, unit: 'synthetic pedestrians/hour' }, waiting: null, score: 58,
  score_breakdown: [{ label: 'Recorded lighting', value: 60, max: 100 }, { label: 'Historical activity', value: 55, max: 100 }],
  confidence: 'Medium', limitations: ['Synthetic example; no source coverage has been measured.'], explanations: ['Illustrative shortest walking route.'],
  sources: [{ name: 'Synthetic fixture', date: null, attribution: 'Frontend demonstration only' }]
};
export function fixture(scenario) {
  if (scenario === 'unsupported') return { error: { code: 'UNSUPPORTED_AREA', message: 'Demo unsupported-area response: selected location is outside the routing graph.' } };
  if (scenario === 'no-route') return { error: { code: 'NO_ROUTE', message: 'Demo no-route response: no walking connection was found.' } };
  const night = { ...structuredClone(fastest), kind: 'night', distance_m: 1100, duration_s: 840, lighting_coverage_pct: 80, score: 72, geometry: { type: 'LineString', coordinates: [[-6.2603,53.3498],[-6.258,53.351],[-6.251,53.350],[-6.248,53.348]] }, score_breakdown: [{ label: 'Recorded lighting', value: 80, max: 100 }, { label: 'Historical activity', value: 64, max: 100 }], explanations: ['Synthetic example of a route with more recorded lighting coverage.'] };
  const response = { mode: 'walking', coverage: { bounds: [-6.28,53.33,-6.22,53.37], description: 'Synthetic demonstration bounds only; actual backend support is unknown.' }, routes: [structuredClone(fastest), scenario === 'identical' ? { ...structuredClone(fastest), kind: 'night' } : night] };
  if (scenario === 'low') for (const route of response.routes) Object.assign(route, { confidence: 'Low', lighting_coverage_pct: null, historical_activity: null, score: null, score_breakdown: [], explanations: ['Distance and estimated walking time remain available.'], limitations: ['Recorded lighting and historical pedestrian activity are missing for this synthetic route.'] });
  return response;
}
