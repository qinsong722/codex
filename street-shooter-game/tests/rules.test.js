import { describe, expect, test } from "vitest";
import { MAX_AMMO, TANK_SHELL_LIMIT, WEAPONS } from "../src/game/constants";
import {
  applyEnemyContact,
  canFireWeapon,
  getAmmoAfterPickup,
  getDamageForHit,
  getShellsAfterPickup,
  isWaveComplete,
} from "../src/game/rules";

describe("canFireWeapon", () => {
  test("weapon fire respects fire-rate timing", () => {
    expect(
      canFireWeapon({
        lastFireAt: 1000,
        now: 1219,
        weapon: WEAPONS.pistol,
      }),
    ).toBe(false);

    expect(
      canFireWeapon({
        lastFireAt: 1000,
        now: 1220,
        weapon: WEAPONS.pistol,
      }),
    ).toBe(true);
  });
});

describe("getAmmoAfterPickup", () => {
  test("ammo pickup clamps at the player max", () => {
    expect(getAmmoAfterPickup({ ammo: 85, amount: 10 })).toBe(MAX_AMMO);
  });
});

describe("getShellsAfterPickup", () => {
  test("shell pickup clamps at the tank max", () => {
    expect(getShellsAfterPickup({ shells: 2, amount: 5 })).toBe(TANK_SHELL_LIMIT);
  });
});

describe("applyEnemyContact", () => {
  test("enemy contact removes health", () => {
    expect(applyEnemyContact({ health: 3 })).toBe(2);
  });
});

describe("getDamageForHit", () => {
  test("tank cannon hit deals more damage than bullets", () => {
    expect(getDamageForHit({ hitType: "tankCannon" })).toBeGreaterThan(
      getDamageForHit({ hitType: "bullet" }),
    );
  });
});

describe("isWaveComplete", () => {
  test("wave completion detection returns true only when all enemies are gone", () => {
    expect(isWaveComplete({ enemies: [] })).toBe(true);
    expect(isWaveComplete({ enemies: [{ id: 1 }] })).toBe(false);
  });
});
