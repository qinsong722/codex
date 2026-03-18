import { describe, expect, test } from "vitest";
import { createInitialState } from "../src/game/state";
import { advanceRunnerFrame } from "../src/game/loop";
import { getVisiblePlatforms } from "../src/game/render";

function createRunnerState(overrides = {}) {
  return {
    ...createInitialState(),
    ...overrides,
    cat: {
      ...createInitialState().cat,
      ...(overrides.cat ?? {}),
    },
    world: overrides.world ?? createInitialState().world,
  };
}

describe("advanceRunnerFrame", () => {
  test("moves the cat forward and steers toward the target x position", () => {
    const state = createRunnerState({
      cat: {
        ...createInitialState().cat,
        x: 0,
        y: 0,
        onGround: true,
      },
    });

    const nextState = advanceRunnerFrame(state, { targetX: 240 }, { random: () => 0.5 });

    expect(nextState.cat.x).toBeGreaterThan(0);
    expect(nextState.cameraX).toBeGreaterThanOrEqual(0);
  });

  test("moves the cat horizontally toward the mouse target", () => {
    const initialState = createInitialState();
    const state = createRunnerState({
      cameraX: 120,
      cat: {
        ...initialState.cat,
        x: 360,
        screenX: 240,
        y: 0,
        onGround: true,
      },
    });

    const nextState = advanceRunnerFrame(state, { targetX: 420 }, { random: () => 0.5 });

    expect(nextState.cat.screenX).toBeGreaterThan(240);
  });

  test("consumes a jump request and applies upward velocity", () => {
    const state = createRunnerState();

    const nextState = advanceRunnerFrame(state, { jumpRequested: true }, { random: () => 0.5 });

    expect(nextState.cat.onGround).toBe(false);
    expect(nextState.cat.vy).toBeLessThan(0);
  });

  test("buffers a jump pressed shortly before landing", () => {
    const initialState = createInitialState();
    let state = createRunnerState({
      cat: {
        ...initialState.cat,
        y: -6,
        vy: 5,
        onGround: false,
      },
    });

    state = advanceRunnerFrame(state, { jumpRequested: true, targetX: 240 }, { random: () => 0.5 });
    const bufferedJumpState = advanceRunnerFrame(state, { targetX: 240 }, { random: () => 0.5 });

    expect(bufferedJumpState.cat.onGround).toBe(false);
    expect(bufferedJumpState.cat.vy).toBeLessThan(0);
  });

  test("resolves catches on occupied platforms", () => {
    const initialState = createInitialState();
    const state = createRunnerState({
      cameraX: 0,
      cat: {
        ...initialState.cat,
        x: 40,
        screenX: 40,
        y: -24,
        vy: 6,
        onGround: false,
      },
      world: {
        ground: createInitialState().world.ground,
        platforms: [
          {
            x: 0,
            y: -24,
            width: 100,
            height: 16,
            mouse: { level: 1 },
          },
        ],
      },
    });

    const nextState = advanceRunnerFrame(state, {}, { random: () => 0.5 });

    expect(nextState.miceCaught).toBe(1);
    expect(nextState.world.platforms[0].mouse).toBeNull();
  });

  test("adds fall damage when the cat drops from a platform to the ground", () => {
    const state = createRunnerState({
      health: 3,
      cat: {
        ...createInitialState().cat,
        x: 18,
        y: -2,
        vy: 0,
        onGround: true,
      },
      world: {
        ground: createInitialState().world.ground,
        platforms: [
          {
            x: 0,
            y: -2,
            width: 20,
            height: 16,
            mouse: null,
          },
        ],
      },
    });

    const nextState = advanceRunnerFrame(state, { targetX: 100 }, { random: () => 0.5, frameTime: 400 });

    expect(nextState.health).toBeLessThan(3);
    expect(nextState.cat.onGround).toBe(true);
  });

  test("prunes platforms that are far behind the cat", () => {
    const initialState = createInitialState();
    const state = createRunnerState({
      cameraX: 1200,
      cat: {
        ...initialState.cat,
        x: 1440,
        screenX: 240,
        y: 0,
        onGround: true,
      },
      world: {
        ground: createInitialState().world.ground,
        platforms: [
          { x: 0, y: -80, width: 100, height: 16, mouse: null },
          { x: 1180, y: -90, width: 100, height: 16, mouse: null },
          { x: 1600, y: -100, width: 100, height: 16, mouse: { level: 2 } },
        ],
      },
    });

    const nextState = advanceRunnerFrame(state, { targetX: 1200 }, { random: () => 0.5 });

    expect(nextState.world.platforms.some((platform) => platform.x === 0)).toBe(false);
    expect(nextState.world.platforms.some((platform) => platform.x === 1180)).toBe(true);
  });

  test("extends ground items so boxes or mice keep appearing", () => {
    const initialState = createInitialState();
    const state = createRunnerState({
      cameraX: 1000,
      cat: {
        ...initialState.cat,
        x: 1240,
        screenX: 240,
        y: 0,
        onGround: true,
      },
      world: {
        ...initialState.world,
        groundMice: [
          { x: 100, y: 0, hasBox: true, mouse: null },
          { x: 220, y: 0, hasBox: true, mouse: { level: 1 } },
        ],
        platforms: [
          { x: 1700, y: -60, width: 100, height: 16, hasBox: true, mouse: { level: 1 } },
        ],
      },
    });

    const nextState = advanceRunnerFrame(state, { targetX: 240 }, { random: () => 0.8 });

    expect(nextState.world.groundMice.length).toBeGreaterThan(0);
    expect(
      nextState.world.groundMice.some((item) => item.x > nextState.cat.x),
    ).toBe(true);
  });

  test("extends ground items even when platforms are still far ahead", () => {
    const initialState = createInitialState();
    const state = createRunnerState({
      cameraX: 900,
      cat: {
        ...initialState.cat,
        x: 1140,
        screenX: 240,
        y: 0,
        onGround: true,
      },
      world: {
        ...initialState.world,
        groundMice: [
          { x: 320, y: 0, hasBox: true, mouse: null },
          { x: 560, y: 0, hasBox: true, mouse: { level: 1 } },
        ],
        platforms: [
          { x: 1320, y: -40, width: 120, height: 16, hasBox: true, mouse: { level: 1 } },
          { x: 1900, y: -52, width: 140, height: 16, hasBox: true, mouse: null },
        ],
      },
    });

    const nextState = advanceRunnerFrame(state, { targetX: 240 }, { random: () => 0.8 });

    expect(nextState.world.groundMice.some((item) => item.x > nextState.cat.x)).toBe(true);
  });

  test("keeps at least one visible target during a long run", () => {
    let state = createInitialState();
    const input = { targetX: 240, jumpRequested: false };

    for (let frame = 0; frame < 900; frame += 1) {
      state = advanceRunnerFrame(state, input, { random: () => 0.8 });

      const visiblePlatforms = getVisiblePlatforms(state);
      const visibleGroundItems = (state.world.groundMice ?? []).filter(
        (item) => item.x >= (state.cameraX ?? 0) - 240 && item.x <= (state.cameraX ?? 0) + 1600,
      );

      expect(
        visiblePlatforms.length + visibleGroundItems.length,
        `visible world emptied at frame ${frame}, camera ${state.cameraX}, cat ${state.cat.x}`,
      ).toBeGreaterThan(0);
    }
  });
});
