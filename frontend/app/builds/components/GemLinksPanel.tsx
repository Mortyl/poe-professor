"use client";

interface GemEntry {
  name: string;
  pct: number;
}

interface SkillGem {
  name: string;
  pct: number;
  supports: GemEntry[];
}

interface GemLinkData {
  main_skill: string;
  skill_gems: SkillGem[];
  builds_analysed: number;
}

interface GemLinksPanelProps {
  data: GemLinkData;
}

// CDN icon URLs for active skills — add more as we scrape new skill/ascendancy combos
const SKILL_ICONS: Record<string, string> = {
  "Lightning Arrow":  "https://web.poecdn.com/gen/image/WzI1LDE0LHsiZiI6IjJESXRlbXMvR2Vtcy9OZXcvTGlnaHRuaW5nQXJyb3dTa2lsbEdlbSIsInciOjEsImgiOjEsInNjYWxlIjoxLCJyZWFsbSI6InBvZTIifV0/f803440d2b/LightningArrowSkillGem.png",
  "Lightning Rod":    "https://web.poecdn.com/gen/image/WzI1LDE0LHsiZiI6IjJESXRlbXMvR2Vtcy9OZXcvUmFuZ2VyTGlnaHRuaW5nUm9kUmFpblNraWxsR2VtIiwidyI6MSwiaCI6MSwic2NhbGUiOjEsInJlYWxtIjoicG9lMiJ9XQ/dbb4597574/RangerLightningRodRainSkillGem.png",
  "Herald of Thunder":"https://web.poecdn.com/gen/image/WzI1LDE0LHsiZiI6IjJESXRlbXMvR2Vtcy9OZXcvSGVyYWxkb2ZUaHVuZGVyU2tpbGxHZW0iLCJ3IjoxLCJoIjoxLCJzY2FsZSI6MSwicmVhbG0iOiJwb2UyIn1d/23b055fe42/HeraldofThunderSkillGem.png",
  "Tornado Shot":     "https://web.poecdn.com/gen/image/WzI1LDE0LHsiZiI6IjJESXRlbXMvR2Vtcy9OZXcvVG9ybmFkb1Nob3RTa2lsbEdlbSIsInciOjEsImgiOjEsInNjYWxlIjoxLCJyZWFsbSI6InBvZTIifV0/f00738255a/TornadoShotSkillGem.png",
  "Rhoa Mount":       "https://web.poecdn.com/gen/image/WzI1LDE0LHsiZiI6IjJESXRlbXMvR2Vtcy9OZXcvUmhvYU1vdW50U2tpbGxHZW0iLCJ3IjoxLCJoIjoxLCJzY2FsZSI6MSwicmVhbG0iOiJwb2UyIn1d/a3d95a51d6/RhoaMountSkillGem.png",
  "Barrage":          "https://web.poecdn.com/gen/image/WzI1LDE0LHsiZiI6IjJESXRlbXMvR2Vtcy9OZXcvUmFuZ2VyQmFycmFnZVNraWxsR2VtIiwidyI6MSwiaCI6MSwic2NhbGUiOjEsInJlYWxtIjoicG9lMiJ9XQ/9fc9ce784a/RangerBarrageSkillGem.png",
  "Mirage Deadeye":   "https://web.poecdn.com/gen/image/WzI1LDE0LHsiZiI6IjJESXRlbXMvR2Vtcy9OZXcvTGluZ2VyaW5nTWlyYWdlU2tpbGxHZW0iLCJ3IjoxLCJoIjoxLCJzY2FsZSI6MSwicmVhbG0iOiJwb2UyIn1d/e8d75b6e9f/LingeringMirageSkillGem.png",
  "Wind Dancer":      "https://web.poecdn.com/gen/image/WzI1LDE0LHsiZiI6IjJESXRlbXMvR2Vtcy9OZXcvV2luZERhbmNlclNraWxsR2VtIiwidyI6MSwiaCI6MSwic2NhbGUiOjEsInJlYWxtIjoicG9lMiJ9XQ/9205945635/WindDancerSkillGem.png",
};

export default function GemLinksPanel({ data }: GemLinksPanelProps) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
      <div style={{ fontSize: "11px", color: "#666", letterSpacing: "0.05em", marginBottom: "6px" }}>
        Based on {data.builds_analysed.toLocaleString()} real builds
      </div>

      {data.skill_gems.map((skill, i) => (
        <SkillRow
          key={i}
          skill={{ ...skill, supports: skill.supports.filter(s => s.pct >= 20) }}
          isMain={skill.name === data.main_skill}
        />
      ))}
    </div>
  );
}

const SKILL_COLOR = "#d0cfc8";

function SkillRow({ skill, isMain }: { skill: SkillGem; isMain: boolean }) {
  const iconUrl = SKILL_ICONS[skill.name];

  return (
    <div style={{
      display: "flex",
      alignItems: "center",
      gap: "10px",
      background: "linear-gradient(90deg, #1a1410 0%, #16120c 100%)",
      border: `1px solid ${isMain ? "#3a3330" : "#251e12"}`,
      borderLeft: `3px solid ${SKILL_COLOR}`,
      borderRadius: "4px",
      padding: "8px 12px",
    }}>
      {/* Skill gem */}
      <div style={{ display: "flex", alignItems: "center", gap: "8px", width: "180px", flexShrink: 0 }}>
        <GemCircle color={SKILL_COLOR} letter={skill.name[0]} size={32} iconUrl={iconUrl} />
        <div>
          <div style={{
            color: SKILL_COLOR,
            fontSize: "12px",
            fontWeight: 600,
            fontFamily: "var(--font-cinzel, serif)",
            lineHeight: 1.2,
          }}>
            {skill.name}
          </div>
          <div style={{ color: "#666", fontSize: "10px" }}>
            {skill.pct.toFixed(0)}% of builds
          </div>
        </div>
      </div>

      {/* Divider */}
      <div style={{ width: "1px", alignSelf: "stretch", background: "#2a2010", flexShrink: 0 }} />

      {/* Support gems */}
      <div style={{ display: "flex", alignItems: "center", gap: "6px", flexWrap: "wrap" }}>
        {skill.supports.length > 0 ? (
          skill.supports.map((sup, j) => (
            <SupportChip key={j} gem={sup} />
          ))
        ) : (
          <span style={{ color: "#444", fontSize: "11px", fontStyle: "italic" }}>
            no support data
          </span>
        )}
      </div>
    </div>
  );
}

function SupportChip({ gem }: { gem: GemEntry }) {
  const isOptional = gem.pct < 30;
  const color = isOptional ? "#9b6fd4" : getAdoptionColor(gem.pct);
  return (
    <div style={{
      display: "flex",
      alignItems: "center",
      gap: "5px",
      background: "#0e0c08",
      border: `1px solid ${isOptional ? "#3a2a5a" : "#2a2010"}`,
      borderRadius: "20px",
      padding: "3px 8px 3px 4px",
    }}>
      <GemCircle color={color} letter={gem.name[0]} size={20} />
      <span style={{ color: isOptional ? "#a890c8" : "#c8bfa8", fontSize: "10px", whiteSpace: "nowrap" }}>
        {gem.name}
      </span>
      {isOptional && (
        <span style={{
          color: "#7a5a9a",
          fontSize: "9px",
          fontStyle: "italic",
          whiteSpace: "nowrap",
        }}>
          opt
        </span>
      )}
      <span style={{ color: color, fontSize: "10px", fontWeight: 600 }}>
        {gem.pct.toFixed(0)}%
      </span>
    </div>
  );
}

function GemCircle({
  color,
  letter,
  size,
  iconUrl,
}: {
  color: string;
  letter: string;
  size: number;
  iconUrl?: string;
}) {
  if (iconUrl) {
    return (
      <div style={{
        width:        `${size}px`,
        height:       `${size}px`,
        borderRadius: "50%",
        border:       `1.5px solid ${color}`,
        boxShadow:    `0 0 6px ${color}44`,
        flexShrink:   0,
        overflow:     "hidden",
        background:   "#110e06",
      }}>
        <img
          src={iconUrl}
          alt=""
          width={size}
          height={size}
          style={{ display: "block", width: "100%", height: "100%", objectFit: "cover" }}
          onError={(e) => {
            // Fallback to letter circle if CDN fails
            const el = e.currentTarget.parentElement!;
            el.innerHTML = letter;
            el.style.display = "flex";
            el.style.alignItems = "center";
            el.style.justifyContent = "center";
            el.style.color = "#fff";
            el.style.fontSize = `${Math.round(size * 0.42)}px`;
            el.style.fontWeight = "700";
          }}
        />
      </div>
    );
  }

  return (
    <div style={{
      width:        `${size}px`,
      height:       `${size}px`,
      borderRadius: "50%",
      background:   `radial-gradient(circle at 35% 35%, ${lighten(color)}, #110e06)`,
      border:       `1.5px solid ${color}`,
      boxShadow:    `0 0 6px ${color}44`,
      display:      "flex",
      alignItems:   "center",
      justifyContent: "center",
      flexShrink:   0,
      color:        "#fff",
      fontSize:     `${Math.round(size * 0.42)}px`,
      fontWeight:   700,
      fontFamily:   "var(--font-cinzel, serif)",
      userSelect:   "none",
    }}>
      {letter}
    </div>
  );
}

function getAdoptionColor(pct: number): string {
  if (pct >= 60) return "#4abecc";
  if (pct >= 30) return "#8fbc5a";
  return "#c8a84a";
}

function lighten(hex: string): string {
  const map: Record<string, string> = {
    "#d0cfc8": "#eceae4",
    "#4abecc": "#7dd8e4",
    "#8fbc5a": "#b0d87a",
    "#c8a84a": "#e8c870",
    "#9b6fd4": "#c4a0f0",
  };
  return map[hex] ?? hex;
}
