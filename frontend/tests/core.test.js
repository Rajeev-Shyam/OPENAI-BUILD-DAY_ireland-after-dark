import test from 'node:test';
import assert from 'node:assert/strict';
import { fixture } from '../src/fixtures.js';
import { validateResponse, getRoutes } from '../src/api.js';
import { departurePayload } from '../src/time.js';

test('normal, identical and unknown evidence shapes validate',()=>{
  for(const scenario of ['normal','identical','low']) assert.equal(validateResponse(fixture(scenario)).routes.length,2);
});
test('malformed route never silently becomes a result',()=>{
  const data=fixture('normal');data.routes[0].geometry.coordinates=[[999,53]];
  assert.throws(()=>validateResponse(data));
});
test('API errors and network failures remain errors',async()=>{
  await assert.rejects(getRoutes({}, {fetcher:async()=>({ok:false,json:async()=>fixture('no-route')})}),{code:'NO_ROUTE'});
  await assert.rejects(getRoutes({}, {fetcher:async()=>{throw new Error('offline')}}),{code:'NETWORK_ERROR'});
});
test('Dublin time is independent of browser timezone, including DST gap',()=>{
  assert.equal(departurePayload('2026-10-04T20:00').departure_time,'2026-10-04T19:00:00.000Z');
  assert.throws(()=>departurePayload('2026-03-29T01:30'));
});
