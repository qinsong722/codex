import { describe, expect, test } from "vitest";
import { BOX_TYPES } from "../src/game/constants";
import {
  getGrowthThresholdForLevel,
  resolveFallDamage,
  resolveRunnerEncounter,
  rollMouseLevel,
} from "../src/game/rules";

describe("resolveRunnerEncounter", () => {
  test("cat catches mouse when cat level is high enough", () => {
    expect(resolveRunnerEncounter({ catLevel: 4, mouseLevel: 2 })).toEqual({
      outcome: "eat",
      healthLoss: 0,
      growthGain: 1,
    });
  });

  test("cat loses health when mouse level is higher", () => {
    expect(resolveRunnerEncounter({ catLevel: 1, mouseLevel: 3 })).toEqual({
      outcome: "bounce",
      healthLoss: 1,
      growthGain: 0,
    });
  });
});

describe("resolveFallDamage", () => {
  test("cat loses health when falling off a platform", () => {
    expect(resolveFallDamage()).toEqual({
      outcome: "fall",
      healthLoss: 1,
      growthGain: 0,
    });
  });
});

describe("getGrowthThresholdForLevel", () => {
  test("returns the configured threshold for a known level", () => {
    expect(getGrowthThresholdForLevel(4)).toBe(5);
  });
});

describe("rollMouseLevel", () => {
  test("safe box keeps early mice close to the cat level", () => {
    const mouseLevel = rollMouseLevel({
      boxType: BOX_TYPES.SAFE,
      catLevel: 2,
      random: () => 0,
    });

    expect(mouseLevel).toBe(1);
  });

  test("risky box can produce stronger mice", () => {
    const mouseLevel = rollMouseLevel({
      boxType: BOX_TYPES.RISKY,
      catLevel: 2,
      random: () => 0.99,
    });

    expect(mouseLevel).toBe(4);
  });
});
