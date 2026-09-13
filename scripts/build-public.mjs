import { mkdirSync, copyFileSync } from 'node:fs';
import { resolve, dirname } from 'node:path';
import { publicFiles } from './public-files.mjs';

const root = resolve(import.meta.dirname, '..');
const target = resolve(root, 'dist-public');
const files = publicFiles(root);
// Refuse an existing output directory: old files must never leak into a release.
mkdirSync(target);
for (const file of files) {
  mkdirSync(dirname(resolve(target, file)), { recursive: true });
  copyFileSync(resolve(root, file), resolve(target, file));
}
console.log(`Public artifact: ${files.length} allowlisted files; no operational directories.`);
