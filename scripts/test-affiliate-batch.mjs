import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

const root = resolve(import.meta.dirname, '..');
const files = [
  'led-mask-buying-checklist.html',
  'airtight-container-buying-checklist.html',
  'robot-vacuum-buying-checklist.html',
  'yoga-mat-buying-checklist.html',
  'automatic-pet-feeder-buying-checklist.html',
  'baby-wipes-buying-checklist.html',
  'travel-compression-pouch-buying-checklist.html',
  'laptop-stand-buying-checklist.html',
  'heated-humidifier-buying-checklist.html',
  'bone-conduction-earphones-buying-checklist.html'
];
const categories = new Set(), links = new Set(), keys = new Set(), errors = [];

for (const file of files) {
  const text = readFileSync(resolve(root, 'offers', file), 'utf8');
  const category = text.match(/<div class="category">([^<]+)<\/div>/)?.[1];
  const link = text.match(/href="(https:\/\/link\.coupang\.com\/a\/[^"]+)"/)?.[1];
  const key = text.match(/data-link-key="([^"]+)"/)?.[1];
  if (!category || !link || !key) errors.push(`${file}: category, link or key missing`);
  if (!text.includes('이 포스팅은 쿠팡 파트너스 활동의 일환으로, 이에 따른 일정액의 수수료를 제공받습니다.')) errors.push(`${file}: disclosure missing`);
  if (!text.includes('rel="sponsored nofollow"')) errors.push(`${file}: sponsored nofollow missing`);
  categories.add(category); links.add(link); keys.add(key);
}
if (categories.size !== 10) errors.push(`expected 10 categories, found ${categories.size}`);
if (links.size !== 10) errors.push(`expected 10 unique affiliate links, found ${links.size}`);
if (keys.size !== 10) errors.push(`expected 10 unique tracking keys, found ${keys.size}`);
if (errors.length) { console.error(errors.join('\n')); process.exit(1); }
console.log('PASS: 10 categories, 10 unique Coupang links, disclosures and tracking keys.');
