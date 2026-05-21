#!/usr/bin/env node
// Bulk-extract PoE2 gear icons (uniques + base types) to PNG.
//
// Reads ./tables/English/{BaseItemTypes,ItemVisualIdentity,UniqueStashLayout,Words}.json
// (produced by `pathofexile-dat` table export), extracts each unique DDSFile from
// PoE2's Steam bundles, converts to PNG via ImageMagick, and writes:
//   - <OUT_DIR>/<IVI_ID>.png       — one file per ItemVisualIdentity row
//   - <OUT_DIR>/index.json         — { uniques: {name: filename}, bases: {name: filename} }
//
// Re-running skips already-converted files. Set FORCE=1 to re-extract everything.

import * as fs from 'fs/promises';
import * as path from 'path';
import { spawn } from 'child_process';

const STEAM = 'C:\\Program Files (x86)\\Steam\\steamapps\\common\\Path of Exile 2';
const MAGICK = 'C:\\Program Files\\ImageMagick-7.1.2-Q16-HDRI\\magick.exe';
const OUT_DIR = path.resolve('../../../frontend/public/icons/items');
const INDEX_OUT = path.resolve('../../../frontend/app/builds/components/itemIcons.json');
const TABLE_DIR = path.resolve('tables/English');
const FORCE = process.env.FORCE === '1';

const PKG = 'file:///C:/Users/marcu/AppData/Roaming/npm/node_modules/pathofexile-dat/dist';
const { SteamBundleLoader, FileLoader } = await import(`${PKG}/cli/bundle-loaders.js`);

const readJson = async (p) => JSON.parse(await fs.readFile(p, 'utf8'));

console.log('Loading dat tables...');
const [bit, ivi, usl, words] = await Promise.all([
  readJson(path.join(TABLE_DIR, 'BaseItemTypes.json')),
  readJson(path.join(TABLE_DIR, 'ItemVisualIdentity.json')),
  readJson(path.join(TABLE_DIR, 'UniqueStashLayout.json')),
  readJson(path.join(TABLE_DIR, 'Words.json')),
]);

// Build name maps + the set of IVI rows we need to extract
const uniqueNameToIviId = {};
const baseNameToIviId = {};
const wantedIviIds = new Set();

for (const r of usl) {
  const name = words[r.WordsKey]?.Text;
  const ivIdx = r.ItemVisualIdentityKey;
  const ivRow = ivi[ivIdx];
  if (!name || !ivRow?.DDSFile) continue;
  uniqueNameToIviId[name] = ivRow.Id;
  wantedIviIds.add(ivIdx);
}

for (const b of bit) {
  const ivIdx = b.ItemVisualIdentity;
  if (ivIdx == null) continue;
  const ivRow = ivi[ivIdx];
  if (!b.Name || !ivRow?.DDSFile) continue;
  if (baseNameToIviId[b.Name]) continue;
  baseNameToIviId[b.Name] = ivRow.Id;
  wantedIviIds.add(ivIdx);
}

console.log(`uniques (named): ${Object.keys(uniqueNameToIviId).length}`);
console.log(`bases   (named): ${Object.keys(baseNameToIviId).length}`);
console.log(`distinct icons to extract: ${wantedIviIds.size}`);

await fs.mkdir(OUT_DIR, { recursive: true });

// Convert a DDS buffer to PNG via ImageMagick subprocess (stdin -> file out).
function convertDDS(dds, outPath) {
  return new Promise((resolve, reject) => {
    const proc = spawn(MAGICK, ['dds:-', outPath], { stdio: ['pipe', 'ignore', 'pipe'] });
    let err = '';
    proc.stderr.on('data', (d) => { err += d.toString(); });
    proc.on('error', reject);
    proc.on('exit', (code) => code === 0 ? resolve() : reject(new Error(`magick ${code}: ${err.trim()}`)));
    proc.stdin.write(Buffer.from(dds));
    proc.stdin.end();
  });
}

console.log('\nOpening bundles...');
const loader = await FileLoader.create(new SteamBundleLoader(STEAM));

let ok = 0, skipped = 0, missing = 0, failed = 0;
const failures = [];
const idsToProcess = [...wantedIviIds];

for (let i = 0; i < idsToProcess.length; i++) {
  const ivIdx = idsToProcess[i];
  const row = ivi[ivIdx];
  const outPath = path.join(OUT_DIR, `${row.Id}.png`);

  if (!FORCE) {
    try { await fs.access(outPath); skipped++; continue; } catch {}
  }

  // PoE2 paths are lowercase in the bundle index
  const bundlePath = row.DDSFile.toLowerCase();
  const dds = await loader.tryGetFileContents(bundlePath);
  if (!dds) { missing++; failures.push(`MISSING ${row.Id}: ${bundlePath}`); continue; }

  try {
    await convertDDS(dds, outPath);
    ok++;
  } catch (e) {
    failed++;
    failures.push(`FAIL ${row.Id} (${bundlePath}): ${e.message}`);
  }

  if ((i + 1) % 100 === 0 || i === idsToProcess.length - 1) {
    process.stdout.write(`\r  [${i + 1}/${idsToProcess.length}] ok=${ok} skip=${skipped} miss=${missing} fail=${failed}     `);
  }
}
process.stdout.write('\n');

// Drop the lookup index where the frontend imports it (committed source).
// Minified — this gets bundled into the client JS.
const indexJson = JSON.stringify({
  generated: new Date().toISOString(),
  uniques: uniqueNameToIviId,
  bases: baseNameToIviId,
});
await fs.writeFile(INDEX_OUT, indexJson);

console.log(`\nDone. ${ok} converted, ${skipped} skipped, ${missing} missing in bundle, ${failed} convert errors.`);
console.log(`Index: ${INDEX_OUT}`);
if (failures.length) {
  console.log(`\nFirst 20 failures:`);
  failures.slice(0, 20).forEach((f) => console.log('  ' + f));
}
