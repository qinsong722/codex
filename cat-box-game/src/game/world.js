const DEFAULT_PLATFORM_COUNT = 5;
const PLATFORM_WIDTH = 120;
const PLATFORM_HEIGHT = 16;
const PLATFORM_GAP = 135;
const GROUND_HEIGHT = 40;
const PLATFORM_BASE_Y = 52;
const LOW_PLATFORM_STEP = 12;
const GROUND_MOUSE_GAP = 220;

function roll(random) {
  return typeof random === "function" ? random() : Math.random();
}

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
