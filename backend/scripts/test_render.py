"""
Quick test: render a small section of the passive tree to a PNG.
Uses Pillow to simulate what the canvas renderer will do.
Run from backend/ directory.
"""
import json, math, os
from PIL import Image, ImageDraw

FRONTEND = os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "public")
TREE_JSON = os.path.join(FRONTEND, "tree_nodes.json")
ATLAS_PNG = os.path.join(FRONTEND, "tree-assets", "skills_64.png")
ORBIT_DIR = os.path.join(FRONTEND, "tree-assets", "orbit")
OUT_PNG   = os.path.join(os.path.dirname(__file__), "test_render.png")

# ── load data ─────────────────────────────────────────────────────────
with open(TREE_JSON, encoding="utf-8") as f:
    data = json.load(f)

nodes      = {n["id"]: n for n in data["nodes"]}
groups     = data["groups"]
orbit_radii = data["orbitRadii"]
orbit_map  = data["orbitMap"]   # "1" -> "Character_orbit_normal9.png"

# Pick a small region: Witch class anchor area (node 54447)
ANCHOR_ID = 54447
anchor    = nodes.get(ANCHOR_ID)
if not anchor:
    print("Anchor not found"); exit(1)

CENTER_X, CENTER_Y = anchor["x"], anchor["y"]
REGION_RADIUS = 2500   # tree-units radius around anchor

# Filter nodes within region
region_nodes = [n for n in data["nodes"]
                if abs(n["x"] - CENTER_X) < REGION_RADIUS
                and abs(n["y"] - CENTER_Y) < REGION_RADIUS]
print(f"Region nodes: {len(region_nodes)}")

# Fake "selected" = all notable/keystone nodes in region
selected_ids = {n["id"] for n in region_nodes if n["isNotable"] or n["isKeystone"]}
print(f"Selected (notable/keystone): {len(selected_ids)}")

# ── canvas setup ──────────────────────────────────────────────────────
W, H = 1200, 900
img  = Image.new("RGBA", (W, H), (7, 7, 16, 255))
draw = ImageDraw.Draw(img)

# Camera: fit region
xs = [n["x"] for n in region_nodes]
ys = [n["y"] for n in region_nodes]
camMinX, camMaxX = min(xs) - 200, max(xs) + 200
camMinY, camMaxY = min(ys) - 200, max(ys) + 200
scaleX = W / (camMaxX - camMinX)
scaleY = H / (camMaxY - camMinY)
scale  = min(scaleX, scaleY)
offX   = (W - (camMaxX - camMinX) * scale) / 2 - camMinX * scale
offY   = (H - (camMaxY - camMinY) * scale) / 2 - camMinY * scale

def tc(x, y):
    return x * scale + offX, y * scale + offY

BASE_R = 5

# ── orbit rings ───────────────────────────────────────────────────────
orbit_imgs: dict[int, Image.Image] = {}
for idx_str, fname in orbit_map.items():
    path = os.path.join(ORBIT_DIR, fname)
    if os.path.exists(path):
        orbit_imgs[int(idx_str)] = Image.open(path).convert("RGBA")

groups_in_region = set(str(n["group"]) for n in region_nodes)

for gid, g in groups.items():
    if gid not in groups_in_region:
        continue
    gcx, gcy = tc(g["x"], g["y"])
    for orbit_idx in g["orbits"]:
        if orbit_idx <= 0 or orbit_idx > 9:
            continue
        radius = orbit_radii[orbit_idx] if orbit_idx < len(orbit_radii) else 0
        if not radius:
            continue
        draw_size = int(2 * radius * scale)
        if draw_size < 3:
            continue
        ring = orbit_imgs.get(orbit_idx)
        if ring:
            scaled = ring.resize((draw_size, draw_size), Image.LANCZOS)
            px = int(gcx - draw_size / 2)
            py = int(gcy - draw_size / 2)
            # Paste with alpha, dim unselected rings
            ring_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            ring_layer.paste(scaled, (px, py), scaled)
            # Blend at 55% opacity
            blended = Image.blend(Image.new("RGBA", (W, H), (0,0,0,0)), ring_layer, 0.55)
            img = Image.alpha_composite(img, blended)

draw = ImageDraw.Draw(img)

# ── connections ───────────────────────────────────────────────────────
region_ids = {n["id"] for n in region_nodes}
for node in region_nodes:
    cx1, cy1 = tc(node["x"], node["y"])
    for conn_id in node["connections"]:
        if conn_id not in region_ids or conn_id <= node["id"]:
            continue
        n2 = nodes[conn_id]
        cx2, cy2 = tc(n2["x"], n2["y"])
        both_sel = node["id"] in selected_ids and conn_id in selected_ids
        color = (200, 155, 60, 220) if both_sel else (40, 40, 55, 150)
        draw.line([(cx1, cy1), (cx2, cy2)], fill=color, width=2 if both_sel else 1)

# ── node icons ────────────────────────────────────────────────────────
atlas = Image.open(ATLAS_PNG).convert("RGBA")

for node in region_nodes:
    cx, cy = tc(node["x"], node["y"])
    mult = 2.5 if node["isKeystone"] else 1.5 if node["isNotable"] else 1
    r    = int(BASE_R * mult * 2)  # *2 for higher res render
    isSel = node["id"] in selected_ids

    if node["iconX"] >= 0:
        # Crop from atlas
        icon = atlas.crop((node["iconX"], node["iconY"], node["iconX"]+64, node["iconY"]+64))
        icon = icon.resize((r*2, r*2), Image.LANCZOS)
        if not isSel:
            # Dim unselected
            dimmed = icon.copy()
            r_ch, g_ch, b_ch, a_ch = dimmed.split()
            a_ch = a_ch.point(lambda p: int(p * 0.45))
            dimmed = Image.merge("RGBA", (r_ch, g_ch, b_ch, a_ch))
            icon = dimmed
        else:
            # Gold tint overlay for selected
            gold = Image.new("RGBA", icon.size, (200, 155, 60, 60))
            icon = Image.alpha_composite(icon, gold)

        icon_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        icon_layer.paste(icon, (int(cx) - r, int(cy) - r), icon)
        img = Image.alpha_composite(img, icon_layer)

        # Gold ring for selected notables/keystones
        if isSel and (node["isNotable"] or node["isKeystone"]):
            draw = ImageDraw.Draw(img)
            draw.ellipse(
                [int(cx)-r-3, int(cy)-r-3, int(cx)+r+3, int(cy)+r+3],
                outline=(255, 215, 0, 200),
                width=2
            )
    else:
        # Fallback circle
        color = (200, 155, 60, 255) if isSel else (60, 60, 80, 180)
        draw = ImageDraw.Draw(img)
        draw.ellipse([int(cx)-r, int(cy)-r, int(cx)+r, int(cy)+r], fill=color)

img = img.convert("RGB")
img.save(OUT_PNG, "PNG")
print(f"Saved -> {OUT_PNG}")
