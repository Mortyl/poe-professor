"""
Convert PoB-PoE2 passive-tree DDS sprite atlases into web-ready WebP files
+ a JSON manifest the frontend uses to look up sprites by name.

PoE2 tree assets are stored as DDS *texture arrays* (one image per array slice,
each with its own mipmap chain), Zstandard-compressed. tree.json maps named
sprites (`PSSkillFrame`, `Art/2DArt/SkillIcons/passives/Foo.dds`, etc.) to
1-indexed array positions inside each atlas via the `ddsCoords` table.

This script:
  1. Decompresses each .dds.zst → DDS bytes
  2. Parses the DX10 header to find dimensions, array size, dxgi format
  3. For each array slice, decodes only mip-0 (the full-size image)
  4. Picks an output strategy per atlas:
       - single-slice (arr=1)  → one WebP, same name as source
       - many small slices     → pack into a sprite sheet WebP + mapping
       - few large slices      → one WebP per slice (e.g. ascendancy backgrounds)
  5. Writes frontend/public/images/tree/manifest.json listing every sprite's
     atlas + (x, y, w, h) so the canvas can blit by name.

Run:  python backend/scripts/convert_tree_assets.py
"""

import json
import math
import struct
import sys
from pathlib import Path

import zstandard
import texture2ddecoder
from PIL import Image


POB_TREE_DIR = Path(r"C:/Users/marcu/Downloads/PathOfBuilding-PoE2-dev/PathOfBuilding-PoE2-dev/src/TreeData/0_4")
OUT_DIR      = Path(__file__).resolve().parent.parent.parent / "frontend" / "public" / "images" / "tree"

# Atlases whose slices should be saved as individual files (one WebP per slice)
# rather than packed into a sprite sheet. Used for backgrounds where each
# slice is large and likely shown alone.
INDIVIDUAL_OUTPUT: dict[str, str] = {
    "ascendancy-background_1500_1500_BC7.dds.zst": "ascendancies",   # 33 × 1500x1500 → per-asc files
}

# DXGI_FORMAT constants we recognise
DXGI = {
    71: ("BC1_UNORM", 8),     # block size in bytes
    72: ("BC1_UNORM_SRGB", 8),
    77: ("BC3_UNORM", 16),
    78: ("BC3_UNORM_SRGB", 16),
    80: ("BC4_UNORM", 8),
    83: ("BC5_UNORM", 16),
    98: ("BC7_UNORM", 16),
    99: ("BC7_UNORM_SRGB", 16),
    28: ("R8G8B8A8_UNORM", 0),  # raw, not block-compressed
}


def block_count(size_px: int) -> int:
    """Number of 4x4 blocks along one axis, rounded up. Min 1."""
    return max(1, (size_px + 3) // 4)


def mip_bytes(w: int, h: int, block_bytes: int) -> int:
    if block_bytes == 0:   # raw RGBA
        return w * h * 4
    return block_count(w) * block_count(h) * block_bytes


def slice_bytes(w0: int, h0: int, mip_count: int, block_bytes: int) -> int:
    total = 0
    for level in range(mip_count):
        mw = max(1, w0 >> level)
        mh = max(1, h0 >> level)
        total += mip_bytes(mw, mh, block_bytes)
    return total


def decode_slice(pixels: bytes, w: int, h: int, dxgi: int) -> Image.Image:
    """Decode a single mip-0 slice (already extracted) to a Pillow RGBA Image."""
    if dxgi in (71, 72):
        decoded = texture2ddecoder.decode_bc1(pixels, w, h)
    elif dxgi in (77, 78):
        decoded = texture2ddecoder.decode_bc3(pixels, w, h)
    elif dxgi == 80:
        decoded = texture2ddecoder.decode_bc4(pixels, w, h)
    elif dxgi == 83:
        decoded = texture2ddecoder.decode_bc5(pixels, w, h)
    elif dxgi in (98, 99):
        decoded = texture2ddecoder.decode_bc7(pixels, w, h)
    elif dxgi == 28:
        return Image.frombytes("RGBA", (w, h), pixels[: w * h * 4])
    else:
        raise ValueError(f"unsupported dxgi format {dxgi}")
    return Image.frombytes("RGBA", (w, h), decoded, "raw", "BGRA")


def extract_slices(dds: bytes) -> tuple[int, int, int, list[Image.Image]]:
    """Decompose a DDS texture array → list of mip-0 PIL Images, one per slice."""
    if dds[:4] != b"DDS ":
        raise ValueError("not a DDS file")
    h = struct.unpack("<I", dds[12:16])[0]
    w = struct.unpack("<I", dds[16:20])[0]
    mipmaps = max(1, struct.unpack("<I", dds[28:32])[0])
    fourcc = dds[84:88]
    if fourcc != b"DX10":
        raise ValueError("expected DX10 header — legacy DDS not supported here")
    dxgi = struct.unpack("<I", dds[128:132])[0]
    arr  = max(1, struct.unpack("<I", dds[140:144])[0])
    if dxgi not in DXGI:
        raise ValueError(f"unsupported dxgi format {dxgi}")
    _, block_bytes = DXGI[dxgi]

    pixels = dds[148:]
    per_slice = slice_bytes(w, h, mipmaps, block_bytes)
    mip0_bytes = mip_bytes(w, h, block_bytes)
    if len(pixels) < per_slice * arr:
        raise ValueError(
            f"pixel data short: have {len(pixels):,}, need {per_slice * arr:,} "
            f"({arr} slices × {per_slice})"
        )

    imgs: list[Image.Image] = []
    for i in range(arr):
        slice_start = i * per_slice
        mip0 = pixels[slice_start : slice_start + mip0_bytes]
        imgs.append(decode_slice(mip0, w, h, dxgi))
    return w, h, arr, imgs


def pack_sheet(slices: list[Image.Image]) -> tuple[Image.Image, list[tuple[int, int]]]:
    """Pack equal-sized slices into a square-ish grid sprite sheet.
    Returns the sheet image + list of (x, y) for each slice in input order."""
    if not slices:
        raise ValueError("nothing to pack")
    n = len(slices)
    cw, ch = slices[0].size
    cols = math.ceil(math.sqrt(n))
    rows = math.ceil(n / cols)
    sheet = Image.new("RGBA", (cols * cw, rows * ch), (0, 0, 0, 0))
    coords: list[tuple[int, int]] = []
    for i, img in enumerate(slices):
        col = i % cols
        row = i // cols
        x, y = col * cw, row * ch
        sheet.paste(img, (x, y))
        coords.append((x, y))
    return sheet, coords


def reverse_ddscoords(tree_json: dict) -> dict[str, dict[int, str]]:
    """Build {atlas_filename: {1-indexed-slice: spriteName}} from tree.json."""
    out: dict[str, dict[int, str]] = {}
    for atlas, sprites in tree_json.get("ddsCoords", {}).items():
        out[atlas] = {idx: name for name, idx in sprites.items()}
    return out


def main() -> int:
    if not POB_TREE_DIR.exists():
        print(f"PoB folder not found: {POB_TREE_DIR}", file=sys.stderr)
        return 1
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    tree_src = POB_TREE_DIR / "tree.json"
    with tree_src.open() as f:
        tree = json.load(f)
    rev_coords = reverse_ddscoords(tree)

    zst_files = sorted(POB_TREE_DIR.glob("*.dds.zst"))
    print(f"Converting {len(zst_files)} atlases from {POB_TREE_DIR}\n")

    # manifest: {spriteName: {sheet: 'name.webp', x, y, w, h}}
    manifest: dict[str, dict] = {}
    sheets_written = 0

    for zst in zst_files:
        raw = zst.read_bytes()
        dds = zstandard.ZstdDecompressor().decompress(raw)
        try:
            w, h, arr, slices = extract_slices(dds)
        except Exception as e:
            print(f"  {zst.name:<55} FAILED: {e}")
            continue

        sprite_for_idx = rev_coords.get(zst.name, {})
        base = zst.name.replace(".dds.zst", "")

        if arr == 1:
            # ── Single image — save as-is ──────────────────────────────
            out_path = OUT_DIR / f"{base}.webp"
            slices[0].save(out_path, "WEBP", quality=92, method=6)
            sheets_written += 1
            # Register every name that maps to this atlas (typically 1 name)
            for idx, name in sprite_for_idx.items():
                manifest[name] = {"sheet": out_path.name, "x": 0, "y": 0, "w": w, "h": h}
            print(f"  {zst.name:<55} {w:>4}x{h:<4} arr=1   -> {out_path.name}")

        elif zst.name in INDIVIDUAL_OUTPUT:
            # ── Many large slices — one WebP per slice ─────────────────
            sub_dir = OUT_DIR.parent / INDIVIDUAL_OUTPUT[zst.name]
            sub_dir.mkdir(parents=True, exist_ok=True)
            for i, img in enumerate(slices, start=1):
                name = sprite_for_idx.get(i)
                if not name:
                    continue
                display = name.removeprefix("Classes").strip()
                fname = _slug(display) + ".webp"
                # Trim transparent borders to actual content
                bbox = img.getbbox()
                cropped = img.crop(bbox) if bbox else img
                cropped.save(sub_dir / fname, "WEBP", quality=92, method=6)
            print(f"  {zst.name:<55} {w:>4}x{h:<4} arr={arr:<3} -> {INDIVIDUAL_OUTPUT[zst.name]}/ ({arr} files)")

        else:
            # ── Many small slices — pack into a sprite sheet ───────────
            sheet, coords = pack_sheet(slices)
            out_path = OUT_DIR / f"{base}.webp"
            sheet.save(out_path, "WEBP", quality=92, method=6)
            sheets_written += 1
            # Register each slice's manifest entry — use 1-indexed slice → name
            for i, (sx, sy) in enumerate(coords, start=1):
                name = sprite_for_idx.get(i)
                if not name:
                    continue
                manifest[name] = {"sheet": out_path.name, "x": sx, "y": sy, "w": w, "h": h}
            print(f"  {zst.name:<55} {w:>4}x{h:<4} arr={arr:<3} -> {out_path.name} ({sheet.size[0]}x{sheet.size[1]})")

    # Write manifest
    manifest_path = OUT_DIR / "manifest.json"
    with manifest_path.open("w", encoding="utf-8") as f:
        json.dump(manifest, f, separators=(",", ":"))
    print(f"\nmanifest: {manifest_path}  ({len(manifest):,} sprites)")
    print(f"sheets written: {sheets_written}")
    return 0


def _slug(name: str) -> str:
    """Lowercase + non-alphanum→dash + collapse + trim."""
    import re
    s = name.lower().replace("'", "").replace("’", "")
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = re.sub(r"-+", "-", s)
    return s.strip("-")


if __name__ == "__main__":
    sys.exit(main())
