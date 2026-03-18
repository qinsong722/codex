import { describe, expect, test } from "vitest";
import { LANGUAGES } from "../src/game/i18n";
import {
  applyJump,
  applyLevelUp,
  applyMovementTarget,
  createInitialState,
  resolveCatch,
  resolveFallReset,
} from "../src/game/state";

describe("createInitialState", () => {
  test("cat starts on the ground", () => {
    const state = createInitialState();

    expect(state.cat.y).toBe(0);
    expect(state.cat.vy).toBe(0);
    expect(state.cat.onGround).toBe(true);
  });

  test("health starts at 3 and language defaults to Chinese", () => {
    const state = createInitialState();

    expect(state.health).toBe(3);
    expect(state.language).toBe(LANGUAGES.ZH);
  });

  test("game starts in running state", () => {
    const state = createInitialState();

    expect(state.status).toBe("running");
    expect(state.gameOver).toBe(false);
    expect(state.messageKey).toBe("runner.start");
  });
});

describe("applyJump", () => {
  test("gives the cat upward velocity when grounded", () => {
    const state = applyJump(createInitialState());

    expect(state.cat.onGround).toBe(false);
    expect(state.cat.vy).toBeLessThan(0);
  });
});

describe("applyMovementTarget", () => {
  test("moves the cat to the right when requested", () => {
    const state = applyMovementTarget(createInitialState(), "right");

    expect(state.cat.vx).toBeGreaterThan(0);
  });
});

describe("resolveCatch", () => {
  test("catching a weak mouse increases count and growth", () => {
    const state = resolveCatch(createInitialState(), { level: 1 });

    expect(state.miceCaught).toBe(1);
    expect(state.growth).toBe(1);
    expect(state.health).toBe(3);
    expect(state.messageKey).toBe("runner.catch");
  });

  test("stronger mouse reduces health", () => {
    const state = resolveCatch(createInitialState(), { level: 4 });

    expect(state.miceCaught).toBe(0);
    expect(state.growth).toBe(0);
    expect(state.health).toBe(2);
    expect(state.messageKey).toBe("runner.hit");
  });
});

describe("resolveFallReset", () => {
  test("lethal falls end in a terminal game-over state", () => {
    const state = resolveFallReset({
      ...createInitialState(),
      health: 1,
      cat: {
        ...createInitialState().cat,
        y: 120,
        vy: 18,
        onGround: false,
      },
    });

    expect(state.health).toBe(0);
    expect(state.gameOver).toBe(true);
    expect(state.status).toBe("gameover");
    expect(state.messageKey).toBe("runner.gameOver");
  });

  test("falling resets the cat to safe ground and removes one health", () => {
    const state = resolveFallReset({
      ...createInitialState(),
      cat: {
        ...createInitialState().cat,
        y: 120,
        vy: 18,
        onGround: false,
      },
    });

    expect(state.cat.y).toBe(0);
    expect(state.cat.vy).toBe(0);
    expect(state.cat.onGround).toBe(true);
    expect(state.health).toBe(2);
    expect(state.messageKey).toBe("runner.fall");
  });
});

describe("applyLevelUp", () => {
  test("levels up once growth reaches the threshold", () => {
    const state = applyLevelUp({
      ...createInitialState(),
      level: 1,
      growth: 2,
    });

    expect(state.level).toBe(2);
    expect(state.growth).toBe(0);
    expect(state.messageKey).toBe("runner.levelUp");
  });

  test("carries leftover growth through multiple levels", () => {
    const state = applyLevelUp({
      ...createInitialState(),
      level: 1,
      growth: 5,
    });

    expect(state.level).toBe(3);
    expect(state.growth).toBe(0);
  });
});
