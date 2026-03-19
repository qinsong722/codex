import { describe, expect, test } from "vitest";
import {
  LANGUAGES,
  getHudLabel,
  getStatusLabel,
  getText,
  getWeaponLabel,
  toggleLanguage,
} from "../src/game/i18n";

describe("getText", () => {
  test("Chinese shooter HUD labels return Chinese text", () => {
    expect(getText("hud.health", LANGUAGES.ZH)).toBe("\u8840\u91cf");
    expect(getText("hud.ammo", LANGUAGES.ZH)).toBe("\u5b50\u5f39");
    expect(getText("hud.wave", LANGUAGES.ZH)).toBe("\u6ce2\u6b21");
    expect(getText("hud.kills", LANGUAGES.ZH)).toBe("\u51fb\u6740");
    expect(getText("hud.tank", LANGUAGES.ZH)).toBe("\u5766\u514b");
  });

  test("English shooter HUD labels return English text", () => {
    expect(getText("hud.health", LANGUAGES.EN)).toBe("Health");
    expect(getText("hud.ammo", LANGUAGES.EN)).toBe("Ammo");
    expect(getText("hud.wave", LANGUAGES.EN)).toBe("Wave");
    expect(getText("hud.kills", LANGUAGES.EN)).toBe("Kills");
    expect(getText("hud.tank", LANGUAGES.EN)).toBe("Tank");
  });

  test("HUD helper reads from the same translations", () => {
    expect(getHudLabel("health", LANGUAGES.ZH)).toBe("\u8840\u91cf");
    expect(getHudLabel("wave", LANGUAGES.EN)).toBe("Wave");
  });

  test("weapon and status helpers read from the same translations", () => {
    expect(getWeaponLabel("pistol", LANGUAGES.ZH)).toBe("\u624b\u67aa");
    expect(getStatusLabel("health", LANGUAGES.EN)).toBe("Health");
  });

  test("existing box and runner translations still work", () => {
    expect(getText("box.safe", LANGUAGES.ZH)).toBe("\u5b89\u5168\u4e00\u70b9");
    expect(getText("box.safe", LANGUAGES.EN)).toBe("Safer");
    expect(getText("runner.restart", LANGUAGES.ZH)).toBe("\u91cd\u6765\u4e00\u6b21");
    expect(getText("runner.restart", LANGUAGES.EN)).toBe("Restart run");
  });
});

describe("toggleLanguage", () => {
  test("language toggle flips between the two modes", () => {
    expect(toggleLanguage(LANGUAGES.ZH)).toBe(LANGUAGES.EN);
    expect(toggleLanguage(LANGUAGES.EN)).toBe(LANGUAGES.ZH);
  });
});
