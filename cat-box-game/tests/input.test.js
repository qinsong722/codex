import { describe, expect, test } from "vitest";
import {
  applyPointerMove,
  createInputState,
  requestJump,
  requestLanguageToggle,
} from "../src/game/input";

describe("applyPointerMove", () => {
  test("updates the target x position from pointer movement", () => {
    const input = createInputState();

    applyPointerMove(input, { clientX: 260 }, { left: 100, width: 200 });

    expect(input.targetX).toBe(160);
  });

  test("clamps the target x position within the play area", () => {
    const input = createInputState();

    applyPointerMove(input, { clientX: 20 }, { left: 100, width: 200 });

    expect(input.targetX).toBe(0);
  });
});

describe("click actions", () => {
  test("regular clicks request a jump", () => {
    const input = createInputState();

    requestJump(input);

    expect(input.jumpRequested).toBe(true);
  });

  test("language button clicks request a language toggle", () => {
    const input = createInputState();

    requestLanguageToggle(input);

    expect(input.languageToggleRequested).toBe(true);
  });
});
