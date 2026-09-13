import { readFileSync, existsSync, readdirSync, lstatSync } from 'node:fs';
import { resolve, dirname, relative } from 'node:path';
import { publicFiles } from './public-files.mjs';

const root = resolve(process.argv[2] || resolve(import.meta.dirname, '..'));
const files = publicFiles(root), allowed = new Set(files), errors = [];
if (process.argv[2]) {
  const walk = dir => readdirSync(dir).flatMap(name => {
    const path = resolve(dir, name), stat = lstatSync(path);
    if (stat.isSymbolicLink()) { errors.push(`Unexpected symlink: ${relative(root, path)}`); return []; }
    return stat.isDirectory() ? walk(path) : [relative(root, path)];
  });
  for (const file of walk(root)) if (!allowed.has(file)) errors.push(`Non-public artifact file: ${file}`);
}
const html = files.filter(file => file.endsWith('.html'));
for (const file of html) {
  const path = resolve(root, file), text = readFileSync(path, 'utf8');
  if (!/<title>[^<]+<\/title>/.test(text)) errors.push(`${file}: title missing`);
  if (!/<meta name="viewport"/.test(text)) errors.push(`${file}: viewport missing`);
  for (const match of text.matchAll(/(?:href|src)="([^"#?]+)"/g)) {
    const url = match[1];
    if (/^(https?:|mailto:|data:|tel:|\/\/)/.test(url)) continue;
    const target = resolve(dirname(path), url), rel = relative(root, target);
    if (!allowed.has(rel) && !allowed.has(`${rel}/index.html`)) errors.push(`${file}: non-public/broken ${url}`);
    if (!existsSync(target) && !existsSync(resolve(target, 'index.html'))) errors.push(`${file}: missing ${url}`);
  }
  for (const match of text.matchAll(/<a\b[^>]*data-affiliate[^>]*>/g)) {
    const href = match[0].match(/href="([^"]+)"/)?.[1];
    if (href && /^https:\/\/link\.coupang\.com\//.test(href)) {
      if (!text.includes('쿠팡 파트너스 활동의 일환으로') || !text.includes('수수료를 제공받습니다')) errors.push(`${file}: Coupang disclosure missing`);
      if (!/data-link-key="[a-z0-9_-]+"/i.test(match[0])) errors.push(`${file}: tracking key missing`);
      if (!/rel="[^"]*sponsored/.test(match[0])) errors.push(`${file}: sponsored marker missing`);
    }
  }
}
for (const file of files.filter(file => /\.(html|js|css|xml|txt|svg)$/.test(file))) {
  const text = readFileSync(resolve(root, file), 'utf8');
  if (/-----BEGIN (?:OPENSSH|RSA|EC) PRIVATE KEY-----/.test(text)) errors.push(`${file}: private key detected`);
}
if (errors.length) { console.error(errors.join('\n')); process.exit(1); }
console.log(`PASS: ${html.length} public HTML pages; links, affiliate disclosures and private-key patterns. ${files.length} public files. Not a full security or GA receipt audit.`);
