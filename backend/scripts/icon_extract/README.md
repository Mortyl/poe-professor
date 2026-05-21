# PoE2 Gear Icon Extraction

Pulls item icons directly from a local Steam install of Path of Exile 2 and writes
PNGs to `frontend/public/icons/items/`. Re-run after each PoE2 patch to pick up
new uniques / bases.

## Prereqs

- PoE2 installed via Steam at the default location (edit `STEAM` constant if not).
- Node 22+ (`pathofexile-dat` is a global npm package).
- ImageMagick 7 (`magick` CLI). `winget install ImageMagick.ImageMagick`.

If `pathofexile-dat` isn't installed:

```
npm install -g pathofexile-dat
```

## Files

- `config.json` — driver for `pathofexile-dat`: extracts the four .datc64 tables
  (BaseItemTypes, ItemVisualIdentity, UniqueStashLayout, Words) into `./tables/`.
- `extract_all.mjs` — reads `./tables/English/*.json`, opens the Steam bundle index
  directly via `pathofexile-dat`'s `SteamBundleLoader`, extracts each unique DDS,
  and pipes it through `magick dds:- out.png` into the frontend public dir.
- `explore.mjs` — debugging helper. `node explore.mjs <dir-path> [<filter>]`
  lists files/dirs inside the bundle at any path. Useful when GGG renames things.
- `extract.mjs` — extract a handful of files by path for ad-hoc inspection.

## Workflow

```
cd backend/scripts/icon_extract
pathofexile-dat            # exports tables -> ./tables/
node extract_all.mjs       # ~3000 icons in ~30s, writes to frontend/public/icons/items/
```

Output:
- `<IVI_ID>.png` — one per ItemVisualIdentity row (e.g. `FourUniqueBodyInt13.png`)
- `index.json` — `{ uniques: { name: filename }, bases: { name: filename } }`

Frontend code looks up by item name:

```ts
import index from '@/public/icons/items/index.json';
const file = index.uniques[itemName] ?? index.bases[baseName];
// <img src={`/icons/items/${file}.png`} />
```

`FORCE=1 node extract_all.mjs` re-extracts everything; otherwise existing PNGs are skipped.

## PoE2 vs PoE1 gotchas

PoE2 changed several things from PoE1's data layout:
- Tables: `.dat64` → `.datc64`, located in `data/balance/` (not `data/`).
- Path casing: the bundle index stores all paths lowercase — must lowercase before lookup.
- Item identifiers in `ItemVisualIdentity.Id` are `Four*` (Four = PoE2 internal codename).
- Many PoE2 uniques aren't in `UniqueStashLayout` (only ~399 entries) — only ones with
  stash-tab placement are listed. The other tables we'd need for "unbeknownst" uniques
  don't yet exist in PoE2's data.
