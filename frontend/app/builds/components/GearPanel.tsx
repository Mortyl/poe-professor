"use client";

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

// PoE2 equipment layout — positions in a CSS grid (rows x cols, 1-indexed)
// Grid is 7 cols x 6 rows
const SLOT_LAYOUT: Record<string, { row: number; col: number; rowSpan?: number; colSpan?: number }> = {
  "Weapon 1":    { row: 1, col: 1, rowSpan: 3 },
  "Helmet":      { row: 1, col: 3 },
  "Weapon 2":    { row: 1, col: 5, rowSpan: 3 },
  "Ring 1":      { row: 2, col: 2 },
  "Body Armour": { row: 2, col: 3, rowSpan: 2 },
  "Amulet":      { row: 2, col: 4 },
  "Gloves":      { row: 4, col: 1 },
  "Ring 2":      { row: 3, col: 4 },
  "Boots":       { row: 4, col: 5 },
  "Belt":        { row: 4, col: 3 },
};

const CHARM_SLOTS = ["Charm 1", "Charm 2", "Charm 3"];

const SLOT_LABELS: Record<string, string> = {
  "Weapon 1":    "Weapon",
  "Weapon 2":    "Offhand",
  "Helmet":      "Helmet",
  "Body Armour": "Body",
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

export default function GearPanel({ data, usefulUniques }: GearPanelProps) {
  const slotMap = Object.fromEntries(data.slots.map(s => [s.slot, s]));

  const hasAnyCharm = CHARM_SLOTS.some(c => slotMap[c]);

  return (
    <div>
      <div style={{ fontSize: "11px", color: "#666", letterSpacing: "0.05em", marginBottom: "12px" }}>
        Based on {data.builds_analysed.toLocaleString()} real builds
      </div>

      {/* Gear grid + Useful Uniques side by side */}
      <div style={{ display: "flex", gap: "16px", alignItems: "flex-start" }}>

        {/* Left: gear grid + charms */}
        <div style={{ flex: "0 0 auto" }}>
          <div style={{
            display: "grid",
            gridTemplateColumns: "repeat(5, 1fr)",
            gridTemplateRows: "repeat(4, auto)",
            gap: "6px",
            width: "560px",
          }}>
            {Object.entries(SLOT_LAYOUT).map(([slotName, pos]) => {
              const slot = slotMap[slotName];
              return (
                <SlotCell
                  key={slotName}
                  label={SLOT_LABELS[slotName]}
                  slot={slot ?? null}
                  rowSpan={pos.rowSpan}
                />
              );
            })}
          </div>

          {/* Charms */}
          {hasAnyCharm && (
            <div style={{ marginTop: "10px" }}>
              <div style={{
                fontSize: "10px",
                color: "#555",
                letterSpacing: "0.08em",
                textTransform: "uppercase",
                marginBottom: "6px",
              }}>
                Charms
              </div>
              <div style={{
                display: "grid",
                gridTemplateColumns: "repeat(3, 1fr)",
                gap: "6px",
                width: "560px",
              }}>
                {CHARM_SLOTS.map(slotName => (
                  <SlotCell
                    key={slotName}
                    label={SLOT_LABELS[slotName]}
                    slot={slotMap[slotName] ?? null}
                  />
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Right: Useful Uniques */}
        {(usefulUniques?.length ?? 0) > 0 && (
          <div style={{ flex: "1 1 auto", minWidth: 0 }}>
            <div style={{
              fontSize: "10px",
              color: "#555",
              letterSpacing: "0.08em",
              textTransform: "uppercase",
              marginBottom: "6px",
            }}>
              Useful Uniques
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
              {usefulUniques!.map((u, i) => (
                <div key={i} style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  background: "linear-gradient(90deg, #1a1208 0%, #16120c 100%)",
                  border: "1px solid #3a2e1a",
                  borderLeft: "3px solid #c8a84a",
                  borderRadius: "4px",
                  padding: "8px 12px",
                }}>
                  <div>
                    <div style={{ color: "#c8a84a", fontSize: "13px", fontWeight: 600, fontFamily: "var(--font-cinzel, serif)" }}>
                      {u.name}
                    </div>
                    <div style={{ color: "#666", fontSize: "10px" }}>{u.base} · {u.slot}</div>
                  </div>
                  <div style={{ color: "#8a7040", fontSize: "11px", fontWeight: 600, whiteSpace: "nowrap", marginLeft: "8px" }}>
                    {u.pct.toFixed(1)}%
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Optional unique charms */}
      {(data.top_charm_uniques?.length ?? 0) > 0 && (
        <div style={{ maxWidth: "560px", marginTop: "14px" }}>
          <div style={{
            fontSize: "10px",
            color: "#666",
            letterSpacing: "0.08em",
            textTransform: "uppercase",
            marginBottom: "6px",
          }}>
            Optional Unique Charms
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
            {data.top_charm_uniques!.map((u, i) => (
              <div key={i} style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                background: "linear-gradient(90deg, #1a1208 0%, #16120c 100%)",
                border: "1px solid #3a2e1a",
                borderLeft: "3px solid #c8a84a",
                borderRadius: "4px",
                padding: "6px 10px",
              }}>
                <div>
                  <div style={{ color: "#c8a84a", fontSize: "12px", fontWeight: 600, fontFamily: "var(--font-cinzel, serif)" }}>
                    {u.name}
                  </div>
                  <div style={{ color: "#555", fontSize: "10px" }}>{u.base}</div>
                </div>
                <div style={{ color: "#8a7040", fontSize: "11px", fontWeight: 600 }}>
                  {u.pct.toFixed(1)}%
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Jewels */}
      {((data.top_jewel_bases?.length ?? 0) > 0 || (data.top_jewel_uniques?.length ?? 0) > 0) && (
        <div style={{ maxWidth: "560px", marginTop: "14px" }}>
          <div style={{
            fontSize: "10px",
            color: "#666",
            letterSpacing: "0.08em",
            textTransform: "uppercase",
            marginBottom: "6px",
          }}>
            Jewels
          </div>

          {/* Magic jewel bases */}
          {(data.top_jewel_bases?.length ?? 0) > 0 && (
            <div style={{ display: "flex", flexDirection: "column", gap: "4px", marginBottom: "8px" }}>
              {data.top_jewel_bases!.map((j, i) => (
                <div key={i} style={{
                  background: "linear-gradient(160deg, #0e1a14 0%, #0a120e 100%)",
                  border: "1px solid #1e2e22",
                  borderTop: "2px solid #4a9a6a",
                  borderRadius: "4px",
                  padding: "8px",
                }}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                    <span style={{ color: "#6aba8a", fontSize: "12px", fontFamily: "var(--font-cinzel, serif)", fontWeight: 600 }}>
                      {j.base}
                    </span>
                    <span style={{ color: "#3a6a4a", fontSize: "10px", fontWeight: 600 }}>
                      {j.pct.toFixed(1)}% of builds
                    </span>
                  </div>
                  {j.top_mods.length > 0 && (
                    <div style={{ marginTop: "4px", display: "flex", flexDirection: "column", gap: "2px" }}>
                      {j.top_mods.map((mod, mi) => (
                        <div key={mi} style={{ color: "#7a9aaa", fontSize: "9px", lineHeight: 1.3 }}>{mod}</div>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}

          {/* Unique jewels */}
          {(data.top_jewel_uniques?.length ?? 0) > 0 && (
            <div style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
              {data.top_jewel_uniques!.map((u, i) => (
                <div key={i} style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  background: "linear-gradient(90deg, #1a1208 0%, #16120c 100%)",
                  border: "1px solid #3a2e1a",
                  borderLeft: "3px solid #c8a84a",
                  borderRadius: "4px",
                  padding: "6px 10px",
                }}>
                  <div>
                    <div style={{ color: "#c8a84a", fontSize: "12px", fontWeight: 600, fontFamily: "var(--font-cinzel, serif)" }}>
                      {u.name}
                    </div>
                    <div style={{ color: "#555", fontSize: "10px" }}>{u.base}</div>
                  </div>
                  <div style={{ color: "#8a7040", fontSize: "11px", fontWeight: 600 }}>
                    {u.pct.toFixed(1)}%
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

    </div>
  );
}

function SlotCell({ label, slot, rowSpan }: { label: string; slot: GearSlot | null; rowSpan?: number }) {
  const useUnique   = !!slot?.top_unique;
  const accentColor = useUnique ? "#c8a84a" : "#4a7a8a";
  const baseName    = useUnique ? slot!.top_unique!.name : (slot?.top_rare_base || "—");
  const basePct     = useUnique ? slot?.top_unique?.pct  : slot?.top_rare_base_pct;

  return (
    <div style={{
      gridRow: rowSpan ? `span ${rowSpan}` : undefined,
      background: "linear-gradient(160deg, #1a1410 0%, #12100c 100%)",
      border: "1px solid #1e1e18",
      borderTop: `2px solid ${accentColor}`,
      borderRadius: "4px",
      padding: "8px",
      display: "flex",
      flexDirection: "column",
      gap: "4px",
      minHeight: rowSpan ? `${rowSpan * 90}px` : "90px",
    }}>
      {/* Slot label */}
      <div style={{ fontSize: "9px", color: "#555", letterSpacing: "0.08em", textTransform: "uppercase" }}>
        {label}
      </div>

      {slot ? (
        <>
          {/* Item name */}
          <div style={{
            color: accentColor,
            fontSize: "11px",
            fontWeight: 600,
            fontFamily: "var(--font-cinzel, serif)",
            lineHeight: 1.3,
          }}>
            {baseName}
          </div>

          {/* % of builds */}
          {basePct !== undefined && basePct > 0 && (
            <div style={{ color: "#555", fontSize: "9px" }}>
              {basePct.toFixed(1)}% of builds
            </div>
          )}

          {/* Top mods — only show for rares */}
          {!useUnique && slot.top_mods.length > 0 && (
            <div style={{ marginTop: "4px", display: "flex", flexDirection: "column", gap: "2px" }}>
              {slot.top_mods.map((mod, i) => (
                <div key={i} style={{ color: "#7a9aaa", fontSize: "9px", lineHeight: 1.3 }}>
                  {mod}
                </div>
              ))}
            </div>
          )}
        </>
      ) : (
        <div style={{ color: "#333", fontSize: "10px", fontStyle: "italic" }}>no data</div>
      )}
    </div>
  );
}
