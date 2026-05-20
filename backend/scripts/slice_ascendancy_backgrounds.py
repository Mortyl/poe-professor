"""
Slice the 33-sprite ascendancy-background atlas into individual WebP files,
one per ascendancy, named to match the frontend's icons.ts slug convention.

Atlas:  frontend/public/images/tree/ascendancy-background_1500_1500_BC7.webp
Layout: 6×6 grid of 250×250 sprites (1-indexed, row-major).
Map:    frontend/public/images/tree/tree.json -> ddsCoords[atlas-name][sprite-name] = index

Output: frontend/public/images/ascendancies/{slug}.webp
"""

import json
import re
import sys
from pathlib import Path
from PIL import Image

PUB_DIR  = Path(__file__).resolve().parent.parent.parent / "frontend" / "public" / "images"
ATLAS    = PUB_DIR / "tree" / "ascendancy-background_1500_1500_BC7.webp"
TREEJSON = PUB_DIR / "tree" / "tree.json"
OUT_DIR  = PUB_DIR / "ascendancies"

GRID_COLS  = 6
CELL_SIZE  = 250          # 1500 / 6
ATLAS_KEY  = "ascendancy-background_1500_1500_BC7.dds.zst"


def slug(name: str) -> str:
    """Match frontend/app/builds/components/icons.ts:slugify."""
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-",
        name.lower().replace("'", "").replace("’", ""))).strip("-")


def main() -> int:
    if not ATLAS.exists():
        print(f"atlas missing: {ATLAS}", file=sys.stderr)
        return 1
    if not TREEJSON.exists():
        print(f"tree.json missing: {TREEJSON}", file=sys.stderr)
        return 1

    with TREEJSON.open() as f:
        tree = json.load(f)
    coords = tree.get("ddsCoords", {}).get(ATLAS_KEY, {})
    if not coords:
        print(f"no ddsCoords for atlas key: {ATLAS_KEY}", file=sys.stderr)
        return 1

    atlas = Image.open(ATLAS)
    print(f"atlas: {atlas.size}, sprites in coords: {len(coords)}")

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    skipped: list[str] = []
    written: list[tuple[str, str]] = []

    for name, idx in coords.items():
        # Strip the leading "Classes" prefix that PoB uses internally
        display = name.removeprefix("Classes").strip()
        s = slug(display)

        col = (idx - 1) % GRID_COLS
        row = (idx - 1) // GRID_COLS
        x, y = col * CELL_SIZE, row * CELL_SIZE

        crop = atlas.crop((x, y, x + CELL_SIZE, y + CELL_SIZE))
        # Skip pure-transparent slots (out-of-bounds indices for ascendancies that
        # haven't shipped yet would land here)
        alpha_max = crop.split()[-1].getextrema()[1]
        if alpha_max == 0:
            skipped.append(display)
            continue

        out_path = OUT_DIR / f"{s}.webp"
        crop.save(out_path, "WEBP", quality=92, method=6)
        written.append((display, str(out_path.name)))

    print(f"\nWrote {len(written)} ascendancy/class backgrounds to {OUT_DIR}:")
    for name, fname in sorted(written):
        print(f"  {name:<26} -> {fname}")
    if skipped:
        print(f"\nSkipped (empty sprite cell): {', '.join(skipped)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
