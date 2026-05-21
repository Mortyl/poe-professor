"use client";

import { useState } from "react";
import Navbar from "../components/Navbar";
import { goalsForClass, type CommonGoal } from "./common-goals";
import styles from "./crafting.module.css";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// ── Wire types matching backend Pydantic models ────────────────────────────

interface ParsedItem {
  item_class: string;
  rarity: string;
  name: string;
  base_type: string;
  item_level: number;
  quality: number;
  implicits: string[];
  explicit_mods: string[];
  corrupted: boolean;
  mirrored: boolean;
  warnings: string[];
}

interface RecipeStep {
  verb: string;
  currency: string | null;
  qty: number;
  outcome: string;
}

interface Recipe {
  id: string;
  name: string;
  description: string;
  guaranteed_mod_families: string[];
  rollable_mod_families: string[];
  steps: RecipeStep[];
  estimated_cost_chaos_range: [number, number];
  estimated_success_pct: number | null;
  notes_for_user: string;
  skill_floor: string;
  coverage_score: number;
  guaranteed_coverage: number;
  rollable_coverage: number;
  live_cost_chaos: number | null;
}

interface AnalyseResponse {
  item: ParsedItem;
  recipes: Recipe[];
  no_recipes_reason: string | null;
}

// ── Page ───────────────────────────────────────────────────────────────────

export default function CraftingPage() {
  const [itemText, setItemText] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [response, setResponse] = useState<AnalyseResponse | null>(null);
  const [selectedGoalId, setSelectedGoalId] = useState<string | null>(null);
  const [expandedRecipeId, setExpandedRecipeId] = useState<string | null>(null);

  /** Run an analysis with the current text + an optional target goal. */
  async function runAnalysis(goal: CommonGoal | null) {
    if (!itemText.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const r = await fetch(`${API_URL}/api/crafting/analyse`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          item_text: itemText,
          target_mod_groups: goal ? goal.families : [],
          top_n: 3,
        }),
      });
      if (!r.ok) {
        const e = await r.json().catch(() => ({ detail: "Unknown error" }));
        setError(e.detail || "Failed to parse item.");
        setResponse(null);
      } else {
        const data: AnalyseResponse = await r.json();
        setResponse(data);
        setExpandedRecipeId(null);
      }
    } catch (e) {
      setError((e as Error).message);
      setResponse(null);
    } finally {
      setLoading(false);
    }
  }

  const goals = response ? goalsForClass(response.item.item_class) : [];

  function selectGoal(goal: CommonGoal | null) {
    setSelectedGoalId(goal?.id ?? null);
    runAnalysis(goal);
  }

  function resetAll() {
    setItemText("");
    setResponse(null);
    setSelectedGoalId(null);
    setExpandedRecipeId(null);
    setError(null);
  }

  return (
    <>
      <Navbar />
      <main className={styles.main}>
        <div className={styles.container}>

          <header className={styles.hero}>
            <div className={styles.flourish}>
              <span className={styles.flourishLine} />
              <span className={styles.flourishDiamond} />
              <span className={`${styles.flourishDiamond} ${styles.flourishCenter}`} />
              <span className={styles.flourishDiamond} />
              <span className={styles.flourishLine} />
            </div>
            <h1 className={styles.heroTitle}>CRAFTING ARCHITECT</h1>
            <p className={styles.heroSubtitle}>
              Paste an item, pick what you want, and we&apos;ll show you the cheapest crafting paths to get there —
              with step-by-step instructions.
            </p>
          </header>

          {/* ── Paste input ────────────────────────────────────────────── */}
          {!response && (
            <section className={styles.pasteCard}>
              <label className={styles.fieldLabel}>Item text (Ctrl+C from in-game)</label>
              <textarea
                className={styles.codeBox}
                rows={10}
                placeholder={"Item Class: Amulets\nRarity: Normal\nOnyx Amulet\n--------\nItem Level: 80"}
                value={itemText}
                onChange={(e) => setItemText(e.target.value)}
              />
              <div className={styles.hint}>
                In-game, hover the item and press <code>Ctrl+C</code>. Paste the full text here — it should start with
                <code> Item Class:</code>.
              </div>
              <button
                className={styles.runButton}
                disabled={loading || !itemText.trim()}
                onClick={() => runAnalysis(null)}
              >
                {loading ? "Analysing…" : "Analyse this item"}
              </button>
              {error && <div className={styles.error}>{error}</div>}
            </section>
          )}

          {/* ── Parsed result ──────────────────────────────────────────── */}
          {response && (
            <>
              <ItemDisplay item={response.item} onReset={resetAll} />

              <GoalPicker
                goals={goals}
                selectedGoalId={selectedGoalId}
                onSelect={selectGoal}
              />

              {loading && (
                <div className={styles.loading}>Looking for matching recipes…</div>
              )}

              {!loading && response.recipes.length === 0 && (
                <div className={styles.empty}>
                  {response.no_recipes_reason ?? "No applicable recipes for this item yet."}
                </div>
              )}

              {!loading && response.recipes.length > 0 && (
                <div className={styles.recipeList}>
                  {response.recipes.map((r) => (
                    <RecipeCard
                      key={r.id}
                      recipe={r}
                      expanded={expandedRecipeId === r.id}
                      onToggle={() => setExpandedRecipeId(expandedRecipeId === r.id ? null : r.id)}
                    />
                  ))}
                </div>
              )}

              <div className={styles.disclaimerBar}>
                Costs are estimated ranges. PoE crafting is RNG — expect outcomes 2–3× either way of the average.
              </div>
            </>
          )}
        </div>
      </main>
    </>
  );
}

// ── Parsed item display ────────────────────────────────────────────────────

function ItemDisplay({ item, onReset }: { item: ParsedItem; onReset: () => void }) {
  return (
    <section className={styles.itemCard}>
      <div className={styles.itemHeaderRow}>
        <div className={styles.itemMeta}>
          <span className={styles.itemMetaLabel}>Detected</span>
          <h2 className={`${styles.itemName} ${styles[`rarity_${item.rarity.toLowerCase()}`] ?? ""}`}>
            {item.name || item.base_type || "(unknown item)"}
          </h2>
          {item.name && <div className={styles.itemBase}>{item.base_type}</div>}
          <div className={styles.itemSub}>
            {[item.item_class, `Item Level ${item.item_level}`, item.rarity, item.quality > 0 ? `Q${item.quality}%` : null]
              .filter(Boolean)
              .join(" · ")}
            {item.corrupted && <span className={styles.itemFlag}> · Corrupted</span>}
          </div>
        </div>
        <button className={styles.smallButton} onClick={onReset}>← Paste another</button>
      </div>

      {item.warnings.length > 0 && (
        <ul className={styles.warnings}>
          {item.warnings.map((w, i) => <li key={i}>⚠ {w}</li>)}
        </ul>
      )}

      {(item.implicits.length > 0 || item.explicit_mods.length > 0) && (
        <div className={styles.itemMods}>
          {item.implicits.length > 0 && (
            <div className={styles.implicitsBlock}>
              {item.implicits.map((m, i) => (
                <div key={`i-${i}`} className={`${styles.modLine} ${styles.implicit}`}>{m}</div>
              ))}
            </div>
          )}
          {item.explicit_mods.length > 0 && (
            <div className={styles.explicitsBlock}>
              {item.explicit_mods.map((m, i) => (
                <div key={`e-${i}`} className={styles.modLine}>{m}</div>
              ))}
            </div>
          )}
        </div>
      )}
    </section>
  );
}

// ── Goal picker (beginner mode) ────────────────────────────────────────────

function GoalPicker({
  goals,
  selectedGoalId,
  onSelect,
}: {
  goals: CommonGoal[];
  selectedGoalId: string | null;
  onSelect: (goal: CommonGoal | null) => void;
}) {
  if (goals.length === 0) {
    return (
      <div className={styles.goalEmpty}>
        Common-goals haven&apos;t been curated for this item class yet. (Phase C2 will add the advanced
        mod-by-mod picker for any item class.)
      </div>
    );
  }
  return (
    <section className={styles.goalPicker}>
      <div className={styles.goalPickerLabel}>What do you want to craft toward?</div>
      <div className={styles.goalGrid}>
        {goals.map((g) => (
          <button
            key={g.id}
            className={`${styles.goalCard} ${selectedGoalId === g.id ? styles.goalCardActive : ""}`}
            onClick={() => onSelect(g)}
          >
            <div className={styles.goalLabel}>{g.label}</div>
            <div className={styles.goalDescription}>{g.description}</div>
          </button>
        ))}
      </div>
    </section>
  );
}

// ── Recipe card ────────────────────────────────────────────────────────────

function fmtCost(low: number, high: number): string {
  if (low === high) return `~${low.toFixed(0)}c`;
  return `${low.toFixed(0)}–${high.toFixed(0)}c`;
}

function RecipeCard({
  recipe,
  expanded,
  onToggle,
}: {
  recipe: Recipe;
  expanded: boolean;
  onToggle: () => void;
}) {
  const [costLow, costHigh] = recipe.estimated_cost_chaos_range;
  const liveLabel = recipe.live_cost_chaos !== null ? ` (live ~${recipe.live_cost_chaos.toFixed(0)}c)` : "";
  const guaranteed = recipe.guaranteed_mod_families;
  const rollable = recipe.rollable_mod_families;

  return (
    <article className={`${styles.recipeCard} ${expanded ? styles.recipeCardExpanded : ""}`}>
      <button className={styles.recipeHeader} onClick={onToggle} aria-expanded={expanded}>
        <div className={styles.recipeHeaderLeft}>
          <div className={styles.recipeName}>{recipe.name}</div>
          <div className={styles.recipeMeta}>
            <span className={styles.recipeCost}>{fmtCost(costLow, costHigh)}{liveLabel}</span>
            {recipe.estimated_success_pct !== null && (
              <span className={styles.recipeSuccess}>{recipe.estimated_success_pct.toFixed(0)}% success</span>
            )}
            <span className={styles.recipeStepCount}>{recipe.steps.length} steps</span>
            <span className={`${styles.recipeSkillFloor} ${styles[`skill_${recipe.skill_floor}`] ?? ""}`}>
              {recipe.skill_floor}
            </span>
          </div>
        </div>
        <div className={styles.recipeChevron} aria-hidden>{expanded ? "▾" : "▸"}</div>
      </button>

      {expanded && (
        <div className={styles.recipeBody}>
          <p className={styles.recipeDescription}>{recipe.description}</p>

          {guaranteed.length > 0 && (
            <div className={styles.modsRow}>
              <span className={styles.modsLabel}>Guaranteed:</span>
              {guaranteed.map((g) => <span key={g} className={`${styles.modChip} ${styles.modChipGuaranteed}`}>{g}</span>)}
            </div>
          )}
          {rollable.length > 0 && (
            <div className={styles.modsRow}>
              <span className={styles.modsLabel}>Rollable:</span>
              {rollable.slice(0, 12).map((g) => <span key={g} className={styles.modChip}>{g}</span>)}
              {rollable.length > 12 && (
                <span className={styles.modChipMore}>+{rollable.length - 12} more</span>
              )}
            </div>
          )}

          <ol className={styles.stepList}>
            {recipe.steps.map((s, i) => (
              <li key={i} className={styles.stepItem}>
                <div className={styles.stepHeader}>
                  <span className={styles.stepNumber}>{i + 1}</span>
                  <span className={styles.stepVerb}>{s.verb}</span>
                  {s.currency && (
                    <span className={styles.stepCurrency}>
                      {s.qty !== 1 ? `${s.qty}× ` : ""}{s.currency}
                    </span>
                  )}
                </div>
                <div className={styles.stepOutcome}>{s.outcome}</div>
              </li>
            ))}
          </ol>

          {recipe.notes_for_user && (
            <div className={styles.recipeNotes}>{recipe.notes_for_user}</div>
          )}
        </div>
      )}
    </article>
  );
}
