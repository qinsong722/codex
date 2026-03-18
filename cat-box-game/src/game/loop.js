import { createElevatedPlatforms, createGroundMice, createWorld } from "./world";
import {
  applyJump,
  COYOTE_FRAMES,
  DEFAULT_SCREEN_X,
  JUMP_BUFFER_FRAMES,
  resolveCatch,
  resolveFallReset,
} from "./state";

const FRAME_TIME = 16;
const GRAVITY = 1.2;
const FORWARD_SPEED = 6;
const SCREEN_STEER_SPEED = 0.18;
const WORLD_AHEAD_THRESHOLD = 640;
const WORLD_BEHIND_THRESHOLD = 320;
const requestFrameFallback = (callback) => setTimeout(() => callback(Date.now()), FRAME_TIME);
const cancelFrameFallback = (handle) => clearTimeout(handle);

function clamp(value, min, max) {
  return Math.min(max, Math.max(min, value));
}

function getPlatformUnderCat(platforms, x) {
  return platforms.find((platform) => x >= platform.x && x <= platform.x + platform.width) ?? null;
}

function getLandingPlatform(platforms, x, previousY, nextY) {
  const landingPlatforms = platforms.filter(
    (platform) =>
      x >= platform.x &&
      x <= platform.x + platform.width &&
      previousY <= platform.y &&
      nextY >= platform.y,
  );

  if (landingPlatforms.length === 0) {
    return null;
  }

  return landingPlatforms.sort((left, right) => left.y - right.y)[0];
}

function extendWorldAhead(world, catX, level, random) {
  if (world.platforms.length === 0) {
    return createWorld({ catX, level, random });
  }

  const lastPlatform = world.platforms[world.platforms.length - 1];
  const groundItems = world.groundMice ?? [];
  const lastGroundItem = groundItems[groundItems.length - 1] ?? null;
  const needsPlatformExtension = lastPlatform.x - catX < WORLD_AHEAD_THRESHOLD;
  const needsGroundExtension = !lastGroundItem || lastGroundItem.x - catX < WORLD_AHEAD_THRESHOLD;

  if (!needsPlatformExtension && !needsGroundExtension) {
    return world;
  }

  const platformExtension = needsPlatformExtension
    ? createElevatedPlatforms({
        catX: lastPlatform.x + 10,
        level,
        random,
      })
    : [];
  const groundExtension = needsGroundExtension
    ? createGroundMice({
        catX: Math.max(lastGroundItem?.x ?? catX, catX) + 10,
        level,
        random,
      })
    : [];

  return {
    ...world,
    platforms: needsPlatformExtension ? [...world.platforms, ...platformExtension] : world.platforms,
    groundMice: needsGroundExtension ? [...(world.groundMice ?? []), ...groundExtension] : (world.groundMice ?? []),
  };
}

function pruneWorldBehind(world, catX) {
  return {
    ...world,
    groundMice: (world.groundMice ?? []).filter(
      (item) => item.x >= catX - WORLD_BEHIND_THRESHOLD,
    ),
    platforms: world.platforms.filter(
      (platform) => platform.x + platform.width >= catX - WORLD_BEHIND_THRESHOLD,
    ),
  };
}

export function advanceRunnerFrame(state, input = {}, options = {}) {
  if (state.gameOver) {
    return state;
  }

  const random = options.random ?? Math.random;
  const frameTime = options.frameTime ?? FRAME_TIME;
  const step = frameTime / FRAME_TIME;
  const jumpRequested = Boolean(input.jumpRequested);

  input.jumpRequested = false;

  let nextState = state;
  let cat = {
    ...nextState.cat,
    jumpBufferFrames: jumpRequested
      ? JUMP_BUFFER_FRAMES
      : Math.max((nextState.cat.jumpBufferFrames ?? 0) - 1, 0),
    coyoteFramesRemaining: nextState.cat.onGround
      ? COYOTE_FRAMES
      : Math.max((nextState.cat.coyoteFramesRemaining ?? 0) - 1, 0),
  };
  nextState = {
    ...nextState,
    cat,
  };

  if (cat.jumpBufferFrames > 0) {
    nextState = applyJump(nextState);
    cat = { ...nextState.cat };
  }

  const world = nextState.world;
  const previousY = cat.y;
  let fellFromPlatform = false;

  const previousScreenX = cat.screenX ?? DEFAULT_SCREEN_X;
  const targetX = input.targetX ?? previousScreenX;
  const nextCameraX = Math.max(0, (nextState.cameraX ?? 0) + FORWARD_SPEED * step);
  const desiredScreenX = clamp(targetX, 40, 860);
  cat.screenX = previousScreenX + (desiredScreenX - previousScreenX) * SCREEN_STEER_SPEED;
  cat.vx = cat.screenX - previousScreenX;
  cat.x = nextCameraX + cat.screenX;

  if (cat.onGround && cat.y < 0) {
    const support = getPlatformUnderCat(world.platforms, cat.x);
    if (!support || support.y !== cat.y) {
      cat.onGround = false;
      fellFromPlatform = true;
    }
  }

  if (!cat.onGround || fellFromPlatform) {
    cat.vy += GRAVITY * step;
    cat.y += cat.vy * step;
  }

  let updatedWorld = pruneWorldBehind(
    extendWorldAhead(world, cat.x, nextState.level, random),
    cat.x,
  );
  const landingPlatform = getLandingPlatform(updatedWorld.platforms, cat.x, previousY, cat.y);

  if (landingPlatform) {
    cat.y = landingPlatform.y;
    cat.vy = 0;
    cat.onGround = true;

    if (landingPlatform.mouse) {
      const landingIndex = updatedWorld.platforms.indexOf(landingPlatform);
      const clearedWorld = {
        ...updatedWorld,
        platforms: updatedWorld.platforms.map((platform, index) =>
          index === landingIndex ? { ...platform, mouse: null } : platform,
        ),
      };

      nextState = resolveCatch(
        {
          ...nextState,
          cat,
          world: clearedWorld,
        },
        landingPlatform.mouse,
      );
      cat = { ...nextState.cat };
      updatedWorld = nextState.world;
    }
  } else if (cat.y >= 0) {
    if (fellFromPlatform) {
      nextState = resolveFallReset({
        ...nextState,
        cat,
        world: updatedWorld,
      });
      cat = { ...nextState.cat };
    } else {
      cat.y = 0;
      cat.vy = 0;
      cat.onGround = true;
    }
  } else if (cat.onGround) {
    const support = getPlatformUnderCat(updatedWorld.platforms, cat.x);
    if (!support || support.y !== cat.y) {
      cat.onGround = false;
    }
  }

  return {
    ...nextState,
    cat,
    cameraX: nextCameraX,
    world: updatedWorld,
  };
}

export function startRunnerLoop({
  getState,
  setState,
  input,
  random = Math.random,
  requestFrame = globalThis.requestAnimationFrame ?? requestFrameFallback,
  cancelFrame = globalThis.cancelAnimationFrame ?? cancelFrameFallback,
}) {
  let stopped = false;
  let handle = 0;

  function frame() {
    if (stopped) {
      return;
    }

    const currentState = getState();
    const nextState = advanceRunnerFrame(currentState, input, { random, frameTime: FRAME_TIME });
    setState(nextState);

    if (!nextState.gameOver) {
      handle = requestFrame(frame);
    }
  }

  handle = requestFrame(frame);

  return () => {
    stopped = true;
    cancelFrame(handle);
  };
}
