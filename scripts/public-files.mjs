import { readdirSync, lstatSync } from 'node:fs';
import { resolve, extname } from 'node:path';

// This list is a publication boundary, not an inventory of the repository.
const rootFiles = ['index.html', 'about.html', 'contact.html', 'privacy.html',
  'affiliate-disclosure.html', 'config.js', 'robots.txt', 'sitemap.xml', 'notes/ai-business-os.html'];
const tools = ['index', 'humidifier-calculator', 'heating-cost', 'air-purifier-tco',
  'food-disposer-tco', 'robot-vacuum-fit', 'beauty-device-tco', 'pet-feeder-capacity',
  'local-llm-memory', 'power-bank-flight', 'black-friday-price'];
const extensions = new Set(['.html', '.css', '.js', '.png', '.jpg', '.jpeg', '.webp', '.svg', '.ico', '.woff2']);
const buildInputs = new Set(['guides/backlog.json', 'guides/catalog.json', 'stories/catalog.json']);

export function publicFiles(root) {
  const result = [...rootFiles, ...tools.map(name => `tools/${name}.html`)];
  function walk(dir) {
    for (const name of readdirSync(resolve(root, dir)).sort()) {
      if (name.startsWith('.')) throw Error(`Hidden file in public directory: ${dir}/${name}`);
      const path = `${dir}/${name}`, stat = lstatSync(resolve(root, path));
      if (stat.isSymbolicLink()) throw Error(`Symlink in public directory: ${path}`);
      if (buildInputs.has(path)) continue;
      if (stat.isDirectory()) walk(path);
      else if (extensions.has(extname(name))) result.push(path);
      else throw Error(`Unapproved public file type: ${path}`);
    }
  }
  for (const dir of ['assets', 'guides', 'offers', 'stories']) walk(dir);
  for (const path of result) {
    if (!lstatSync(resolve(root, path)).isFile()) throw Error(`Not a regular public file: ${path}`);
  }
  return result.sort();
}
