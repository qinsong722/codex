const STREET_STAGE_WIDTH = 1280;
const STREET_STAGE_HEIGHT = 720;

const STREET_DECORATION_ANCHORS = [
  { x: 120, y: 96, kind: "streetlight" },
  { x: 310, y: 132, kind: "barrier" },
  { x: 980, y: 118, kind: "streetlight" },
  { x: 1160, y: 168, kind: "barrier" },
];

const WEAPON_PICKUP_PLACEMENTS = [
  { x: 180, y: 520, weapon: "shotgun" },
  { x: 1080, y: 500, weapon: "rifle" },
];

const AMMO_PICKUP_PLACEMENTS = [
  { x: 360, y: 560, amount: 24 },
  { x: 640, y: 600, amount: 24 },
  { x: 900, y: 556, amount: 24 },
];

const AMMO_PICKUP_CANDIDATE_PLACEMENTS = [
  { x: 220, y: 520, amount: 24 },
  { x: 360, y: 560, amount: 24 },
  { x: 500, y: 610, amount: 24 },
  { x: 640, y: 600, amount: 24 },
  { x: 780, y: 548, amount: 24 },
  { x: 900, y: 556, amount: 24 },
  { x: 1050, y: 515, amount: 24 },
];

const TANK_PLACEMENT = { x: 640, y: 420, facing: "south" };

const TANK_SHELL_PICKUP_PLACEMENTS = [
  { x: 240, y: 220, amount: 2 },
  { x: 1040, y: 240, amount: 2 },
];

const ENEMY_SPAWN_LANES = [
  { x: 180, y: 88, width: 160, direction: "down" },
  { x: 560, y: 72, width: 160, direction: "down" },
  { x: 940, y: 96, width: 160, direction: "down" },
];

function clonePlacements(placements) {
  return placements.map((placement) => ({ ...placement }));
}

function roll(random) {
  return typeof random === "function" ? random() : Math.random();
}

function shufflePlacements(placements, random = Math.random) {
  const nextPlacements = clonePlacements(placements);

  for (let index = nextPlacements.length - 1; index > 0; index -= 1) {
    const swapIndex = Math.floor(roll(random) * (index + 1));
    [nextPlacements[index], nextPlacements[swapIndex]] = [nextPlacements[swapIndex], nextPlacements[index]];
  }

  return nextPlacements;
}

export function createStageBounds() {
  return {
    left: 0,
    top: 0,
    width: STREET_STAGE_WIDTH,
    height: STREET_STAGE_HEIGHT,
    right: STREET_STAGE_WIDTH,
    bottom: STREET_STAGE_HEIGHT,
  };
}

export function createStreetDecorationAnchors() {
  return clonePlacements(STREET_DECORATION_ANCHORS);
}

export function createWeaponPickupPlacements() {
  return clonePlacements(WEAPON_PICKUP_PLACEMENTS);
}

export function createAmmoPickupPlacements(random = Math.random) {
  return shufflePlacements(AMMO_PICKUP_CANDIDATE_PLACEMENTS, random).slice(0, AMMO_PICKUP_PLACEMENTS.length);
}

export function createTankPlacement() {
  return { ...TANK_PLACEMENT };
}

export function createTankShellPickupPlacements() {
  return clonePlacements(TANK_SHELL_PICKUP_PLACEMENTS);
}

export function createEnemySpawnLanes() {
  return clonePlacements(ENEMY_SPAWN_LANES);
}

export function createStreetWorld({ random = Math.random } = {}) {
  return {
    stageBounds: createStageBounds(),
    streetDecorationAnchors: createStreetDecorationAnchors(),
    weaponPickupPlacements: createWeaponPickupPlacements(),
    ammoPickupPlacements: createAmmoPickupPlacements(random),
    tankPlacement: createTankPlacement(),
    tankShellPickupPlacements: createTankShellPickupPlacements(),
    enemySpawnLanes: createEnemySpawnLanes(),
  };
}

const DEFAULT_PLATFORM_COUNT = 5;
const PLATFORM_WIDTH = 120;
const PLATFORM_HEIGHT = 16;
const PLATFORM_GAP = 135;
const GROUND_HEIGHT = 40;
const PLATFORM_BASE_Y = 52;
const LOW_PLATFORM_STEP = 12;
const GROUND_MOUSE_GAP = 220;

export function createGroundArea({ catX = 0, width = 1200, startX = catX - 200 } = {}) {
  return {
    startX,
    endX: startX + width,
    y: 0,
    width,
    height: GROUND_HEIGHT,
  };
}

export function createElevatedPlatforms({ catX = 0, level = 1, random = Math.random } = {}) {
  const platforms = [];
  let currentX = catX + 180;

  for (let index = 0; index < DEFAULT_PLATFORM_COUNT; index += 1) {
    const platformWidth = PLATFORM_WIDTH + Math.floor(roll(random) * 40);
    const platformY = -(PLATFORM_BASE_Y + index * LOW_PLATFORM_STEP);
    const mouseLevel = Math.max(1, level + Math.floor(index / 2));
    const hasMouse = roll(random) > 0.12;

    platforms.push({
      x: currentX,
      y: platformY,
      width: platformWidth,
      height: PLATFORM_HEIGHT,
      hasBox: true,
      mouse: hasMouse ? { level: mouseLevel } : null,
    });

    currentX += PLATFORM_GAP + Math.floor(roll(random) * 50);
  }

  return platforms;
}

export function createGroundMice({ catX = 0, level = 1, random = Math.random } = {}) {
  const mice = [];
  let currentX = catX + 120;

  for (let index = 0; index < 4; index += 1) {
    const shouldSpawn = roll(random) > 0.45;
    mice.push({
      x: currentX,
      y: 0,
      hasBox: true,
      mouse: shouldSpawn
        ? {
            level: Math.max(1, level + (index > 2 ? 1 : 0)),
          }
        : null,
    });

    currentX += GROUND_MOUSE_GAP + Math.floor(roll(random) * 40);
  }

  return mice;
}

export function createWorld({ catX = 0, level = 1, random = Math.random } = {}) {
  return {
    ground: createGroundArea({ catX }),
    groundMice: createGroundMice({ catX, level, random }),
    platforms: createElevatedPlatforms({ catX, level, random }),
  };
}
