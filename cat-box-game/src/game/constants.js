export const MAX_HEALTH = 3;

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
