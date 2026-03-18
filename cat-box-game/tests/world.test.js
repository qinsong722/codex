import { describe, expect, test } from "vitest";
import { createElevatedPlatforms, createGroundArea, createWorld } from "../src/game/world";

function createSequenceRandom(values) {
  let index = 0;

  return () => {
    const value = values[index % values.length];
    index += 1;
    return value;
  };
}

describe("createGroundArea", () => {
  test("ground extends behind the cat position", () => {
    const ground = createGroundArea({ catX: 25 });

    expect(ground.startX).toBeLessThanOrEqual(25);
    expect(ground.endX).toBeGreaterThan(25);
  });
});

describe("createElevatedPlatforms", () => {
  test("platforms are above the ground line", () => {
    const ground = createGroundArea({ catX: 0 });
    const platforms = createElevatedPlatforms({ catX: 0, level: 1, random: createSequenceRandom([0.5]) });

    expect(platforms.length).toBeGreaterThan(0);
    expect(platforms.every((platform) => platform.y < ground.y)).toBe(true);
  });

  test("some platforms can be generated without mice", () => {
    const platforms = createElevatedPlatforms({
      catX: 0,
      level: 2,
      random: createSequenceRandom([0.4, 0.1]),
    });

    expect(platforms.some((platform) => platform.mouse === null)).toBe(true);
    expect(platforms.some((platform) => platform.mouse)).toBe(true);
  });
});

describe("createWorld", () => {
  test("platforms are generated ahead of the cat", () => {
    const world = createWorld({ catX: 10, level: 1, random: () => 0.5 });

    expect(world.ground.startX).toBeLessThanOrEqual(10);
    expect(world.platforms.length).toBeGreaterThan(0);
    expect(world.platforms.every((platform) => platform.x > 10)).toBe(true);
  });

  test("some platforms include mice", () => {
    const world = createWorld({ catX: 0, level: 2, random: () => 0.4 });

    expect(world.platforms.some((platform) => platform.mouse)).toBe(true);
  });

  test("mouse levels scale from easy to harder over time", () => {
    const easyWorld = createWorld({ catX: 0, level: 1, random: () => 0.99 });
    const hardWorld = createWorld({ catX: 0, level: 6, random: () => 0.99 });

    const easyMouseLevels = easyWorld.platforms
      .map((platform) => platform.mouse?.level)
      .filter(Boolean);
    const hardMouseLevels = hardWorld.platforms
      .map((platform) => platform.mouse?.level)
      .filter(Boolean);

    expect(Math.max(...hardMouseLevels)).toBeGreaterThan(Math.max(...easyMouseLevels));
  });

  test("platforms stay above the world ground", () => {
    const world = createWorld({ catX: 0, level: 1, random: () => 0.5 });

    expect(world.platforms.every((platform) => platform.y < world.ground.y)).toBe(true);
  });
});
