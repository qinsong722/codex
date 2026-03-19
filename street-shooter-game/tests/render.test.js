import { describe, expect, test } from "vitest";
import { createInitialState } from "../src/game/state";
import { LANGUAGES, getHudLabel, getStatusLabel } from "../src/game/i18n";
import { renderGame } from "../src/game/render";

describe("renderGame", () => {
  test("renders hud labels for health ammo wave and kills", () => {
    const html = renderGame({
      ...createInitialState(LANGUAGES.EN),
      health: 3,
      ammo: 12,
      wave: 4,
      kills: 7,
    });

    expect(html).toContain(getHudLabel("health", LANGUAGES.EN));
    expect(html).toContain(getHudLabel("ammo", LANGUAGES.EN));
    expect(html).toContain(getHudLabel("wave", LANGUAGES.EN));
    expect(html).toContain(getHudLabel("kills", LANGUAGES.EN));
    expect(html).toContain("3");
    expect(html).toContain("12");
    expect(html).toContain("4");
    expect(html).toContain("7");
  });

  test("renders street background layers and decorative props", () => {
    const html = renderGame({
      ...createInitialState(LANGUAGES.ZH),
      world: {
        ...createInitialState(LANGUAGES.ZH).world,
        streetDecorationAnchors: [
          { x: 120, y: 96, kind: "streetlight" },
          { x: 310, y: 132, kind: "barrier" },
        ],
      },
    });

    expect(html).toContain("street-scene");
    expect(html).toContain("street-road");
    expect(html).toContain("street-lane");
    expect(html).toContain("street-decoration");
    expect(html).toContain("streetlight");
    expect(html).toContain("barrier");
    expect(html).toContain('data-stage="street"');
    expect(html).toContain('class="street-world" style="width:100%; height:100%;"');
  });

  test("renders weapon pickups and ammo pickups", () => {
    const html = renderGame({
      ...createInitialState(LANGUAGES.EN),
      pickups: {
        weapons: [
          { x: 180, y: 520, weapon: "shotgun" },
          { x: 1080, y: 500, weapon: "rifle" },
        ],
        ammo: [
          { x: 360, y: 560, amount: 24 },
          { x: 640, y: 600, amount: 24 },
        ],
        shells: [],
      },
    });

    expect(html).toContain("data-weapon-pickup");
    expect(html).toContain("data-ammo-pickup");
    expect(html).toContain("shotgun");
    expect(html).toContain("rifle");
    expect(html).toContain("24");
    expect(html).toContain("🔫");
    expect(html).toContain("🧰");
  });

  test("renders player enemies and bullets", () => {
    const html = renderGame({
      ...createInitialState(LANGUAGES.EN),
      player: {
        ...createInitialState(LANGUAGES.EN).player,
        position: { x: 260, y: 400 },
        facing: "east",
      },
      enemies: [
        { id: "enemy-1", x: 500, y: 320, health: 2, kind: "drone" },
        { id: "enemy-2", x: 760, y: 280, health: 3, kind: "grunt" },
      ],
      bullets: [
        { id: "bullet-1", x: 320, y: 360, kind: "bullet", owner: "player" },
        { id: "bullet-2", x: 640, y: 260, kind: "shell", owner: "tank" },
      ],
    });

    expect(html).toContain("data-player");
    expect(html).toContain("data-enemy");
    expect(html).toContain("data-bullet");
    expect(html).toContain("drone");
    expect(html).toContain("grunt");
    expect(html).toContain("shell");
    expect(html).toContain("🐱");
  });

  test("renders tank when present", () => {
    const html = renderGame({
      ...createInitialState(LANGUAGES.EN),
      tank: {
        ...createInitialState(LANGUAGES.EN).tank,
        occupiedBy: "player",
        shells: 3,
      },
    });

    expect(html).toContain("data-tank");
    expect(html).toContain(getStatusLabel("tank", LANGUAGES.EN));
    expect(html).toContain("3");
    expect(html).toContain("🛡️");
  });

  test("renders game over banner and restart controls", () => {
    const html = renderGame({
      ...createInitialState(LANGUAGES.EN),
      gameOver: true,
      message: "Game over. Try again.",
    });

    expect(html).toContain("game-result");
    expect(html).toContain("game-over");
    expect(html).toContain('data-action="restart"');
    expect(html).toContain("Game over. Try again.");
  });

  test("renders the corrected language toggle copy", () => {
    const zhHtml = renderGame(createInitialState(LANGUAGES.ZH));
    const enHtml = renderGame(createInitialState(LANGUAGES.EN));

    expect(zhHtml).toContain("切换语言 EN");
    expect(enHtml).toContain("Switch language 中文");
  });
});
