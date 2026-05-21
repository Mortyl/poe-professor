"use client";

import { useEffect, useRef, useState } from "react";

const ORBIT_RADII      = [0, 82, 162, 335, 493, 662, 846, 251, 1080, 1332];
const SKILLS_PER_ORBIT = [1, 12, 24, 24, 72, 72, 72, 24, 72, 144];

// Screen-space hit radius in canvas pixels
const HIT_RADIUS = 10;

interface RawGroup { X: number; Y: number; Nodes: number[]; }
interface NodeOverride {
  Name?: string;
  Type?: number;
  Stats?: Record<string, number>;
}
interface RawNode {
  Group: number;
  Orbit: number;
  OrbitIndex: number;
  Type: number;
  Name: string;
  Ascendancy?: string;
  Stats?: Record<string, number>;
  Connections: Record<string, number>;
  Override?: Record<string, NodeOverride>;
}
interface RawData {
  Groups: RawGroup[];
  Nodes: Record<string, RawNode>;
}

interface NodeData {
  id: number;
  x: number;
  y: number;
  ascendancy: string | undefined;
  name: string;
  stats: Record<string, number>;
  type: number;
}
interface Line { x1: number; y1: number; x2: number; y2: number; n1: number; n2: number; }
interface Arc  { cx: number; cy: number; r: number; sa: number; ea: number; n1: number; n2: number; }
interface Bounds { minX: number; minY: number; maxX: number; maxY: number; }
interface DrawData { nodes: NodeData[]; lines: Line[]; arcs: Arc[]; bounds: Bounds; }

interface Tooltip { cx: number; cy: number; id: number; name: string; stats: Record<string, number>; type: number; }

// Maps display ascendancy names → internal tree keys used in SkillTreeCore.json
const ASCENDANCY_KEY: Record<string, string> = {
  // Ranger
  "Deadeye":              "Ranger1",
  "Pathfinder":           "Ranger3",
  // Witch
  "Infernalist":          "Witch1",
  "Blood Mage":           "Witch2",
  "Lich":                 "Witch3",
  // Warrior
  "Titan":                "Warrior1",
  "Warbringer":           "Warrior2",
  // Huntress
  "Amazon":               "Huntress1",
  "Spirit Walker":        "Huntress3",
  // Sorceress
  "Stormweaver":          "Sorceress1",
  "Chronomancer":         "Sorceress2",
  "Disciple of Varashta": "Sorceress3",
  // Monk
  "Invoker":              "Monk2",
  "Acolyte of Chayula":   "Monk3",
  // Mercenary
  "Tactician":            "Mercenary1",
  "Witchhunter":          "Mercenary2",
  "Gemling Legionnaire":  "Mercenary3",
  // Druid
  "Oracle":               "Druid1",
  "Shaman":               "Druid2",
};

const cache = new Map<string, DrawData>();
let fetchPromise: Promise<unknown> | null = null;
let rawData: RawData | null = null;

// ── PoB sprite assets ────────────────────────────────────────────────────────
// Loaded lazily on first canvas mount, then shared across instances.
interface SpriteCoord { sheet: string; x: number; y: number; w: number; h: number; }
interface PobNode { icon?: string; isAscendancyStart?: boolean; }
interface PobTree { nodes: Record<string, PobNode>; }

let spriteManifest: Record<string, SpriteCoord> | null = null;
let nodeIconMap:    Map<number, string> | null         = null;   // nodeId → icon path (manifest key)
let ascStartSet:    Set<number> | null                 = null;   // ids of every ascendancy entry node
let bgImage:        HTMLImageElement | null            = null;
const sheetImages = new Map<string, HTMLImageElement>();         // sheet filename → loaded <img>
let assetsPromise: Promise<void> | null = null;

function loadImage(src: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload  = () => resolve(img);
    img.onerror = () => reject(new Error(`failed to load ${src}`));
    img.src = src;
  });
}

function ensureSheet(name: string): HTMLImageElement | null {
  const cached = sheetImages.get(name);
  if (cached) return cached;
  // Kick off load; subsequent draws will pick it up once it lands.
  loadImage(`/images/tree/${name}`).then(img => {
    sheetImages.set(name, img);
  }).catch(() => {
    // Mark as failed to avoid retry storms — store a 1x1 transparent placeholder
    const placeholder = document.createElement("canvas") as unknown as HTMLImageElement;
    sheetImages.set(name, placeholder);
  });
  return null;
}

function loadTreeAssets(): Promise<void> {
  if (assetsPromise) return assetsPromise;
  assetsPromise = (async () => {
    const [manifestRes, treeRes, bg] = await Promise.all([
      fetch("/images/tree/manifest.json").then(r => r.json()) as Promise<Record<string, SpriteCoord>>,
      fetch("/images/tree/tree.json").then(r => r.json())     as Promise<PobTree>,
      loadImage("/images/tree/background_1024_1024_BC7.webp").catch(() => null),
    ]);
    spriteManifest = manifestRes;
    nodeIconMap = new Map();
    ascStartSet = new Set();
    for (const [idStr, n] of Object.entries(treeRes.nodes)) {
      const id = parseInt(idStr, 10);
      if (n.icon) nodeIconMap.set(id, n.icon);
      if (n.isAscendancyStart) ascStartSet.add(id);
    }
    bgImage = bg ?? null;
    // Preload sheets used by the first frame: node icon atlases + frame atlases.
    // Lazy-load anything else (group rings, jewel sockets) on demand via ensureSheet.
    const FIRST_FRAME_SHEETS = [
      "skills_128_128_BC1.webp",      // notable + keystone icons
      "skills_64_64_BC1.webp",        // small/travel node icons
      "group-background_104_104_BC7.webp",  // Normal-node frames (PSSkillFrame*)
      "group-background_152_156_BC7.webp",  // Notable + Jewel frames
      "group-background_220_224_BC7.webp",  // Keystone frames
      "group-background_160_164_BC7.webp",  // Ascendancy small frames ({Asc}FrameSmall*)
      "group-background_208_208_BC7.webp",  // Ascendancy large frames ({Asc}FrameLarge*)
      "group-background_528_528_BC7.webp",  // PSStartNodeBackgroundInactive (asc entry node)
    ];
    await Promise.all(FIRST_FRAME_SHEETS.map(name =>
      loadImage(`/images/tree/${name}`)
        .then(img => sheetImages.set(name, img))
        .catch(() => undefined)
    ));
  })();
  return assetsPromise;
}

function formatStat(key: string, val: number): string {
  const isPct    = key.endsWith("_+%") || key.endsWith("+%");
  const isFlatPct = !isPct && key.endsWith("_%");
  let name = key.replace(/_\+%$/, "").replace(/_%$/, "").replace(/_/g, " ");
  name = name.replace(/\b\w/g, c => c.toUpperCase());
  if (isPct)     return `${val}% increased ${name}`;
  if (isFlatPct) return `${val}% ${name}`;
  return val > 0 ? `+${val} ${name}` : `${val} ${name}`;
}

function parseData(data: RawData, className?: string): DrawData {
  const nodeMap = new Map<number, NodeData>();
  const nodes: NodeData[] = [];

  for (const [idStr, node] of Object.entries(data.Nodes)) {
    const id = parseInt(idStr, 10);
    if (node.Type === 4) continue; // Mastery — non-allocatable
    const g = data.Groups[node.Group];
    if (!g) continue;
    const r     = ORBIT_RADII[node.Orbit] ?? 0;
    const total = SKILLS_PER_ORBIT[node.Orbit] ?? 1;
    const angle = (node.OrbitIndex / total) * 2 * Math.PI;

    // Apply class-specific override if present
    const override = className ? node.Override?.[className] : undefined;
    const nd: NodeData = {
      id,
      x:          g.X + r * Math.sin(angle),
      y:          g.Y - r * Math.cos(angle),
      ascendancy: node.Ascendancy,
      name:       override?.Name  ?? node.Name  ?? "",
      stats:      override?.Stats ?? node.Stats ?? {},
      type:       override?.Type  ?? node.Type,
    };
    nodeMap.set(id, nd);
    nodes.push(nd);
  }

  const seen  = new Set<string>();
  const lines: Line[] = [];
  const arcs:  Arc[]  = [];

  for (const [idStr, node] of Object.entries(data.Nodes)) {
    const aId = parseInt(idStr, 10);
    const a   = nodeMap.get(aId);
    if (!a) continue;

    for (const [bIdStr, connOrbit] of Object.entries(node.Connections ?? {})) {
      const bId = parseInt(bIdStr, 10);
      const b   = nodeMap.get(bId);
      if (!b) continue;
      if (a.ascendancy !== b.ascendancy) continue; // skip cross-boundary

      const key = aId < bId ? `${aId}-${bId}` : `${bId}-${aId}`;
      if (seen.has(key)) continue;
      seen.add(key);

      if (connOrbit === 0) {
        lines.push({ x1: a.x, y1: a.y, x2: b.x, y2: b.y, n1: aId, n2: bId });
        continue;
      }

      const r = ORBIT_RADII[Math.abs(connOrbit)];
      if (!r) { lines.push({ x1: a.x, y1: a.y, x2: b.x, y2: b.y, n1: aId, n2: bId }); continue; }

      const dx   = b.x - a.x;
      const dy   = b.y - a.y;
      const dist = Math.sqrt(dx * dx + dy * dy);
      if (dist === 0 || dist >= r * 2) continue;

      const perpLen = Math.sqrt(r * r - (dist * dist) / 4) * (connOrbit > 0 ? 1 : -1);
      const cx = a.x + dx / 2 + perpLen * (dy / dist);
      const cy = a.y + dy / 2 - perpLen * (dx / dist);

      let sa = Math.atan2(a.y - cy, a.x - cx);
      let ea = Math.atan2(b.y - cy, b.x - cx);
      if (sa > ea) { const t = sa; sa = ea; ea = t; }
      const span = ea - sa;
      if (span >= Math.PI) { const t = sa; sa = ea; ea = t; }

      arcs.push({ cx, cy, r, sa, ea, n1: aId, n2: bId });
    }
  }

  // Compute bounding box of main-tree nodes only (exclude ascendancy sub-trees)
  let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
  for (const n of nodes) {
    if (n.ascendancy) continue;
    if (n.x < minX) minX = n.x;
    if (n.y < minY) minY = n.y;
    if (n.x > maxX) maxX = n.x;
    if (n.y > maxY) maxY = n.y;
  }
  const bounds: Bounds = { minX, minY, maxX, maxY };

  return { nodes, lines, arcs, bounds };
}

function getData(className?: string): Promise<DrawData> {
  const key = className ?? "__default__";
  if (cache.has(key)) return Promise.resolve(cache.get(key)!);

  const doparse = (data: RawData): DrawData => {
    const parsed = parseData(data, className);
    cache.set(key, parsed);
    return parsed;
  };

  if (rawData) return Promise.resolve(doparse(rawData));

  if (!fetchPromise) {
    fetchPromise = fetch("/SkillTreeCore.json").then(r => r.json()).then((data: RawData) => { rawData = data; });
  }
  return (fetchPromise as Promise<void>).then(() => doparse(rawData!));
}

const NODE_STYLE: Record<number, { colour: string; r: number }> = {
  0: { colour: "#4a6080", r: 16 }, // Normal      — blue-grey
  1: { colour: "#c8a050", r: 26 }, // Notable     — gold
  2: { colour: "#cc3030", r: 38 }, // Keystone    — red
  3: { colour: "#40aa60", r: 28 }, // JewelSocket — green
};
// Frame size per node type (in world units) — the outer ring around each node.
// Sized to match PoB's in-game tree where notables are ~2× a normal node and
// keystones ~3×. Icons render at ~62% of frame size to sit inside the ring.
const FRAME_R: Record<number, number> = {
  0: 28,   // Normal — small ring
  1: 56,   // Notable — pronounced gold ring
  2: 88,   // Keystone — biggest ring
  3: 56,   // Jewel socket — same as notable
};
const ICON_FRACTION = 0.62;
const MIN_SCREEN_R = 2;
const MIN_FRAME_SCREEN = 6;

// Frame sprite names per node type + state, matching tree.json's nodeOverlay table.
// All these names exist in manifest.json under the group-background_* sheets.
type FrameState = "alloc" | "path" | "unalloc";
const FRAME_SPRITE: Record<number, Record<FrameState, string>> = {
  0: { alloc: "PSSkillFrameActive",         path: "PSSkillFrameHighlighted",       unalloc: "PSSkillFrame" },
  1: { alloc: "NotableFrameAllocated",      path: "NotableFrameCanAllocate",       unalloc: "NotableFrameUnallocated" },
  2: { alloc: "KeystoneFrameAllocated",     path: "KeystoneFrameCanAllocate",      unalloc: "KeystoneFrameUnallocated" },
  3: { alloc: "JewelFrameAllocated",        path: "JewelFrameCanAllocate",         unalloc: "JewelFrameUnallocated" },
};
const OPTIONAL_COLOUR = "#4ab8cc"; // teal-blue for optional nodes (node dots only)

export default function PassiveTreeCanvas({
  className,
  ascendancy,
  highlightedNodes = [],
  optionalNodes = [],
}: {
  className?: string;
  ascendancy?: string;
  highlightedNodes?: number[];
  optionalNodes?: number[];
} = {}) {
  const canvasRef   = useRef<HTMLCanvasElement>(null);
  const camRef      = useRef({ tx: 0, ty: 0, scale: 1 });
  const minScaleRef = useRef(0.008);
  const maxScaleRef = useRef(0.2);
  const dataRef     = useRef<DrawData | null>(null);
  const dragRef     = useRef<{ sx: number; sy: number; tx: number; ty: number } | null>(null);
  const highlightedSet = useRef<Set<number>>(new Set());
  const optionalSet    = useRef<Set<number>>(new Set());
  const [tooltip, setTooltip] = useState<Tooltip | null>(null);

  function draw() {
    const canvas = canvasRef.current;
    if (!canvas || !dataRef.current) return;
    const ctx = canvas.getContext("2d")!;
    const { tx, ty, scale } = camRef.current;
    const W = canvas.width;
    const H = canvas.height;
    const { nodes, lines, arcs } = dataRef.current;
    // Main tree only — exclude edges that touch ascendancy nodes
    const ascNodes = new Set(nodes.filter(n => n.ascendancy).map(n => n.id));
    const mainLines = lines.filter(l => !ascNodes.has(l.n1) && !ascNodes.has(l.n2));
    const mainArcs  = arcs.filter(a => !ascNodes.has(a.n1) && !ascNodes.has(a.n2));

    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.fillStyle = "#040608";
    ctx.fillRect(0, 0, W, H);

    ctx.setTransform(scale, 0, 0, scale, tx, ty);
    const inv = 1 / scale;

    // ── Tree background image — stretched to cover world bounds (with padding) ──
    if (bgImage && dataRef.current) {
      const b = dataRef.current.bounds;
      const cx = (b.minX + b.maxX) / 2;
      const cy = (b.minY + b.maxY) / 2;
      const treeW = b.maxX - b.minX;
      const treeH = b.maxY - b.minY;
      // The radial backdrop is one image — paint it large and centered, with
      // generous overflow so users can pan past the tree edges without seam.
      const bgSize = Math.max(treeW, treeH) * 1.4;
      ctx.drawImage(bgImage, cx - bgSize / 2, cy - bgSize / 2, bgSize, bgSize);
    }

    const core     = highlightedSet.current;
    const optional = optionalSet.current;

    const isCoreEdge     = (n1: number, n2: number) => core.has(n1) && core.has(n2);
    // Teal for optional–optional AND for the junction edge where one side is
    // core and the other is optional (visually connects teal path to gold tree).
    // Both endpoints must be highlighted — never draw teal to an unhighlighted node.
    const isHighlighted  = (n: number) => core.has(n) || optional.has(n);
    const isOptionalEdge = (n1: number, n2: number) =>
      isHighlighted(n1) && isHighlighted(n2) &&
      (optional.has(n1) || optional.has(n2)) &&
      !(core.has(n1) && core.has(n2));

    // 1. Dim edges (neither core nor optional)
    ctx.strokeStyle = "#1a2030";
    ctx.lineWidth   = inv;
    ctx.beginPath();
    for (const l of mainLines) {
      if (isCoreEdge(l.n1, l.n2) || isOptionalEdge(l.n1, l.n2)) continue;
      ctx.moveTo(l.x1, l.y1); ctx.lineTo(l.x2, l.y2);
    }
    ctx.stroke();
    ctx.beginPath();
    for (const a of mainArcs) {
      if (isCoreEdge(a.n1, a.n2) || isOptionalEdge(a.n1, a.n2)) continue;
      ctx.moveTo(a.cx + a.r * Math.cos(a.sa), a.cy + a.r * Math.sin(a.sa));
      ctx.arc(a.cx, a.cy, a.r, a.sa, a.ea, false);
    }
    ctx.stroke();

    // 2. Optional edges — teal
    ctx.strokeStyle = OPTIONAL_COLOUR;
    ctx.lineWidth   = inv * 2;
    ctx.beginPath();
    for (const l of mainLines) {
      if (!isOptionalEdge(l.n1, l.n2)) continue;
      ctx.moveTo(l.x1, l.y1); ctx.lineTo(l.x2, l.y2);
    }
    ctx.stroke();
    ctx.beginPath();
    for (const a of mainArcs) {
      if (!isOptionalEdge(a.n1, a.n2)) continue;
      ctx.moveTo(a.cx + a.r * Math.cos(a.sa), a.cy + a.r * Math.sin(a.sa));
      ctx.arc(a.cx, a.cy, a.r, a.sa, a.ea, false);
    }
    ctx.stroke();

    // 3. Core edges — gold (drawn last so they sit on top)
    ctx.strokeStyle = "#e8c84a";
    ctx.lineWidth   = inv * 2;
    ctx.beginPath();
    for (const l of mainLines) {
      if (!isCoreEdge(l.n1, l.n2)) continue;
      ctx.moveTo(l.x1, l.y1); ctx.lineTo(l.x2, l.y2);
    }
    ctx.stroke();
    ctx.beginPath();
    for (const a of mainArcs) {
      if (!isCoreEdge(a.n1, a.n2)) continue;
      ctx.moveTo(a.cx + a.r * Math.cos(a.sa), a.cy + a.r * Math.sin(a.sa));
      ctx.arc(a.cx, a.cy, a.r, a.sa, a.ea, false);
    }
    ctx.stroke();

    // 4. Nodes — frame ring + icon inside (PoB-style)
    //    Order: draw frames first so connecting lines don't poke into the
    //    centre of each node. Then icons on top of frames.
    for (const n of nodes) {
      if (n.ascendancy) continue;
      const isCore     = core.has(n.id);
      const isOptional = optional.has(n.id) && !isCore;
      const state: FrameState = isCore ? "alloc" : isOptional ? "path" : "unalloc";

      // Frame size in world units. Minimum on-screen size keeps the node legible
      // when zoomed far out (otherwise the frame collapses to a single pixel).
      const frameR = Math.max(
        (FRAME_R[n.type] ?? FRAME_R[0]) / 2,
        MIN_FRAME_SCREEN * inv,
      );
      const frameSize = frameR * 2;

      // 1. Icon FIRST — frame is drawn on top to cover any spillover at edges
      const iconPath = nodeIconMap?.get(n.id);
      const coord    = iconPath ? spriteManifest?.[iconPath] : undefined;
      const sheet    = coord ? sheetImages.get(coord.sheet) : undefined;
      if (coord && sheet && sheet.width > 1) {
        const iconSize = frameSize * ICON_FRACTION;
        ctx.globalAlpha = isCore ? 1.0 : isOptional ? 0.95 : 0.75;
        ctx.drawImage(
          sheet,
          coord.x, coord.y, coord.w, coord.h,
          n.x - iconSize / 2, n.y - iconSize / 2, iconSize, iconSize,
        );
        ctx.globalAlpha = 1.0;
      } else {
        // No icon? Tiny coloured dot in the centre so node is still distinguishable
        const style = NODE_STYLE[n.type] ?? NODE_STYLE[0];
        ctx.fillStyle = isCore ? "#e8c84a" : isOptional ? OPTIONAL_COLOUR : style.colour;
        ctx.beginPath();
        ctx.arc(n.x, n.y, Math.max(2 * inv, frameR * 0.25), 0, Math.PI * 2);
        ctx.fill();
        if (coord) ensureSheet(coord.sheet);
      }

      // Frame sprite overlay disabled on the main tree for now — keeping the
      // bare icon look. The ascendancy canvas still uses frames.
      // (Was: drawImage(FRAME_SPRITE[n.type]?.[state] ...) here.)

      // Optional path (teal) — overlay a subtle teal ring on top of the icon
      if (isOptional) {
        ctx.strokeStyle = OPTIONAL_COLOUR;
        ctx.lineWidth   = inv * 2;
        ctx.beginPath();
        ctx.arc(n.x, n.y, frameR * 0.9, 0, Math.PI * 2);
        ctx.stroke();
      }
    }
  }

  function hitTest(canvasPx: number, canvasPy: number): NodeData | null {
    const data = dataRef.current;
    if (!data) return null;
    const { tx, ty, scale } = camRef.current;
    const wx = (canvasPx - tx) / scale;
    const wy = (canvasPy - ty) / scale;
    const worldThresh = (HIT_RADIUS / scale) ** 2;
    let best: NodeData | null = null;
    let bestD = Infinity;
    for (const n of data.nodes) {
      const d = (n.x - wx) ** 2 + (n.y - wy) ** 2;
      if (d < worldThresh && d < bestD) { bestD = d; best = n; }
    }
    return best;
  }

  useEffect(() => {
    highlightedSet.current = new Set(highlightedNodes);
    if (dataRef.current) draw();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [highlightedNodes]);

  useEffect(() => {
    optionalSet.current = new Set(optionalNodes);
    if (dataRef.current) draw();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [optionalNodes]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const W = canvas.width;
    const H = canvas.height;

    // Set min scale synchronously so the wheel handler is locked before data arrives.
    // 44000 × 40000 is a conservative estimate of the main tree world extent.
    const approxScale = Math.min(W / 44000, H / 40000);
    minScaleRef.current = approxScale;
    camRef.current = { tx: W / 2, ty: H / 2, scale: approxScale };

    // Kick off PoB-asset preload in parallel with tree data fetch. Once it
    // resolves we redraw — the canvas swaps from flat circles to real sprites.
    loadTreeAssets().then(() => {
      if (dataRef.current) draw();
    });

    getData(className).then(d => {
      dataRef.current = d;
      const { minX, minY, maxX, maxY } = d.bounds;
      const treeW = maxX - minX;
      const treeH = maxY - minY;
      const fitScale = Math.min(W / treeW, H / treeH) * 0.95;
      maxScaleRef.current = fitScale * 2.5; // max zoom = 2.5× the fit-to-screen scale
      // minScale is set after startScale is computed below

      // Center on the bounding box of highlighted nodes if any exist,
      // and start zoomed in (2× fit) so the tree feels readable on first load.
      const allHighlighted = [...highlightedSet.current, ...optionalSet.current];
      const nodeById = new Map(d.nodes.map(n => [n.id, n]));
      const hNodes = allHighlighted
        .map(id => nodeById.get(id))
        .filter((n): n is NodeData => !!n && !n.ascendancy);

      let focusX: number, focusY: number, startScale: number;
      if (hNodes.length > 0) {
        const hMinX = Math.min(...hNodes.map(n => n.x));
        const hMaxX = Math.max(...hNodes.map(n => n.x));
        const hMinY = Math.min(...hNodes.map(n => n.y));
        const hMaxY = Math.max(...hNodes.map(n => n.y));
        focusX = (hMinX + hMaxX) / 2;
        focusY = (hMinY + hMaxY) / 2;
        const pad = 1800; // world-space padding around highlighted cluster
        const hFitScale = Math.min(
          W / (hMaxX - hMinX + pad * 2),
          H / (hMaxY - hMinY + pad * 2),
        );
        // Clamp: never zoom in past max, never zoom out past the full-tree fit
        startScale = Math.min(Math.max(hFitScale, fitScale), maxScaleRef.current);
      } else {
        focusX = (minX + maxX) / 2;
        focusY = (minY + maxY) / 2;
        startScale = fitScale * 2;  // start zoomed in 2× so nodes are readable
      }

      minScaleRef.current = startScale; // can't zoom out past the starting view
      camRef.current = {
        tx:    W / 2 - focusX * startScale,
        ty:    H / 2 - focusY * startScale,
        scale: startScale,
      };
      draw();
    });

    function onWheel(e: WheelEvent) {
      e.preventDefault();
      if (!canvas) return;
      const rect     = canvas.getBoundingClientRect();
      const mx       = (e.clientX - rect.left) * (canvas.width  / rect.width);
      const my       = (e.clientY - rect.top)  * (canvas.height / rect.height);
      const { tx, ty, scale } = camRef.current;
      const factor   = e.deltaY < 0 ? 1.15 : 1 / 1.15;
      const newScale = Math.max(minScaleRef.current, Math.min(maxScaleRef.current, scale * factor));
      const wx = (mx - tx) / scale;
      const wy = (my - ty) / scale;
      camRef.current = { tx: mx - wx * newScale, ty: my - wy * newScale, scale: newScale };
      draw();
    }
    canvas.addEventListener("wheel", onWheel, { passive: false });
    return () => canvas.removeEventListener("wheel", onWheel);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function onMouseDown(e: React.MouseEvent) {
    dragRef.current = { sx: e.clientX, sy: e.clientY, tx: camRef.current.tx, ty: camRef.current.ty };
    setTooltip(null);
  }

  function onMouseMove(e: React.MouseEvent) {
    if (dragRef.current) {
      camRef.current.tx = dragRef.current.tx + (e.clientX - dragRef.current.sx);
      camRef.current.ty = dragRef.current.ty + (e.clientY - dragRef.current.sy);
      draw();
      return;
    }

    // Hit-test for tooltip
    const canvas = canvasRef.current;
    if (!canvas) return;
    const rect  = canvas.getBoundingClientRect();
    const cpx   = (e.clientX - rect.left) * (canvas.width  / rect.width);
    const cpy   = (e.clientY - rect.top)  * (canvas.height / rect.height);
    const hit   = hitTest(cpx, cpy);
    if (hit) {
      setTooltip({ cx: e.clientX - rect.left, cy: e.clientY - rect.top, id: hit.id, name: hit.name, stats: hit.stats, type: hit.type });
    } else {
      setTooltip(null);
    }
  }

  function stopDrag() { dragRef.current = null; }

  const TYPE_LABEL: Record<number, string> = { 1: "Notable", 2: "Keystone", 3: "Jewel Socket" };

  return (
    <div style={{ position: "relative", display: "block" }}>
      <canvas
        ref={canvasRef}
        width={860}
        height={540}
        style={{ display: "block", width: "100%", height: "auto", cursor: dragRef.current ? "grabbing" : "grab", borderRadius: "4px", border: "1px solid #1a2030" }}
        onMouseDown={onMouseDown}
        onMouseMove={onMouseMove}
        onMouseUp={stopDrag}
        onMouseLeave={() => { stopDrag(); setTooltip(null); }}
      />

      {/* ascendancy prop reserved for future use */ ascendancy && null}
      {tooltip && (
        <div style={{
          position:        "absolute",
          left:            tooltip.cx + 14,
          top:             tooltip.cy - 8,
          pointerEvents:   "none",
          background:      "rgba(10,10,20,0.95)",
          border:          `1px solid ${NODE_STYLE[tooltip.type]?.colour ?? "#666688"}`,
          borderRadius:    "4px",
          padding:         "8px 12px",
          minWidth:        "160px",
          maxWidth:        "260px",
          zIndex:          10,
          fontFamily:      "monospace",
        }}>
          <div style={{ color: "#666", fontSize: "10px", marginBottom: "2px", fontFamily: "monospace" }}>
            #{tooltip.id}
          </div>
          <div style={{ color: NODE_STYLE[tooltip.type]?.colour ?? "#ffffff", fontWeight: "bold", marginBottom: "4px", fontSize: "13px" }}>
            {tooltip.name}
            {TYPE_LABEL[tooltip.type] && (
              <span style={{ color: "#888", fontWeight: "normal", marginLeft: "6px", fontSize: "11px" }}>
                {TYPE_LABEL[tooltip.type]}
              </span>
            )}
          </div>
          {Object.entries(tooltip.stats).map(([k, v]) => (
            <div key={k} style={{ color: "#c8c8d8", fontSize: "12px", lineHeight: "1.5" }}>
              {formatStat(k, v)}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ── Ascendancy-only canvas ────────────────────────────────────────────────────
// Tier colours for ascendancy paid nodes (groups of 2 by rank)
const ASC_TIER_COLOURS = [
  "#e8c84a", // tier 1 (rank 1–2) — gold
  "#4a9a5a", // tier 2 (rank 3–4) — green
  "#4a7acc", // tier 3 (rank 5–6) — blue
  "#cc4444", // tier 4 (rank 7–8) — red
];

// Frame world-radii for ascendancy nodes — sized to match PoB where notables
// and keystones almost touch their neighbours rather than floating apart.
// Roughly 1.7× the main-tree node sizes since the asc canvas is much smaller
// and nodes need to dominate the class portrait.
const ASC_FRAME_R: Record<number, number> = {
  0: 90,    // small/travel — sized so connecting lines have visible mid-section
  1: 160,   // notable
  2: 220,   // keystone (the red endpoint)
  3: 160,   // jewel
};
const ASC_ICON_FRACTION = 0.62;

// Module cache for per-ascendancy background portraits.
const ascBgCache = new Map<string, HTMLImageElement>();
function loadAscBg(ascendancy: string): HTMLImageElement | null {
  const slug = ascendancy.toLowerCase().replace(/['']/g, "").replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "");
  const cached = ascBgCache.get(slug);
  if (cached) return cached;
  loadImage(`/images/ascendancies/${slug}.webp`)
    .then(img => ascBgCache.set(slug, img))
    .catch(() => {
      const placeholder = document.createElement("canvas") as unknown as HTMLImageElement;
      ascBgCache.set(slug, placeholder);
    });
  return null;
}

export function AscendancyCanvas({
  className,
  ascendancy,
  highlightedNodes = [],
  optionalNodes = [],
  ascNodes = [],
}: {
  className?: string;
  ascendancy: string;
  highlightedNodes?: number[];
  optionalNodes?: number[];
  ascNodes?: number[];
}) {
  const canvasRef      = useRef<HTMLCanvasElement>(null);
  const camRef         = useRef({ tx: 0, ty: 0, scale: 1 });
  const minScaleRef    = useRef(0.01);
  const maxScaleRef    = useRef(1);
  const dataRef        = useRef<DrawData | null>(null);
  const dragRef        = useRef<{ sx: number; sy: number; tx: number; ty: number } | null>(null);
  const highlightedSet = useRef<Set<number>>(new Set());
  const optionalSet    = useRef<Set<number>>(new Set());
  // Maps paid asc node id → tier colour string
  const ascTierMap     = useRef<Map<number, string>>(new Map());
  // Odd-index ascNodes are endpoint notables (travel=even, endpoint=odd)
  const ascEndpointSet = useRef<Set<number>>(new Set());
  const [tooltip, setTooltip] = useState<Tooltip | null>(null);

  function draw() {
    const canvas = canvasRef.current;
    if (!canvas || !dataRef.current) return;
    const ctx = canvas.getContext("2d")!;
    const { tx, ty, scale } = camRef.current;
    const W = canvas.width;
    const H = canvas.height;
    const { nodes, lines, arcs } = dataRef.current;

    const core     = highlightedSet.current;
    const optional = optionalSet.current;

    // Filter to this ascendancy only (resolve display name → tree key)
    const treeKey    = ASCENDANCY_KEY[ascendancy] ?? ascendancy;
    const ascNodeIds = new Set(nodes.filter(n => n.ascendancy === treeKey).map(n => n.id));
    const ascLines   = lines.filter(l => ascNodeIds.has(l.n1) && ascNodeIds.has(l.n2));
    const ascArcs    = arcs.filter(a => ascNodeIds.has(a.n1) && ascNodeIds.has(a.n2));
    const treeNodes  = nodes.filter(n => n.ascendancy === treeKey);

    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.fillStyle = "#040608";
    ctx.fillRect(0, 0, W, H);
    ctx.setTransform(scale, 0, 0, scale, tx, ty);
    const inv = 1 / scale;

    // ── Ascendancy class portrait background ────────────────────────────
    // In PoB the cluster sits inside ~35-40% of the bg circle (character art
    // dominates). Size the bg image to ~2.8× the node cluster's max dimension
    // so the portrait reads as the dominant element, not just a tight halo.
    const ascBg = loadAscBg(ascendancy);
    if (ascBg && ascBg.width > 1 && treeNodes.length) {
      let bminX = Infinity, bminY = Infinity, bmaxX = -Infinity, bmaxY = -Infinity;
      for (const n of treeNodes) {
        if (n.x < bminX) bminX = n.x;
        if (n.y < bminY) bminY = n.y;
        if (n.x > bmaxX) bmaxX = n.x;
        if (n.y > bmaxY) bmaxY = n.y;
      }
      const bcx = (bminX + bmaxX) / 2;
      const bcy = (bminY + bmaxY) / 2;
      const bgSize = Math.max(bmaxX - bminX, bmaxY - bminY) * 2.4;
      ctx.drawImage(ascBg, bcx - bgSize / 2, bcy - bgSize / 2, bgSize, bgSize);
    }

    const isCoreEdge     = (n1: number, n2: number) => core.has(n1) && core.has(n2);
    const isHighlighted  = (n: number) => core.has(n) || optional.has(n);
    const isOptionalEdge = (n1: number, n2: number) =>
      isHighlighted(n1) && isHighlighted(n2) &&
      (optional.has(n1) || optional.has(n2)) &&
      !(core.has(n1) && core.has(n2));

    // Edges between ascendancy nodes — coloured by tier-pair when both endpoints
    // have a tier colour, so the user can see at a glance which path connects
    // each ranked pick (gold = tier 1, green = tier 2, blue = tier 3, red = tier 4).

    const tierMapEdges = ascTierMap.current;
    const sameTierEdge = (n1: number, n2: number): string | null => {
      const t1 = tierMapEdges.get(n1);
      const t2 = tierMapEdges.get(n2);
      return (t1 && t1 === t2) ? t1 : null;
    };

    // 1. Dim (unallocated, no tier) edges
    ctx.strokeStyle = "#7a8090"; ctx.lineWidth = inv * 4;
    ctx.beginPath();
    for (const l of ascLines) {
      if (isCoreEdge(l.n1, l.n2) || isOptionalEdge(l.n1, l.n2)) continue;
      if (sameTierEdge(l.n1, l.n2)) continue;
      ctx.moveTo(l.x1, l.y1); ctx.lineTo(l.x2, l.y2);
    }
    ctx.stroke();
    ctx.beginPath();
    for (const a of ascArcs) {
      if (isCoreEdge(a.n1, a.n2) || isOptionalEdge(a.n1, a.n2)) continue;
      if (sameTierEdge(a.n1, a.n2)) continue;
      ctx.moveTo(a.cx + a.r * Math.cos(a.sa), a.cy + a.r * Math.sin(a.sa));
      ctx.arc(a.cx, a.cy, a.r, a.sa, a.ea, false);
    }
    ctx.stroke();

    // 2. Optional edges — teal
    ctx.strokeStyle = OPTIONAL_COLOUR; ctx.lineWidth = inv * 6;
    ctx.beginPath();
    for (const l of ascLines) {
      if (!isOptionalEdge(l.n1, l.n2)) continue;
      ctx.moveTo(l.x1, l.y1); ctx.lineTo(l.x2, l.y2);
    }
    ctx.stroke();

    // 3. Core (mandatory, no tier) edges — gold
    ctx.strokeStyle = "#e8c84a"; ctx.lineWidth = inv * 6;
    ctx.beginPath();
    for (const l of ascLines) {
      if (!isCoreEdge(l.n1, l.n2)) continue;
      if (sameTierEdge(l.n1, l.n2)) continue;  // tier edges drawn separately
      ctx.moveTo(l.x1, l.y1); ctx.lineTo(l.x2, l.y2);
    }
    ctx.stroke();

    // 4. Same-tier edges — coloured by tier (gold/green/blue/red), one stroke per tier
    const tierEdgeBuckets = new Map<string, { lines: Line[]; arcs: Arc[] }>();
    for (const l of ascLines) {
      const col = sameTierEdge(l.n1, l.n2);
      if (!col) continue;
      const b = tierEdgeBuckets.get(col) ?? { lines: [], arcs: [] };
      b.lines.push(l);
      tierEdgeBuckets.set(col, b);
    }
    for (const a of ascArcs) {
      const col = sameTierEdge(a.n1, a.n2);
      if (!col) continue;
      const b = tierEdgeBuckets.get(col) ?? { lines: [], arcs: [] };
      b.arcs.push(a);
      tierEdgeBuckets.set(col, b);
    }
    for (const [col, { lines: ls, arcs: as }] of tierEdgeBuckets) {
      ctx.strokeStyle = col; ctx.lineWidth = inv * 6;
      ctx.beginPath();
      for (const l of ls) { ctx.moveTo(l.x1, l.y1); ctx.lineTo(l.x2, l.y2); }
      ctx.stroke();
      ctx.beginPath();
      for (const a of as) {
        ctx.moveTo(a.cx + a.r * Math.cos(a.sa), a.cy + a.r * Math.sin(a.sa));
        ctx.arc(a.cx, a.cy, a.r, a.sa, a.ea, false);
      }
      ctx.stroke();
    }

    // Nodes — ascendancy-specific frame sprite + icon (PoB style)
    const tierMap   = ascTierMap.current;
    const endpoints = ascEndpointSet.current;
    // PoB stores per-ascendancy frame sprite names like "DeadeyeFrameSmallNormal".
    // Endpoint notables use the Large variant; everything else uses Small.
    const ascSpritePrefix = ascendancy;
    const ascFrameName = (isEndpoint: boolean, state: FrameState) => {
      const size = isEndpoint ? "Large" : "Small";
      const suffix = state === "alloc" ? "Allocated" : state === "path" ? "CanAllocate" : "Normal";
      return `${ascSpritePrefix}Frame${size}${suffix}`;
    };

    for (const n of treeNodes) {
      const isCore     = core.has(n.id);
      const isOptional = optional.has(n.id) && !isCore;
      const tierColour = tierMap.get(n.id);
      const isActive   = isCore || isOptional || !!tierColour;
      const isEndpoint = endpoints.has(n.id);
      const isStart    = ascStartSet?.has(n.id) ?? false;
      const state: FrameState = (isCore || tierColour) ? "alloc" : isOptional ? "path" : "unalloc";

      // ── Ascendancy entry node — dark socket + icon on top
      if (isStart) {
        const startSpriteName = "PSStartNodeBackgroundInactive";
        const startCoord = spriteManifest?.[startSpriteName];
        const startSheet = startCoord ? sheetImages.get(startCoord.sheet) : undefined;
        // Smaller than before so connecting lines aren't swallowed by the socket
        const startR = Math.max(130, MIN_FRAME_SCREEN * inv);
        if (startCoord && startSheet && startSheet.width > 1) {
          ctx.drawImage(
            startSheet,
            startCoord.x, startCoord.y, startCoord.w, startCoord.h,
            n.x - startR, n.y - startR, startR * 2, startR * 2,
          );
        } else if (startCoord) {
          ensureSheet(startCoord.sheet);
        }
        // Overlay the entry node's icon (the ascendancy emblem) on top of the socket
        const sIconPath = nodeIconMap?.get(n.id);
        const sCoord    = sIconPath ? spriteManifest?.[sIconPath] : undefined;
        const sSheet    = sCoord ? sheetImages.get(sCoord.sheet) : undefined;
        if (sCoord && sSheet && sSheet.width > 1) {
          const iconR = startR * 0.55;
          ctx.drawImage(
            sSheet,
            sCoord.x, sCoord.y, sCoord.w, sCoord.h,
            n.x - iconR, n.y - iconR, iconR * 2, iconR * 2,
          );
        } else if (sCoord) {
          ensureSheet(sCoord.sheet);
        }
        continue;  // skip the regular frame+icon render for start nodes
      }

      // Frame size — endpoint notables get the larger frame
      const baseR = isEndpoint ? ASC_FRAME_R[1] : (ASC_FRAME_R[n.type] ?? ASC_FRAME_R[0]);
      const frameR = Math.max(baseR / 2, MIN_FRAME_SCREEN * inv);
      const frameSize = frameR * 2;

      // 1. Icon FIRST so the frame border overlays any spillover at the edges
      const iconPath = nodeIconMap?.get(n.id);
      const coord    = iconPath ? spriteManifest?.[iconPath] : undefined;
      const sheet    = coord ? sheetImages.get(coord.sheet) : undefined;
      if (coord && sheet && sheet.width > 1) {
        const iconSize = frameSize * ASC_ICON_FRACTION;
        ctx.globalAlpha = isActive ? 1.0 : 0.75;
        ctx.drawImage(
          sheet,
          coord.x, coord.y, coord.w, coord.h,
          n.x - iconSize / 2, n.y - iconSize / 2, iconSize, iconSize,
        );
        ctx.globalAlpha = 1.0;
      } else {
        const style = NODE_STYLE[n.type] ?? NODE_STYLE[0];
        ctx.fillStyle = tierColour ?? (isCore ? "#e8c84a" : isOptional ? OPTIONAL_COLOUR : style.colour);
        ctx.beginPath();
        ctx.arc(n.x, n.y, Math.max(2 * inv, frameR * 0.25), 0, Math.PI * 2);
        ctx.fill();
        if (coord) ensureSheet(coord.sheet);
      }

      // 2. Frame on top — its ring border covers any icon edge that extends out
      const frameKey   = ascFrameName(isEndpoint, state);
      const frameCoord = spriteManifest?.[frameKey];
      const frameSheet = frameCoord ? sheetImages.get(frameCoord.sheet) : undefined;
      if (frameCoord && frameSheet && frameSheet.width > 1) {
        ctx.drawImage(
          frameSheet,
          frameCoord.x, frameCoord.y, frameCoord.w, frameCoord.h,
          n.x - frameR, n.y - frameR, frameSize, frameSize,
        );
      } else {
        if (frameCoord) ensureSheet(frameCoord.sheet);
        // Fall back to the generic node frame from the main tree
        const fallbackName = FRAME_SPRITE[isEndpoint ? 1 : n.type]?.[state] ?? FRAME_SPRITE[0][state];
        const fc = spriteManifest?.[fallbackName];
        const fs = fc ? sheetImages.get(fc.sheet) : undefined;
        if (fc && fs && fs.width > 1) {
          ctx.drawImage(fs, fc.x, fc.y, fc.w, fc.h, n.x - frameR, n.y - frameR, frameSize, frameSize);
        }
      }

      // 3. Tier-colour overlay ring (gold / green / blue / red) on top of frame
      if (tierColour) {
        ctx.strokeStyle = tierColour;
        ctx.lineWidth   = inv * 3;
        ctx.beginPath();
        ctx.arc(n.x, n.y, frameR * 1.05, 0, Math.PI * 2);
        ctx.stroke();
      } else if (isOptional) {
        ctx.strokeStyle = OPTIONAL_COLOUR;
        ctx.lineWidth   = inv * 2;
        ctx.beginPath();
        ctx.arc(n.x, n.y, frameR * 0.9, 0, Math.PI * 2);
        ctx.stroke();
      }
    }
  }

  function hitTest(cpx: number, cpy: number): NodeData | null {
    const data = dataRef.current;
    if (!data) return null;
    const { tx, ty, scale } = camRef.current;
    const wx = (cpx - tx) / scale;
    const wy = (cpy - ty) / scale;
    const thresh = (HIT_RADIUS / scale) ** 2;
    let best: NodeData | null = null, bestD = Infinity;
    const treeKey = ASCENDANCY_KEY[ascendancy] ?? ascendancy;
    for (const n of data.nodes) {
      if (n.ascendancy !== treeKey) continue;
      const d = (n.x - wx) ** 2 + (n.y - wy) ** 2;
      if (d < thresh && d < bestD) { bestD = d; best = n; }
    }
    return best;
  }

  useEffect(() => { highlightedSet.current = new Set(highlightedNodes); if (dataRef.current) draw(); }, [highlightedNodes]);
  useEffect(() => { optionalSet.current    = new Set(optionalNodes);    if (dataRef.current) draw(); }, [optionalNodes]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    getData(className).then(d => {
      dataRef.current = d;
      // Seed highlight sets here so draw() always has them, regardless of effect order
      highlightedSet.current = new Set(highlightedNodes);
      optionalSet.current    = new Set(optionalNodes);
      // Build tier colour map: every pair of 2 gets a colour from ASC_TIER_COLOURS
      const tm = new Map<number, string>();
      ascNodes.forEach((id, i) => tm.set(id, ASC_TIER_COLOURS[Math.floor(i / 2)] ?? ASC_TIER_COLOURS[ASC_TIER_COLOURS.length - 1]));
      ascTierMap.current = tm;
      // Odd-index positions are endpoint notables (travel=even index, endpoint=odd index)
      const es = new Set<number>();
      ascNodes.forEach((id, i) => { if (i % 2 === 1) es.add(id); });
      ascEndpointSet.current = es;
      const treeKey      = ASCENDANCY_KEY[ascendancy] ?? ascendancy;
      const filteredNodes = d.nodes.filter(n => n.ascendancy === treeKey);
      if (filteredNodes.length === 0) return;
      let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
      for (const n of filteredNodes) {
        if (n.x < minX) minX = n.x; if (n.y < minY) minY = n.y;
        if (n.x > maxX) maxX = n.x; if (n.y > maxY) maxY = n.y;
      }
      // Match PoB's framing: cluster fills ~55-60% of the canvas with the class
      // portrait dominant behind it. View 1.8× cluster (so cluster reads big),
      // bg image sized 2.4× cluster so it overflows canvas edges for natural fade.
      const clusterMax = Math.max(maxX - minX, maxY - minY);
      const viewDim = clusterMax * 1.8;
      const W = canvas.width;
      const H = canvas.height;

      const fitScale = Math.min(W, H) / viewDim;
      minScaleRef.current = fitScale;
      maxScaleRef.current = fitScale * 2; // max zoom = 2× the fit-to-screen scale
      camRef.current = {
        tx:    W / 2 - ((minX + maxX) / 2) * fitScale,
        ty:    H / 2 - ((minY + maxY) / 2) * fitScale,
        scale: fitScale,
      };
      draw();
    });

    function onWheel(e: WheelEvent) {
      e.preventDefault();
      if (!canvas) return;
      const rect = canvas.getBoundingClientRect();
      const mx   = (e.clientX - rect.left) * (canvas.width  / rect.width);
      const my   = (e.clientY - rect.top)  * (canvas.height / rect.height);
      const { tx, ty, scale } = camRef.current;
      const factor   = e.deltaY < 0 ? 1.15 : 1 / 1.15;
      const newScale = Math.max(minScaleRef.current, Math.min(maxScaleRef.current, scale * factor));
      const wx = (mx - tx) / scale, wy = (my - ty) / scale;
      camRef.current = { tx: mx - wx * newScale, ty: my - wy * newScale, scale: newScale };
      draw();
    }
    canvas.addEventListener("wheel", onWheel, { passive: false });
    return () => canvas.removeEventListener("wheel", onWheel);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ascendancy, highlightedNodes, optionalNodes, ascNodes]);

  function onMouseDown(e: React.MouseEvent) {
    dragRef.current = { sx: e.clientX, sy: e.clientY, tx: camRef.current.tx, ty: camRef.current.ty };
    setTooltip(null);
  }
  function onMouseMove(e: React.MouseEvent) {
    if (dragRef.current) {
      camRef.current.tx = dragRef.current.tx + (e.clientX - dragRef.current.sx);
      camRef.current.ty = dragRef.current.ty + (e.clientY - dragRef.current.sy);
      draw(); return;
    }
    const canvas = canvasRef.current;
    if (!canvas) return;
    const rect = canvas.getBoundingClientRect();
    const cpx  = (e.clientX - rect.left) * (canvas.width  / rect.width);
    const cpy  = (e.clientY - rect.top)  * (canvas.height / rect.height);
    const hit  = hitTest(cpx, cpy);
    if (hit) setTooltip({ cx: e.clientX - rect.left, cy: e.clientY - rect.top, id: hit.id, name: hit.name, stats: hit.stats, type: hit.type });
    else setTooltip(null);
  }
  function stopDrag() { dragRef.current = null; }

  const TYPE_LABEL: Record<number, string> = { 1: "Notable", 2: "Keystone", 3: "Jewel Socket" };

  return (
    <div style={{ position: "relative", display: "block" }}>
      <canvas
        ref={canvasRef}
        width={380}
        height={380}
        style={{ display: "block", width: "380px", height: "380px", cursor: "grab", borderRadius: "4px", border: "1px solid #1a2030" }}
        onMouseDown={onMouseDown}
        onMouseMove={onMouseMove}
        onMouseUp={stopDrag}
        onMouseLeave={() => { stopDrag(); setTooltip(null); }}
      />
      {tooltip && (
        <div style={{
          position: "absolute", left: tooltip.cx + 14, top: tooltip.cy - 8,
          pointerEvents: "none", background: "rgba(10,10,20,0.95)",
          border: `1px solid ${NODE_STYLE[tooltip.type]?.colour ?? "#666688"}`,
          borderRadius: "4px", padding: "8px 12px", minWidth: "160px", maxWidth: "260px", zIndex: 10,
        }}>
          <div style={{ color: "#666", fontSize: "10px", marginBottom: "2px" }}>#{tooltip.id}</div>
          <div style={{ color: NODE_STYLE[tooltip.type]?.colour ?? "#fff", fontWeight: "bold", marginBottom: "4px", fontSize: "13px" }}>
            {tooltip.name}
            {TYPE_LABEL[tooltip.type] && <span style={{ color: "#888", fontWeight: "normal", marginLeft: "6px", fontSize: "11px" }}>{TYPE_LABEL[tooltip.type]}</span>}
          </div>
          {Object.entries(tooltip.stats).map(([k, v]) => (
            <div key={k} style={{ color: "#c8c8d8", fontSize: "12px", lineHeight: "1.5" }}>{formatStat(k, v)}</div>
          ))}
        </div>
      )}
    </div>
  );
}
