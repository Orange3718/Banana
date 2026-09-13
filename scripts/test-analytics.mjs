// Offline harness: no GA requests or affiliate navigation.
import { readFileSync } from 'node:fs';
import { runInNewContext } from 'node:vm';
import assert from 'node:assert/strict';
import { test } from 'node:test';
const source = readFileSync(new URL('../assets/analytics.js', import.meta.url), 'utf8');
function fixture({ id = 'G-TEST123', loaded = false } = {}) {
  const listeners = {}, scripts = [], calls = [];
  const window = { ATEMOYA_CONFIG: { gaMeasurementId: id }, gtag: (...args) => calls.push(args) };
  const document = { readyState: 'complete', body: { dataset: { category: 'beauty' } },
    querySelector: () => loaded ? {} : null, createElement: () => ({}),
    head: { appendChild: s => scripts.push(s) }, addEventListener: (event, fn) => { listeners[event] = fn; } };
  const context = { window, document, location: { pathname: '/Banana/offers/a.html', href: 'https://example.org/Banana/offers/a.html', origin: 'https://example.org' }, URL };
  runInNewContext(source, context);
  function click(href, marked = true, type = 'click', button = 0) {
    const anchor = { href, matches: () => marked, dataset: { linkKey: 'lg-pral-bwj1' } };
    listeners[type]?.({ type, button, target: { closest: () => anchor }, preventDefault: () => { throw Error('navigation blocked'); } });
  }
  return { calls, scripts, context, click, events: name => calls.filter(x => x[0] === 'event' && x[1] === name) };
}
test('internal calculator is not an affiliate click', () => {
  const f = fixture(); f.click('../tools/beauty.html');
  assert.equal(f.events('affiliate_click').length, 0); assert.equal(f.events('internal_cta_click').length, 1);
});
test('Coupang emits one event with stable key, without destination query values', () => {
  const f = fixture(); f.click('https://link.coupang.com/a/example?private=secret');
  assert.equal(f.events('affiliate_click').length, 1);
  assert.equal(f.events('affiliate_click')[0][2].link_key, 'lg-pral-bwj1');
  assert.ok(!JSON.stringify(f.calls).includes('secret'));
});
test('unrelated and lookalike hosts are not Coupang affiliate clicks', () => {
  const f = fixture(); f.click('https://link.coupang.com.example.org/'); f.click('https://example.net/');
  assert.equal(f.events('affiliate_click').length, 0); assert.equal(f.events('outbound_click').length, 2);
});
test('duplicate script loads do not duplicate configuration or views', () => {
  const f = fixture(); runInNewContext(source, f.context);
  assert.equal(f.scripts.length, 1); assert.equal(f.events('content_view').length, 1);
  assert.equal(f.calls.filter(x => x[0] === 'config').length, 1);
});
test('existing tag keeps existing page_view configuration', () => {
  const f = fixture({ loaded: true }); assert.equal(f.scripts.length, 0);
  assert.equal(f.calls.filter(x => x[0] === 'config').length, 0); assert.equal(f.events('content_view').length, 1);
});
test('disabled configuration creates no analytics work', () => {
  const f = fixture({ id: '' }); assert.equal(f.calls.length, 0); assert.equal(f.scripts.length, 0);
});
test('middle click counted once; right click excluded', () => {
  const f = fixture(); f.click('https://link.coupang.com/a/example', true, 'auxclick', 1);
  f.click('https://link.coupang.com/a/example', true, 'auxclick', 2);
  assert.equal(f.events('affiliate_click').length, 1);
});
test('tracking failure does not block navigation; non-http links ignored', () => {
  const f = fixture(); f.context.window.gtag = () => { throw Error('blocked'); };
  assert.doesNotThrow(() => f.click('https://link.coupang.com/a/example'));
  const g = fixture(); g.click('mailto:private@example.org'); assert.equal(g.events('affiliate_click').length, 0);
});
