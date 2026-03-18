import { describe, expect, test } from "vitest";
import { getSoundProfile } from "../src/game/audio";

describe("getSoundProfile", () => {
  test("returns a jump profile for jump feedback", () => {
    const profile = getSoundProfile("runner.jump");

    expect(profile?.notes[0]).toMatchObject({
      frequency: 740,
      type: "triangle",
    });
  });

  test("returns null for unknown feedback", () => {
    expect(getSoundProfile("runner.unknown")).toBeNull();
  });
});
