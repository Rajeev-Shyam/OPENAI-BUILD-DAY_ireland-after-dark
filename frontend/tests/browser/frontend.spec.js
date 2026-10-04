import { test, expect } from '@playwright/test';
import { fixture } from '../../src/fixtures.js';

async function setup(page, scenario='normal') {
  await page.route('**/tile.openstreetmap.org/**', route=>route.abort());
  await page.route('**/route', route=>route.fulfill({status:scenario==='no-route'?404:200,json:fixture(scenario)}));
  await page.goto('/');
  await page.getByLabel('Start',{exact:true}).fill('53.3478, -6.2497');
  await page.getByLabel('Destination',{exact:true}).fill('53.3524, -6.2440');
}
test('phase1 cards show factors, caveats, and clear stale results on edit',async({page})=>{
  await setup(page);await page.getByRole('button',{name:'Find route'}).click();
  await expect(page.getByRole('heading',{name:/Night route/})).toBeVisible();
  await expect(page.locator('.recommended')).toHaveCount(1);
  await expect(page.locator('.factor-label').first()).toContainText('Recorded lighting');
  await page.getByText('Evidence and limitations',{exact:true}).first().click();
  await expect(page.locator('details.evidence').first()).toContainText('Synthetic example');
  await page.getByLabel('Start',{exact:true}).fill('53.3480, -6.2500');
  await expect(page.locator('#sheet')).toBeHidden();
});
test('identical routes and unknown evidence render honestly',async({page})=>{
  await setup(page,'low');await page.getByRole('button',{name:'Find route'}).click();
  await expect(page.locator('.card')).toHaveCount(2);
  await expect(page.locator('.badge').first()).toHaveText('Low confidence');
  await expect(page.locator('.factors').first()).toContainText('No recorded');
});
test('no-route and network errors do not fall back to fixtures',async({page})=>{
  await setup(page,'no-route');await page.getByRole('button',{name:'Find route'}).click();
  await expect(page.locator('#status')).toContainText('NO_ROUTE');
  await expect(page.locator('#sheet')).toBeHidden();
  await page.route('**/route',route=>route.abort());
  await page.getByRole('button',{name:'Find route'}).click();
  await expect(page.locator('#status')).toContainText('NETWORK_ERROR');
});
test('server text is escaped and never executes HTML',async({page})=>{
  await setup(page);const data=fixture('normal');data.routes[0].explanations=['<img src=x onerror="window.injected=true">'];
  await page.route('**/route',route=>route.fulfill({json:data}));
  await page.getByRole('button',{name:'Find route'}).click();
  await expect(page.locator('.explain').first()).toContainText('<img');
  expect(await page.evaluate(()=>window.injected)).toBeUndefined();
  await expect(page.locator('.explain img')).toHaveCount(0);
});
test('Luas layer is opt-in and missing snapshots do not block walking',async({page})=>{
  await setup(page);
  await page.route('**/transport/stops',route=>route.fulfill({status:503,json:{}}));
  await page.route('**/transport/status',route=>route.fulfill({json:{status:'missing'}}));
  await page.getByLabel('Show Luas stops').click();
  await expect(page.locator('#transport-status')).toContainText('unavailable');
  await page.getByRole('button',{name:'Find route'}).click();
  await expect(page.locator('.card')).toHaveCount(2);
});
test('keyboard submits, mobile fits, and named search uses the backend',async({page})=>{
  await page.setViewportSize({width:390,height:844});await setup(page);
  await page.route('**/geocode',route=>route.fulfill({json:{coordinates:[-6.2497,53.3478],label:'Synthetic place'}}));
  await page.getByLabel('Start',{exact:true}).fill('Synthetic place');
  await page.getByRole('button',{name:'Find route'}).focus();await page.keyboard.press('Enter');
  await expect(page.locator('.card')).toHaveCount(2);
  expect(await page.evaluate(()=>document.documentElement.scrollWidth)).toBeLessThanOrEqual(390);
});
