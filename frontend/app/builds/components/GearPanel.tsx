"use client";

import { useState } from "react";
import { itemIconPath } from "./icons";

interface UniqueItem {
  name: string;
  base: string;
  slot: string;
  pct: number;
}

interface GearSlot {
  slot: string;
  top_unique: UniqueItem | null;
  top_rare_base: string;
  top_rare_base_pct: number;
  top_mods: string[];
}

interface JewelBase {
  base: string;
  pct: number;
  top_mods: string[];
}

interface GearData {
  builds_analysed: number;
  slots: GearSlot[];
  top_charm_uniques?: UniqueItem[];
  top_jewel_bases?: JewelBase[];
  top_jewel_uniques?: UniqueItem[];
}

interface GearPanelProps {
  data: GearData;
  usefulUniques?: UniqueItem[];
}

// PoE2 doll layout — 5 cols x 4 rows.
// Vertical cards (icon on top, text below) — bigger icons on row-spanning cards
// soak up the extra height. Belt/boots are normal cells below.
const SLOT_LAYOUT: Record<string, { row: number; col: string; rowSpan?: number; iconSize?: number; compact?: boolean }> = {
  "Weapon 1":    { row: 1, col: "1", rowSpan: 2, iconSize: 200 },
  "Helmet":      { row: 1, col: "3" },
  "Weapon 2":    { row: 1, col: "5", rowSpan: 2, iconSize: 200 },
  "Ring 1":      { row: 2, col: "2" },
  "Body Armour": { row: 2, col: "3", rowSpan: 2, iconSize: 160 },
  "Amulet":      { row: 2, col: "4" },
  "Gloves":      { row: 3, col: "2" },
  "Ring 2":      { row: 3, col: "4" },
  "Belt":        { row: 4, col: "1" },
  "Charm 1":     { row: 4, col: "2", iconSize: 48, compact: true },
  "Charm 2":     { row: 4, col: "3", iconSize: 48, compact: true },
  "Charm 3":     { row: 4, col: "4", iconSize: 48, compact: true },
  "Boots":       { row: 4, col: "5" },
};

const SLOT_LABELS: Record<string, string> = {
  "Weapon 1":    "Weapon",
  "Weapon 2":    "Offhand",
  "Helmet":      "Helmet",
  "Body Armour": "Body Armour",
  "Gloves":      "Gloves",
  "Boots":       "Boots",
  "Amulet":      "Amulet",
  "Ring 1":      "Ring 1",
  "Ring 2":      "Ring 2",
  "Belt":        "Belt",
  "Charm 1":     "Charm 1",
  "Charm 2":     "Charm 2",
  "Charm 3":     "Charm 3",
};

const GRID_WIDTH = 1080;         // 5 cols × ~200px
const ICON_SIZE  = 80;           // default; row-spanning cells override via SLOT_LAYOUT.iconSize

export default function GearPanel({ data, usefulUniques }: GearPanelProps) {
  const slotMap = Object.fromEntries(data.slots.map(s => [s.slot, s]));

  return (
    <div>
      <div style={{
        fontFamily: "var(--font-mono)",
        fontSize: "11px",
        color: "var(--text-faint)",
        letterSpacing: "0.12em",
        textTransform: "uppercase",
        marginBottom: "16px",
      }}>
        Based on {data.builds_analysed.toLocaleString()} real builds
      </div>

      <div style={{ display: "flex", gap: "20px", alignItems: "flex-start", flexWrap: "wrap" }}>

        {/* Left: gear doll + charms */}
        <div style={{ flex: "0 0 auto" }}>
          <div style={{
            display: "grid",
            gridTemplateColumns: "repeat(5, 1fr)",
            gridAutoRows: "minmax(120px, auto)",
            gap: "10px",
            width: `${GRID_WIDTH}px`,
            maxWidth: "100%",
          }}>
            {Object.entries(SLOT_LAYOUT).map(([slotName, pos]) => (
              <SlotCell
                key={slotName}
                label={SLOT_LABELS[slotName]}
                slot={slotMap[slotName] ?? null}
                gridRow={pos.row}
                gridCol={pos.col}
                rowSpan={pos.rowSpan}
                iconSize={pos.iconSize ?? ICON_SIZE}
                compact={pos.compact}
              />
            ))}
          </div>
        </div>

        {/* Right: Useful Uniques (collapsed by default) */}
        {(usefulUniques?.length ?? 0) > 0 && (
          <div style={{ flex: "1 1 320px", minWidth: "320px" }}>
            <Collapsible label="Useful Uniques" count={usefulUniques!.length}>
              <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
                {usefulUniques!.map((u, i) => (
                  <UniqueRow key={i} unique={u} />
                ))}
              </div>
            </Collapsible>
          </div>
        )}
      </div>

      {/* Optional unique charms (collapsed by default) */}
      {(data.top_charm_uniques?.length ?? 0) > 0 && (
        <div style={{ maxWidth: `${GRID_WIDTH}px`, marginTop: "20px" }}>
          <Collapsible label="Optional Unique Charms" count={data.top_charm_uniques!.length}>
            <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
              {data.top_charm_uniques!.map((u, i) => (
                <UniqueRow key={i} unique={u} />
              ))}
            </div>
          </Collapsible>
        </div>
      )}

      {/* Jewels */}
      {((data.top_jewel_bases?.length ?? 0) > 0 || (data.top_jewel_uniques?.length ?? 0) > 0) && (
        <div style={{ maxWidth: `${GRID_WIDTH}px`, marginTop: "20px" }}>
          <SectionLabel>Jewels</SectionLabel>

          {(data.top_jewel_bases?.length ?? 0) > 0 && (
            <div style={{ display: "flex", flexDirection: "column", gap: "8px", marginBottom: "12px" }}>
              {data.top_jewel_bases!.map((j, i) => (
                <div key={i} style={cardStyle()}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
                    <span style={{ fontFamily: "var(--font-serif)", fontSize: "15px", fontWeight: 600, color: "var(--text)" }}>
                      {j.base}
                    </span>
                    <span style={{ fontFamily: "var(--font-mono)", fontSize: "10px", color: "var(--text-faint)", letterSpacing: "0.08em" }}>
                      {j.pct.toFixed(1)}% of builds
                    </span>
                  </div>
                  {j.top_mods.length > 0 && (
                    <div style={modsBlockStyle()}>
                      {j.top_mods.map((mod, mi) => (
                        <div key={mi}>+ {mod}</div>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}

          {(data.top_jewel_uniques?.length ?? 0) > 0 && (
            <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
              {data.top_jewel_uniques!.map((u, i) => (
                <UniqueRow key={i} unique={u} />
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ── Building blocks ───────────────────────────────────────────────────────

function Collapsible({ label, count, children }: { label: string; count?: number; children: React.ReactNode }) {
  return (
    <details style={{
      background: "var(--surface)",
      border: "1px solid var(--line)",
    }}>
      <summary style={{
        cursor: "pointer",
        listStyle: "none",
        padding: "12px 16px",
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        userSelect: "none",
      }}>
        <span style={{
          fontFamily: "var(--font-display)",
          fontSize: "11px",
          color: "var(--amber)",
          letterSpacing: "0.24em",
          textTransform: "uppercase",
        }}>
          {label}
          {count !== undefined && (
            <span style={{ color: "var(--amber-dim)", marginLeft: "8px" }}>{count}</span>
          )}
        </span>
        <span aria-hidden style={{
          fontFamily: "var(--font-display)",
          fontSize: "10px",
          color: "var(--amber-dim)",
          letterSpacing: "0.1em",
        }}>
          OPEN ▾
        </span>
      </summary>
      <div style={{ padding: "0 12px 12px" }}>
        {children}
      </div>
    </details>
  );
}

function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <div style={{
      fontFamily: "var(--font-display)",
      fontSize: "10px",
      color: "var(--amber)",
      letterSpacing: "0.24em",
      textTransform: "uppercase",
      marginBottom: "10px",
    }}>
      {children}
    </div>
  );
}

function cardStyle(): React.CSSProperties {
  return {
    background: "var(--surface)",
    border: "1px solid var(--line)",
    padding: "14px 16px",
  };
}

function modsBlockStyle(): React.CSSProperties {
  return {
    marginTop: "8px",
    fontFamily: "var(--font-mono)",
    fontSize: "11px",
    color: "var(--text-dim)",
    lineHeight: 1.55,
    letterSpacing: "0.02em",
  };
}

function ItemIcon({ name, base, size }: { name: string | null | undefined; base?: string | null; size: number }) {
  const src = itemIconPath(name, base);
  const [ok, setOk] = useState(true);
  const wrapStyle: React.CSSProperties = {
    width: size,
    height: size,
    flexShrink: 0,
    background: "var(--bg-deep)",
    border: "1px solid var(--line)",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    overflow: "hidden",
  };
  if (!src || !ok) {
    return (
      <div style={wrapStyle}>
        <span style={{
          fontFamily: "var(--font-display)",
          fontSize: "11px",
          color: "var(--text-faint)",
          letterSpacing: "0.1em",
        }}>—</span>
      </div>
    );
  }
  return (
    <div style={wrapStyle}>
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src={src}
        alt={name ?? base ?? ""}
        width={size}
        height={size}
        style={{ width: size, height: size, objectFit: "contain" }}
        onError={() => setOk(false)}
      />
    </div>
  );
}

function SlotCell({ label, slot, gridRow, gridCol, rowSpan, iconSize = ICON_SIZE, compact = false }: { label: string; slot: GearSlot | null; gridRow?: number; gridCol?: number | string; rowSpan?: number; iconSize?: number; compact?: boolean }) {
  const useUnique = !!slot?.top_unique;
  const itemName  = useUnique ? slot!.top_unique!.name : (slot?.top_rare_base || null);
  const baseName  = useUnique ? slot!.top_unique!.base : slot?.top_rare_base;
  const pct       = useUnique ? slot?.top_unique?.pct : slot?.top_rare_base_pct;

  return (
    <div style={{
      gridRow: rowSpan ? `${gridRow} / span ${rowSpan}` : gridRow,
      gridColumn: gridCol,
      ...cardStyle(),
      display: "flex",
      flexDirection: "column",
      gap: "10px",
      justifyContent: "center",   // centre content vertically so empty space splits top/bottom
    }}>
      <div style={{
        fontFamily: "var(--font-display)",
        fontSize: "10px",
        color: "var(--amber)",
        letterSpacing: "0.2em",
        textTransform: "uppercase",
        textAlign: "center",
      }}>
        {label}
      </div>

      {slot ? (
        <div style={{ display: "flex", flexDirection: "column", alignItems: "stretch", gap: compact ? "6px" : "10px" }}>
          <div style={{ display: "flex", justifyContent: "center" }}>
            <ItemIcon name={itemName} base={baseName} size={iconSize} />
          </div>
          <div style={{ minWidth: 0 }}>
            <div style={{
              fontFamily: "var(--font-serif)",
              fontSize: compact ? "13px" : "16px",
              fontWeight: 600,
              color: useUnique ? "var(--amber-bright)" : "var(--text)",
              lineHeight: 1.25,
              marginBottom: "3px",
              textAlign: "center",
            }}>
              {itemName ?? "—"}
            </div>
            {useUnique && baseName && !compact && (
              <div style={{
                fontFamily: "var(--font-serif)",
                fontSize: "13px",
                fontStyle: "italic",
                color: "var(--text-dim)",
                marginBottom: "4px",
                textAlign: "center",
              }}>
                {baseName}
                {pct !== undefined && pct > 0 && (
                  <span style={{ color: "var(--text-faint)" }}> · {pct.toFixed(1)}%</span>
                )}
              </div>
            )}
            {!useUnique && !compact && slot.top_mods.length > 0 && (
              <div style={modsBlockStyle()}>
                {slot.top_mods.map((mod, i) => (
                  <div key={i}>+ {mod}</div>
                ))}
              </div>
            )}
          </div>
        </div>
      ) : (
        <div style={{
          fontFamily: "var(--font-serif)",
          fontSize: "13px",
          fontStyle: "italic",
          color: "var(--text-faint)",
        }}>
          no data
        </div>
      )}
    </div>
  );
}

function UniqueRow({ unique }: { unique: UniqueItem }) {
  return (
    <div style={{
      ...cardStyle(),
      display: "flex",
      gap: "12px",
      alignItems: "center",
      borderLeft: "2px solid var(--amber)",
    }}>
      <ItemIcon name={unique.name} base={unique.base} size={40} />
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{
          fontFamily: "var(--font-serif)",
          fontSize: "14px",
          fontWeight: 600,
          color: "var(--amber-bright)",
          lineHeight: 1.25,
        }}>
          {unique.name}
        </div>
        <div style={{
          fontFamily: "var(--font-serif)",
          fontSize: "12px",
          fontStyle: "italic",
          color: "var(--text-dim)",
        }}>
          {unique.base}{unique.slot ? ` · ${unique.slot}` : ""}
        </div>
      </div>
      <div style={{
        fontFamily: "var(--font-mono)",
        fontSize: "11px",
        color: "var(--amber-dim)",
        letterSpacing: "0.08em",
        whiteSpace: "nowrap",
      }}>
        {unique.pct.toFixed(1)}%
      </div>
    </div>
  );
}
