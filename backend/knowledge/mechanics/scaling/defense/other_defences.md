# Other Defences

## Overview
Life, Resistances, Armour, Evasion, Energy Shield, and Mana are not the only defensive tools available. The following mechanics provide additional layers of damage mitigation and survivability.

---

## Reduced / Less Damage Taken

These affixes directly reduce the damage you take and are among the strongest defensive modifiers available. The distinction between "reduced" and "less" is critical.

### "Reduced" Damage Taken (Additive)
All "reduced damage taken" sources add together.
- 3 sources of 20% reduced damage taken = 60% reduced damage taken total (20+20+20)
- **For defences, "reduced" is stronger than "less"** when stacking multiple sources

### "Less" Damage Taken (Multiplicative)
Each "less damage taken" source multiplies separately.
- 3 sources of 20% less damage taken = 48.8% less damage taken total
  - First 20% less: take 80% of damage
  - Second 20% less: take 80% × 80% = 64% of damage
  - Third 20% less: take 64% × 80% = 51.2% of damage
- **For defences, "less" has diminishing returns** — each additional source is worth less than the previous

**Note:** For offensive damage, the opposite is true — "more" damage is stronger than "increased" damage when stacking. See `offense/damage_scaling.md`.

---

## Damage Shifting
"X% of Physical Damage taken as [Element] Damage" converts a portion of incoming Physical damage into Elemental damage, allowing your Elemental Resistances to mitigate it.

**Important distinctions:**
- "50% of Physical Damage **from Hits** taken as Lightning Damage" — applies only to hits, NOT Damage over Time
- "40% of Physical Damage taken as Fire Damage" — applies to **all** Physical damage including Bleed

Damage Shifting is particularly strong against Physical-heavy enemies and bosses when you have high Elemental Resistances.

---

## Damage Taken Before You
Offloads damage you take onto another entity (totem, minion, etc.) before it reaches you.

- **Wooden Wall** (Warbringer ascendancy notable) — redirects damage to a totem
- **Loyal Hellhound** (Infernalist ascendancy notable) — redirects damage to the Hellhound minion

Effectively reduces your incoming damage by the amount redirected. The entity absorbing the damage takes it instead of you.

---

## Overflow
Temporarily gain up to double the maximum of a resource pool.

- **Sanguimancy** — Overflow Life (up to 2× maximum Life)
- **Grim Feast** — Overflow Energy Shield (up to 2× maximum ES)
- **Mana Remnants** — Overflow Mana (up to 2× maximum Mana)

Overflow provides a temporary buffer beyond your normal maximum, effectively doubling your pool in that moment.

---

## Passive Tree Keystones

### Heartstopper
- Take 50% less Damage over Time for the first 4 seconds of DoT application
- If the DoT persists beyond 4 seconds, it deals 50% more damage
- Strong against short burst DoT damage; dangerous against sustained DoT

### Eternal Youth
- Swaps the behaviour of Life and Energy Shield
- Life Recharges like ES does; ES functions like Life
- Allows Life Flasks to recover ES (via Eternal Youth interaction with recovery)

### Bulwark
- Reduces damage taken during Dodge Roll instead of granting invincibility frames
- **Not recommended** — see `defense/dodge.md` for full reasoning

### Vaal Pact
- Life Leech becomes instant rather than over time
- **Disables Life Flask recovery entirely**
- Only viable in builds with very high Leech that do not need Flask recovery

### Oasis
- Increases Recovery from Life Flasks
- **Disables Charms entirely** — losing Freeze and Bleed immunity is a significant trade-off
- Rarely worth taking unless the build has alternative ailment protection

---

## General Survival Tips
These apply to all builds and all content:

- **Never stand still.** Moving constantly reduces projectile hits and ground AoE damage.
- **Don't backtrack into attacks.** Push forward or sideways — retreating puts you back into attacks already heading your way.
- **Watch for on-death effects and corpse explosions.** Killing a mob is not the end of the danger.
- **Counter Damage over Time with Life Flasks** — watch for the visual indicator and respond immediately.
- **Larger, slower enemies hit harder.** Dodge their telegraphed attacks.
- **Mouse over Rare monsters** to read their affixes before engaging.
- **Read Waystone modifiers before activating.** Some map mods are build-specific death traps. Identify and avoid the most dangerous ones for your build.
- **Dodge Roll is your strongest tool.** Mastering timing is equivalent to a large defensive upgrade with no gear cost. See `defense/dodge.md`.
- **Deaths are information.** A sudden death almost always means resistances dropped, a new damage type appeared, or Life pool did not keep up with content difficulty.

---

*Last verified May 2026. PoE2 Early Access — subject to change with patches.*
