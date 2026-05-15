"""
Run once to generate static data files from the PoB 0_4 tree.json:
  - frontend/public/tree_nodes.json      (node data + icon atlas coords + orbit map + groups)
  - frontend/public/tree-assets/skills_64.png   (16-col sprite atlas, 64x64 icons)
  - frontend/public/tree-assets/orbit/   (orbit ring PNGs copied from PoB)
  - backend/data/tree_name_lookup.json   (name -> [node_id, ...])
  - backend/data/class_nodes.json        (ascendancy/class -> [node_names])

Usage: python scripts/preprocess_tree.py  (from backend/ directory)
Requires: pip install zstandard Pillow
"""

import json
import math
import os
import shutil
import struct
import io
from collections import deque

import zstandard
from PIL import Image

# ── paths ─────────────────────────────────────────────────────────────
POB_DIR       = r"C:\Users\marcu\AppData\Roaming\Path of Building Community (PoE2)\TreeData\0_4"
POB_TREE_PATH = os.path.join(POB_DIR, "tree.json")

SCRIPT_DIR    = os.path.dirname(__file__)
BACKEND_DIR   = os.path.join(SCRIPT_DIR, "..")
FRONTEND_DIR  = os.path.join(SCRIPT_DIR, "..", "..", "frontend")

FRONTEND_OUT  = os.path.join(FRONTEND_DIR, "public", "tree_nodes.json")
ASSETS_DIR    = os.path.join(FRONTEND_DIR, "public", "tree-assets")
ORBIT_DIR     = os.path.join(ASSETS_DIR, "orbit")
ATLAS_OUT     = os.path.join(ASSETS_DIR, "skills_64.png")
NAMES_OUT     = os.path.join(BACKEND_DIR, "data", "tree_name_lookup.json")
CLASS_OUT     = os.path.join(BACKEND_DIR, "data", "class_nodes.json")

for path in [FRONTEND_OUT, ATLAS_OUT, NAMES_OUT, CLASS_OUT]:
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
os.makedirs(ORBIT_DIR, exist_ok=True)

# ── load tree.json ─────────────────────────────────────────────────────
print("Loading tree.json ...")
with open(POB_TREE_PATH, encoding="utf-8") as f:
    tree = json.load(f)

orbit_radii  = tree["constants"]["orbitRadii"]
orbit_angles = tree["constants"]["orbitAnglesByOrbit"]
groups_raw   = tree["groups"]
nodes_raw    = tree["nodes"]
assets_raw   = tree.get("assets", {})
dds_coords   = tree.get("ddsCoords", {})
icon_layer_map: dict[str, int] = dds_coords.get("skills_64_64_BC1.dds.zst", {})

# ── orbit ring asset map: orbit_index → PNG filename ──────────────────
# assets field has "CharacterOrbitNNormal" -> "Character_orbit_normalX.png"
orbit_normal_map: dict[int, str] = {}
orbit_active_map: dict[int, str] = {}
for key, fval in assets_raw.items():
    fname = fval[0] if isinstance(fval, list) else fval
    if key.startswith("CharacterOrbit") and not key.startswith("CharacterOrbitLine") \
       and not key.startswith("CharacterOrbitActive") \
       and "Ascendancy" not in key and "Planned" not in key:
        if key.endswith("Normal"):
            try:
                idx = int(key[len("CharacterOrbit"):-len("Normal")])
                orbit_normal_map[idx] = fname
            except ValueError:
                pass
        elif key.endswith("Active"):
            try:
                idx = int(key[len("CharacterOrbit"):-len("Active")])
                orbit_active_map[idx] = fname
            except ValueError:
                pass

print(f"Orbit normal map: {orbit_normal_map}")

# ── copy orbit ring PNGs ───────────────────────────────────────────────
print("Copying orbit ring PNGs ...")
copied = 0
for fname in set(list(orbit_normal_map.values()) + list(orbit_active_map.values())):
    src = os.path.join(POB_DIR, fname)
    dst = os.path.join(ORBIT_DIR, fname)
    if os.path.exists(src):
        shutil.copy2(src, dst)
        copied += 1
print(f"  Copied {copied} orbit PNGs to {ORBIT_DIR}")

# ── DX10 BC1 layer extraction ──────────────────────────────────────────
def make_dxt1_dds_header(width: int, height: int) -> bytes:
    """Build a standard 128-byte DDS header for a DXT1 (BC1) texture."""
    magic = b"DDS "
    # DDS_PIXELFORMAT (32 bytes)
    pf = struct.pack("<II4sIIIII",
        32,        # pfSize
        4,         # pfFlags = DDPF_FOURCC
        b"DXT1",   # pfFourCC
        0, 0, 0, 0, 0,  # rgb/a bit counts/masks
    )
    top_mip_linear = max(1, (width + 3) // 4) * max(1, (height + 3) // 4) * 8
    # DDS_HEADER (124 bytes)
    header = struct.pack("<II", 124, 0x00001007)  # dwSize, dwFlags (CAPS|HEIGHT|WIDTH|PF|LINEARSIZE)
    header += struct.pack("<IIII", height, width, top_mip_linear, 0)  # H, W, pitchOrLinearSize, depth
    header += struct.pack("<I", 0)      # mipMapCount
    header += b"\x00" * 44             # reserved1[11]
    header += pf
    header += struct.pack("<IIIII", 0x00001000, 0, 0, 0, 0)  # caps, caps2, caps3, caps4, reserved2
    return magic + header  # 4 + 124 = 128 bytes


def extract_bc1_atlas(dds_zst_path: str, num_layers: int, layer_w: int, layer_h: int) -> list[Image.Image]:
    """Decompress a DX10 BC1 texture array and return each layer as a PIL Image."""
    print(f"Decompressing {os.path.basename(dds_zst_path)} ...")
    with open(dds_zst_path, "rb") as f:
        data = zstandard.ZstdDecompressor().decompress(f.read())

    # Verify magic
    assert data[:4] == b"DDS ", "Not a DDS file"
    actual_array_size = struct.unpack_from("<I", data, 140)[0]
    print(f"  DX10 array_size={actual_array_size}, using num_layers={num_layers}")

    mips  = max(1, struct.unpack_from("<I", data, 28)[0])
    # Compute layer byte size from mip chain
    layer_size = 0
    mw, mh = layer_w, layer_h
    for _ in range(mips):
        layer_size += max(1, (mw + 3) // 4) * max(1, (mh + 3) // 4) * 8
        mw = max(1, mw // 2)
        mh = max(1, mh // 2)
    print(f"  mips={mips}, layer_size={layer_size} bytes")

    top_mip_bytes = max(1, (layer_w + 3) // 4) * max(1, (layer_h + 3) // 4) * 8
    dxt1_header   = make_dxt1_dds_header(layer_w, layer_h)
    images: list[Image.Image] = []
    for n in range(num_layers):
        offset = 148 + n * layer_size
        mip0   = data[offset : offset + top_mip_bytes]
        img    = Image.open(io.BytesIO(dxt1_header + mip0))
        img.load()
        images.append(img.convert("RGBA"))
    print(f"  Extracted {len(images)} layers")
    return images


ATLAS_COLS = 16

print("\nBuilding 64×64 sprite atlas ...")
skills64_path = os.path.join(POB_DIR, "skills_64_64_BC1.dds.zst")
icon_images   = extract_bc1_atlas(skills64_path, num_layers=165, layer_w=64, layer_h=64)

atlas_rows  = math.ceil(len(icon_images) / ATLAS_COLS)
atlas_w     = ATLAS_COLS * 64
atlas_h     = atlas_rows * 64
atlas       = Image.new("RGBA", (atlas_w, atlas_h), (0, 0, 0, 0))

for i, img in enumerate(icon_images):
    col = i % ATLAS_COLS
    row = i // ATLAS_COLS
    atlas.paste(img, (col * 64, row * 64))

atlas.save(ATLAS_OUT, "PNG")
print(f"Saved atlas {atlas_w}x{atlas_h} -> {ATLAS_OUT}")

# groups_raw may be a list (indexed by int) or dict (keyed by str)
def _get_group(group_idx):
    if isinstance(groups_raw, list):
        return groups_raw[group_idx] if 0 <= group_idx < len(groups_raw) else None
    return groups_raw.get(str(group_idx)) or groups_raw.get(group_idx)


# ── node position formula ──────────────────────────────────────────────
def node_position(node: dict) -> tuple[float, float]:
    group_idx = node.get("group")
    if group_idx is None:
        return 0.0, 0.0
    g = _get_group(group_idx)
    if g is None or g.get("x") is None or g.get("y") is None:
        return 0.0, 0.0
    orbit       = node.get("orbit", 0)
    orbit_index = node.get("orbitIndex", 0)
    radius      = orbit_radii[orbit] if orbit < len(orbit_radii) else 0
    if radius == 0:
        return float(g["x"]), float(g["y"])
    angle_list = orbit_angles[orbit] if orbit < len(orbit_angles) else [0.0]
    angle = float(angle_list[orbit_index]) if orbit_index < len(angle_list) else 0.0
    return float(g["x"]) + radius * math.sin(angle), float(g["y"]) - radius * math.cos(angle)


# ── stat → color hint ──────────────────────────────────────────────────
def color_hint(stats: list[str]) -> str:
    text = " ".join(stats).lower()
    if "maximum life" in text or "increased life" in text:
        return "life"
    if "mana" in text:
        return "mana"
    if "lightning" in text:
        return "lightning"
    if "fire" in text:
        return "fire"
    if "cold" in text or "freeze" in text or "chill" in text:
        return "cold"
    if "chaos" in text:
        return "chaos"
    if "critical" in text:
        return "crit"
    if "spell" in text or "intelligence" in text:
        return "int"
    if "strength" in text or "melee" in text or "physical damage" in text:
        return "str"
    if "dexterity" in text or "evasion" in text or "bow" in text or "projectile" in text:
        return "dex"
    return "default"


# ── build node list + lookups ──────────────────────────────────────────
print("\nBuilding node list ...")
nodes_out:   list[dict]           = []
name_lookup: dict[str, list[int]] = {}
id_to_node:  dict[int, dict]      = {}

for node_id_str, node in nodes_raw.items():
    x, y   = node_position(node)
    conns  = [c["id"] for c in node.get("connections", []) if isinstance(c, dict)]
    icon   = node.get("icon", "")
    layer  = icon_layer_map.get(icon, 0)          # 1-indexed; 0 = no icon
    col    = (layer - 1) % ATLAS_COLS if layer > 0 else -1
    row    = (layer - 1) // ATLAS_COLS if layer > 0 else -1

    orbit  = node.get("orbit", 0)
    grp    = node.get("group")

    entry = {
        "id":        node["skill"],
        "name":      node.get("name", ""),
        "x":         round(x, 1),
        "y":         round(y, 1),
        "connections": conns,
        "isNotable": bool(node.get("isNotable", False)),
        "isKeystone": bool(node.get("isKeystone", False)),
        "stats":     node.get("stats", []),
        "color":     color_hint(node.get("stats", [])),
        "iconX":     col * 64 if col >= 0 else -1,
        "iconY":     row * 64 if row >= 0 else -1,
        "orbit":     orbit,
        "group":     grp,
    }
    nodes_out.append(entry)
    id_to_node[node["skill"]] = entry

    name = node.get("name", "").strip()
    if name:
        key = name.lower()
        name_lookup.setdefault(key, [])
        if node["skill"] not in name_lookup[key]:
            name_lookup[key].append(node["skill"])

print(f"  {len(nodes_out)} nodes, {len(name_lookup)} unique names")

# ── groups data (centres for orbit ring rendering) ─────────────────────
groups_out: dict[str, dict] = {}
if isinstance(groups_raw, list):
    for gid, g in enumerate(groups_raw):
        if g and g.get("x") is not None and g.get("y") is not None:
            orbits_used = [o for o in (g.get("orbits") or []) if o > 0]
            groups_out[str(gid)] = {
                "x":      round(float(g["x"]), 1),
                "y":      round(float(g["y"]), 1),
                "orbits": orbits_used,
            }
else:
    for gid, g in groups_raw.items():
        if g and g.get("x") is not None and g.get("y") is not None:
            orbits_used = [o for o in (g.get("orbits") or []) if o > 0]
            groups_out[str(gid)] = {
                "x":      round(float(g["x"]), 1),
                "y":      round(float(g["y"]), 1),
                "orbits": orbits_used,
            }

# ── class zone BFS ─────────────────────────────────────────────────────
ANCHOR_IDS = {
    "Witch":              54447,
    "Blood Mage":         59822,
    "Infernalist":        32699,
    "Lich":               None,
    "Abyssal Lich":       None,
    "Sorceress":          None,
    "Stormweaver":        40721,
    "Chronomancer":       22147,
    "Ranger":             50459,
    "Deadeye":            46990,
    "Pathfinder":         1583,
    "Huntress":           None,
    "Amazon":             41736,
    "Ritualist":          36365,
    "Warrior":            None,
    "Titan":              32534,
    "Warbringer":         None,
    "Smith of Kitava":    5852,
    "Mercenary":          None,
    "Tactician":          36252,
    "Witchhunter":        7120,
    "Gemling Legionnaire": None,
    "Monk":               None,
    "Acolyte of Chayula": 74,
    "Invoker":            None,
}

adj: dict[int, list[int]] = {}
for node in nodes_out:
    nid = node["id"]
    adj[nid] = node["connections"][:]
    for c in node["connections"]:
        adj.setdefault(c, [])
        if nid not in adj[c]:
            adj[c].append(nid)


def bfs_nodes(start_id: int, max_hops: int = 25) -> list[str]:
    if start_id not in id_to_node:
        return []
    visited = {start_id}
    queue   = deque([(start_id, 0)])
    names: set[str] = set()
    while queue:
        nid, hops = queue.popleft()
        name = id_to_node[nid]["name"]
        if name:
            names.add(name)
        if hops < max_hops:
            for nb in adj.get(nid, []):
                if nb not in visited and nb in id_to_node:
                    visited.add(nb)
                    queue.append((nb, hops + 1))
    return sorted(names)


class_nodes: dict[str, list[str]] = {}
for zone, anchor_id in ANCHOR_IDS.items():
    class_nodes[zone] = bfs_nodes(anchor_id, 25) if anchor_id else []
    print(f"  {zone}: {len(class_nodes[zone])} nodes")

# ── bounds ─────────────────────────────────────────────────────────────
xs     = [n["x"] for n in nodes_out]
ys     = [n["y"] for n in nodes_out]
bounds = {
    "minX": round(min(xs), 1), "maxX": round(max(xs), 1),
    "minY": round(min(ys), 1), "maxY": round(max(ys), 1),
}

# ── write outputs ──────────────────────────────────────────────────────
print("\nWriting outputs ...")

tree_json_out = {
    "nodes":      nodes_out,
    "bounds":     bounds,
    "groups":     groups_out,
    "orbitRadii": orbit_radii,
    "orbitMap":   {str(k): v for k, v in orbit_normal_map.items()},
    "orbitMapActive": {str(k): v for k, v in orbit_active_map.items()},
}
with open(os.path.abspath(FRONTEND_OUT), "w", encoding="utf-8") as f:
    json.dump(tree_json_out, f, separators=(",", ":"))
print(f"  tree_nodes.json ({len(nodes_out)} nodes)")

with open(os.path.abspath(NAMES_OUT), "w", encoding="utf-8") as f:
    json.dump(name_lookup, f, separators=(",", ":"))
print(f"  tree_name_lookup.json ({len(name_lookup)} names)")

with open(os.path.abspath(CLASS_OUT), "w", encoding="utf-8") as f:
    json.dump(class_nodes, f, indent=2)
print("  class_nodes.json")

print(f"\nDone. Processed {len(nodes_out)} nodes, bounds: {bounds}")
