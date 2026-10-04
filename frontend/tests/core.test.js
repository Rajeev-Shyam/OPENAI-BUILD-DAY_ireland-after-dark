import { test } from 'node:test';
import assert from 'node:assert/strict';
import { departurePayload, dublinNow } from '../src/time.js';
import { getRoutes, validateResponse, toLeaflet } from '../src/api.js';
import { fixture } from '../src/fixtures.js';
import { searchPlaces } from '../src/places.js';

test('Dublin calendar is independent of host timezone, including both DST transitions', () => {
  assert.equal(dublinNow(new Date('2026-10-04T19:00:00Z')),'2026-10-04T20:00');
  assert.equal(departurePayload('2026-10-04T20:00').departure_time,'2026-10-04T19:00:00.000Z');
  assert.equal(departurePayload('2026-12-04T20:00').departure_time,'2026-12-04T20:00:00.000Z');
  assert.throws(() => departurePayload('2026-03-29T01:30'),/does not exist/);
  assert.equal(departurePayload('2026-10-25T01:30','earlier').departure_time,'2026-10-25T00:30:00.000Z');
  assert.equal(departurePayload('2026-10-25T01:30','later').departure_time,'2026-10-25T01:30:00.000Z');
  assert.throws(() => departurePayload('2026-02-30T12:00'));
});
test('fixtures retain missing metrics and identical geometries', () => {
  for (const scenario of ['normal','identical','low']) validateResponse(fixture(scenario));
  assert.deepEqual(fixture('identical').routes[0].geometry,fixture('identical').routes[1].geometry);
  assert.equal(fixture('low').routes[0].score,null);
  assert.deepEqual(toLeaflet([-6,53]),[53,-6]);
});
test('adapter posts exact contract and does not fall back on network failure', async () => {
  const payload = {origin:[-6,53],destination:[-6.1,53.1],...departurePayload('2026-10-04T20:00')};
  await getRoutes(payload,{mode:'api',contract:'development',baseUrl:'http://localhost:8000/',fetcher:async (url,options) => { assert.equal(url,'http://localhost:8000/route'); assert.deepEqual(JSON.parse(options.body),payload); assert.equal(options.method,'POST'); return {ok:true,json:async () => fixture('normal')}; }});
  await assert.rejects(getRoutes(payload,{mode:'api',contract:'development',fetcher:async () => { throw new Error('offline'); }}),{code:'NETWORK_ERROR'});
});
test('clear error codes and malformed responses',async () => {
  for (const [scenario,code] of [['unsupported','UNSUPPORTED_AREA'],['no-route','NO_ROUTE']]) await assert.rejects(getRoutes({}, {mode:'mock',scenario}),{code});
  await assert.rejects(getRoutes({}, {mode:'api',contract:'development',fetcher:async () => ({ok:false,json:async () => ({error:{code:'INVALID_INPUT',message:'Bad input'}})})}),{code:'INVALID_INPUT'});
  const malformed = fixture('normal'); malformed.routes[0].lighting_coverage_pct = undefined; assert.throws(() => validateResponse(malformed),{code:'INVALID_RESPONSE'});
});
test('local search is explicit and bounded', () => { assert.equal(searchPlaces('cork').length,1); assert.equal(searchPlaces('').length,0); assert.equal(searchPlaces('unknown address').length,0); });

test('phase1 contract serializes lat/lng and never substitutes factor scores for measurements',async () => {
  const payload = {origin:[-6.26,53.35],destination:[-6.25,53.36],...departurePayload('2026-10-04T20:00')};
  const backend = {routes:{fastest:{geometry:fixture('normal').routes[0].geometry,distance_metres:950,duration_minutes:12.3,route_score:null},night:{geometry:fixture('normal').routes[1].geometry,distance_metres:1080,duration_minutes:14.1,route_score:78}},score_breakdown:{lighting:82,activity:65,crossings:null,waiting:null},data_confidence:{level:'low',reasons:['Incomplete recorded evidence.']},explanation:['Test explanation.'],warnings:['Test warning.']};
  const result = await getRoutes(payload,{mode:'api',fetcher:async (url,options) => {
    assert.deepEqual(JSON.parse(options.body),{origin:{lat:53.35,lng:-6.26},destination:{lat:53.36,lng:-6.25},departure_time:'2026-10-04T19:00:00.000Z'});
    return {ok:true,json:async () => backend};
  }});
  assert.equal(result.routes[1].score,78);
  assert.equal(result.routes[1].score_breakdown[0].value,82);
  assert.equal(result.routes[1].lighting_coverage_pct,null);
  assert.equal(result.routes[1].historical_activity,null);
  assert.equal(result.routes[0].confidence,'Low');
  assert.equal(result.coverage.bounds,null);
});

test('phase1 OUT_OF_AREA maps to the UI unsupported state',async () => {
  const payload = {origin:[-6,53],destination:[-6.1,53.1],...departurePayload('2026-10-04T20:00')};
  await assert.rejects(getRoutes(payload,{mode:'api',fetcher:async () => ({ok:false,json:async () => ({routes:null,error:{code:'OUT_OF_AREA',message:'Outside graph.'}})})}),{code:'UNSUPPORTED_AREA'});
});
