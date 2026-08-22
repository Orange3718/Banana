# Atemoya next automation queue

Updated: 2026-08-22

## Running automatically

1. **Affiliate health check — daily 09:30 KST**
   - Checks the public affiliate page, disclosure, sponsored destination and
     live GA4 measurement configuration.
   - Stores the result in PostgreSQL and sends a concise Telegram report.
2. **Business scouting and owner brief**
   - Existing scheduled workflows continue collecting opportunities and
     reporting only decision-worthy changes.
3. **GA4 signal accumulation**
   - `content_view` and `affiliate_click` are now sent to the verified Atemoya
     GA4 measurement stream. The first useful trend review begins after at
     least seven days of real visitor data.

## Next execution order

1. Observe seven days of real visits and affiliate-click events without
   generating artificial traffic or clicks.
2. Review the first data point: page views, referral source and
   `affiliate_click` count. Keep the first page if it earns engagement;
   otherwise revise its title and opening copy.
3. Use the active Commerce Scout workflow to select one evidence-backed second
   buying-checklist topic. Create only a reviewable draft; publishing remains
   gated by the existing disclosure and quality checks.
4. Once the cumulative Coupang earnings threshold enables it, complete the
   settlement information in Coupang directly. Financial identifiers never
   enter Atemoya, Git or Telegram.

## Human-only blocker

Google Search Console currently requires the Google account that owns the
`orange3718.github.io` property (or an owner-granted account) before an
individual URL indexing request can be submitted. The sitemap remains public
and already includes the affiliate page, so normal discovery continues while
that access is restored.
