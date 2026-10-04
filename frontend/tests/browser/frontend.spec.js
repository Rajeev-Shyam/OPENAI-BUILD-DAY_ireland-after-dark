import { test, expect } from '@playwright/test';
import { fixture } from '../../src/fixtures.js';

test.beforeEach(async ({ page }) => {
  await page.route('https://tile.openstreetmap.org/**', route => route.abort());
  await page.goto('/');
});
async function selectJourney(page) {
  await page.getByLabel('Origin place search').fill('Dublin');
  await page.getByRole('button',{name:'Search directory'}).first().click();
  await page.getByRole('button',{name:'Dublin city centre (approximate centre)',exact:true}).click();
  await page.getByLabel('Destination place search').fill('Docklands');
  await page.getByRole('button',{name:'Search directory'}).last().click();
  await page.getByRole('button',{name:'Dublin Docklands (approximate centre)',exact:true}).click();
}
test('normal routes, explicit demo banner, map layers and identical routes',async ({page}) => {
  await expect(page.locator('#demo-banner')).toContainText('not a real journey recommendation');
  await page.getByRole('button',{name:'Compare routes'}).click();
  await expect(page.locator('#status')).toContainText('Select both');
  await selectJourney(page);
  await page.getByRole('button',{name:'Compare routes'}).click();
  await expect(page.locator('#results article')).toHaveCount(2);
  await expect(page.getByRole('heading',{name:'Night Route Score factors'})).toBeVisible();
  await expect(page.locator('.leaflet-overlay-pane path')).toHaveCount(3);
  await page.getByLabel('Demo scenario').selectOption('identical');
  await page.getByRole('button',{name:'Compare routes'}).click();
  await expect(page.locator('#status')).toContainText('same route');
});
test('low confidence, missing metrics, unsupported and disconnected routes',async ({page}) => {
  await selectJourney(page);
  await page.getByLabel('Demo scenario').selectOption('low');
  await page.getByRole('button',{name:'Compare routes'}).click();
  await expect(page.locator('#results .warning')).toHaveCount(2);
  await expect(page.locator('#results')).toContainText('Unknown');
  await expect(page.locator('#results')).toContainText('Not applicable (walking only)');
  await expect(page.locator('#results')).toContainText('12.0 min');
  for (const [scenario,code] of [['unsupported','UNSUPPORTED_AREA'],['no-route','NO_ROUTE']]) {
    await page.getByLabel('Demo scenario').selectOption(scenario);
    await page.getByRole('button',{name:'Compare routes'}).click();
    await expect(page.locator('#status')).toContainText(code);
    await expect(page.locator('#results article')).toHaveCount(0);
  }
});
test('API payload, plain-text rendering, real errors and no silent fallback',async ({page}) => {
  await selectJourney(page);
  await page.getByLabel('Departure · Europe/Dublin', {exact:true}).fill('2026-10-04T20:00');
  await page.getByRole('combobox',{name:'Data mode',exact:true}).selectOption('api');
  await expect(page.locator('#demo-banner')).toBeHidden();
  let captured;
  await page.route('**/route',async route => {
    captured = route.request().postDataJSON();
    const data = fixture('normal'); data.routes[1].explanations = ['<img src=x onerror=alert(1)>'];
    await route.fulfill({json:data});
  });
  await page.getByRole('button',{name:'Compare routes'}).click();
  await expect(page.locator('#results article')).toHaveCount(2);
  expect(captured).toEqual({origin:[-6.2603,53.3498],destination:[-6.248,53.348],departure_time:'2026-10-04T19:00:00.000Z',timezone:'Europe/Dublin'});
  await expect(page.locator('#results img')).toHaveCount(0);
  await expect(page.locator('#results')).toContainText('<img src=x onerror=alert(1)>');
  await page.unroute('**/route');
  await page.route('**/route',route => route.abort());
  await page.getByRole('button',{name:'Compare routes'}).click();
  await expect(page.locator('#status')).toContainText('NETWORK_ERROR');
  await expect(page.locator('#demo-banner')).toBeHidden();
  await expect(page.locator('#results article')).toHaveCount(0);
  await page.getByRole('combobox',{name:'Data mode',exact:true}).selectOption('mock');
  await expect(page.locator('#demo-banner')).toBeVisible();
});
test('keyboard search and phone width',async ({page}) => {
  await page.setViewportSize({width:375,height:812});
  await page.getByLabel('Origin place search').focus();
  await page.keyboard.type('Cork'); await page.keyboard.press('Enter');
  await page.keyboard.press('Tab'); await page.keyboard.press('Tab'); await page.keyboard.press('Enter');
  await expect(page.locator('#origin-selected')).toContainText('Cork city centre');
  await selectJourney(page);
  await page.getByRole('button',{name:'Compare routes'}).click();
  await expect(page.locator('#results article')).toHaveCount(2);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({path:'test-results/mobile.png',fullPage:true});
});
test('editing cancels stale API results and loading is visible',async ({page}) => {
  await selectJourney(page);
  await page.getByRole('combobox',{name:'Data mode',exact:true}).selectOption('api');
  let release;
  const waiting = new Promise(resolve => { release = resolve; });
  await page.route('**/route',async route => { await waiting; await route.fulfill({json:fixture('normal')}).catch(() => {}); });
  await page.getByRole('button',{name:'Compare routes'}).click();
  await expect(page.locator('#status')).toContainText('Finding');
  await expect(page.getByRole('button',{name:'Compare routes'})).toBeDisabled();
  await page.getByLabel('Origin place search').fill('Cork');
  release();
  await expect(page.locator('#results article')).toHaveCount(0);
  await expect(page.getByRole('button',{name:'Compare routes'})).toBeEnabled();
});

test('redesigned navigation, empty state and responsive planner',async ({page}) => {
  await expect(page.locator('#results-empty')).toBeVisible();
  await page.getByRole('link',{name:'Plan your walk'}).click();
  await expect(page).toHaveURL(/#planner$/);
  for (const width of [320,768,1440]) {
    await page.setViewportSize({width,height:1000});
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  }
  await page.evaluate(() => window.scrollTo({top:0,behavior:'instant'}));
  await page.screenshot({path:'test-results/desktop-hero.png'});
  await selectJourney(page);
  await page.getByRole('button',{name:'Compare routes'}).click();
  await expect(page.locator('#results-empty')).toBeHidden();
  await page.getByRole('button',{name:'Show routes'}).click();
  await page.locator('.planner-grid').screenshot({path:'test-results/desktop-planner.png'});
  await page.getByLabel('Origin place search').fill('Cork');
  await expect(page.locator('#results-empty')).toBeVisible();
});
