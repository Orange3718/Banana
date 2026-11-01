import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { publicFiles } from './public-files.mjs';

const root = resolve(process.argv[2] || new URL('..', import.meta.url).pathname);
const files = publicFiles(root);
const errors = [];
for (const file of files.filter(name => /\.(?:html|js)$/.test(name))) {
  const content = readFileSync(resolve(root, file), 'utf8');
  if (/https?:\/\/(?:link\.coupang\.com|coupa\.ng)\b/i.test(content)) errors.push(`${file}: retired partner link`);
  if (/쿠팡 파트너스 활동의 일환|data-affiliate|id="affiliate-link"/.test(content)) errors.push(`${file}: retired affiliate UI`);
  if (file.startsWith("offers/") && /상품 ID|링크 확인일|쿠팡/.test(content)) errors.push(`${file}: stale partner reference`);
}
const configText = readFileSync(resolve(root, 'config.js'), 'utf8');
const config = JSON.parse(configText.match(/^window\.ATEMOYA_CONFIG=(.*);\s*$/s)?.[1] || 'null');
if (config?.affiliateUrl !== '' || Object.values(config?.affiliateUrls || {}).some(Boolean)) errors.push('config.js: affiliate URL re-enabled');
if (errors.length) {
  console.error(errors.join('\n'));
  process.exit(1);
}
console.log(`PASS: ${files.length} public files contain no retired partner links or affiliate UI.`);
