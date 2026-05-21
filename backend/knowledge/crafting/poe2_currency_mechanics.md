# PoE2 Currency Mechanics — Source of Truth

> **Why this file exists.** The crafting tool's recipes need to reference accurate PoE2 mechanics
> (not PoE1 carry-overs). This document is the verified ground truth — confirmed against in-game
> behaviour and the poe2db.tw data. When editing or adding a recipe, check here first.
>
> **When PoE2 patches change a mechanic**, update this file before updating recipes. Each section
> tags its source (`[user-verified]`, `[poe2db]`, or `[unverified]`) so it's clear what's checked
> against actual gameplay vs scraped third-party data.

---

## Rarity tiers `[user-verified]`

| Rarity | Colour | Mod count |
|---|---|---|
| Normal | White | 0 |
| Magic | Blue | up to 2 (1 prefix + 1 suffix max) |
| Rare | Yellow | up to 6 (3 prefix + 3 suffix max) |

---

## Standard currency orbs `[poe2db + user-verified]`

| Orb | Effect | Works on |
|---|---|---|
| **Orb of Transmutation** | Normal → Magic with 1 random modifier | Normal |
| **Orb of Augmentation** | Adds 1 random modifier to a Magic item | Magic (1 mod) |
| **Orb of Alchemy** | Upgrades a Normal **or Magic** item to a Rare with 4 random mods | Normal, Magic |
| **Regal Orb** | Magic → Rare, adds 1 random modifier (so 2-mod Magic → 3-mod Rare) | Magic |
| **Exalted Orb** | Adds 1 random modifier to a Rare, up to the 6-mod cap | Rare |
| **Chaos Orb** | Removes 1 random modifier **AND** adds 1 new random modifier (single-mod swap, not a full reroll) | Rare |
| **Orb of Annulment** | Removes 1 random modifier | Magic, Rare |
| **Divine Orb** | Re-rolls the numeric values of all modifiers on an item | Any with mods |
| **Vaal Orb** | Corrupts the item (random outcome — implicit, destroy, mod change, white socket, etc.) | Any |
| **Orb of Chance** | Normal → Unique (rare success) OR destroys the item | Normal |
| **Mirror of Kalandra** | Creates a mirrored copy of an item | Any |
| **Hinekora's Lock** | Previews the result of the next currency item used on this item | Any |
| **Fracturing Orb** | Locks 1 random modifier on a Rare with 4+ mods (becomes permanent / cannot be removed) | Rare with 4+ mods |
| **Artificer's Orb** | Adds an Augment Socket to a martial weapon, wand, staff, or armour | Specific bases |

**Chaos vs PoE1.** In PoE1, Chaos Orb re-rolled the entire item. In PoE2 it's a **single-mod swap** —
removes one random, adds one random. Means it can be used iteratively to chip away at bad mods.
Pairs strongly with omens (see Omen section).

---

## Tiered orbs (Lesser → Greater → Perfect) `[poe2db]`

Several orbs come in three tiers. Higher tiers gate by **minimum modifier level** — the rolled mod
must be unlocked at that ilvl or above.

| Base orb | Greater = mods ≥ | Perfect = mods ≥ |
|---|---|---|
| Orb of Transmutation | level 55 | level 70 |
| Orb of Augmentation | level 55 | level 70 |
| Regal Orb | level 35 | level 50 |
| Exalted Orb | level 35 | level 50 |
| Chaos Orb | level 35 | level 50 |

> A "Perfect Regal" on an ilvl 80 item only rolls mods at or above level 50. If the item has no
> mods left in that tier range that aren't already on the item, the result can be… disappointing.
> Greater/Perfect tiers are budget-killers — only use when you actually want the highest mod tiers.

---

## Essences `[user-verified]`

Essences come in five tiers. The first three (Lesser, Standard, Greater) **upgrade Magic items to
Rare**. The other two (Perfect, Corrupted) **modify existing Rare items**.

### Lesser / Standard / Greater Essences — used on Magic

**Mechanic:** the Magic item becomes Rare. **Existing magic modifiers are preserved.** The essence's
guaranteed modifier is added on top.

- Magic with 1 mod → Rare with 2 mods (1 existing + 1 essence)
- Magic with 2 mods → Rare with 3 mods (2 existing + 1 essence)

> Essences do **NOT** roll extra random mods on top of the guaranteed one. They preserve what's
> there and add exactly 1. This is the opposite of Regal Orb, which adds 1 *random* mod —
> Essence is the "guaranteed flavour" version of Regal.

### Greater Essences — required-level bump

Greater Essences can be used on **any Magic or Rare base at any item level** — but the resulting
item's **required level for equipping** goes up.

Example: use a Greater Essence on an ilvl 15 body armour → the item is now Rare, but its
**Required Level to wear becomes 48** (or whatever the essence tier dictates).

**Practical implication:** a Greater Essence on a low-ilvl base creates an item your character may
not be able to equip until much later. For most early-game crafting, Lesser is the right choice.

### Perfect / Corrupted Essences — used on Rare

**Mechanic:** adds the essence's special modifier to the Rare item.

- If the item has **< 6 mods**, the essence mod is simply added.
- If the item is at **6/6 mods**, the essence mod **overwrites a random existing modifier** (item
  stays at 6 mods, one swapped out).

> Perfect/Corrupted essences are **NOT safe** on 6/6 rares — you can lose a hit mod to the swap.
> Annul first (preferably with an Omen of Sinistral/Dextral Erasure to control which side gets
> removed) before applying.

### Item-class restrictions

Many Perfect essences specify a slot (e.g. *"Perfect Essence of Insulation — Fire damage recoup on
**belts**"*). Applying the essence to a non-matching item class **refuses to apply anything** — the
essence is not consumed, the item is unchanged.

### Essence categories and what each guarantees

| Essence name | Guaranteed mod family |
|---|---|
| Body | Maximum Life |
| Mind | Maximum Mana |
| Enhancement | Defensive scaling (armour / evasion / ES %) |
| Abrasion | Physical damage |
| Flames | Fire damage |
| Ice | Cold damage |
| Electricity | Lightning damage |
| Ruin | Chaos Resistance |
| Battle | Accuracy |
| Sorcery | Spell damage |
| Haste | Attack speed |
| Infinite | Attributes (Strength / Dexterity / Intelligence / All) |
| Seeking | Critical Hit Chance |
| Insulation | Fire Resistance |
| Thawing | Cold Resistance |
| Grounding | Lightning Resistance |
| Alacrity | Cast Speed |
| Opulence | Item Rarity Found |
| Command | Ally Damage / Aura magnitude (Spirit-related) |

Each appears in Lesser, Standard, Greater, Perfect, and (some) Corrupted tiers — totalling ~81
essence items across the system.

---

## Omens — PoE2's meta-crafting layer `[user-verified]`

Omens modify the **next use** of a specific currency item. To use one, hold the omen in your
inventory and then use the paired currency. The omen is consumed only when the currency action
**actually does something**.

### Consumption rules

- If you have *Omen of Sinistral Exaltation* (prefix-only) and your rare is **at 6/6 mods**, using
  Exalt does nothing **and the omen is NOT consumed**. Item state unchanged.
- If you annul a mod (opening a slot) and then exalt, the omen IS consumed and the exalt is forced
  prefix-only.

### Stacking

**Omens CAN stack.** Hold multiple omens that target the same currency, and the effects combine:

| Stacked omens | Result on next Exalt |
|---|---|
| Omen of Greater Exaltation + Omen of Sinistral Exaltation | Adds 2 prefix-only mods |
| Omen of Greater Exaltation + Omen of Homogenising Exaltation | Adds 2 mods of the same type as an existing mod |

(All Exalt-targeted omens stack with each other; same for the Annul-targeted, Chaos-targeted, etc.
Cross-currency stacking — e.g. an Exalt omen with an Annul omen — has no interaction by design,
they activate on different orbs.)

### Common omen families

Naming convention: **Sinistral** = prefix-only, **Dextral** = suffix-only, **Greater** = doubled
effect, **Homogenising** = same-type-as-existing-mod.

| Omen | Modifies | What it does |
|---|---|---|
| Omen of Sinistral Exaltation | Exalted Orb | Adds prefix only |
| Omen of Dextral Exaltation | Exalted Orb | Adds suffix only |
| Omen of Greater Exaltation | Exalted Orb | Adds 2 modifiers instead of 1 |
| Omen of Homogenising Exaltation | Exalted Orb | Adds a mod of the same type as an existing mod |
| Omen of Catalysing Exaltation | Exalted Orb | Consumes all Catalyst Quality to bias the rolled mod type |
| Omen of Sinistral Coronation | Regal Orb | Adds prefix only |
| Omen of Dextral Coronation | Regal Orb | Adds suffix only |
| Omen of Homogenising Coronation | Regal Orb | Adds a same-type mod |
| Omen of Sinistral Alchemy | Orb of Alchemy | Result has the maximum number of prefixes |
| Omen of Dextral Alchemy | Orb of Alchemy | Result has the maximum number of suffixes |
| Omen of Sinistral Annulment | Orb of Annulment | Removes a prefix only |
| Omen of Dextral Annulment | Orb of Annulment | Removes a suffix only |
| Omen of Greater Annulment | Orb of Annulment | Removes 2 modifiers |
| Omen of Whittling | Chaos Orb | Next Chaos removes the **lowest-level** modifier |
| Omen of Sinistral Erasure | Chaos Orb | Removes a prefix only (the Chaos still adds 1 random) |
| Omen of Dextral Erasure | Chaos Orb | Removes a suffix only |
| Omen of the Blessed | Divine Orb | Re-rolls only implicit modifiers |
| Omen of Sanctification | Divine Orb (on Rare) | Sanctifies the item (special effect) |
| Omen of Chance | Orb of Chance | Won't destroy the item on failure |
| Omen of the Ancients | Orb of Chance | Upgrades to a random Unique of the same item class |
| Omen of Corruption | Vaal Orb | Always results in a change (no "no effect" outcome) |
| Omen of Light | Orb of Annulment | Removes a Desecrated modifier only |
| Omen of Sinistral / Dextral Crystallisation | Perfect / Corrupted Essence | Restrict the essence-overwrite swap to prefix-only / suffix-only |

(There are also non-crafting omens for Shrines, Strongboxes, Vaal monsters, Recombinators,
Desecration, etc. — see poe2db.tw/us/Omens for the full list.)

---

## Currency hierarchy quick-reference

Going from cheapest/most-common to rarest:

```
Transmutation  → Augmentation → Regal      (the "build a Rare from Normal" chain)
Alchemy                                     (shortcut: Normal → Rare directly)
Exalted        → Chaos        → Divine     (modify existing Rare)
Annulment                                   (subtract from any item)
Essences       (guaranteed-mod alternatives to Regal / random Rare upgrade)
Omens          (meta-modifiers for the next currency use)
Vaal           (final-step corruption — gambling for upside)
Mirror         (chase item — clone someone else's god-roll)
```

---

## Known gaps / things to verify next time

- **Catalyst Quality** — referenced in *Omen of Catalysing Exaltation*. Catalysts exist in PoE2 and
  add quality to jewellery; need to verify exact mechanic of "bias mod type."
- **Recombinators** — referenced in *Omen of Recombination*. Likely the PoE2 equivalent of PoE1's
  Harvest recombinators — combine two items, blend their mods. Mechanic specifics not yet researched.
- **Desecrated modifiers** — *Omen of Light* removes only Desecrated mods. Desecrated mods are added
  by some currency (Sovereign / Liege / Blackblooded omens reference them). Need to research the
  desecration crafting system separately.
- **Sanctified items** — *Omen of Sanctification* references this. Special item state? Need to verify.
- **Currency prices** — costs are league-dependent and rapidly changing. Static fallback ranges in
  recipes are guesses; live pricing via poe.ninja currency API would be better when we identify the
  endpoint.

---

## How to use this document when editing recipes

1. **Before writing a step**: check the orb behaviour table above. If your step description
   contradicts what's documented here, fix the step — don't override the docs without verifying
   against the game.
2. **When using an essence in a step**: confirm the tier (Lesser / Standard / Greater / Perfect /
   Corrupted) and the target rarity (Magic for the first three, Rare for the last two).
3. **When suggesting an omen as an "advanced" note**: confirm the omen name matches what's in this
   doc. Cross-reference poe2db.tw/us/Omens if uncertain.
4. **When a PoE2 patch changes a mechanic**: update this doc FIRST, then sweep the recipes that
   reference the changed behaviour. The mtime-aware recipe loader picks up edits immediately.

---

## Sources

- **User (in-game verified)** — rarity tiers, essence-on-magic mechanic, Greater essence
  required-level bump, item-class refusal behaviour, omen consumption + stacking rules.
- **poe2db.tw** (May 2026 scrape) — orb effects, essence names + categories, omen names + targets.
- **Direct gameplay** — not yet systematically verified for edge cases (Sanctification, Catalyst
  interactions, Desecration system).
