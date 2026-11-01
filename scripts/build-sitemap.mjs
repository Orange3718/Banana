import { writeFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { publicFiles } from './public-files.mjs';

const root = resolve(import.meta.dirname, '..');
const base = 'https://orange3718.github.io/Banana/';
const pages = publicFiles(root).filter(file => file.endsWith('.html'));
const paths = ['', ...pages.filter(file => file !== 'index.html')];
const xml = `<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n${paths.map(path => `  <url><loc>${base}${path}</loc></url>`).join('\n')}\n</urlset>\n`;

writeFileSync(resolve(root, 'sitemap.xml'), xml);
console.log(`Generated sitemap with ${paths.length} public URLs.`);
