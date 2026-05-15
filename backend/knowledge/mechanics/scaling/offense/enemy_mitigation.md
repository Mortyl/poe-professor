# Enemy Mitigation

## Overview
Enemy defences directly reduce your damage output. Mitigating enemy defences is often more impactful than adding raw damage, especially against Bosses and Rare monsters which have significantly higher defence values than white mobs.

---

## Resistances
Enemies have Fire, Cold, Lightning, and Chaos resistances that reduce the corresponding damage type on hit. Always account for enemy resistances when choosing a damage type for a build.

### Ways to Reduce Enemy Resistances

**Penetration**
- "Damage Penetrates #% of X Resistance" reduces the enemy's effective resistance during the hit calculation
- Cannot reduce enemy resistance below 0% — penetration beyond the enemy's total resistance is wasted
- Stacks additively with other penetration sources

**Exposure**
- Reduces a monster's resistance by 20% for 4 seconds by default
- Cannot stack multiple applications — only one Exposure per element at a time
- Can be scaled with "Increased Exposure Effect"
- Sources: Frost Bomb (cold), Lightning Exposure, various skills and items

**Curses**
- Flammability, Conductivity, Frostbite etc. reduce specific elemental resistances
- Only one Curse can be active on an enemy by default (see buffs_and_debuffs.md)

**Doryani's Prototype**
- Unique item that sets enemy Lightning Resistance to a specific value — a special interaction for Lightning builds

---

## Armour
Enemy armour reduces Physical Damage dealt to them. Relevant for all physical damage builds.

### Ways to Reduce Enemy Armour

**Armour Break**
- Reduces enemy armour directly, causing them to take more physical damage
- Standard armour break cannot reduce enemy armour below 0
- **Exception:** Warbringer ascendancy node "Imploding Impacts" allows armour to be broken below 0%, causing enemies to take MORE physical damage than normal — a significant damage multiplier for Warbringer builds

---

## Priority Note
Bosses and Rare enemies have substantially higher Armour and Resistance values than white mobs. Investing in penetration, exposure, and armour break has a much larger proportional DPS increase on Bosses than on normal monsters. Always factor enemy mitigation into boss-killing build recommendations.

---

*Last verified May 2026. PoE2 Early Access — subject to change with patches.*
