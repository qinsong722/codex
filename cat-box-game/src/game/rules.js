import {
  BOX_TYPES,
  LEVEL_UP_REQUIREMENTS,
  RISKY_LEVEL_OFFSETS,
  SAFE_LEVEL_OFFSETS,
} from "./constants";

export function resolveRunnerEncounter({ catLevel, mouseLevel }) {
  if (catLevel >= mouseLevel) {
    return {
      outcome: "eat",
      healthLoss: 0,
      growthGain: 1,
    };
  }

  return {
    outcome: "bounce",
    healthLoss: 1,
    growthGain: 0,
  };
}

export function resolveFallDamage() {
  return {
    outcome: "fall",
    healthLoss: 1,
    growthGain: 0,
  };
}

export function getGrowthThresholdForLevel(level) {
  return LEVEL_UP_REQUIREMENTS[level] ?? Math.max(2, level + 1);
}

export function rollMouseLevel({ boxType, catLevel, random = Math.random }) {
  const offsets = boxType === BOX_TYPES.RISKY ? RISKY_LEVEL_OFFSETS : SAFE_LEVEL_OFFSETS;
  const index = Math.min(offsets.length - 1, Math.floor(random() * offsets.length));
  const level = catLevel + offsets[index];

  return Math.max(1, level);
}
