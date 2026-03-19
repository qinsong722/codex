export const MAX_HEALTH = 10;
export const MAX_AMMO = 90;

export const WEAPONS = {
  pistol: {
    labelKey: "weapon.pistol",
    ammoPerShot: 1,
    damage: 1,
    fireCooldownMs: 220,
    range: 520,
  },
  rifle: {
    labelKey: "weapon.rifle",
    ammoPerShot: 1,
    damage: 1,
    fireCooldownMs: 110,
    range: 760,
  },
  shotgun: {
    labelKey: "weapon.shotgun",
    ammoPerShot: 1,
    damage: 1,
    fireCooldownMs: 500,
    range: 360,
    pelletCount: 5,
  },
};

export const TANK_SHELL_LIMIT = 3;

export const TANK_STATS = {
  health: 30,
  speed: 0.8,
  shellSpeed: 5,
  fireCooldownMs: 1400,
};

export const WAVE_SPAWN_TUNING = {
  baseEnemyCount: 4,
  enemyGrowthPerWave: 2,
  spawnIntervalMs: 700,
  tankWaveStart: 4,
  tankWaveInterval: 3,
};

export const BOX_TYPES = {
  SAFE: "safe",
  RISKY: "risky",
};

export const FORM_STAGES = [
  { minLevel: 1, id: "kitten" },
  { minLevel: 3, id: "cat" },
  { minLevel: 5, id: "fancy" },
];

export const LEVEL_UP_REQUIREMENTS = {
  1: 2,
  2: 3,
  3: 4,
  4: 5,
  5: 6,
};

export const SAFE_LEVEL_OFFSETS = [-1, 0, 0, 0, 1];
export const RISKY_LEVEL_OFFSETS = [0, 1, 1, 2, 2];
