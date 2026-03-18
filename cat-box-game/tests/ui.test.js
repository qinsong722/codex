import { describe, expect, test, vi } from "vitest";
import { LANGUAGES } from "../src/game/i18n";
import { createInitialState } from "../src/game/state";

const stopLoop = vi.fn();
let loopConfig = null;

vi.mock("../src/game/loop", () => ({
  startRunnerLoop: vi.fn((config) => {
    loopConfig = config;
    return stopLoop;
  }),
}));

import { initGame } from "../src/game/ui";

function createMockRoot() {
  const listeners = {};

  return {
    innerHTML: "",
    addEventListener(type, handler) {
      listeners[type] = handler;
    },
    dispatch(type, target) {
      listeners[type]?.({ target });
    },
  };
}

function createTarget(selectorToMatch) {
  return {
    closest(selector) {
      return selector === selectorToMatch ? {} : null;
    },
  };
}

describe("initGame", () => {
  test("re-renders language changes and restarts from the current language", () => {
    const root = createMockRoot();
    initGame(root);

    expect(root.innerHTML).toContain("data-runner-stage");
    expect(root.innerHTML).toContain("\u5207\u6362\u8bed\u8a00 EN");

    root.dispatch("click", createTarget("[data-action='language']"));
    expect(root.innerHTML).toContain("Switch language \u4e2d\u6587");

    loopConfig.setState({
      ...createInitialState(LANGUAGES.EN),
      gameOver: true,
      messageKey: "runner.gameOver",
      message: "Game over. Try again.",
    });

    expect(root.innerHTML).toContain('data-action="restart"');

    root.dispatch("click", createTarget("[data-action='restart']"));

    expect(root.innerHTML).toContain("Switch language \u4e2d\u6587");
    expect(root.innerHTML).not.toContain('data-action="restart"');
    expect(stopLoop).toHaveBeenCalled();
  });

  test("requests a jump as soon as the pointer is pressed on the stage", () => {
    const root = createMockRoot();
    initGame(root);

    root.dispatch("pointerdown", createTarget("[data-runner-stage]"));

    expect(loopConfig.input.jumpRequested).toBe(true);
  });
});
