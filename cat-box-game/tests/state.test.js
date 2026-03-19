import { describe, expect, test } from "vitest";
import { MAX_AMMO } from "../src/game/constants";
import { LANGUAGES } from "../src/game/i18n";
import {
  applyAmmoPickup,
  applyDamage,
  applyShellPickup,
  applyWeaponPickup,
  completeWave,
  createInitialState,
  enterTank,
} from "../src/game/state";

describe("createInitialState", () => {
  test("player starts alive at the stage center", () => {
    const state = createInitialState();
    const { width, height } = state.world.stageBounds;

    expect(state.player.alive).toBe(true);
    expect(state.player.health).toBeGreaterThan(0);
    expect(state.player.position).toEqual({ x: width / 2, y: height / 2 });
    expect(state.player.target).toEqual({ x: width / 2, y: height / 2 });
  });

  test("current weapon starts empty", () => {
    const state = createInitialState();

    expect(state.currentWeapon).toBeNull();
  });

  test("ammo starts below the max", () => {
    const state = createInitialState();

    expect(state.ammo).toBeLessThan(MAX_AMMO);
  });

  test("tank starts on the map but unoccupied", () => {
    const state = createInitialState();

    expect(state.tank.position).toEqual(state.world.tankPlacement);
    expect(state.tank.occupiedBy).toBeNull();
  });

  test("wave starts at 1", () => {
    const state = createInitialState();

    expect(state.wave).toBe(1);
  });

  test("game starts in running state with Chinese by default", () => {
    const state = createInitialState();

    expect(state.status).toBe("running");
    expect(state.gameOver).toBe(false);
    expect(state.language).toBe(LANGUAGES.ZH);
  });
});

describe("state transitions", () => {
  test("picking up a weapon swaps the current weapon", () => {
    const state = applyWeaponPickup(createInitialState(), { weapon: "rifle" });

    expect(state.currentWeapon).toBe("rifle");
  });

  test("ammo pickup increases ammo but not beyond max", () => {
    const state = applyAmmoPickup(
      {
        ...createInitialState(),
        ammo: MAX_AMMO - 5,
      },
      { amount: 20 },
    );

    expect(state.ammo).toBe(MAX_AMMO);
  });

  test("entering the tank changes control state", () => {
    const state = enterTank(createInitialState());

    expect(state.player.controlState).toBe("tank");
    expect(state.tank.occupiedBy).toBe("player");
  });

  test("shell pickup increases tank ammo", () => {
    const state = applyShellPickup(
      {
        ...createInitialState(),
        tank: {
          ...createInitialState().tank,
          shells: 1,
        },
      },
      { amount: 2 },
    );

    expect(state.tank.shells).toBe(3);
  });

  test("nonlethal and lethal damage use different feedback keys", () => {
    const woundedState = applyDamage(createInitialState(), 1);
    const lethalState = applyDamage(createInitialState(), 999);

    expect(woundedState.player.health).toBeGreaterThan(0);
    expect(woundedState.status).toBe("running");
    expect(woundedState.messageKey).toBe("damage");

    expect(lethalState.player.health).toBe(0);
    expect(lethalState.player.alive).toBe(false);
    expect(lethalState.status).toBe("gameover");
    expect(lethalState.gameOver).toBe(true);
    expect(lethalState.messageKey).toBe("damageFatal");
  });

  test("clearing a wave advances the wave counter", () => {
    const state = completeWave({
      ...createInitialState(),
      enemies: [],
    });

    expect(state.wave).toBe(2);
  });
});
