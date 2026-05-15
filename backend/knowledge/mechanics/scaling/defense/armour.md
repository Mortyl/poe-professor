# Armour

## Overview
Armour mitigates Physical Damage from hits. It applies regardless of whether the incoming hit is from an Attack or a Spell. Armour is a powerful mitigation tool throughout the campaign and endgame for physical damage reduction.

---

## How Armour Works
- Reduces Physical Damage taken from hits
- Very effective at mitigating many small hits
- Less effective against single large hits — the mitigation formula means large hits bypass a higher proportion of your armour
- Does NOT protect against Damage over Time (Bleed, Poison, Ignite) — only hit damage

---

## Scaling Armour

**Passive Tree**
- Armour nodes near Strength starting areas (Warrior, Marauder positions)
- "% Increased Armour" notables throughout the tree

**Gear**
- Base armour on Strength-based gear (helmets, chest, gloves, boots)
- "% Increased Armour" prefix on gear
- "% Increased Armour and Evasion" hybrid prefix

**Skills and Supports**
- **Scavenged Plating** — increases your Armour. Requires a source of Armour Break to function.
- **Iron Reflexes** (keystone) — converts all Evasion into additional Armour. Removes the ability to Evade but significantly increases Armour pool for Dexterity-adjacent builds.

---

## Armour Break Interaction
Armour Break reduces enemy armour, making them take more Physical Damage. This is an offensive mechanic. See `offense/enemy_mitigation.md` for details.

Scavenged Plating requires Armour Break to function — budget for a source of Armour Break if using this skill.

---

## Armour Formula
Armour becomes less effective the larger the hit it defends against. It is excellent against many small hits but struggles against large single hits. Armour mitigation can never exceed 90%.

```
Damage Reduction = Armour / (Armour + 12 × Damage taken)
```

### Rule of Thumb
| Mitigation | Armour Required |
|-----------|----------------|
| 33% (1/3) | 6× the hit size (e.g. 600 Armour for a 100 damage hit) |
| 50% (1/2) | 12× the hit size |
| 66% (2/3) | 24× the hit size |
| 75% | 36× the hit size |
| 90% (max) | 108× the hit size |

**Practical implication:** Do not rely solely on Armour against boss slam attacks. A boss hitting for 2,000 damage requires 24,000 Armour for 50% mitigation — unrealistic for most builds. Layer Armour with Evasion, Block, and Life pool for large hit survivability.

---

## Common Misconceptions
- Armour does NOT reduce Spell damage unless the Spell deals Physical Damage
- Armour does NOT protect against Damage over Time
- Armour is not a flat damage reduction — it uses a formula that scales with hit size, making it more effective against smaller hits

---

*Last verified May 2026. PoE2 Early Access — subject to change with patches.*
