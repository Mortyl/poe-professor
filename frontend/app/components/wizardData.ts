export interface ClassData {
  id: string;
  name: string;
  image: string; // path to image in /public/images/classes/
  ascendancies: AscendancyData[];
}

export interface AscendancyData {
  id: string;
  name: string;
  image: string; // path to image in /public/images/ascendancies/
  weapons: string[]; // weapon IDs available for this ascendancy
}

export interface WeaponData {
  id: string;
  name: string;
  image: string; // path to image in /public/images/weapons/
  skills: string[];
}

export const CLASSES: ClassData[] = [
  {
    id: "warrior",
    name: "Warrior",
    image: "/images/classes/warrior.png",
    ascendancies: [
      { id: "titan",      name: "Titan",      image: "/images/ascendancies/titan.png",      weapons: ["mace", "primal", "quarterstaff"] },
      { id: "warbringer", name: "Warbringer", image: "/images/ascendancies/warbringer.png", weapons: ["mace", "primal", "quarterstaff"] },
    ],
  },
  {
    id: "ranger",
    name: "Ranger",
    image: "/images/classes/ranger.png",
    ascendancies: [
      { id: "pathfinder", name: "Pathfinder", image: "/images/ascendancies/pathfinder.png", weapons: ["bow", "crossbow", "spear"] },
      { id: "deadeye",    name: "Deadeye",    image: "/images/ascendancies/deadeye.png",    weapons: ["bow", "crossbow", "spear"] },
    ],
  },
  {
    id: "huntress",
    name: "Huntress",
    image: "/images/classes/huntress.png",
    ascendancies: [
      { id: "amazon",      name: "Amazon",       image: "/images/ascendancies/amazon.png",      weapons: ["bow", "occult", "spear"] },
      { id: "ritualist",   name: "Ritualist",    image: "/images/ascendancies/ritualist.png",   weapons: ["bow", "occult", "spear"] },
      { id: "spiritwalker", name: "Spirit Walker", image: "/images/ascendancies/spiritwalker.png", weapons: ["bow", "occult", "spear"] },
    ],
  },
  {
    id: "witch",
    name: "Witch",
    image: "/images/classes/witch.png",
    ascendancies: [
      { id: "lich",        name: "Lich",        image: "/images/ascendancies/lich.png",        weapons: ["occult"] },
      { id: "infernalist", name: "Infernalist", image: "/images/ascendancies/infernalist.png", weapons: ["elemental", "occult"] },
      { id: "bloodmage",   name: "Bloodmage",   image: "/images/ascendancies/bloodmage.png",   weapons: ["elemental"] },
    ],
  },
  {
    id: "sorceress",
    name: "Sorceress",
    image: "/images/classes/sorceress.png",
    ascendancies: [
      { id: "stormweaver",       name: "Stormweaver",       image: "/images/ascendancies/stormweaver.png",       weapons: ["elemental"] },
      { id: "chronomancer",      name: "Chronomancer",      image: "/images/ascendancies/chronomancer.png",      weapons: ["elemental"] },
      { id: "discipleofvarashta", name: "Disciple of Varashta", image: "/images/ascendancies/discipleofvarashta.png", weapons: ["elemental"] },
    ],
  },
  {
    id: "monk",
    name: "Monk",
    image: "/images/classes/monk.png",
    ascendancies: [
      { id: "invoker",          name: "Invoker",          image: "/images/ascendancies/invoker.png",          weapons: ["quarterstaff", "primal"] },
      { id: "acolyteofchayula", name: "Acolyte of Chayula", image: "/images/ascendancies/acolyteofchayula.png", weapons: ["quarterstaff", "primal"] },
      { id: "martialartist",    name: "Martial Artist",   image: "/images/ascendancies/martialartist.png",    weapons: ["quarterstaff", "primal"] },
    ],
  },
  {
    id: "mercenary",
    name: "Mercenary",
    image: "/images/classes/mercenary.png",
    ascendancies: [
      { id: "gemlinglegionaire", name: "Gemling Legionaire", image: "/images/ascendancies/gemlinglegionaire.png", weapons: ["crossbow"] },
      { id: "witchhunter",       name: "Witchhunter",        image: "/images/ascendancies/witchhunter.png",       weapons: ["crossbow"] },
      { id: "tactician",         name: "Tactician",          image: "/images/ascendancies/tactician.png",         weapons: ["crossbow"] },
    ],
  },
  {
    id: "druid",
    name: "Druid",
    image: "/images/classes/druid.png",
    ascendancies: [
      { id: "shaman", name: "Shaman", image: "/images/ascendancies/shaman.png", weapons: ["primal"] },
      { id: "oracle", name: "Oracle", image: "/images/ascendancies/oracle.png", weapons: ["primal", "elemental"] },
    ],
  },
];

export const WEAPONS: WeaponData[] = [
  {
    id: "bow",
    name: "Bow",
    image: "/images/weapons/bow.png",
    skills: [
      "Poisonburst Arrow",
      "Escape Shot",
      "Lightning Arrow",
      "Lightning Rod",
      "Vine Arrow",
      "Freezing Salvo",
      "Snipe",
      "Stormcaller Arrow",
      "Toxic Growth",
      "Ice-tipped Arrows",
      "Barrage",
      "Electrocuting Arrow",
      "Gas Arrow",
      "Ice Shot",
      "Rain of Arrows",
      "Detonating Arrow",
      "Tornado Shot",
      "Shockchain Arrow",
    ],
  },
  {
    id: "mace",
    name: "Mace",
    image: "/images/weapons/mace.png",
    skills: [
      "Boneshatter",
      "Earthquake",
      "Earthshatter",
      "Volcanic Fissure",
      "Sunder",
      "Stampede",
      "Rolling Slam",
      "Perfect Strike",
      "Hammer of the Gods",
      "Molten Blast",
      "Forge Hammer",
      "Leap Slam",
      "Supercharged Slam",
    ],
  },
  {
    id: "spear",
    name: "Spear",
    image: "/images/weapons/spear.png",
    skills: [
      "Lightning Spear",
      "Primal Strikes",
      "Rapid Assault",
      "Spearfield",
      "Thunderous Leap",
      "Glacial Lance",
      "Explosive Spear",
      "Storm Lance",
      "Fangs of Frost",
      "Rake",
      "Blood Hunt",
      "Whirling Slash",
      "Wind Serpent's Fury",
      "Barrage",
    ],
  },
  {
    id: "dagger",
    name: "Dagger",
    image: "/images/weapons/dagger.png",
    skills: ["Coming Soon"],
  },
  {
    id: "quarterstaff",
    name: "Quarterstaff",
    image: "/images/weapons/quarterstaff.png",
    skills: [
      "Tempest Flurry",
      "Ice Strike",
      "Storm Wave",
      "Wave of Frost",
      "Glacial Cascade",
      "Gathering Storm",
      "Flicker Strike",
      "Tempest Bell",
      "Whirling Assault",
      "Vaulting Impact",
      "Shattering Palm",
      "Staggering Palm",
      "Killing Palm",
      "Wind Blast",
      "Frozen Locus",
    ],
  },
  {
    id: "occult",
    name: "Occult",
    image: "/images/weapons/occult.png",
    skills: [
      "Raise Zombie",
      "Skeletal Warrior Minion",
      "Skeletal Brute Minion",
      "Raging Spirits",
      "Grim Resurrection",
      "Essence Drain",
      "Contagion",
      "Bonestorm",
      "Chaos Bolt",
      "Hexblast",
      "Exsanguinate",
      "Detonate Dead",
      "Volatile Dead",
      "Soulrend",
    ],
  },
  {
    id: "elemental",
    name: "Elemental",
    image: "/images/weapons/elemental.png",
    skills: [
      "Arc",
      "Ball Lightning",
      "Comet",
      "Lightning Conduit",
      "Orb of Storms",
      "Fireball",
      "Firestorm",
      "Flameblast",
      "Incinerate",
      "Frostbolt",
      "Ice Nova",
      "Glacial Cascade",
      "Icestorm",
      "Eye of Winter",
      "Spark",
    ],
  },
  {
    id: "flail",
    name: "Flail",
    image: "/images/weapons/flail.png",
    skills: ["Coming Soon"],
  },
  {
    id: "primal",
    name: "Primal",
    image: "/images/weapons/primal.png",
    skills: [
      "Pounce",
      "Lunar Assault",
      "Arctic Howl",
      "Ferocious Roar",
      "Furious Slam",
      "Fury of the Mountain",
      "Rampage",
      "Molten Crash",
      "Flame Breath",
      "Rolling Magma",
      "Wing Blast",
      "Cross Slash",
    ],
  },
  {
    id: "axe",
    name: "Axe",
    image: "/images/weapons/axe.png",
    skills: ["Coming Soon"],
  },
  {
    id: "sword",
    name: "Sword",
    image: "/images/weapons/sword.png",
    skills: ["Coming Soon"],
  },
  {
    id: "crossbow",
    name: "Crossbow",
    image: "/images/weapons/crossbow.png",
    skills: [
      "Explosive Shot",
      "Fragmentation Rounds",
      "Galvanic Shards",
      "Armour Piercing Rounds",
      "High Velocity Rounds",
      "Permafrost Bolts",
      "Rapid Shot",
      "Shockburst Rounds",
      "Incendiary Shot",
      "Glacial Bolt",
      "Hailstorm Rounds",
      "Plasma Blast",
      "Explosive Grenade",
      "Cluster Grenade",
      "Voltaic Grenade",
      "Siege Ballista",
    ],
  },
];
