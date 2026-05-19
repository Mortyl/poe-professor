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
const MIN_SCREEN_R = 2;
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
    ctx.fillStyle = "#07070f";
    ctx.fillRect(0, 0, W, H);

    ctx.setTransform(scale, 0, 0, scale, tx, ty);
    const inv = 1 / scale;

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
    ctx.strokeStyle = "#2a2a4a";
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

    // 4. Nodes (main tree only — ascendancy nodes rendered in separate canvas)
    for (const n of nodes) {
      if (n.ascendancy) continue;
      const isCore     = core.has(n.id);
      const isOptional = optional.has(n.id) && !isCore;
      const isActive   = isCore || isOptional;

      const style  = NODE_STYLE[n.type] ?? NODE_STYLE[0];
      const baseR  = isActive ? style.r * 1.4 : style.r;
      const worldR = Math.max(baseR, MIN_SCREEN_R * inv);

      const fillColour = isCore ? "#e8c84a" : isOptional ? OPTIONAL_COLOUR : style.colour;
      const glowColour = isCore ? "#e8c84a" : OPTIONAL_COLOUR;

      if (isActive) {
        ctx.strokeStyle = glowColour;
        ctx.lineWidth   = inv * 2.5;
        ctx.beginPath();
        ctx.arc(n.x, n.y, worldR + inv * 3, 0, Math.PI * 2);
        ctx.stroke();
        ctx.fillStyle   = fillColour;
        ctx.strokeStyle = "#ffffff44";
        ctx.lineWidth   = inv;
      } else {
        ctx.fillStyle   = style.colour;
        ctx.strokeStyle = style.colour + "99";
        ctx.lineWidth   = inv;
      }

      ctx.beginPath();
      ctx.arc(n.x, n.y, worldR, 0, Math.PI * 2);
      ctx.fill();
      ctx.stroke();
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

    getData(className).then(d => {
      dataRef.current = d;
      const { minX, minY, maxX, maxY } = d.bounds;
      const treeW = maxX - minX;
      const treeH = maxY - minY;
      const fitScale = Math.min(W / treeW, H / treeH) * 0.95;
      maxScaleRef.current = fitScale * 6; // max zoom = 6× the fit-to-screen scale
      // minScale is set after startScale is computed below

      // Center on the bounding box of highlighted nodes if any exist,
      // and start zoomed to fit that box. Falls back to full tree centre/scale.
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
        startScale = fitScale;
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
        style={{ display: "block", width: "100%", height: "auto", cursor: dragRef.current ? "grabbing" : "grab", borderRadius: "4px", border: "1px solid #2a2a3a" }}
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
    ctx.fillStyle = "#07070f";
    ctx.fillRect(0, 0, W, H);
    ctx.setTransform(scale, 0, 0, scale, tx, ty);
    const inv = 1 / scale;

    const isCoreEdge     = (n1: number, n2: number) => core.has(n1) && core.has(n2);
    const isHighlighted  = (n: number) => core.has(n) || optional.has(n);
    const isOptionalEdge = (n1: number, n2: number) =>
      isHighlighted(n1) && isHighlighted(n2) &&
      (optional.has(n1) || optional.has(n2)) &&
      !(core.has(n1) && core.has(n2));

    // Dim edges
    ctx.strokeStyle = "#2a2a4a"; ctx.lineWidth = inv;
    ctx.beginPath();
    for (const l of ascLines) {
      if (isCoreEdge(l.n1, l.n2) || isOptionalEdge(l.n1, l.n2)) continue;
      ctx.moveTo(l.x1, l.y1); ctx.lineTo(l.x2, l.y2);
    }
    ctx.stroke();
    ctx.beginPath();
    for (const a of ascArcs) {
      if (isCoreEdge(a.n1, a.n2) || isOptionalEdge(a.n1, a.n2)) continue;
      ctx.moveTo(a.cx + a.r * Math.cos(a.sa), a.cy + a.r * Math.sin(a.sa));
      ctx.arc(a.cx, a.cy, a.r, a.sa, a.ea, false);
    }
    ctx.stroke();

    // Optional edges — teal
    ctx.strokeStyle = OPTIONAL_COLOUR; ctx.lineWidth = inv * 2;
    ctx.beginPath();
    for (const l of ascLines) {
      if (!isOptionalEdge(l.n1, l.n2)) continue;
      ctx.moveTo(l.x1, l.y1); ctx.lineTo(l.x2, l.y2);
    }
    ctx.stroke();

    // Core edges — gold
    ctx.strokeStyle = "#e8c84a"; ctx.lineWidth = inv * 2;
    ctx.beginPath();
    for (const l of ascLines) {
      if (!isCoreEdge(l.n1, l.n2)) continue;
      ctx.moveTo(l.x1, l.y1); ctx.lineTo(l.x2, l.y2);
    }
    ctx.stroke();

    // Nodes
    const tierMap    = ascTierMap.current;
    const endpoints  = ascEndpointSet.current;
    for (const n of treeNodes) {
      const isCore     = core.has(n.id);
      const isOptional = optional.has(n.id) && !isCore;
      const tierColour = tierMap.get(n.id);          // paid asc tier colour, if any
      const isActive   = isCore || isOptional || !!tierColour;
      const isEndpoint = endpoints.has(n.id);        // endpoint notable in a tier pair

      const style  = NODE_STYLE[n.type] ?? NODE_STYLE[0];
      // Endpoint notables always render at notable radius regardless of stored type
      const effectiveR = isEndpoint ? NODE_STYLE[1].r : style.r;
      const baseR  = isActive ? effectiveR * 1.4 : effectiveR;
      const worldR = Math.max(baseR, MIN_SCREEN_R * inv);

      const fillColour = tierColour ?? (isCore ? "#e8c84a" : isOptional ? OPTIONAL_COLOUR : style.colour);
      const glowColour = tierColour ?? (isCore ? "#e8c84a" : OPTIONAL_COLOUR);

      if (isActive) {
        ctx.strokeStyle = glowColour; ctx.lineWidth = inv * 2.5;
        ctx.beginPath(); ctx.arc(n.x, n.y, worldR + inv * 3, 0, Math.PI * 2); ctx.stroke();
        ctx.fillStyle = fillColour; ctx.strokeStyle = "#ffffff44"; ctx.lineWidth = inv;
      } else {
        ctx.fillStyle = style.colour; ctx.strokeStyle = style.colour + "99"; ctx.lineWidth = inv;
      }
      ctx.beginPath(); ctx.arc(n.x, n.y, worldR, 0, Math.PI * 2); ctx.fill(); ctx.stroke();
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
      const pad = 200;
      const treeW = maxX - minX + pad * 2;
      const treeH = maxY - minY + pad * 2;
      const W = canvas.width;
      const H = canvas.height;

      const fitScale = Math.min(W / treeW, H / treeH) * 0.9;
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
        style={{ display: "block", width: "380px", height: "380px", cursor: "grab", borderRadius: "4px", border: "1px solid #2a2a3a" }}
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
