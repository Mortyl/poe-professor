# Damage Scaling

## Core Rule
Mixing different types of damage multipliers is always more effective than stacking one type. Diminishing returns apply within the same multiplier group. Never over-invest in a single scaling method.

---

## Skill Tags
Every skill gem has tags that determine which modifiers apply to it. Always check tags before recommending scaling methods — recommending a modifier that doesn't match the skill's tags is incorrect.

- A skill tagged **Lightning** benefits from Lightning Damage, Elemental Damage, and Spell or Attack modifiers
- A skill tagged **Projectile** benefits from Projectile Damage modifiers
- A skill tagged **Duration** can be scaled with Duration modifiers
- **Cold, Fire, and Lightning** tags also grant access to Elemental Damage modifiers
- **Attacks** and **Spells** scale differently — see Base Damage below

---

## The Damage Formula
`(Base Damage + Added Damage) × Increased Damage × More Damage × Hit Rate = DPS`

Then apply: Critical Hits, Enemy Mitigation, Debuffs, Buffs.

---

## Types of Damage Scaling

### 1. Base Damage
- **Attacks** scale with weapon damage. Upgrading weapons is the single most impactful early game action.
- **Spells** scale with skill gem level. Use higher-level Uncut Skill Gems on existing skills to raise damage.
- Spells gain flat damage per level. Attacks increase how well they scale with weapon damage per level.
- Exception: Shockwave Totem uses its own weapon damage even though it behaves like a totem.

### 2. Added Damage (Flat)
- "Adds X to Y [Type] Damage to [Attacks/Spells]" on gear or gems
- Applied before multipliers — very efficient early
- Example: "Adds 7 to 13 Physical Damage to Attacks" on a ring adds directly to the hit before any multipliers

### 3. "Increased" Damage (Additive)
- All "increased" modifiers applicable to the skill add together into one multiplier
- Example: 20% Increased Fire Damage + 20% Increased Elemental Damage = ×1.4 total (NOT ×1.44)
- High diminishing returns when stacked heavily — the more you have, the less each new source adds
- Strong early investment, weaker when already stacked

### 4. "More" Damage (Multiplicative)
- Always multiplicative with everything else — never diminishes against other multiplier types
- Primarily gained from Support Gems socketed into skill gems
- Example: 20% more × 20% more = ×1.44 (vs ×1.4 if both were "increased")
- Each additional support gem socket on a skill is extremely valuable for this reason
- "More" sources are multiplicative WITH EACH OTHER — two 20% more sources = ×1.44, not ×1.40

### 5. Hit Rate
- More hits per second = more DPS, even without changing the damage per hit
- Attack Speed (for attacks) and Cast Speed (for spells)
- **Attacks require Accuracy to hit — spells do not**
- Keep Chance to Hit as close to 100% as possible — missing on a slow skill is a large DPS loss
- Accuracy decreases with distance from the enemy
- Excessive hit rate causes mana drain — balance speed with mana sustainability

### 6. Critical Strikes
- Default Critical Damage Multiplier: +100% (meaning crits deal 200% of base damage — double damage)
- **Crit Chance and Crit Multiplier must both be invested — one without the other wastes the other**
- Spells: inherent crit chance per skill, scaled with "Increased Critical Hit Chance for Spells"
- Attacks: use weapon's local Critical Hit Chance, scaled with "Increased Critical Hit Chance with Attacks"
- "+#% to Critical Damage Bonus" on weapons is flat damage to the crit multiplier base — extremely strong
- Example: +100% base + 30% from weapon = +130% base, then multiplied by increased crit damage
- Aim for a balance — 100% crit chance with low multiplier or 5% crit with huge multiplier are both inefficient

### 7. Gained Damage
- "Gain #% of [Type] Damage as [X] Damage" adds a percentage of your base damage as a different type
- Additive with other Gained Damage sources, but multiplicative with the rest of your scaling
- Only modifiers of the NEW damage type apply to the gained portion
- Example: A physical spell that gains fire damage — only fire damage modifiers apply to the gained fire portion

---

## Mixing Multipliers — The Most Important Rule

**Never over-invest in one type of scaling.**

### Bad: 1,000% Increased Damage Only
1,000 base DPS × (1 + 10.0) = **11,000 DPS**

### Good: Mixed Scaling
1,000 base DPS × (1 + 3.0 increased) × 1.30 more × 1.30 more × 1.50 cast speed × 1.30 gained × crit × 1.30 shock = **~51,000 DPS**

That is almost 5× more damage despite using 700% less "increased" damage — because different multiplier types are multiplicative with each other.

### Why: Diminishing Returns Within Groups
Two 80% increased sources = 1,000 × (1 + 0.8 + 0.8) = **2,600 DPS**
NOT: 1,000 × 1.8 × 1.8 = 3,240 DPS

The only exception: sources of "more" damage are always multiplicative even with each other.

---

## Compounding Upgrades
Small consistent damage upgrades compound significantly.

- A 5% upgrade to a 1,000 DPS skill = 50 DPS gained
- A 5% upgrade to a 3,000 DPS skill = 150 DPS gained
- The passive tree provides ~123 points — at an average 3% more damage per node, the last 24 nodes roughly double your total DPS
- Never dismiss small consistent upgrades as insignificant — they scale with everything you already have

---

## Mechanical Damage Increases (Not Shown on Tooltip)
These increase actual damage without affecting the tooltip DPS value:

- **Extra Projectiles** — can hit the same enemy multiple times (Shotgunning)
- **Chain** — bouncing projectiles off terrain can generate extra hits on nearby enemies
- **Payoff Skills** — skills with conditional bonuses, e.g. Boneshatter deals far more damage against an enemy primed for stun

---

---

## Common Misconceptions — Be Careful

### Minions vs Totems
- **Minions** do NOT scale with your damage modifiers. They have their own separate modifiers explicitly stating "to Minions". Never recommend generic damage scaling for minion builds.
- **Totems are NOT minions.** Totems scale with your character's damage modifiers in addition to applicable Totem modifiers. They also count as Allies.

### Damage Conversion
- Some skills convert damage from one type to another (e.g. Physical to Cold)
- Damage modifiers only affect the **final damage type after conversion**
- If a skill fully converts Physical to Cold, modifiers to Physical Damage do NOT apply — only Cold modifiers do
- Never recommend physical scaling for a skill that converts fully to another damage type

### Weapon Flat Damage vs Spells
- Flat damage on a weapon (e.g. "Adds 10 to 20 Physical Damage") is added to the weapon's base damage and does **not** affect spells
- "Increased Physical Damage" on a weapon increases the weapon's local base damage and does **not** affect spells
- **"Increased Global Physical Damage"** however affects both attacks AND spells — this distinction is critical

---

## Summary
1. Check Skill Tags to know what modifiers apply
2. Understand Base → Added → Increased → More → Hit Rate formula
3. Mix multiplier types — never over-stack one category
4. Layer Persistent Buffs, Curses, Temporary Buffs, and Debuffs on top
5. Small compounding upgrades add up substantially over time
6. Watch for the common misconceptions above — they are the most frequent source of incorrect build advice

---

*Source: Community guide by Cptn Garbage. Last verified May 2026. PoE2 Early Access — subject to change with patches.*
