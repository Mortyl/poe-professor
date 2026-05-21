"use client";

/**
 * PIXI 7 port of the passive tree renderer.
 *
 * All `pixi.js` / `pixi-viewport` imports happen DYNAMICALLY inside the
 * effect — these libraries touch `window` at module-load time, which breaks
 * Next.js SSR. The static imports we use up top are types only.
 *
 * Data layer is shared with the canvas2d version via `./treeData`.
 */

import { useEffect, useRef, useState } from "react";
import {
  ASCENDANCY_KEY, OPTIONAL_COLOUR, HIT_RADIUS,
  loadTreeAssets, FIRST_FRAME_SHEETS, spriteManifest, nodeIconMap, ascStartSet,
  getData, formatStat,
  type DrawData, type NodeData, type Tooltip,
} from "./treeData";

// PIXI types — imported only for type checking, no runtime side-effects.
import type { Application, Texture, Sprite, Graphics, Container } from "pixi.js";

// Module caches keyed by sheet/sprite name — survive component remounts.
const baseTextures = new Map<string, Texture>();
const subTextures  = new Map<string, Texture>();
let bgTexture: Texture | null = null;
let ascBgTextures = new Map<string, Texture>();
let pixiAssetsLoaded: Promise<void> | null = null;

// Node icon world-radius (sprite displayed size in world coords).
// Must fit inside the transparent inner hole of the frame sprite, which is
// ~60% of the sprite's natural pixel width for all frame types.
// Icon = FRAME_SIZE × 0.55 keeps a visible gap between icon edge and ring.
const NODE_SIZE: Record<number, number> = {
  0: 55,    // Normal/travel  (PSSkillFrame inner hole ~60px world)
  1: 100,   // Notable        (NotableFrame inner hole ~108px world)
  2: 150,   // Keystone       (KeystoneFrame inner hole ~162px world)
  3: 100,   // Jewel          (JewelFrame inner hole ~108px world)
};
// Frame size — the frame ring sprite rendered at this world-space diameter
const FRAME_SIZE: Record<number, number> = {
  0: 100,
  1: 180,
  2: 270,
  3: 180,
};

const EDGE_DIM   = 0x3a4050;        // brighter than 0x1a2030 — visible on dark bg
const EDGE_GOLD  = 0xe8c84a;
const EDGE_TEAL  = 0x4ab8cc;
const TINT_FULL  = 0xffffff;
const TINT_DIM   = 0xa0a8b8;        // brighter dim — unallocated nodes still readable

const ASC_TIER_COLOURS = [0xe8c84a, 0x4a9a5a, 0x4a7acc, 0xcc4444];

// ── PIXI asset loaders (called from inside effects, after dynamic import) ──
async function loadPixiAssets(pixi: typeof import("pixi.js")): Promise<void> {
  if (pixiAssetsLoaded) return pixiAssetsLoaded;
  pixiAssetsLoaded = (async () => {
    const sheetUrls = FIRST_FRAME_SHEETS.map(name => `/images/tree/${name}`);
    const results = await Promise.allSettled(sheetUrls.map(url => pixi.Assets.load(url)));
    results.forEach((res, i) => {
      if (res.status === "fulfilled" && res.value) {
        baseTextures.set(FIRST_FRAME_SHEETS[i], res.value as Texture);
      }
    });
    try {
      bgTexture = await pixi.Assets.load("/images/tree/background_1024_1024_BC7.webp") as Texture;
    } catch { bgTexture = null; }
  })();
  return pixiAssetsLoaded;
}

/**
 * Find the per-ascendancy node icon (the diamond/crest used for the
 * start node) by scanning the manifest for keys ending in `{Asc}Node.dds`.
 * PoB stores these in inconsistently-cased dirs (e.g. "DeadEye/", "PathFinder/"),
 * so a case-insensitive suffix scan is the most robust lookup.
 */
function findAscNodeIconKey(ascendancy: string): string | undefined {
  if (!spriteManifest) return undefined;
  const suffix = `/${ascendancy}Node.dds`.toLowerCase();
  for (const key of Object.keys(spriteManifest)) {
    if (key.toLowerCase().endsWith(suffix)) return key;
  }
  return undefined;
}

function getSubTexture(pixi: typeof import("pixi.js"), spriteName: string): Texture | null {
  const cached = subTextures.get(spriteName);
  if (cached) return cached;
  const coord = spriteManifest?.[spriteName];
  if (!coord) return null;
  const base = baseTextures.get(coord.sheet);
  if (!base || !base.baseTexture) {
    // Lazy load this sheet for next render
    pixi.Assets.load(`/images/tree/${coord.sheet}`).then(tex => {
      if (tex) baseTextures.set(coord.sheet, tex as Texture);
    }).catch(() => undefined);
    return null;
  }
  try {
    const sub = new pixi.Texture(base.baseTexture, new pixi.Rectangle(coord.x, coord.y, coord.w, coord.h));
    subTextures.set(spriteName, sub);
    return sub;
  } catch { return null; }
}

async function loadAscBgTexture(pixi: typeof import("pixi.js"), ascendancy: string): Promise<Texture | null> {
  const slug = ascendancy.toLowerCase().replace(/['']/g, "").replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "");
  const cached = ascBgTextures.get(slug);
  if (cached) return cached;
  try {
    const tex = await pixi.Assets.load(`/images/ascendancies/${slug}.webp`) as Texture;
    if (tex) ascBgTextures.set(slug, tex);
    return tex ?? null;
  } catch { return null; }
}

// ── Main passive tree canvas ─────────────────────────────────────────────────
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
  const mountRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const appRef = useRef<Application | null>(null);
  const cameraRef = useRef<Container | null>(null);
  const camStateRef = useRef({ tx: 0, ty: 0, scale: 1, minScale: 0.01, maxScale: 1 });
  const nodeSpritesRef = useRef<Map<number, Sprite>>(new Map());
  const dataRef = useRef<DrawData | null>(null);
  const highlightedSet = useRef<Set<number>>(new Set());
  const optionalSet    = useRef<Set<number>>(new Set());
  const [tooltip, setTooltip] = useState<Tooltip | null>(null);

  function applyTints() {
    const sprites = nodeSpritesRef.current;
    const core = highlightedSet.current;
    const opt  = optionalSet.current;
    for (const [id, sprite] of sprites) {
      const isCore = core.has(id);
      const isOpt  = !isCore && opt.has(id);
      if (isCore)      { sprite.tint = TINT_FULL; sprite.alpha = 1.0; }
      else if (isOpt)  { sprite.tint = 0xb0e4ec;  sprite.alpha = 1.0; }
      else             { sprite.tint = TINT_DIM;  sprite.alpha = 0.85; }
    }
  }

  useEffect(() => { highlightedSet.current = new Set(highlightedNodes); applyTints(); }, [highlightedNodes]);
  useEffect(() => { optionalSet.current    = new Set(optionalNodes);    applyTints(); }, [optionalNodes]);

  useEffect(() => {
    const canvasEl = canvasRef.current;
    if (!canvasEl) return;
    let cancelled = false;
    let cleanupApp: Application | null = null;

    let onWheel: ((e: WheelEvent) => void) | null = null;
    let onPointerDownDom: ((e: PointerEvent) => void) | null = null;
    let onPointerMoveDom: ((e: PointerEvent) => void) | null = null;
    let onPointerUpDom:   ((e: PointerEvent) => void) | null = null;

    (async () => {
      const pixi = await import("pixi.js");
      if (cancelled) return;

      // Disable PIXI's own event system entirely — we drive pan/zoom from
      // DOM events directly on the canvas. Avoids all pixi-viewport / @pixi/events
      // version-skew crashes ("currentTarget.isInteractive is not a function").
      const W = 860, H = 540;
      let app: Application;
      try {
        app = new pixi.Application({
          view: canvasEl,
          width: W,
          height: H,
          backgroundColor: 0x040608,    // matches PoB — near-black with slight blue undertone
          antialias: true,
          resolution: window.devicePixelRatio || 1,
          autoDensity: true,
        });
      } catch (err) {
        console.error("[Tree] PIXI 7 init failed:", err);
        return;
      }
      // PIXI sets canvas.style.width/height to pixel values — override so CSS
      // width:100% takes effect and the canvas fills its container.
      canvasEl.style.width = "100%";
      canvasEl.style.height = "auto";
      // Tear down PIXI's event listening — we don't want it hit-testing anything
      // Disable PIXI's event system entirely — it removes the DOM listeners
      // and detaches cleanly. We drive all interaction via our own DOM events.
      try {
        const events = (app.renderer as unknown as {
          events?: { setTargetElement?: (el: HTMLElement | null) => void };
        }).events;
        events?.setTargetElement?.(null as unknown as HTMLElement);
      } catch {}
      if (cancelled) { app.destroy(false, { children: true }); return; }
      appRef.current = app;
      cleanupApp = app;

      const [data] = await Promise.all([
        getData(className),
        loadTreeAssets(),
        loadPixiAssets(pixi),
      ]);
      if (cancelled) return;
      dataRef.current = data;

      // ── Viewport ──
      const treeW = data.bounds.maxX - data.bounds.minX;
      const treeH = data.bounds.maxY - data.bounds.minY;
      const focusX = (data.bounds.minX + data.bounds.maxX) / 2;
      const focusY = (data.bounds.minY + data.bounds.maxY) / 2;
      const fitScale = Math.min(W / treeW, H / treeH) * 0.95;

      const allHL = [...highlightedSet.current, ...optionalSet.current];
      const nodeById = new Map(data.nodes.map(n => [n.id, n]));
      const hNodes = allHL.map(id => nodeById.get(id)).filter((n): n is NodeData => !!n && !n.ascendancy);
      let initFocusX = focusX, initFocusY = focusY, initScale = fitScale * 1.3;
      if (hNodes.length > 0) {
        const xs = hNodes.map(n => n.x), ys = hNodes.map(n => n.y);
        const hMinX = Math.min(...xs), hMaxX = Math.max(...xs);
        const hMinY = Math.min(...ys), hMaxY = Math.max(...ys);
        initFocusX = (hMinX + hMaxX) / 2;
        initFocusY = (hMinY + hMaxY) / 2;
        const pad = 1800;
        const hFit = Math.min(W / (hMaxX - hMinX + pad * 2), H / (hMaxY - hMinY + pad * 2));
        initScale = Math.min(Math.max(hFit, fitScale * 1.2), fitScale * 1.8);
      }

      // Plain camera container — pan/zoom handled by DOM events below
      const camera = new pixi.Container();
      app.stage.addChild(camera);
      cameraRef.current = camera;

      // Initial camera state — center on focus, apply initScale
      const initState = {
        tx: W / 2 - initFocusX * initScale,
        ty: H / 2 - initFocusY * initScale,
        scale: initScale,
        minScale: fitScale * 0.8,    // allow a bit of zoom-out past fit for breathing room
        maxScale: fitScale * 15,     // deep zoom — inspect individual nodes up close
      };
      camStateRef.current = initState;
      camera.x = initState.tx;
      camera.y = initState.ty;
      camera.scale.set(initState.scale);

      // ── Pan + zoom via DOM events (skips PIXI's event system entirely) ──
      let dragStart: { x: number; y: number; tx: number; ty: number } | null = null;
      onWheel = (e: WheelEvent) => {
        e.preventDefault();
        const rect = canvasEl.getBoundingClientRect();
        const mx = (e.clientX - rect.left) * (W / rect.width);
        const my = (e.clientY - rect.top)  * (H / rect.height);
        const s = camStateRef.current;
        const factor = e.deltaY < 0 ? 1.15 : 1 / 1.15;
        const newScale = Math.max(s.minScale, Math.min(s.maxScale, s.scale * factor));
        const wx = (mx - s.tx) / s.scale;
        const wy = (my - s.ty) / s.scale;
        s.scale = newScale;
        s.tx = mx - wx * newScale;
        s.ty = my - wy * newScale;
        camera.x = s.tx;
        camera.y = s.ty;
        camera.scale.set(s.scale);
      };
      onPointerDownDom = (e: PointerEvent) => {
        canvasEl.setPointerCapture(e.pointerId);
        const s = camStateRef.current;
        dragStart = { x: e.clientX, y: e.clientY, tx: s.tx, ty: s.ty };
        canvasEl.style.cursor = "grabbing";
      };
      onPointerMoveDom = (e: PointerEvent) => {
        if (!dragStart) return;
        const rect = canvasEl.getBoundingClientRect();
        const scaleX = W / rect.width;
        const dx = (e.clientX - dragStart.x) * scaleX;
        const dy = (e.clientY - dragStart.y) * scaleX;
        const s = camStateRef.current;
        s.tx = dragStart.tx + dx;
        s.ty = dragStart.ty + dy;
        camera.x = s.tx;
        camera.y = s.ty;
      };
      onPointerUpDom = (e: PointerEvent) => {
        canvasEl.releasePointerCapture?.(e.pointerId);
        dragStart = null;
        canvasEl.style.cursor = "grab";
      };
      canvasEl.addEventListener("wheel", onWheel, { passive: false });
      canvasEl.addEventListener("pointerdown", onPointerDownDom);
      canvasEl.addEventListener("pointermove", onPointerMoveDom);
      canvasEl.addEventListener("pointerup",   onPointerUpDom);
      canvasEl.addEventListener("pointercancel", onPointerUpDom);

      // Tree backdrop — we used to blit the 1024x1024 PoB image here, but
      // stretched 30x across the world it produced a mottled/spotted look.
      // Cleaner to rely on the canvas's solid background colour (set in init).

      // Edges (single Graphics, three passes)
      const edgeGfx = new pixi.Graphics();
      camera.addChild(edgeGfx);

      const core = highlightedSet.current;
      const opt  = optionalSet.current;
      const ascNodes = new Set(data.nodes.filter(n => n.ascendancy).map(n => n.id));
      const mainLines = data.lines.filter(l => !ascNodes.has(l.n1) && !ascNodes.has(l.n2));
      const mainArcs  = data.arcs .filter(a => !ascNodes.has(a.n1) && !ascNodes.has(a.n2));

      const isCoreEdge = (n1: number, n2: number) => core.has(n1) && core.has(n2);
      const isOptEdge  = (n1: number, n2: number) =>
        (core.has(n1) || opt.has(n1)) && (core.has(n2) || opt.has(n2)) &&
        (opt.has(n1) || opt.has(n2)) && !(core.has(n1) && core.has(n2));

      // Dim
      edgeGfx.lineStyle(8, EDGE_DIM);
      for (const l of mainLines) {
        if (isCoreEdge(l.n1, l.n2) || isOptEdge(l.n1, l.n2)) continue;
        edgeGfx.moveTo(l.x1, l.y1); edgeGfx.lineTo(l.x2, l.y2);
      }
      for (const a of mainArcs) {
        if (isCoreEdge(a.n1, a.n2) || isOptEdge(a.n1, a.n2)) continue;
        edgeGfx.moveTo(a.cx + a.r * Math.cos(a.sa), a.cy + a.r * Math.sin(a.sa));
        edgeGfx.arc(a.cx, a.cy, a.r, a.sa, a.ea);
      }
      // Teal optional
      edgeGfx.lineStyle(14, EDGE_TEAL);
      for (const l of mainLines) {
        if (!isOptEdge(l.n1, l.n2)) continue;
        edgeGfx.moveTo(l.x1, l.y1); edgeGfx.lineTo(l.x2, l.y2);
      }
      for (const a of mainArcs) {
        if (!isOptEdge(a.n1, a.n2)) continue;
        edgeGfx.moveTo(a.cx + a.r * Math.cos(a.sa), a.cy + a.r * Math.sin(a.sa));
        edgeGfx.arc(a.cx, a.cy, a.r, a.sa, a.ea);
      }
      // Gold core
      edgeGfx.lineStyle(14, EDGE_GOLD);
      for (const l of mainLines) {
        if (!isCoreEdge(l.n1, l.n2)) continue;
        edgeGfx.moveTo(l.x1, l.y1); edgeGfx.lineTo(l.x2, l.y2);
      }
      for (const a of mainArcs) {
        if (!isCoreEdge(a.n1, a.n2)) continue;
        edgeGfx.moveTo(a.cx + a.r * Math.cos(a.sa), a.cy + a.r * Math.sin(a.sa));
        edgeGfx.arc(a.cx, a.cy, a.r, a.sa, a.ea);
      }

      // Nodes — icon first, frame ring sprite on top (PoB-style)
      const nodeContainer = new pixi.Container();
      camera.addChild(nodeContainer);
      const sprites = nodeSpritesRef.current;
      sprites.clear();

      // Pick frame sprite by node-type + allocation state
      // (core/opt already declared above for edge rendering)
      const frameNameFor = (type: number, isCore: boolean, isOpt: boolean): string => {
        const state = isCore ? "Allocated" : isOpt ? "CanAllocate" : "Unallocated";
        if (type === 1) return `NotableFrame${state}`;
        if (type === 2) return `KeystoneFrame${state}`;
        if (type === 3) return `JewelFrame${state}`;
        // Normal nodes use the legacy PS prefix
        if (isCore) return "PSSkillFrameActive";
        if (isOpt)  return "PSSkillFrameHighlighted";
        return "PSSkillFrame";
      };

      for (const n of data.nodes) {
        if (n.ascendancy) continue;
        const isCore = core.has(n.id);
        const isOpt  = !isCore && opt.has(n.id);

        // 1. Icon
        const iconPath = nodeIconMap?.get(n.id);
        const iconTex = iconPath ? getSubTexture(pixi, iconPath) : null;
        if (iconTex) {
          const sprite = new pixi.Sprite(iconTex);
          const size = NODE_SIZE[n.type] ?? NODE_SIZE[0];
          sprite.anchor.set(0.5);
          sprite.x = n.x; sprite.y = n.y;
          sprite.width = size; sprite.height = size;
          nodeContainer.addChild(sprite);
          sprites.set(n.id, sprite);
        }

        // 2. Frame ring sprite — drawn on top so its rim overlays icon edges
        const frameTex = getSubTexture(pixi, frameNameFor(n.type, isCore, isOpt));
        if (frameTex) {
          const fsize = FRAME_SIZE[n.type] ?? FRAME_SIZE[0];
          const frame = new pixi.Sprite(frameTex);
          frame.anchor.set(0.5);
          frame.x = n.x; frame.y = n.y;
          frame.width = fsize; frame.height = fsize;
          nodeContainer.addChild(frame);
        }
      }
      applyTints();
    })();

    return () => {
      cancelled = true;
      if (canvasEl) {
        if (onWheel)           canvasEl.removeEventListener("wheel", onWheel);
        if (onPointerDownDom)  canvasEl.removeEventListener("pointerdown", onPointerDownDom);
        if (onPointerMoveDom)  canvasEl.removeEventListener("pointermove", onPointerMoveDom);
        if (onPointerUpDom)    canvasEl.removeEventListener("pointerup",   onPointerUpDom);
        if (onPointerUpDom)    canvasEl.removeEventListener("pointercancel", onPointerUpDom);
      }
      if (cleanupApp) {
        try { cleanupApp.destroy(false, { children: true, texture: false }); } catch {}
      }
      appRef.current = null;
      cameraRef.current = null;
      nodeSpritesRef.current.clear();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [className]);

  function onPointerMove(e: React.PointerEvent<HTMLDivElement>) {
    const data = dataRef.current;
    const cam  = camStateRef.current;
    if (!cam || !data || !mountRef.current) { setTooltip(null); return; }
    const rect = mountRef.current.getBoundingClientRect();
    const cpx = (e.clientX - rect.left) * (860 / rect.width);
    const cpy = (e.clientY - rect.top)  * (540 / rect.height);
    const wx = (cpx - cam.tx) / cam.scale;
    const wy = (cpy - cam.ty) / cam.scale;
    const worldThresh = (HIT_RADIUS / cam.scale) ** 2;
    let best: NodeData | null = null;
    let bestD = Infinity;
    for (const n of data.nodes) {
      if (n.ascendancy) continue;
      const d = (n.x - wx) ** 2 + (n.y - wy) ** 2;
      if (d < worldThresh && d < bestD) { bestD = d; best = n; }
    }
    if (best) {
      setTooltip({
        cx: e.clientX - rect.left, cy: e.clientY - rect.top,
        id: best.id, name: best.name, stats: best.stats, type: best.type,
      });
    } else setTooltip(null);
  }

  const TYPE_LABEL: Record<number, string> = { 1: "Notable", 2: "Keystone", 3: "Jewel Socket" };

  return (
    <div
      ref={mountRef}
      style={{ position: "relative", width: "100%", height: "auto" }}
      onPointerMove={onPointerMove}
      onPointerLeave={() => setTooltip(null)}
    >
      <canvas
        ref={canvasRef}
        style={{
          display: "block", width: "100%", height: "auto",
          borderRadius: "4px", border: "1px solid #1a2030", cursor: "grab",
        }}
      />
      {ascendancy && null}
      {tooltip && (
        <div style={{
          position: "absolute", left: tooltip.cx + 14, top: tooltip.cy - 8,
          pointerEvents: "none", background: "rgba(10,10,20,0.95)",
          border: "1px solid #666688", borderRadius: "4px",
          padding: "8px 12px", minWidth: "160px", maxWidth: "260px", zIndex: 10,
          fontFamily: "monospace",
        }}>
          <div style={{ color: "#666", fontSize: "10px", marginBottom: "2px" }}>#{tooltip.id}</div>
          <div style={{ color: "#fff", fontWeight: "bold", marginBottom: "4px", fontSize: "13px" }}>
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

// ── Ascendancy canvas — PIXI 7 ───────────────────────────────────────────────
// Notables (type 1) and endpoints render larger than travel nodes (type 0).
const ASC_FRAME_R: Record<number, number> = { 0: 115, 1: 175, 2: 190, 3: 130 };
const ASC_ICON_FRACTION = 0.62;

export function AscendancyCanvas({
  className,
  ascendancy,
  highlightedNodes = [],
  optionalNodes = [],
  ascNodes = [],
  activeTier = null,
}: {
  className?: string;
  ascendancy: string;
  highlightedNodes?: number[];
  optionalNodes?: number[];
  ascNodes?: number[];
  /** If set (0–3), only the nodes for that single tier are highlighted gold;
      everything else renders dim. Null = highlight all tiers. */
  activeTier?: number | null;
}) {
  const mountRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const appRef = useRef<Application | null>(null);
  // Scene refs — populated once per (className, ascendancy). Highlight redraws
  // mutate these directly without re-initialising PIXI (the WebGL context
  // cannot be safely re-created on the same canvas).
  const sceneRef = useRef<null | {
    edgeGfx: Graphics;
    halos: Map<number, Graphics>;
    ascLines: import("./treeData").Line[];
    ascArcs:  import("./treeData").Arc[];
    tierOfNode: Map<number, number>;
    endpointSet: Set<number>;
    startId: number | undefined;
    nodes: NodeData[];
    cam: { tx: number; ty: number; scale: number };
  }>(null);
  const [tooltip, setTooltip] = useState<Tooltip | null>(null);

  useEffect(() => {
    const canvasEl = canvasRef.current;
    if (!canvasEl) return;
    let cancelled = false;
    let cleanupApp: Application | null = null;
    const W = 380, H = 380;

    (async () => {
      const pixi = await import("pixi.js");
      if (cancelled) return;

      let app: Application;
      try {
        app = new pixi.Application({
          view: canvasEl,
          width: W,
          height: H,
          backgroundColor: 0x040608,
          antialias: true,
          resolution: window.devicePixelRatio || 1,
          autoDensity: true,
        });
      } catch (err) {
        console.error("[AscTree] PIXI 7 init failed:", err);
        return;
      }
      // Disable PIXI's event system entirely — it removes the DOM listeners
      // and detaches cleanly. We drive all interaction via our own DOM events.
      try {
        const events = (app.renderer as unknown as {
          events?: { setTargetElement?: (el: HTMLElement | null) => void };
        }).events;
        events?.setTargetElement?.(null as unknown as HTMLElement);
      } catch {}
      if (cancelled) { app.destroy(false, { children: true }); return; }
      appRef.current = app;
      cleanupApp = app;

      const [data, , ascBgTex] = await Promise.all([
        getData(className),
        loadTreeAssets(),
        loadPixiAssets(pixi).then(() => loadAscBgTexture(pixi, ascendancy)),
      ]);
      if (cancelled) return;

      const treeKey = ASCENDANCY_KEY[ascendancy] ?? ascendancy;
      const treeNodes = data.nodes.filter(n => n.ascendancy === treeKey);
      if (treeNodes.length === 0) return;

      const xs = treeNodes.map(n => n.x), ys = treeNodes.map(n => n.y);
      const minX = Math.min(...xs), maxX = Math.max(...xs);
      const minY = Math.min(...ys), maxY = Math.max(...ys);
      const clusterMax = Math.max(maxX - minX, maxY - minY);
      const viewDim = clusterMax * 1.4;     // tighter framing — cluster fills more of canvas
      const fitScale = Math.min(W, H) / viewDim;
      const centerX = (minX + maxX) / 2;
      const centerY = (minY + maxY) / 2;

      const camera = new pixi.Container();
      app.stage.addChild(camera);

      const camState = {
        tx: W / 2 - centerX * fitScale,
        ty: H / 2 - centerY * fitScale,
        scale: fitScale,
        minScale: fitScale,
        maxScale: fitScale * 2.5,
      };
      camera.x = camState.tx;
      camera.y = camState.ty;
      camera.scale.set(camState.scale);

      // Ascendancy canvas is static — no pan/zoom. (The main tree is interactive
      // via the other canvas.) Cursor stays default to signal non-interactivity.
      canvasEl.style.cursor = "default";

      if (ascBgTex) {
        const bgSprite = new pixi.Sprite(ascBgTex);
        const bgSize = clusterMax * 2.4;
        bgSprite.width = bgSprite.height = bgSize;
        bgSprite.x = centerX - bgSize / 2;
        bgSprite.y = centerY - bgSize / 2;
        camera.addChild(bgSprite);
      }

      // Per-node tier index (0-3 → which tier-pair this node belongs to).
      // ascNodes is flat: [tier1-travel, tier1-endpoint, tier2-travel, tier2-endpoint, ...]
      const tierOfNode = new Map<number, number>();
      const endpointSet = new Set<number>();
      ascNodes.forEach((id, i) => {
        tierOfNode.set(id, Math.floor(i / 2));
        if (i % 2 === 1) endpointSet.add(id);
      });

      const startNode = treeNodes.find(n => ascStartSet?.has(n.id));
      const startId = startNode?.id;

      const ascNodeIds = new Set(treeNodes.map(n => n.id));
      const ascLines = data.lines.filter(l => ascNodeIds.has(l.n1) && ascNodeIds.has(l.n2));
      const ascArcs  = data.arcs .filter(a => ascNodeIds.has(a.n1) && ascNodeIds.has(a.n2));

      // Gateway nodes: free non-start ascendancy nodes that bridge paid tier nodes
      // (e.g. Deadeye's 42416 which is auto-allocated between 61461 and the PoB choices).
      // Detected by having 2+ adjacent paid tier nodes. Stored at tier -1 so they
      // are always active regardless of activeTier.
      for (const n of treeNodes) {
        if (tierOfNode.has(n.id) || (ascStartSet?.has(n.id) ?? false)) continue;
        let tierNeighbourCount = 0;
        for (const l of ascLines) {
          if (l.n1 === n.id && tierOfNode.has(l.n2)) tierNeighbourCount++;
          if (l.n2 === n.id && tierOfNode.has(l.n1)) tierNeighbourCount++;
        }
        for (const a of ascArcs) {
          if (a.n1 === n.id && tierOfNode.has(a.n2)) tierNeighbourCount++;
          if (a.n2 === n.id && tierOfNode.has(a.n1)) tierNeighbourCount++;
        }
        if (tierNeighbourCount >= 2) tierOfNode.set(n.id, -1);
      }

      // When activeTier is set we only treat nodes up to that tier as "highlighted gold".
      // Gateway nodes (tier=-1) are always active. The asc-start is always active too.
      const isActiveNode = (id: number): boolean => {
        if (startId !== undefined && id === startId) return true;
        if (activeTier == null) return tierOfNode.has(id);
        const t = tierOfNode.get(id);
        return t !== undefined && t <= activeTier;
      };

      const core = new Set(highlightedNodes);
      const opt  = new Set(optionalNodes);

      const isGoldEdge = (n1: number, n2: number) => isActiveNode(n1) && isActiveNode(n2);

      const edgeGfx = new pixi.Graphics();
      // 1. Dim edges (everything that isn't on the gold path)
      edgeGfx.lineStyle(8, 0x4a5060);
      for (const l of ascLines) {
        if (isGoldEdge(l.n1, l.n2)) continue;
        edgeGfx.moveTo(l.x1, l.y1); edgeGfx.lineTo(l.x2, l.y2);
      }
      for (const a of ascArcs) {
        if (isGoldEdge(a.n1, a.n2)) continue;
        edgeGfx.moveTo(a.cx + a.r * Math.cos(a.sa), a.cy + a.r * Math.sin(a.sa));
        edgeGfx.arc(a.cx, a.cy, a.r, a.sa, a.ea);
      }
      // 2. Gold path — all highlight edges on top
      edgeGfx.lineStyle(20, EDGE_GOLD);
      for (const l of ascLines) {
        if (!isGoldEdge(l.n1, l.n2)) continue;
        edgeGfx.moveTo(l.x1, l.y1); edgeGfx.lineTo(l.x2, l.y2);
      }
      for (const a of ascArcs) {
        if (!isGoldEdge(a.n1, a.n2)) continue;
        edgeGfx.moveTo(a.cx + a.r * Math.cos(a.sa), a.cy + a.r * Math.sin(a.sa));
        edgeGfx.arc(a.cx, a.cy, a.r, a.sa, a.ea);
      }
      camera.addChild(edgeGfx);

      // Nodes — frame + icon. Frames are always the "Normal/Unallocated"
      // variant; highlight state is communicated solely by the gold halo
      // ring overlay, which the second useEffect toggles by tier.
      const nodeContainer = new pixi.Container();
      camera.addChild(nodeContainer);
      const halos = new Map<number, Graphics>();

      for (const n of treeNodes) {
        const isStart    = ascStartSet?.has(n.id) ?? false;
        const isEndpoint = endpointSet.has(n.id);

        if (isStart) {
          const startR = 80;
          const diamondTex = getSubTexture(pixi, "AscendancyMiddle");
          if (diamondTex) {
            const sprite = new pixi.Sprite(diamondTex);
            sprite.anchor.set(0.5);
            sprite.x = n.x; sprite.y = n.y;
            sprite.width = sprite.height = startR * 2;
            nodeContainer.addChild(sprite);
          } else {
            const startTex = getSubTexture(pixi, "PSStartNodeBackgroundInactive");
            if (startTex) {
              const sprite = new pixi.Sprite(startTex);
              sprite.anchor.set(0.5);
              sprite.x = n.x; sprite.y = n.y;
              sprite.width = sprite.height = startR * 2;
              nodeContainer.addChild(sprite);
            }
          }
          continue;
        }

        const baseR = ASC_FRAME_R[n.type] ?? ASC_FRAME_R[0];
        const frameSize = baseR;

        // Always use the unallocated frame variant (highlight = halo)
        const isLarge = n.type === 1 || n.type === 2;
        const ascSize = isLarge ? "Large" : "Small";
        const ascFrameKey = `${ascendancy}Frame${ascSize}Normal`;
        let frameTex = getSubTexture(pixi, ascFrameKey);
        if (!frameTex) {
          const fallbackKey =
            n.type === 2 ? "KeystoneFrameUnallocated" :
            n.type === 3 ? "JewelFrameUnallocated" :
            n.type === 1 ? "NotableFrameUnallocated" :
            "PSSkillFrame";
          frameTex = getSubTexture(pixi, fallbackKey);
        }

        const iconPath = nodeIconMap?.get(n.id);
        const iconTex = iconPath ? getSubTexture(pixi, iconPath) : null;
        if (iconTex) {
          const iconSize = frameSize * ASC_ICON_FRACTION;
          const sprite = new pixi.Sprite(iconTex);
          sprite.anchor.set(0.5);
          sprite.x = n.x; sprite.y = n.y;
          sprite.width = sprite.height = iconSize;
          nodeContainer.addChild(sprite);
        }

        if (frameTex) {
          const sprite = new pixi.Sprite(frameTex);
          sprite.anchor.set(0.5);
          sprite.x = n.x; sprite.y = n.y;
          sprite.width = sprite.height = frameSize;
          nodeContainer.addChild(sprite);
        }

        // Gold halo — created for EVERY tier node, visibility toggled later
        if (tierOfNode.has(n.id)) {
          const ring = new pixi.Graphics();
          ring.lineStyle(6, EDGE_GOLD, 0.95);
          ring.drawCircle(n.x, n.y, frameSize * 0.55);
          ring.visible = isActiveNode(n.id);
          nodeContainer.addChild(ring);
          halos.set(n.id, ring);
        }
      }

      // Capture scene refs so the redraw effect can mutate without reinit
      sceneRef.current = {
        edgeGfx,
        halos,
        ascLines,
        ascArcs,
        tierOfNode,
        endpointSet,
        startId,
        nodes: treeNodes,
        cam: { tx: camState.tx, ty: camState.ty, scale: camState.scale },
      };

      // camera already positioned/zoomed at fitScale above
    })();

    return () => {
      cancelled = true;
      // (ascendancy canvas is static — no DOM event listeners to detach)
      if (cleanupApp) {
        try { cleanupApp.destroy(false, { children: true, texture: false }); } catch {}
      }
      appRef.current = null;
    };
    // NOTE: activeTier intentionally excluded — re-running this effect would
    // destroy and try to recreate the PIXI WebGL context on the same canvas,
    // which fails. Highlight updates are handled in a separate effect below.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [className, ascendancy]);

  // ── Highlight redraw — fires when activeTier changes, no PIXI reinit ───
  useEffect(() => {
    const s = sceneRef.current;
    if (!s) return;
    const isActive = (id: number) => {
      if (s.startId !== undefined && id === s.startId) return true;
      if (activeTier == null) return s.tierOfNode.has(id);
      const t = s.tierOfNode.get(id);
      // Cumulative: tier N highlights tiers 0..N (e.g. clicking II shows I + II)
      return t !== undefined && t <= activeTier;
    };
    const isGoldEdge = (n1: number, n2: number) => isActive(n1) && isActive(n2);

    s.edgeGfx.clear();
    // Dim base layer
    s.edgeGfx.lineStyle(8, 0x4a5060);
    for (const l of s.ascLines) {
      if (isGoldEdge(l.n1, l.n2)) continue;
      s.edgeGfx.moveTo(l.x1, l.y1); s.edgeGfx.lineTo(l.x2, l.y2);
    }
    for (const a of s.ascArcs) {
      if (isGoldEdge(a.n1, a.n2)) continue;
      s.edgeGfx.moveTo(a.cx + a.r * Math.cos(a.sa), a.cy + a.r * Math.sin(a.sa));
      s.edgeGfx.arc(a.cx, a.cy, a.r, a.sa, a.ea);
    }
    // Gold path — three layered passes (outer faded glow → mid → sharp center)
    // for a bloom/halo effect without needing a real blur filter.
    const goldPasses: Array<{ width: number; alpha: number }> = [
      { width: 50, alpha: 0.10 },   // outer haze
      { width: 32, alpha: 0.28 },   // mid glow
      { width: 20, alpha: 1.00 },   // sharp line
    ];
    for (const pass of goldPasses) {
      s.edgeGfx.lineStyle(pass.width, EDGE_GOLD, pass.alpha);
      for (const l of s.ascLines) {
        if (!isGoldEdge(l.n1, l.n2)) continue;
        s.edgeGfx.moveTo(l.x1, l.y1); s.edgeGfx.lineTo(l.x2, l.y2);
      }
      for (const a of s.ascArcs) {
        if (!isGoldEdge(a.n1, a.n2)) continue;
        s.edgeGfx.moveTo(a.cx + a.r * Math.cos(a.sa), a.cy + a.r * Math.sin(a.sa));
        s.edgeGfx.arc(a.cx, a.cy, a.r, a.sa, a.ea);
      }
    }
    // Toggle halo visibility per tier
    for (const [id, halo] of s.halos) {
      halo.visible = isActive(id);
    }
  }, [activeTier]);

  function onAscPointerMove(e: React.PointerEvent<HTMLDivElement>) {
    const s = sceneRef.current;
    if (!s || !mountRef.current) { setTooltip(null); return; }
    const rect = mountRef.current.getBoundingClientRect();
    const cpx = e.clientX - rect.left;
    const cpy = e.clientY - rect.top;
    const wx = (cpx - s.cam.tx) / s.cam.scale;
    const wy = (cpy - s.cam.ty) / s.cam.scale;
    const thresh = (HIT_RADIUS / s.cam.scale) ** 2;
    let best: NodeData | null = null;
    let bestD = Infinity;
    for (const n of s.nodes) {
      const d = (n.x - wx) ** 2 + (n.y - wy) ** 2;
      if (d < thresh && d < bestD) { bestD = d; best = n; }
    }
    if (best) {
      setTooltip({ cx: e.clientX, cy: e.clientY, id: best.id, name: best.name, stats: best.stats, type: best.type });
    } else {
      setTooltip(null);
    }
  }

  return (
    <div ref={mountRef} style={{ position: "relative" }}
      onPointerMove={onAscPointerMove}
      onPointerLeave={() => setTooltip(null)}
    >
      <canvas
        ref={canvasRef}
        style={{
          display: "block", width: "380px", height: "380px",
          borderRadius: "4px", border: "1px solid #1a2030", cursor: "default",
        }}
      />
      {tooltip && (
        <div style={{
          position: "fixed", left: tooltip.cx + 14, top: tooltip.cy - 8,
          pointerEvents: "none", background: "rgba(10,10,20,0.95)",
          border: "1px solid #666688", borderRadius: "4px",
          padding: "8px 12px", minWidth: "160px", maxWidth: "260px", zIndex: 9999,
        }}>
          <div style={{ color: "#666", fontSize: "10px", marginBottom: "2px" }}>#{tooltip.id}</div>
          <div style={{ color: "#fff", fontWeight: "bold", marginBottom: "4px", fontSize: "13px" }}>
            {tooltip.name}
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
