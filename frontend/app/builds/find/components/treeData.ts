/**
 * Shared passive-tree data layer.
 *
 * Loads SkillTreeCore.json once + PoB's tree.json + the sprite manifest, then
 * exposes parsed node positions, edges, asset lookups, and the per-node icon
 * mapping. Both the canvas2d (`PassiveTreeCanvas.tsx`) and PIXI
 * (`PassiveTreeCanvasPixi.tsx`) renderers consume this — keeping one source
 * of truth for allocation/positions independent of how they're drawn.
 */

// ── Constants ───────────────────────────────────────────────────────────────
export const ORBIT_RADII      = [0, 82, 162, 335, 493, 662, 846, 251, 1080, 1332];
export const SKILLS_PER_ORBIT = [1, 12, 24, 24, 72, 72, 72, 24, 72, 144];

export const HIT_RADIUS = 10;

// Display ascendancy name → internal tree key used in SkillTreeCore.json
export const ASCENDANCY_KEY: Record<string, string> = {
  "Deadeye":              "Ranger1",
  "Pathfinder":           "Ranger3",
  "Infernalist":          "Witch1",
  "Blood Mage":           "Witch2",
  "Lich":                 "Witch3",
  "Titan":                "Warrior1",
  "Warbringer":           "Warrior2",
  "Amazon":               "Huntress1",
  "Spirit Walker":        "Huntress3",
  "Stormweaver":          "Sorceress1",
  "Chronomancer":         "Sorceress2",
  "Disciple of Varashta": "Sorceress3",
  "Invoker":              "Monk2",
  "Acolyte of Chayula":   "Monk3",
  "Tactician":            "Mercenary1",
  "Witchhunter":          "Mercenary2",
  "Gemling Legionnaire":  "Mercenary3",
  "Oracle":               "Druid1",
  "Shaman":               "Druid2",
};

// Node-type style defaults (used by canvas2d fallback rendering)
export const NODE_STYLE: Record<number, { colour: string; r: number }> = {
  0: { colour: "#4a6080", r: 16 }, // Normal      — blue-grey
  1: { colour: "#c8a050", r: 26 }, // Notable     — gold
  2: { colour: "#cc3030", r: 38 }, // Keystone    — red
  3: { colour: "#40aa60", r: 28 }, // JewelSocket — green
};
export const OPTIONAL_COLOUR = "#4ab8cc";

// ── Types ───────────────────────────────────────────────────────────────────
export interface RawGroup { X: number; Y: number; Nodes: number[]; }
export interface NodeOverride {
  Name?: string;
  Type?: number;
  Stats?: Record<string, number>;
}
export interface RawNode {
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
export interface RawData {
  Groups: RawGroup[];
  Nodes: Record<string, RawNode>;
}

export interface NodeData {
  id: number;
  x: number;
  y: number;
  ascendancy: string | undefined;
  name: string;
  stats: Record<string, number>;
  type: number;
}
export interface Line { x1: number; y1: number; x2: number; y2: number; n1: number; n2: number; }
export interface Arc  { cx: number; cy: number; r: number; sa: number; ea: number; n1: number; n2: number; }
export interface Bounds { minX: number; minY: number; maxX: number; maxY: number; }
export interface DrawData { nodes: NodeData[]; lines: Line[]; arcs: Arc[]; bounds: Bounds; }

export interface Tooltip {
  cx: number; cy: number;
  id: number; name: string;
  stats: Record<string, number>;
  type: number;
}

// ── Sprite manifest types ───────────────────────────────────────────────────
export interface SpriteCoord { sheet: string; x: number; y: number; w: number; h: number; }
export interface PobNode { icon?: string; isAscendancyStart?: boolean; }
export interface PobTree { nodes: Record<string, PobNode>; }

// ── Module-level cache (shared across renderers) ────────────────────────────
const dataCache = new Map<string, DrawData>();
let fetchPromise: Promise<unknown> | null = null;
let rawData: RawData | null = null;

export let spriteManifest: Record<string, SpriteCoord> | null = null;
export let nodeIconMap:    Map<number, string> | null         = null;
export let ascStartSet:    Set<number> | null                 = null;
export let bgImage:        HTMLImageElement | null            = null;
export const sheetImages = new Map<string, HTMLImageElement>();

let assetsPromise: Promise<void> | null = null;

// ── Stat formatting (used by tooltips in both renderers) ────────────────────
export function formatStat(key: string, val: number): string {
  const isPct    = key.endsWith("_+%") || key.endsWith("+%");
  const isFlatPct = !isPct && key.endsWith("_%");
  let name = key.replace(/_\+%$/, "").replace(/_%$/, "").replace(/_/g, " ");
  name = name.replace(/\b\w/g, c => c.toUpperCase());
  if (isPct)     return `${val}% increased ${name}`;
  if (isFlatPct) return `${val}% ${name}`;
  return val > 0 ? `+${val} ${name}` : `${val} ${name}`;
}

// ── Image helpers (canvas2d uses these directly; PIXI loads via Assets) ─────
export function loadImage(src: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload  = () => resolve(img);
    img.onerror = () => reject(new Error(`failed to load ${src}`));
    img.src = src;
  });
}

export function ensureSheet(name: string): HTMLImageElement | null {
  const cached = sheetImages.get(name);
  if (cached) return cached;
  loadImage(`/images/tree/${name}`).then(img => {
    sheetImages.set(name, img);
  }).catch(() => {
    const placeholder = document.createElement("canvas") as unknown as HTMLImageElement;
    sheetImages.set(name, placeholder);
  });
  return null;
}

// First-frame sheet names — preloaded so the first paint shows real sprites.
export const FIRST_FRAME_SHEETS = [
  "skills_128_128_BC1.webp",
  "skills_64_64_BC1.webp",
  "group-background_104_104_BC7.webp",
  "group-background_152_156_BC7.webp",
  "group-background_220_224_BC7.webp",
  "group-background_160_164_BC7.webp",
  "group-background_208_208_BC7.webp",
  "group-background_528_528_BC7.webp",
  "group-background_92_92_BC7.webp",
];

export function loadTreeAssets(): Promise<void> {
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
    await Promise.all(FIRST_FRAME_SHEETS.map(name =>
      loadImage(`/images/tree/${name}`)
        .then(img => sheetImages.set(name, img))
        .catch(() => undefined)
    ));
  })();
  return assetsPromise;
}

// ── Tree-data parsing (positions + edges from SkillTreeCore.json) ───────────
export function parseData(data: RawData, className?: string): DrawData {
  const nodeMap = new Map<number, NodeData>();
  const nodes: NodeData[] = [];

  for (const [idStr, node] of Object.entries(data.Nodes)) {
    const id = parseInt(idStr, 10);
    if (node.Type === 4) continue;
    const g = data.Groups[node.Group];
    if (!g) continue;
    const r     = ORBIT_RADII[node.Orbit] ?? 0;
    const total = SKILLS_PER_ORBIT[node.Orbit] ?? 1;
    const angle = (node.OrbitIndex / total) * 2 * Math.PI;
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
      if (a.ascendancy !== b.ascendancy) continue;
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

export function getData(className?: string): Promise<DrawData> {
  const key = className ?? "__default__";
  if (dataCache.has(key)) return Promise.resolve(dataCache.get(key)!);
  const doparse = (data: RawData): DrawData => {
    const parsed = parseData(data, className);
    dataCache.set(key, parsed);
    return parsed;
  };
  if (rawData) return Promise.resolve(doparse(rawData));
  if (!fetchPromise) {
    fetchPromise = fetch("/SkillTreeCore.json").then(r => r.json()).then((data: RawData) => { rawData = data; });
  }
  return (fetchPromise as Promise<void>).then(() => doparse(rawData!));
}
