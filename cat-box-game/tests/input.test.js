import { describe, expect, test } from "vitest";
import * as input from "../src/game/input";

const {
  applyPointerMove,
  createInputState,
  requestLanguageToggle,
  requestRestart,
  setFiringPressed,
} = input;

describe("applyPointerMove", () => {
  test("updates the player target coordinates from pointer movement", () => {
    const input = createInputState();

    applyPointerMove(
      input,
      { clientX: 260, clientY: 140 },
      { left: 100, top: 20, width: 200, height: 200 },
    );

    expect(input.targetX).toBe(160);
    expect(input.targetY).toBe(120);
  });

  test("clamps the player target coordinates within the play area", () => {
    const input = createInputState();

    applyPointerMove(
      input,
      { clientX: 20, clientY: 0 },
      { left: 100, top: 50, width: 200, height: 100 },
    );

    expect(input.targetX).toBe(0);
    expect(input.targetY).toBe(0);
  });
});

describe("firing state", () => {
  test("pointer down starts firing", () => {
    const input = createInputState();

    setFiringPressed(input, true);

    expect(input.firingPressed).toBe(true);
  });

  test("pointer up stops firing", () => {
    const input = createInputState();

    setFiringPressed(input, false);

    expect(input.firingPressed).toBe(false);
  });
});

describe("click actions", () => {
  test("legacy jump input is no longer exported", () => {
    expect("requestJump" in input).toBe(false);
  });

  test("language button clicks request a language toggle", () => {
    const input = createInputState();

    requestLanguageToggle(input);

    expect(input.languageToggleRequested).toBe(true);
  });

  test("restart button clicks request a restart", () => {
    const input = createInputState();

    requestRestart(input);

    expect(input.restartRequested).toBe(true);
  });
});
