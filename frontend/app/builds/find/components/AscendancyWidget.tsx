"use client";

/**
 * Maxroll-style ascendancy widget — circular gold-rimmed portrait with the
 * ascendancy name in a banner above, the tier nodes drawn over the portrait
 * (via AscendancyCanvas), and I/II/III/IV tier-dot buttons below.
 *
 * Clicking a tier button highlights only that tier's gold path on the canvas.
 * Clicking the active tier again clears the filter (back to "all tiers shown").
 */

import { useState } from "react";
import { AscendancyCanvas } from "./PassiveTreeCanvasPixi";
import styles from "./ascendancyWidget.module.css";

interface Props {
  className?: string;
  ascendancy: string;
  highlightedNodes?: number[];
  optionalNodes?: number[];
  ascNodes?: number[];
}

const TIER_LABELS = ["I", "II", "III", "IV"] as const;
const TIER_CLASSES = ["tier1", "tier2", "tier3", "tier4"] as const;

export default function AscendancyWidget({
  className,
  ascendancy,
  highlightedNodes = [],
  optionalNodes = [],
  ascNodes = [],
}: Props) {
  const filledTiers = Math.floor((ascNodes.length || 0) / 2);
  const [activeTier, setActiveTier] = useState<number>(0);

  const onTierClick = (i: number) => {
    if (i >= filledTiers) return;
    setActiveTier(i);
  };

  return (
    <div className={styles.wrap}>
      <div className={styles.titleBanner}>
        <span className={styles.titleBannerText}>{ascendancy}</span>
      </div>

      <div className={styles.portrait}>
        <AscendancyCanvas
          className={className}
          ascendancy={ascendancy}
          highlightedNodes={highlightedNodes}
          optionalNodes={optionalNodes}
          ascNodes={ascNodes}
          activeTier={activeTier}
        />
      </div>

      <div className={styles.tierRow}>
        {TIER_LABELS.map((label, i) => {
          const filled = i < filledTiers;
          const isActive = i <= activeTier;
          const cls = [
            styles.tierDot,
            styles[TIER_CLASSES[i]],
            filled ? styles.tierDotFilled : styles.tierDotEmpty,
            isActive ? styles.tierDotActive : "",
          ].filter(Boolean).join(" ");
          return (
            <button
              key={label}
              type="button"
              className={cls}
              onClick={() => onTierClick(i)}
              disabled={!filled}
              aria-pressed={i === activeTier}
              title={filled ? `Highlight tier ${label} path` : `No tier ${label} chosen`}
            >
              {label}
            </button>
          );
        })}
      </div>
    </div>
  );
}
