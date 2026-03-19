import { describe, expect, test } from "vitest";
import {
  createStreetWorld,
  createStageBounds,
  createWeaponPickupPlacements,
  createAmmoPickupPlacements,
  createTankPlacement,
  createTankShellPickupPlacements,
  createEnemySpawnLanes,
  createGroundArea,
  createElevatedPlatforms,
  createWorld,
} from "../src/game/world";

describe("createStageBounds", () => {
  test("defines a single-screen street arena", () => {
    const bounds = createStageBounds();

    expect(bounds.width).toBeGreaterThan(0);
    expect(bounds.height).toBeGreaterThan(0);
    expect(bounds.left).toBe(0);
    expect(bounds.top).toBe(0);
    expect(bounds.right).toBe(bounds.width);
    expect(bounds.bottom).toBe(bounds.height);
  });
});

describe("createStreetWorld", () => {
  test("includes stage bounds and decoration anchors", () => {
    const world = createStreetWorld();

    expect(world.stageBounds).toEqual(createStageBounds());
    expect(world.streetDecorationAnchors.length).toBeGreaterThan(0);
  });

  test("includes weapon pickup points", () => {
    const world = createStreetWorld();

    expect(world.weaponPickupPlacements.length).toBeGreaterThan(0);
  });

  test("includes ammo pickup points", () => {
    const world = createStreetWorld();

    expect(world.ammoPickupPlacements.length).toBeGreaterThan(0);
  });

  test("includes one tank spawn", () => {
    const world = createStreetWorld();

    expect(world.tankPlacement).toBeDefined();
    expect(world.tankPlacement).toMatchObject({ x: expect.any(Number), y: expect.any(Number) });
  });

  test("tank shell pickup points are separate from normal ammo pickups", () => {
    const world = createStreetWorld();
    const ammoKeys = new Set(world.ammoPickupPlacements.map((pickup) => `${pickup.x}:${pickup.y}`));

    expect(world.tankShellPickupPlacements.length).toBeGreaterThan(0);
    expect(
      world.tankShellPickupPlacements.every((pickup) => !ammoKeys.has(`${pickup.x}:${pickup.y}`)),
    ).toBe(true);
  });

  test("enemy spawn lanes exist near the front/top side of the stage", () => {
    const world = createStreetWorld();
    const topBand = world.stageBounds.height * 0.35;

    expect(world.enemySpawnLanes.length).toBeGreaterThan(0);
    expect(world.enemySpawnLanes.every((lane) => lane.y <= topBand)).toBe(true);
  });
});

describe("street world builders", () => {
  test("weapon pickups are deterministic", () => {
    expect(createWeaponPickupPlacements()).toEqual(createWeaponPickupPlacements());
  });

  test("ammo pickups reshuffle between rounds when randomness changes", () => {
    const firstRound = createAmmoPickupPlacements(() => 0);
    const secondRound = createAmmoPickupPlacements(() => 0.9);

    expect(firstRound).not.toEqual(secondRound);
    expect(firstRound).toHaveLength(secondRound.length);
    expect(new Set(firstRound.map((pickup) => `${pickup.x}:${pickup.y}`)).size).toBe(firstRound.length);
    expect(new Set(secondRound.map((pickup) => `${pickup.x}:${pickup.y}`)).size).toBe(secondRound.length);
  });

  test("tank spawn is deterministic", () => {
    expect(createTankPlacement()).toEqual(createTankPlacement());
  });

  test("tank shell pickups are deterministic", () => {
    expect(createTankShellPickupPlacements()).toEqual(createTankShellPickupPlacements());
  });

  test("enemy spawn lanes are deterministic", () => {
    expect(createEnemySpawnLanes()).toEqual(createEnemySpawnLanes());
  });
});

describe("legacy world exports", () => {
  test("ground extends behind the cat position", () => {
    const ground = createGroundArea({ catX: 25 });

    expect(ground.startX).toBeLessThanOrEqual(25);
    expect(ground.endX).toBeGreaterThan(25);
  });

  test("platforms are generated above the ground line", () => {
    const ground = createGroundArea({ catX: 0 });
    const platforms = createElevatedPlatforms({ catX: 0, level: 1, random: () => 0.5 });

    expect(platforms.length).toBeGreaterThan(0);
    expect(platforms.every((platform) => platform.y < ground.y)).toBe(true);
  });

  test("world still includes ground and platforms for existing consumers", () => {
    const world = createWorld({ catX: 0, level: 1, random: () => 0.5 });

    expect(world.ground.startX).toBeLessThanOrEqual(0);
    expect(world.groundMice.length).toBeGreaterThan(0);
    expect(world.platforms.length).toBeGreaterThan(0);
  });
});
