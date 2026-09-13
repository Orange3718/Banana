import { mkdtempSync, mkdirSync, copyFileSync, writeFileSync, symlinkSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { resolve, dirname } from 'node:path';
import { spawnSync } from 'node:child_process';
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { publicFiles } from './public-files.mjs';
const root = resolve(import.meta.dirname, '..');
function fixture(t) {
  const target = mkdtempSync(resolve(tmpdir(), 'atemoya-public-test-'));
  t.after(() => rmSync(target, { recursive: true, force: true }));
  for (const file of publicFiles(root)) {
    mkdirSync(dirname(resolve(target, file)), { recursive: true });
    copyFileSync(resolve(root, file), resolve(target, file));
  }
  return target;
}
test('public allowlist excludes operational files and rejects contaminated artifacts', t => {
  const target = fixture(t);
  const check = () => spawnSync(process.execPath, [resolve(root, 'scripts/test-site.mjs'), target], { encoding: 'utf8' });
  assert.equal(check().status, 0);
  mkdirSync(resolve(target, 'docs'));
  writeFileSync(resolve(target, 'docs/private.md'), 'fixture, not a secret');
  assert.ok(!publicFiles(target).includes('docs/private.md'));
  assert.equal(check().status, 1);
  assert.match(check().stderr, /Non-public artifact file: docs\/private.md/);
});
test('symlink in a public directory fails closed', t => {
  const target = fixture(t);
  symlinkSync(resolve(target, 'config.js'), resolve(target, 'assets/leak.js'));
  assert.throws(() => publicFiles(target), /Symlink/);
});
test('unapproved file types fail closed', t => {
  const target = fixture(t);
  writeFileSync(resolve(target, 'assets/private.sql'), 'fixture');
  assert.throws(() => publicFiles(target), /Unapproved public file type/);
});
