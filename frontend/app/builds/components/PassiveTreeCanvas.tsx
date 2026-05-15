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
  x: number;
  y: number;
  ascendancy: string | undefined;
  name: string;
  stats: Record<string, number>;
  type: number;
}
interface Line { x1: number; y1: number; x2: number; y2: number; }
interface Arc  { cx: number; cy: number; r: number; sa: number; ea: number; }
interface Bounds { minX: number; minY: number; maxX: number; maxY: number; }
interface DrawData { nodes: NodeData[]; lines: Line[]; arcs: Arc[]; bounds: Bounds; }

interface Tooltip { cx: number; cy: number; name: string; stats: Record<string, number>; type: number; }

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
        lines.push({ x1: a.x, y1: a.y, x2: b.x, y2: b.y });
        continue;
      }

      const r = ORBIT_RADII[Math.abs(connOrbit)];
      if (!r) { lines.push({ x1: a.x, y1: a.y, x2: b.x, y2: b.y }); continue; }

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

      arcs.push({ cx, cy, r, sa, ea });
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

export default function PassiveTreeCanvas({ className }: { className?: string } = {}) {
  const canvasRef  = useRef<HTMLCanvasElement>(null);
  const camRef     = useRef({ tx: 0, ty: 0, scale: 1 });
  const minScaleRef = useRef(0.008);
  const dataRef    = useRef<DrawData | null>(null);
  const dragRef    = useRef<{ sx: number; sy: number; tx: number; ty: number } | null>(null);
  const [tooltip, setTooltip] = useState<Tooltip | null>(null);

  function draw() {
    const canvas = canvasRef.current;
    if (!canvas || !dataRef.current) return;
    const ctx = canvas.getContext("2d")!;
    const { tx, ty, scale } = camRef.current;
    const W = canvas.width;
    const H = canvas.height;
    const { nodes, lines, arcs } = dataRef.current;

    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.fillStyle = "#07070f";
    ctx.fillRect(0, 0, W, H);

    ctx.setTransform(scale, 0, 0, scale, tx, ty);
    const inv = 1 / scale;

    // Connections
    ctx.strokeStyle = "#2a2a4a";
    ctx.lineWidth   = inv;
    ctx.beginPath();
    for (const l of lines) { ctx.moveTo(l.x1, l.y1); ctx.lineTo(l.x2, l.y2); }
    ctx.stroke();

    ctx.beginPath();
    for (const a of arcs) {
      ctx.moveTo(a.cx + a.r * Math.cos(a.sa), a.cy + a.r * Math.sin(a.sa));
      ctx.arc(a.cx, a.cy, a.r, a.sa, a.ea, false);
    }
    ctx.stroke();

    // Nodes — filled circles, sized by type, grow with zoom but never smaller than MIN_SCREEN_R
    for (const n of nodes) {
      const style  = NODE_STYLE[n.type] ?? NODE_STYLE[0];
      const worldR = Math.max(style.r, MIN_SCREEN_R * inv);
      ctx.fillStyle   = style.colour;
      ctx.strokeStyle = style.colour + "99";
      ctx.lineWidth   = inv;
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
      minScaleRef.current = fitScale;
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
      const rect     = canvas.getBoundingClientRect();
      const mx       = (e.clientX - rect.left) * (canvas.width  / rect.width);
      const my       = (e.clientY - rect.top)  * (canvas.height / rect.height);
      const { tx, ty, scale } = camRef.current;
      const factor   = e.deltaY < 0 ? 1.15 : 1 / 1.15;
      const newScale = Math.max(minScaleRef.current, Math.min(0.2, scale * factor));
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
      setTooltip({ cx: e.clientX - rect.left, cy: e.clientY - rect.top, name: hit.name, stats: hit.stats, type: hit.type });
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
