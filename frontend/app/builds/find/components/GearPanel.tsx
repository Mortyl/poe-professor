"use client";

import { useState } from "react";
import { itemIconPath } from "@/lib/icons";

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
  hasLife?: boolean;
  hasEs?: boolean;
  gearTab?: "life" | "es";
  setGearTab?: (tab: "life" | "es") => void;
}

const SLOT_ORDER = [
  "Weapon 1", "Weapon 2",
  "Body Armour", "Helmet",
  "Gloves", "Boots",
  "Ring 1", "Ring 2",
  "Amulet", "Belt",
];

const SLOT_LABELS: Record<string, string> = {
  "Weapon 1":    "Weapon",
  "Weapon 2":    "Offhand",
  "Helmet":      "Helm",
  "Body Armour": "Body Armour",
  "Gloves":      "Gloves",
  "Boots":       "Boots",
  "Amulet":      "Amulet",
  "Ring 1":      "Ring 1",
  "Ring 2":      "Ring 2",
  "Belt":        "Belt",
};

export default function GearPanel({ data, usefulUniques, hasLife, hasEs, gearTab, setGearTab }: GearPanelProps) {
  const slotMap = Object.fromEntries(data.slots.map(s => [s.slot, s]));
  const slots = SLOT_ORDER.map(name => slotMap[name]).filter(Boolean);

  const rows: GearSlot[][] = [];
  for (let i = 0; i < slots.length; i += 2) {
    rows.push(slots.slice(i, i + 2));
  }

  const hasJewels = (data.top_jewel_bases?.length ?? 0) > 0 || (data.top_jewel_uniques?.length ?? 0) > 0;
  const hasCharms = (data.top_charm_uniques?.length ?? 0) > 0;
  const hasUsefulUniques = (usefulUniques?.length ?? 0) > 0;

  return (
    <div>

      {/* Gear slots */}
      <div style={{ display: "flex", alignItems: "center", gap: "12px", marginBottom: "16px" }}>
        <SectionHead label="Main" style={{ marginBottom: 0, flex: 1 }} />
        {hasLife && hasEs && setGearTab && gearTab && (
          <div style={{ display: "flex", gap: "4px", flexShrink: 0 }}>
            {(["life", "es"] as const).map(tab => (
              <button key={tab} onClick={() => setGearTab(tab)} style={{
                fontFamily: "var(--font-display)",
                fontSize: "11px",
                letterSpacing: "0.18em",
                textTransform: "uppercase",
                padding: "4px 12px",
                background: gearTab === tab ? "var(--amber)" : "transparent",
                border: `1px solid ${gearTab === tab ? "var(--amber)" : "var(--line)"}`,
                color: gearTab === tab ? "var(--bg-deep)" : "var(--text-dim)",
                cursor: "pointer",
              }}>
                {tab === "life" ? "Life" : "Energy Shield"}
              </button>
            ))}
          </div>
        )}
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: "2px" }}>
        {rows.map((row, ri) => (
          <div key={ri} style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "2px" }}>
            {row.map(slot => (
              <SlotCard key={slot.slot} slot={slot} />
            ))}
            {row.length === 1 && <div />}
          </div>
        ))}
      </div>

      {/* Useful Uniques — moved above jewels/charms */}
      {hasUsefulUniques && (
        <div style={{ marginTop: "32px" }}>
          <Collapsible label="Useful Uniques" count={usefulUniques!.length}>
            <div style={{ display: "flex", flexDirection: "column", gap: "2px" }}>
              {usefulUniques!.map((u, i) => (
                <div key={i} style={{ ...cardStyle, borderLeft: "2px solid var(--amber-dim)" }}>
                  <ItemIcon name={u.name} base={u.base} size={40} />
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={headingStyle(true)}>{u.name}</div>
                    <div style={baseStyle}>{u.base} · {u.slot}</div>
                  </div>
                  <div style={pctStyle}>{u.pct.toFixed(1)}%</div>
                </div>
              ))}
            </div>
          </Collapsible>
        </div>
      )}

      {/* Jewels — accent strip */}
      {hasJewels && (
        <div style={{ marginTop: "32px" }}>
          <SectionHead label="Jewels" />
          <div style={stripStyle}>
            {data.top_jewel_bases?.map((j, i) => (
              <ShelfCard
                key={`jb-${i}`}
                kind="rare"
                slotTag={`Jewel · ${i + 1}`}
                name={j.base}
                base={null}
                iconName={null}
                iconBase={j.base}
                mods={j.top_mods}
              />
            ))}
            {data.top_jewel_uniques?.map((u, i) => (
              <ShelfCard
                key={`ju-${i}`}
                kind="unique"
                slotTag={`Jewel · ${(data.top_jewel_bases?.length ?? 0) + i + 1}`}
                name={u.name}
                base={u.base}
                iconName={u.name}
                iconBase={u.base}
              />
            ))}
          </div>
        </div>
      )}

      {/* Charms — accent strip */}
      {hasCharms && (
        <div style={{ marginTop: "32px" }}>
          <SectionHead label="Charms" teal />
          <div style={stripStyle}>
            {data.top_charm_uniques!.map((c, i) => (
              <ShelfCard
                key={`ch-${i}`}
                kind="charm"
                slotTag={`Charm · ${i + 1}`}
                name={c.name}
                base={c.base}
                iconName={c.name}
                iconBase={c.base}
              />
            ))}
          </div>
        </div>
      )}

    </div>
  );
}

// ── Slot card (existing gear slots) ───────────────────────────────────────

function SlotCard({ slot }: { slot: GearSlot }) {
  const isUnique  = !!slot.top_unique;
  const itemName  = isUnique ? slot.top_unique!.name : slot.top_rare_base;
  const baseName  = isUnique ? slot.top_unique!.base : null;
  const label     = SLOT_LABELS[slot.slot] ?? slot.slot;

  return (
    <div style={{
      display: "flex",
      gap: "16px",
      padding: "18px 20px",
      background: "var(--surface)",
      border: "1px solid var(--line)",
      alignItems: "flex-start",
    }}>
      <ItemIcon name={itemName} base={baseName ?? undefined} size={72} />
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{
          fontFamily: "var(--font-serif)",
          fontSize: "16px",
          fontWeight: 600,
          lineHeight: 1.2,
          marginBottom: "6px",
        }}>
          <span style={{
            color: "var(--amber)",
            fontFamily: "var(--font-display)",
            fontSize: "11px",
            letterSpacing: "0.2em",
            textTransform: "uppercase",
            marginRight: "10px",
            fontWeight: 400,
          }}>
            {label}
          </span>
          <span style={{ color: isUnique ? "var(--amber-bright)" : "var(--text)" }}>
            {itemName || "—"}
          </span>
        </div>
        {baseName && <div style={baseStyle}>{baseName}</div>}
        <ModList mods={slot.top_mods} />
      </div>
    </div>
  );
}

// ── Shelf card (jewels / charms accent strip) ──────────────────────────────

type ShelfKind = "rare" | "unique" | "charm";

function ShelfCard({ kind, slotTag, name, base, iconName, iconBase, mods }: {
  kind: ShelfKind;
  slotTag: string;
  name: string | null;
  base: string | null;
  iconName: string | null;
  iconBase: string | null;
  mods?: string[];
}) {
  const accentBar: React.CSSProperties = {
    width: "100%",
    height: "4px",
    flexShrink: 0,
    background:
      kind === "unique" ? "linear-gradient(to right, var(--amber-dim), var(--amber-bright), var(--amber-dim))"
      : kind === "charm" ? "linear-gradient(to right, rgba(91,163,160,0.4), #5ba3a0, rgba(91,163,160,0.4))"
      : "var(--surface-3)",
  };

  const cardBorder = kind === "charm" ? "rgba(91,163,160,0.25)" : "var(--line)";
  const nameColor  = kind === "unique" ? "var(--amber-bright)" : "var(--text)";
  const tagColor   = kind === "charm" ? "#5ba3a0" : "var(--amber)";

  return (
    <div style={{
      width: "120px",
      minWidth: "120px",
      background: "var(--surface)",
      border: `1px solid ${cardBorder}`,
      display: "flex",
      flexDirection: "column",
      alignItems: "center",
      flexShrink: 0,
      overflow: "hidden",
    }}>
      <div style={accentBar} />
      <div style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        padding: "10px 10px 12px",
        flex: 1,
        width: "100%",
        textAlign: "center",
      }}>
        <div style={{
          fontFamily: "var(--font-display)",
          fontSize: "7.5px",
          letterSpacing: "0.2em",
          textTransform: "uppercase",
          color: tagColor,
          marginBottom: "8px",
          opacity: 0.75,
          width: "100%",
          textAlign: "center",
        }}>
          {slotTag}
        </div>
        <ItemIcon name={iconName} base={iconBase} size={56} />
        <div style={{
          fontFamily: "var(--font-serif)",
          fontSize: "12px",
          fontWeight: 600,
          color: nameColor,
          lineHeight: 1.25,
          marginTop: "8px",
          wordBreak: "break-word",
        }}>
          {name || "—"}
        </div>
        {base && (
          <div style={{
            fontFamily: "var(--font-serif)",
            fontSize: "11px",
            fontStyle: "italic",
            color: kind === "charm" ? "rgba(91,163,160,0.7)" : "var(--text-dim)",
            lineHeight: 1.2,
            marginTop: "3px",
          }}>
            {base}
          </div>
        )}
        {mods && mods.length > 0 && (
          <ul style={{
            margin: "8px 0 0",
            padding: 0,
            listStyle: "none",
            display: "flex",
            flexDirection: "column",
            gap: "3px",
            width: "100%",
          }}>
            {mods.slice(0, 2).map((mod, i) => (
              <li key={i} style={{
                fontFamily: "'Inter', sans-serif",
                fontSize: "10px",
                color: "var(--text-dim)",
                lineHeight: 1.4,
                textAlign: "left",
              }}>
                {condenseMod(mod)}
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

// ── Section head (label + gradient line) ─────────────────────────────────

function SectionHead({ label, teal, style }: { label: string; teal?: boolean; style?: React.CSSProperties }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: "12px", marginBottom: "16px", ...style }}>
      <span style={{
        fontFamily: "var(--font-display)",
        fontSize: "10px",
        fontWeight: 500,
        letterSpacing: "0.28em",
        textTransform: "uppercase",
        color: teal ? "#5ba3a0" : "var(--amber)",
        whiteSpace: "nowrap",
      }}>
        {label}
      </span>
      <div style={{
        flex: 1,
        height: "1px",
        background: teal
          ? "linear-gradient(to right, #5ba3a0, transparent)"
          : "linear-gradient(to right, var(--amber-dim), transparent)",
        opacity: teal ? 0.3 : 0.4,
      }} />
    </div>
  );
}

// ── Shared sub-components ─────────────────────────────────────────────────

function ModList({ mods }: { mods: string[] }) {
  if (!mods.length) return null;
  return (
    <ol style={{
      margin: "8px 0 0",
      paddingLeft: "18px",
      fontFamily: "'Inter', sans-serif",
      fontSize: "12px",
      color: "var(--text-dim)",
      lineHeight: 1.7,
      letterSpacing: "0.02em",
    }}>
      {mods.map((mod, i) => <li key={i}>{mod}</li>)}
    </ol>
  );
}

function Collapsible({ label, count, children }: { label: string; count?: number; children: React.ReactNode }) {
  return (
    <details style={{ background: "var(--surface)", border: "1px solid var(--line)" }}>
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
        }}>OPEN ▾</span>
      </summary>
      <div style={{ padding: "0 12px 12px" }}>{children}</div>
    </details>
  );
}

function ItemIcon({ name, base, size }: { name: string | null | undefined; base?: string | null; size: number }) {
  const src = itemIconPath(name, base);
  const [ok, setOk] = useState(true);
  const wrap: React.CSSProperties = {
    width: size, height: size, flexShrink: 0,
    background: "var(--bg-deep)",
    border: "1px solid var(--line)",
    display: "flex", alignItems: "center", justifyContent: "center",
    overflow: "hidden",
  };
  if (!src || !ok) {
    return (
      <div style={wrap}>
        <span style={{ fontFamily: "var(--font-display)", fontSize: "10px", color: "var(--text-faint)" }}>—</span>
      </div>
    );
  }
  return (
    <div style={wrap}>
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img src={src} alt={name ?? base ?? ""} width={size} height={size}
        style={{ width: size, height: size, objectFit: "contain" }}
        onError={() => setOk(false)} />
    </div>
  );
}

function condenseMod(mod: string) {
  return mod.replace(/\bincreased\b/gi, "").replace(/\brecover\b/gi, "").replace(/\s{2,}/g, " ").trim();
}

// ── Shared styles ─────────────────────────────────────────────────────────

const stripStyle: React.CSSProperties = {
  display: "flex",
  flexDirection: "row",
  gap: "10px",
  overflowX: "auto",
  paddingBottom: "10px",
  scrollbarWidth: "thin",
  scrollbarColor: "var(--surface-3) transparent",
};

const cardStyle: React.CSSProperties = {
  display: "flex",
  gap: "14px",
  alignItems: "center",
  padding: "12px 16px",
  background: "var(--surface)",
  border: "1px solid var(--line)",
};

const pctStyle: React.CSSProperties = {
  fontFamily: "var(--font-mono)",
  fontSize: "10px",
  color: "var(--text-faint)",
  letterSpacing: "0.08em",
  whiteSpace: "nowrap",
  alignSelf: "flex-start",
  paddingTop: "2px",
};

const baseStyle: React.CSSProperties = {
  fontFamily: "var(--font-serif)",
  fontSize: "12px",
  fontStyle: "italic",
  color: "var(--text-dim)",
  marginBottom: "2px",
};

function headingStyle(isUnique: boolean): React.CSSProperties {
  return {
    fontFamily: "var(--font-serif)",
    fontSize: "15px",
    fontWeight: 600,
    color: isUnique ? "var(--amber-bright)" : "var(--text)",
    lineHeight: 1.25,
  };
}
