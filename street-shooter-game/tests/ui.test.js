import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import { LANGUAGES } from "../src/game/i18n";
import { createInitialState } from "../src/game/state";

const mocks = vi.hoisted(() => {
  let loopConfig = null;
  const stopLoop = vi.fn();
  const startRunnerLoop = vi.fn((config) => {
    loopConfig = config;
    return stopLoop;
  });

  return {
    stopLoop,
    startRunnerLoop,
    getLoopConfig: () => loopConfig,
    resetLoopConfig: () => {
      loopConfig = null;
    },
  };
});

vi.mock("../src/game/loop", () => ({
  startRunnerLoop: mocks.startRunnerLoop,
}));

function createMockRoot() {
  const listeners = {};

  return {
    innerHTML: "",
    addEventListener(type, handler) {
      listeners[type] = handler;
    },
    dispatch(type, event = {}) {
      listeners[type]?.({
        type,
        ...event,
        target: event.target ?? event,
      });
    },
  };
}

function createMockWindow() {
  const listeners = {};

  return {
    addEventListener(type, handler) {
      listeners[type] = handler;
    },
    removeEventListener(type) {
      delete listeners[type];
    },
    dispatch(type, event = {}) {
      listeners[type]?.({
        type,
        ...event,
      });
    },
  };
}

function createStageTarget(bounds = { left: 20, top: 30, width: 200, height: 120 }) {
  const stage = {
    closest(selector) {
      return selector === "[data-stage=\"street\"]" ? stage : null;
    },
    getBoundingClientRect() {
      return bounds;
    },
  };

  return stage;
}

function createActionTarget(selectorToMatch) {
  return {
    closest(selector) {
      return selector === selectorToMatch ? this : null;
    },
  };
}

async function loadInitGame() {
  const module = await import("../src/game/ui.js");
  return module.initGame;
}

describe("initGame", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    mocks.stopLoop.mockClear();
    mocks.startRunnerLoop.mockClear();
    mocks.resetLoopConfig();
    vi.resetModules();
    Reflect.deleteProperty(globalThis, "document");
    Reflect.deleteProperty(globalThis, "window");
  });

  afterEach(() => {
    vi.runOnlyPendingTimers();
    vi.useRealTimers();
  });

  test("app bootstraps into the shooter UI", async () => {
    const root = createMockRoot();
    globalThis.document = {
      querySelector: vi.fn(() => root),
    };

    await import("../src/main.js");

    expect(root.innerHTML).toContain('data-stage="street"');
    expect(root.innerHTML).toContain('data-action="language"');
    expect(mocks.startRunnerLoop).toHaveBeenCalledTimes(1);
  });

  test("pointer events update input state", async () => {
    const initGame = await loadInitGame();
    const root = createMockRoot();

    initGame(root);

    root.dispatch("pointermove", {
      clientX: 110,
      clientY: 170,
      target: createStageTarget(),
    });

    expect(mocks.getLoopConfig().input.targetX).toBe(576);
    expect(mocks.getLoopConfig().input.targetY).toBe(720);
  });

  test("initial input target matches the player's spawn position", async () => {
    const initGame = await loadInitGame();
    const root = createMockRoot();

    initGame(root);

    const state = mocks.getLoopConfig().getState();

    expect(mocks.getLoopConfig().input.targetX).toBe(state.player.position.x);
    expect(mocks.getLoopConfig().input.targetY).toBe(state.player.position.y);
  });

  test("mouse hold starts and stops firing", async () => {
    const initGame = await loadInitGame();
    const root = createMockRoot();

    initGame(root);

    const stage = createStageTarget();
    root.dispatch("pointerdown", { target: stage });
    expect(mocks.getLoopConfig().input.firingPressed).toBe(true);

    root.dispatch("pointerup", { target: stage });
    expect(mocks.getLoopConfig().input.firingPressed).toBe(false);
  });

  test("global pointer release clears firing outside the root", async () => {
    const initGame = await loadInitGame();
    const root = createMockRoot();
    const window = createMockWindow();
    globalThis.window = window;

    initGame(root);

    root.dispatch("pointerdown", { target: createStageTarget() });
    expect(mocks.getLoopConfig().input.firingPressed).toBe(true);

    window.dispatch("pointerup");
    expect(mocks.getLoopConfig().input.firingPressed).toBe(false);
  });

  test("window blur clears firing", async () => {
    const initGame = await loadInitGame();
    const root = createMockRoot();
    const window = createMockWindow();
    globalThis.window = window;

    initGame(root);

    root.dispatch("pointerdown", { target: createStageTarget() });
    expect(mocks.getLoopConfig().input.firingPressed).toBe(true);

    window.dispatch("blur");
    expect(mocks.getLoopConfig().input.firingPressed).toBe(false);
  });

  test("language toggle rerenders labels", async () => {
    const initGame = await loadInitGame();
    const root = createMockRoot();

    initGame(root);

    expect(root.innerHTML).toContain("切换语言 EN");

    root.dispatch("click", {
      target: createActionTarget('[data-action="language"]'),
    });

    expect(root.innerHTML).toContain("Switch language 中文");
    expect(root.innerHTML).not.toContain("切换语言 EN");
  });

  test("restart rebuilds the shooter state", async () => {
    const initGame = await loadInitGame();
    const root = createMockRoot();

    initGame(root);

    mocks.getLoopConfig().setState({
      ...createInitialState(LANGUAGES.EN),
      gameOver: true,
      messageKey: "runner.gameOver",
      message: "Game over. Try again.",
    });

    expect(root.innerHTML).toContain('data-action="restart"');

    root.dispatch("click", {
      target: createActionTarget('[data-action="restart"]'),
    });

    expect(mocks.startRunnerLoop).toHaveBeenCalledTimes(2);
    expect(mocks.stopLoop).toHaveBeenCalledTimes(1);
    expect(mocks.getLoopConfig().getState()).toMatchObject({
      gameOver: false,
      language: LANGUAGES.EN,
      messageKey: "start",
      wave: 1,
    });
    expect(root.innerHTML).not.toContain('data-action="restart"');
  });

  test("game over automatically restarts a new round", async () => {
    const initGame = await loadInitGame();
    const root = createMockRoot();

    initGame(root);

    mocks.getLoopConfig().setState({
      ...createInitialState(LANGUAGES.ZH),
      gameOver: true,
      status: "gameover",
      messageKey: "damageFatal",
      message: "受到致命伤害。",
    });

    vi.advanceTimersByTime(1600);

    expect(mocks.startRunnerLoop).toHaveBeenCalledTimes(2);
    expect(mocks.stopLoop).toHaveBeenCalledTimes(1);
    expect(mocks.getLoopConfig().getState()).toMatchObject({
      gameOver: false,
      messageKey: "start",
      currentWeapon: "pistol",
      wave: 1,
    });
  });
});
