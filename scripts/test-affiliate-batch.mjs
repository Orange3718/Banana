import { readFileSync, readdirSync } from 'node:fs';
import { resolve } from 'node:path';

const root = resolve(import.meta.dirname, '..');
const files = readdirSync(resolve(root, 'offers')).filter(file => file.endsWith('.html') && file !== 'index.html').sort();
const categories = new Set(), links = new Set(), keys = new Set(), pages = new Set(), errors = [];
const disclosure = '이 포스팅은 쿠팡 파트너스 활동의 일환으로, 이에 따른 일정액의 수수료를 제공받습니다.';

for (const file of files) {
  const text = readFileSync(resolve(root, 'offers', file), 'utf8');
  if (!text.includes('https://link.coupang.com/')) continue;
  const category = text.match(/<div class="category">([^<]+)<\/div>/)?.[1];
  const anchors = [...text.matchAll(/<a\b[^>]*data-affiliate[^>]*>/g)];
  if (!category || anchors.length !== 1) errors.push(`${file}: category missing or expected exactly one affiliate CTA`);
  if (text.split(disclosure).length - 1 !== 1) errors.push(`${file}: exact disclosure must appear once`);
  if (!/<link rel="canonical" href="https:\/\/orange3718\.github\.io\/Banana\/offers\/[a-z0-9-]+\.html"/.test(text)) errors.push(`${file}: canonical missing or invalid`);
  for (const match of anchors) {
    const link = match[0].match(/href="(https:\/\/link\.coupang\.com\/a\/[A-Za-z0-9]+)"/)?.[1];
    const key = match[0].match(/data-link-key="([a-z0-9-]+)"/)?.[1];
    if (!link || !key) errors.push(`${file}: verified-host link or tracking key missing`);
    if (!/rel="[^"]*sponsored[^"]*nofollow/.test(match[0])) errors.push(`${file}: sponsored nofollow missing`);
    if (key && keys.has(key)) errors.push(`${file}: duplicate tracking key ${key}`);
    if (link) links.add(link);
    if (key) keys.add(key);
  }
  if (category) categories.add(category);
  pages.add(file);
}
if (pages.size < 10) errors.push(`expected at least 10 affiliate pages, found ${pages.size}`);
if (categories.size < 10) errors.push(`expected at least 10 categories, found ${categories.size}`);
if (keys.size !== pages.size) errors.push(`expected one unique tracking key per page, found ${keys.size} keys for ${pages.size} pages`);
if (errors.length) { console.error(errors.join('\n')); process.exit(1); }
console.log(`PASS: ${pages.size} affiliate pages, ${categories.size} categories, ${links.size} reviewed links, unique tracking keys and exact disclosures.`);
