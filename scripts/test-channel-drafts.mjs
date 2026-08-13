import { readFileSync, statSync } from 'node:fs';
import { resolve } from 'node:path';

const root = resolve('channel-drafts/generated');
const manifest = JSON.parse(readFileSync(resolve(root, 'manifest.json'), 'utf8'));
const expectedFiles = ['web.json', 'blogger-draft.json', 'tistory-copy-paste.html', 'naver-draft.txt', 'social-drafts.json', 'youtube-package.json', 'status.json'];

if (manifest.items.length !== 10) throw new Error(`Expected 10 stories, found ${manifest.items.length}`);
if (manifest.totals.assets !== 70) throw new Error(`Expected 70 assets, found ${manifest.totals.assets}`);

for (const item of manifest.items) {
  if (!item.canonicalUrl.includes(`/stories/${item.slug}.html`)) throw new Error(`${item.slug}: invalid canonical URL`);
  const hashes = new Set(Object.values(item.fingerprints));
  if (hashes.size !== 6) throw new Error(`${item.slug}: duplicate channel draft detected`);
  for (const file of expectedFiles) {
    const path = resolve(root, item.slug, file);
    if (statSync(path).size < 100) throw new Error(`${item.slug}/${file}: missing or too small`);
    const content = readFileSync(path, 'utf8');
    if (!content.includes('수수료') && file !== 'status.json') throw new Error(`${item.slug}/${file}: affiliate disclosure missing`);
    if (!content.includes(item.canonicalUrl) && !['social-drafts.json', 'youtube-package.json', 'status.json'].includes(file)) throw new Error(`${item.slug}/${file}: canonical URL missing`);
  }
}

console.log(`PASS: ${manifest.items.length} stories, ${manifest.totals.assets} assets, disclosures/canonicals/fingerprints verified.`);
