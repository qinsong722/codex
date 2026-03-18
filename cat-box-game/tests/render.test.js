import { describe, expect, test } from "vitest";
import { createInitialState } from "../src/game/state";
import { LANGUAGES } from "../src/game/i18n";
import { renderGame } from "../src/game/render";

describe("renderGame", () => {
  test("renders the runner hud and stage in Chinese", () => {
    const html = renderGame(createInitialState(LANGUAGES.ZH));

    expect(html).toContain("\u7b49\u7ea7");
    expect(html).toContain("\u751f\u547d");
    expect(html).toContain("data-runner-stage");
    expect(html).toContain("runner-ground");
    expect(html).toContain("runner-platform");
    expect(html).toContain("runner-mouse");
  });

  test("renders a restart button and game over feedback", () => {
    const html = renderGame({
      ...createInitialState(LANGUAGES.EN),
      gameOver: true,
      messageKey: "runner.gameOver",
      message: "Game over. Try again.",
    });

    expect(html).toContain('data-action="restart"');
    expect(html).toContain("Game over. Try again.");
  });
});
