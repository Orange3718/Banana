/* Atemoya measurement v2: page_view is GA4's standard view metric. */
(() => {
  const c = window.ATEMOYA_CONFIG || {};
  const id = c.gaMeasurementId;
  if (!/^G-[A-Z0-9]+$/.test(id || '') || window.__atemoyaAnalyticsStarted) return;
  window.__atemoyaAnalyticsStarted = true;
  window.dataLayer = window.dataLayer || [];
  window.gtag = window.gtag || function () { window.dataLayer.push(arguments); };
  const alreadyLoaded = document.querySelector('script[src*="gtag/js?id=' + id + '"]');
  if (!alreadyLoaded) {
    window.gtag('js', new Date());
    window.gtag('config', id);
    const script = document.createElement('script');
    script.async = true;
    script.src = 'https://www.googletagmanager.com/gtag/js?id=' + encodeURIComponent(id);
    document.head.appendChild(script);
  }
  const send = (name, data) => {
    try { window.gtag('event', name, { ...data, send_to: id }); }
    catch (_) { /* Measurement failure must never interrupt navigation. */ }
  };
  const ready = () => {
    const contentPath = location.pathname;
    const type = contentPath.includes('/guides/') ? 'guide' :
      contentPath.includes('/stories/') ? 'story' : contentPath.includes('/offers/') ? 'offer' : 'page';
    send('content_view', { content_type: type, content_path: contentPath });
    const recordClick = e => {
      if (e.type === 'auxclick' && e.button !== 1) return;
      const a = e.target?.closest?.('a');
      if (!a) return;
      let url;
      try { url = new URL(a.href, location.href); } catch (_) { return; }
      if (!['http:', 'https:'].includes(url.protocol)) return;
      const marked = a.matches('[data-affiliate]');
      const external = url.origin !== location.origin;
      // A data-affiliate fallback can still lead to our internal calculator.
      if (marked && external && url.protocol === 'https:' &&
          ['link.coupang.com', 'coupa.ng'].includes(url.hostname)) {
        const key = a.dataset.linkKey;
        send('affiliate_click', {
          content_path: contentPath, category: document.body.dataset.category || '',
          affiliate_host: url.hostname,
          link_key: /^[a-z0-9_-]{1,64}$/i.test(key || '') ? key : 'unmapped',
          measurement_version: 'v2'
        });
      } else if (external) {
        send('outbound_click', { destination: url.hostname, content_path: contentPath });
      } else if (marked) {
        send('internal_cta_click', { content_path: contentPath, destination_path: url.pathname });
      }
    };
    document.addEventListener('click', recordClick);
    document.addEventListener('auxclick', recordClick);
  };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', ready, { once: true });
  else ready();
})();
