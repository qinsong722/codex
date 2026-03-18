import { describe, expect, test } from "vitest";
import { LANGUAGES, getText, toggleLanguage } from "../src/game/i18n";

describe("getText", () => {
  test("Chinese labels return Chinese text", () => {
    expect(getText("box.safe", LANGUAGES.ZH)).toBe("\u5b89\u5168\u4e00\u70b9");
    expect(getText("runner.restart", LANGUAGES.ZH)).toBe("\u91cd\u6765\u4e00\u6b21");
  });

  test("English labels return English text", () => {
    expect(getText("box.safe", LANGUAGES.EN)).toBe("Safer");
    expect(getText("runner.restart", LANGUAGES.EN)).toBe("Restart run");
  });
});

describe("toggleLanguage", () => {
  test("language toggle flips between the two modes", () => {
    expect(toggleLanguage(LANGUAGES.ZH)).toBe(LANGUAGES.EN);
    expect(toggleLanguage(LANGUAGES.EN)).toBe(LANGUAGES.ZH);
  });
});
