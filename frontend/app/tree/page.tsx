"use client";

import { useEffect, useRef } from "react";
import Navbar from "../components/Navbar";

// PoE2 orbit constants (from Path of Building PoE2 tree data)
const ORBIT_RADII      = [0, 82, 162, 335, 493, 662, 846, 251, 1080, 1322];
const SKILLS_PER_ORBIT = [1, 12,  24,  24,  72,  72,  72,  24,   72,  144];

const TREE_URL = "https://repoe-fork.github.io/poe2/passive_skill_trees/Default.json";

interface Passive {
  hash: number;
  radius: number;
  position_clockwise: number;
  connections: number[];
}

interface Group {
  x: number;
  y: number;
  passives: Passive[];
}

interface NodePos {
  x: number;
  y: number;
}

function computePositions(groups: Group[]): NodePos[] {
  const nodes: NodePos[] = [];

  for (const group of groups) {
    for (const passive of group.passives) {
      const orbit = passive.radius;
      const r     = ORBIT_RADII[orbit] ?? 0;

      if (r === 0) {
        nodes.push({ x: group.x, y: group.y });
      } else {
        const total = SKILLS_PER_ORBIT[orbit] ?? 1;
        const angle = (passive.position_clockwise / total) * 2 * Math.PI;
        nodes.push({
          x: group.x + r * Math.sin(angle),
          y: group.y - r * Math.cos(angle),
        });
      }
    }
  }

  return nodes;
}

export default function TreePage() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const camRef    = useRef({ tx: 0, ty: 0, scale: 1 });
  const nodesRef  = useRef<NodePos[]>([]);
  const dragRef   = useRef<{ sx: number; sy: number; tx: number; ty: number } | null>(null);

  function draw() {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d")!;
    const { tx, ty, scale } = camRef.current;
    const W = canvas.width;
    const H = canvas.height;

    // Background
    ctx.fillStyle = "#0a0a0a";
    ctx.fillRect(0, 0, W, H);

    // Nodes
    ctx.strokeStyle = "#666666";
    ctx.lineWidth   = 1;

    for (const n of nodesRef.current) {
      const cx = n.x * scale + tx;
      const cy = n.y * scale + ty;

      // Skip nodes outside the visible area
      if (cx < -10 || cx > W + 10 || cy < -10 || cy > H + 10) continue;

      ctx.beginPath();
      ctx.arc(cx, cy, 3, 0, Math.PI * 2);
      ctx.stroke();
    }
  }

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    // Size canvas to fill the viewport (below navbar)
    canvas.width  = window.innerWidth;
    canvas.height = window.innerHeight - 56;

    // Initial camera: world origin at canvas centre, scale to fit ~50k-unit tree
    camRef.current = {
      tx:    canvas.width  / 2,
      ty:    canvas.height / 2,
      scale: Math.min(canvas.width, canvas.height) / 50000,
    };

    // Fetch tree data and draw
    fetch(TREE_URL)
      .then(r => r.json())
      .then((data: { groups: Group[] }) => {
        nodesRef.current = computePositions(data.groups);
        draw();
      })
      .catch(() => {
        const ctx = canvas.getContext("2d")!;
        ctx.fillStyle = "#666";
        ctx.font = "16px monospace";
        ctx.fillText("Failed to load tree data", 20, 40);
      });

    // Wheel zoom — centred on cursor
    function onWheel(e: WheelEvent) {
      e.preventDefault();
      if (!canvas) return;
      const rect   = canvas.getBoundingClientRect();
      const mx     = e.clientX - rect.left;
      const my     = e.clientY - rect.top;
      const { tx, ty, scale } = camRef.current;
      const factor   = e.deltaY < 0 ? 1.15 : 1 / 1.15;
      const newScale = Math.max(0.003, Math.min(0.5, scale * factor));
      const wx = (mx - tx) / scale;
      const wy = (my - ty) / scale;
      camRef.current = {
        tx:    mx - wx * newScale,
        ty:    my - wy * newScale,
        scale: newScale,
      };
      draw();
    }

    canvas.addEventListener("wheel", onWheel, { passive: false });
    return () => canvas.removeEventListener("wheel", onWheel);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function onMouseDown(e: React.MouseEvent) {
    dragRef.current = {
      sx: e.clientX, sy: e.clientY,
      tx: camRef.current.tx, ty: camRef.current.ty,
    };
  }

  function onMouseMove(e: React.MouseEvent) {
    if (!dragRef.current) return;
    camRef.current.tx = dragRef.current.tx + (e.clientX - dragRef.current.sx);
    camRef.current.ty = dragRef.current.ty + (e.clientY - dragRef.current.sy);
    draw();
  }

  function stopDrag() { dragRef.current = null; }

  return (
    <>
      <Navbar />
      <canvas
        ref={canvasRef}
        style={{ display: "block", cursor: "grab" }}
        onMouseDown={onMouseDown}
        onMouseMove={onMouseMove}
        onMouseUp={stopDrag}
        onMouseLeave={stopDrag}
      />
    </>
  );
}
