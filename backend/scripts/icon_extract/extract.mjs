#!/usr/bin/env node
// Extract one or more files from PoE2 bundles into ./out/
// Usage: node extract.mjs <bundle-path> [<bundle-path> ...]

import * as fs from 'fs/promises';
import * as path from 'path';

const PKG = 'file:///C:/Users/marcu/AppData/Roaming/npm/node_modules/pathofexile-dat/dist';
const { SteamBundleLoader, FileLoader } = await import(`${PKG}/cli/bundle-loaders.js`);

const STEAM = 'C:\\Program Files (x86)\\Steam\\steamapps\\common\\Path of Exile 2';
const OUT = path.resolve('out');
await fs.mkdir(OUT, { recursive: true });

const targets = process.argv.slice(2);
if (!targets.length) { console.error('Pass one or more bundle paths.'); process.exit(1); }

const loader = await FileLoader.create(new SteamBundleLoader(STEAM));

for (const t of targets) {
  const data = await loader.tryGetFileContents(t);
  if (!data) { console.error(`MISSING: ${t}`); continue; }
  const out = path.join(OUT, t.replace(/\//g, '@'));
  await fs.writeFile(out, data);
  const magic = new TextDecoder().decode(data.subarray(0, 4));
  console.log(`OK  ${t}  (${data.byteLength}B, magic="${magic}")  -> ${out}`);
}
