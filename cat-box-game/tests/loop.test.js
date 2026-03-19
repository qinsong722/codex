import { describe, expect, test } from "vitest";
import { createInitialState } from "../src/game/state";
import { advanceRunnerFrame } from "../src/game/loop";

function createShooterState(overrides = {}) {
  const initialState = createInitialState();

  return {
    ...initialState,
    ...overrides,
    player: {
      ...initialState.player,
      ...(overrides.player ?? {}),
      position: {
        ...initialState.player.position,
        ...(overrides.player?.position ?? {}),
      },
      target: {
        ...initialState.player.target,
        ...(overrides.player?.target ?? {}),
      },
    },
    tank: {
      ...initialState.tank,
      ...(overrides.tank ?? {}),
      position: {
        ...initialState.tank.position,
        ...(overrides.tank?.position ?? {}),
      },
    },
    bullets: overrides.bullets ?? initialState.bullets,
    enemies: overrides.enemies ?? initialState.enemies,
    pickups: overrides.pickups ?? initialState.pickups,
  };
}

function distance(left, right) {
  return Math.hypot(left.x - right.x, left.y - right.y);
}

describe("advanceRunnerFrame", () => {
  test("moves the player closer to the pointer target each frame", () => {
    const state = createShooterState({
      player: {
        position: { x: 80, y: 80 },
        target: { x: 200, y: 120 },
      },
    });

    const nextState = advanceRunnerFrame(state, { targetX: 200, targetY: 120 }, { random: () => 0.5 });

    expect(distance(nextState.player.position, state.player.target)).toBeLessThan(
      distance(state.player.position, state.player.target),
    );
  });

  test("holding fire spawns bullets after the weapon cooldown", () => {
    const state = createShooterState({
      currentWeapon: "rifle",
      player: {
        position: { x: 100, y: 100 },
        target: { x: 100, y: 100 },
        fireCooldownRemainingMs: 2,
      },
    });

    const notReadyYet = advanceRunnerFrame(
      state,
      { firingPressed: true, targetX: 100, targetY: 100 },
      { random: () => 0.5, frameTime: 1 },
    );
    const firedState = advanceRunnerFrame(
      notReadyYet,
      { firingPressed: true, targetX: 100, targetY: 100 },
      { random: () => 0.5, frameTime: 1 },
    );

    expect(notReadyYet.bullets).toHaveLength(0);
    expect(firedState.bullets.length).toBeGreaterThan(0);
  });

  test("enemies move toward the player each frame", () => {
    const state = createShooterState({
      player: {
        position: { x: 300, y: 300 },
        target: { x: 300, y: 300 },
      },
      enemies: [
        {
          id: "enemy-1",
          x: 100,
          y: 100,
          health: 3,
          speed: 2,
        },
      ],
    });

    const nextState = advanceRunnerFrame(state, { targetX: 300, targetY: 300 }, { random: () => 0.5 });

    expect(distance(nextState.enemies[0], state.player.position)).toBeLessThan(
      distance(state.enemies[0], state.player.position),
    );
  });

  test("bullet hits remove enemies or reduce health", () => {
    const state = createShooterState({
      bullets: [
        {
          id: "bullet-1",
          owner: "player",
          x: 150,
          y: 150,
          vx: 0,
          vy: 0,
          damage: 1,
          radius: 10,
        },
      ],
      enemies: [
        {
          id: "enemy-1",
          x: 150,
          y: 150,
          health: 2,
          speed: 0,
          radius: 10,
        },
      ],
    });

    const nextState = advanceRunnerFrame(state, { targetX: 150, targetY: 150 }, { random: () => 0.5 });

    expect(nextState.bullets).toHaveLength(0);
    expect(nextState.enemies[0].health).toBeLessThan(state.enemies[0].health);
  });

  test("occupied tank fires shells on its own cooldown", () => {
    const state = createShooterState({
      tank: {
        position: { x: 420, y: 420 },
        occupiedBy: "player",
        shells: 2,
        fireCooldownRemainingMs: 2,
      },
      player: {
        position: { x: 420, y: 420 },
        target: { x: 420, y: 420 },
      },
    });

    const notReadyYet = advanceRunnerFrame(state, { targetX: 420, targetY: 420 }, { random: () => 0.5, frameTime: 1 });
    const firedState = advanceRunnerFrame(notReadyYet, { targetX: 420, targetY: 420 }, { random: () => 0.5, frameTime: 1 });

    expect(notReadyYet.bullets).toHaveLength(0);
    expect(firedState.bullets.some((bullet) => bullet.kind === "shell")).toBe(true);
    expect(firedState.tank.shells).toBeLessThan(state.tank.shells);
  });

  test("empty waves queue the next wave", () => {
    const state = createShooterState({
      wave: 3,
      enemies: [],
    });

    const nextState = advanceRunnerFrame(state, { targetX: 240, targetY: 240 }, { random: () => 0.5 });

    expect(nextState.wave).toBe(4);
    expect(nextState.enemies.length).toBeGreaterThan(0);
  });

  test("the first empty frame keeps wave one instead of skipping ahead", () => {
    const state = createInitialState();

    const nextState = advanceRunnerFrame(state, { targetX: 240, targetY: 240 }, { random: () => 0.5 });

    expect(nextState.wave).toBe(1);
    expect(nextState.enemies.length).toBeGreaterThan(0);
  });
});
