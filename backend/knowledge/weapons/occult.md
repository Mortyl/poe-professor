# Occult (Spells — Witch)

## Weapon Note
Occult spells are **not weapon-restricted** — they can be cast with a Wand, Sceptre, or Staff. "Occult" in this app refers to minion, chaos, and life-based spells used primarily by the Witch class.

## Tags Reference
Tags determine what passive tree nodes and support gems affect a skill.

---

## Active Skills

### Minion Skills
- **Raise Zombie** *(Minion · Physical · Duration)* — raise a Zombie from a nearby Corpse to fight for you
- **Skeletal Warrior Minion** *(Minion · Physical · Duration)* — summon a skeletal warrior
- **Skeletal Brute Minion** *(Minion · Physical · Duration)* — summon a heavy skeletal brute
- **Skeletal Reaver Minion** *(Minion · Physical · Duration)* — summon a skeletal reaver
- **Skeletal Arsonist Minion** *(Minion · Fire · Duration)* — summon a skeletal arsonist
- **Skeletal Frost Mage Minion** *(Minion · Cold · Duration)* — summon a skeletal frost mage
- **Skeletal Storm Mage Minion** *(Minion · Lightning · Duration)* — summon a skeletal storm mage
- **Skeletal Sniper Minion** *(Minion · Physical · Duration)* — summon a skeletal sniper
- **Skeletal Cleric Minion** *(Minion · Duration)* — summon a skeletal cleric that heals minions
- **Grim Resurrection** *(Minion · Duration)* — raise a powerful monster as a minion
- **Raging Spirits** *(Minion · Fire · Duration)* — create short-lived Raging Spirit minions that seek and attack enemies
- **Ravenous Swarm** *(Minion · Physical · Duration)* — summon a swarm of insects
- **Dark Effigy** *(Spell · Duration · Area)* — place a dark effigy that debuffs enemies in its area

### Chaos / Damage Spells
- **Bonestorm** *(Spell · Channel · Projectile · Area · Physical)* — storm of bone shards; deals Physical damage in area; consumes Power Charges
- **Bone Blast** *(Spell · Projectile · Physical · Area)* — fire a blast of bones
- **Bone Cage** *(Spell · Duration · Physical · Area)* — cage an enemy in bones
- **Chaos Bolt** *(Spell · Projectile · Chaos)* — fire a bolt of pure chaos damage
- **Contagion** *(Spell · Area · Chaos · Duration · DoT)* — apply a contagion that spreads Chaos DoT on kill
- **Essence Drain** *(Spell · Projectile · Chaos · DoT · Duration)* — drain the enemy's essence dealing Chaos damage over time
- **Soulrend** *(Spell · Projectile · Chaos · Duration)* — tear at an enemy's soul dealing Chaos damage
- **Exsanguinate** *(Spell · Area · Physical · DoT · Duration)* — unleash blood tendrils damaging and bleeding nearby enemies
- **Hexblast** *(Spell · Area · Chaos)* — blast an enemy affected by a Hex, consuming the Hex for bonus damage
- **Reap** *(Spell · Area · Physical)* — slash with a spectral blade dealing Physical damage in area
- **Decompose** *(Spell · Area · Chaos · Duration)* — cause a corpse to release clouds of caustic gas
- **Volatile Dead** *(Spell · Area · Fire · Duration)* — consume corpses to create volatile orbs that explode on enemies
- **Detonate Dead** *(Spell · Area · Fire)* — detonate a corpse dealing Fire damage based on corpse life

### Corpse Interaction
- **Profane Ritual** *(Spell · Area · Duration)* — consume corpses in a ritual to generate Power Charges
- **Unearth** *(Spell · Projectile · Physical)* — fire a projectile that creates a corpse from nothing

### Curses
- **Despair** *(Spell · Curse · Chaos)* — reduces enemy Chaos Resistance and increases Chaos damage taken
- **Vulnerability** *(Spell · Curse · Physical)* — increases Physical damage taken; enemies Bleed more easily
- **Temporal Chains** *(Spell · Curse · Duration)* — slows all actions of the cursed enemy
- **Enfeeble** *(Spell · Curse)* — reduces enemy attack and defence effectiveness
- **Wither** *(Spell · Chaos · Duration)* — stacks Wither increasing Chaos damage taken

### Offerings (Buff Spells from Corpses)
- **Bone Offering** *(Spell · Duration)* — consume Corpses to grant a bonus to Block
- **Soul Offering** *(Spell · Duration)* — consume Corpses to grant Energy Shield

### Meta-Skills (Trigger)
- **Cast on Critical** — automatically cast socketed spells on Critical Strike
- **Cast on Dodge** — automatically cast socketed spells on Dodge Roll
- **Cast on Elemental Ailment** — automatically cast socketed spells when inflicting an Elemental Ailment
- **Cast on Minion Death** — automatically cast socketed spells when a Minion dies
- **Spellslinger** — reserve Mana to automatically cast socketed spells when attacking

### Utility
- **Blasphemy** *(Spell · Aura · Curse)* — reserves Spirit to apply a socketed Curse as an Aura around you
- **Withering Presence** *(Spell · Aura · Chaos · Duration)* — Aura that stacks Wither on nearby enemies
- **Barrier Invocation** *(Spell · Duration)* — create a barrier that absorbs hits
- **Ghost Dance** *(Spell · Travel)* — dash leaving a ghost copy behind

### Life / Recovery
- **Feast of Flesh** *(Spell · Duration)* — consume Corpses to restore Life and Energy Shield
- **Grim Feast** *(Spell · Duration)* — gain Overflow Energy Shield on kills
- **Sacrifice** *(Spell · Duration)* — consume a Minion for a powerful buff
- **Pain Offering** *(Spell · Duration)* — sacrifice a Minion to empower remaining Minions

---

## Key Tag Interactions
- **Spell** — scaled by Spell Damage, Cast Speed; NOT by Attack Damage
- **Minion** — Minion skills are scaled by Minion Damage, Minion Life, and Minion Speed nodes — NOT by your own damage nodes
- **Chaos** — scaled by Chaos Damage nodes; enemies have no innate Chaos Resistance
- **Physical** — scaled by Physical Damage nodes; can be amplified by Armour Break
- **DoT** — Contagion and Essence Drain deal DoT scaled by Chaos DoT Multiplier, not hit damage
- **Curse** — enemies can have a limited number of Curses; Blasphemy applies a Curse as an Aura reserving Spirit
- **Projectile** — scaled by Projectile Damage nodes (Chaos Bolt, Bone Blast, Essence Drain)
- **Area** — scaled by AoE nodes

## Critical Note: Minion Scaling
Minion damage is **independent** of your character's damage. Minion builds scale through: Minion Damage passives, Minion gem levels, Offerings, and Support gems with the Minion tag. Your character's Spell Damage, Attack Damage, and Crit Chance have zero effect on minions.

---

## Playstyle Notes
Witch spells split into **Minion summoner** and **Chaos caster** builds. Minion builds (Raise Zombie, Skeletons, Raging Spirits) use Lich or Infernalist ascendancy. Chaos casters use Essence Drain + Contagion (DoT spread) or Hexblast (consume Hex for burst). Offering skills and corpse management are central to the gameplay loop. Trigger meta-skills (Cast on X) enable automated cast chains for advanced builds.

---

*Last verified May 2026. PoE2 Early Access — subject to change with patches.*
