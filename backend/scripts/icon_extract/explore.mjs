#!/usr/bin/env node
// Explore PoE2 bundle structure — list files/dirs under a given path
// Usage: node explore.mjs [dir-path]   e.g. node explore.mjs art/2DItems

const PKG = 'file:///C:/Users/marcu/AppData/Roaming/npm/node_modules/pathofexile-dat/dist';
const { SteamBundleLoader } = await import(`${PKG}/cli/bundle-loaders.js`);
const { decompressSliceInBundle, decompressedBundleSize } = await import(`${PKG}/bundles/bundle.js`);
const { readIndexBundle } = await import(`${PKG}/bundles/index-bundle.js`);
const { getDirContent, getRootDirs } = await import(`${PKG}/bundles/index-paths.js`);

const STEAM = 'C:\\Program Files (x86)\\Steam\\steamapps\\common\\Path of Exile 2';
const target = process.argv[2] ?? '';

const loader = new SteamBundleLoader(STEAM);
const indexBin = await loader.fetchFile('_.index.bin');
const indexBundle = new Uint8Array(decompressedBundleSize(indexBin));
decompressSliceInBundle(indexBin, 0, indexBundle);
const { bundlesInfo, filesInfo, dirsInfo, pathRepsBundle } = readIndexBundle(indexBundle);

// pathRepsBundle is itself a compressed bundle; decompress it
const pathReps = new Uint8Array(decompressedBundleSize(pathRepsBundle));
decompressSliceInBundle(pathRepsBundle, 0, pathReps);

if (!target) {
  const roots = getRootDirs(pathReps, dirsInfo);
  console.log('ROOT DIRS:');
  for (const r of roots) console.log('  ' + r);
} else {
  const { files, dirs } = getDirContent(target, pathReps, dirsInfo);
  const filter = process.argv[3];
  let fs2 = files.filter(f => !f.endsWith('.header'));
  if (filter) fs2 = fs2.filter(f => f.toLowerCase().includes(filter.toLowerCase()));
  console.log(`DIRS under "${target}" (${dirs.length}):`);
  for (const d of dirs) console.log('  ' + d);
  console.log(`\nFILES under "${target}" (${fs2.length}${filter ? ` matching "${filter}"` : ''}):`);
  for (const f of fs2) console.log('  ' + f);
}
