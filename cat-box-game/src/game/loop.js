import { TANK_STATS, WEAPONS, WAVE_SPAWN_TUNING } from "./constants";
import {
  applyAmmoPickup,
  applyDamage,
  applyShellPickup,
  applyWeaponPickup,
  completeWave,
} from "./state";
import { createEnemySpawnLanes } from "./world";

const FRAME_TIME = 16;
const PLAYER_FOLLOW = 0.18;
const PLAYER_RADIUS = 16;
const ENEMY_RADIUS = 16;
const BULLET_RADIUS = 6;
const PICKUP_RADIUS = 28;
const DEFAULT_STAGE_WIDTH = 1280;
const DEFAULT_STAGE_HEIGHT = 720;

const requestFrameFallback = (callback) => setTimeout(() => callback(Date.now()), FRAME_TIME);
const cancelFrameFallback = (handle) => clearTimeout(handle);

function clamp(value, min, max) {
  return Math.min(max, Math.max(min, value));
}

function lerp(start, end, amount) {
  return start + (end - start) * amount;
}

function distance(left, right) {
  return Math.hypot((left?.x ?? 0) - (right?.x ?? 0), (left?.y ?? 0) - (right?.y ?? 0));
}

function normalizeVector(dx, dy) {
  const magnitude = Math.hypot(dx, dy);

  if (magnitude === 0) {
    return { x: 1, y: 0 };
  }

  return { x: dx / magnitude, y: dy / magnitude };
}

function getStageBounds(state) {
  return state.world?.stageBounds ?? {
    left: 0,
    top: 0,
    width: DEFAULT_STAGE_WIDTH,
    height: DEFAULT_STAGE_HEIGHT,
    right: DEFAULT_STAGE_WIDTH,
    bottom: DEFAULT_STAGE_HEIGHT,
  };
}

function createId(prefix, index, tick) {
  return `${prefix}-${tick}-${index}`;
}

function getTargetPosition(state, input) {
  const bounds = getStageBounds(state);
  const currentTarget = state.player?.target ?? { x: bounds.width / 2, y: bounds.height / 2 };

  return {
    x: clamp(input.targetX ?? currentTarget.x, bounds.left, bounds.right),
    y: clamp(input.targetY ?? currentTarget.y, bounds.top, bounds.bottom),
  };
}

function movePlayer(player, target, step) {
  if (player.controlState === "tank") {
    return {
      ...player,
      position: { ...target },
      target: { ...target },
      vx: 0,
      vy: 0,
    };
  }

  const nextPosition = {
    x: lerp(player.position?.x ?? 0, target.x, PLAYER_FOLLOW * step),
    y: lerp(player.position?.y ?? 0, target.y, PLAYER_FOLLOW * step),
  };

  return {
    ...player,
    target: { ...target },
    position: nextPosition,
    vx: nextPosition.x - (player.position?.x ?? 0),
    vy: nextPosition.y - (player.position?.y ?? 0),
  };
}

function getWeapon(state) {
  return WEAPONS[state.currentWeapon] ?? null;
}

function spawnBullet({ origin, target, damage, speed, kind, owner, tick, index }) {
  const direction = normalizeVector(target.x - origin.x, target.y - origin.y);

  return {
    id: createId(kind, index, tick),
    kind,
    owner,
    x: origin.x,
    y: origin.y,
    vx: direction.x * speed,
    vy: direction.y * speed,
    damage,
    radius: BULLET_RADIUS,
  };
}

function spawnWaveEnemies({ wave, random, stageBounds }) {
  const lanes = createEnemySpawnLanes();
  const enemyCount = WAVE_SPAWN_TUNING.baseEnemyCount + Math.max(0, wave - 1) * WAVE_SPAWN_TUNING.enemyGrowthPerWave;

  return Array.from({ length: enemyCount }, (_, index) => {
    const lane = lanes[index % lanes.length];
    const offset = (typeof random === "function" ? random() : Math.random()) * 30 - 15;

    return {
      id: createId("enemy", index, wave),
      x: clamp(lane.x + lane.width / 2 + offset, stageBounds.left + 20, stageBounds.right - 20),
      y: clamp(lane.y, stageBounds.top + 20, stageBounds.bottom - 20),
      health: 2 + Math.floor((wave - 1) / 2),
      speed: 1.4 + wave * 0.18,
      damage: 1,
      radius: ENEMY_RADIUS,
    };
  });
}

function moveEnemies(enemies, playerPosition, step) {
  return enemies.map((enemy) => {
    const direction = normalizeVector(playerPosition.x - enemy.x, playerPosition.y - enemy.y);
    const speed = (enemy.speed ?? 1.4) * step;

    return {
      ...enemy,
      x: enemy.x + direction.x * speed,
      y: enemy.y + direction.y * speed,
    };
  });
}

function moveBullets(bullets, step) {
  return bullets.map((bullet) => ({
    ...bullet,
    x: bullet.x + (bullet.vx ?? 0) * step,
    y: bullet.y + (bullet.vy ?? 0) * step,
  }));
}

function collectPickups(state) {
  const playerPosition = state.player?.position ?? { x: 0, y: 0 };
  const tankPosition = state.tank?.position ?? playerPosition;
  let nextState = state;

  for (const pickup of state.pickups?.weapons ?? []) {
    if (distance(playerPosition, pickup) <= PICKUP_RADIUS) {
      nextState = applyWeaponPickup(nextState, pickup);
    }
  }

  for (const pickup of state.pickups?.ammo ?? []) {
    if (distance(playerPosition, pickup) <= PICKUP_RADIUS) {
      nextState = applyAmmoPickup(nextState, pickup);
    }
  }

  if (state.tank?.occupiedBy === "player") {
    for (const pickup of state.pickups?.shells ?? []) {
      if (distance(tankPosition, pickup) <= PICKUP_RADIUS) {
        nextState = applyShellPickup(nextState, pickup);
      }
    }
  }

  return nextState;
}

function firePlayerBullet(state, target, tick, random) {
  const weapon = getWeapon(state);
  if (!weapon || (state.ammo ?? 0) < (weapon.ammoPerShot ?? 1)) {
    return state;
  }

  const player = state.player ?? {};
  if ((player.fireCooldownRemainingMs ?? 0) > 0) {
    return {
      ...state,
      player,
    };
  }

  const spread = typeof random === "function" ? random() : Math.random();
  const origin = player.position ?? target;
  const bullets = state.bullets ?? [];
  const nextBullet = spawnBullet({
    origin,
    target: {
      x: target.x + (spread - 0.5) * 16,
      y: target.y + (spread - 0.5) * 16,
    },
    damage: weapon.damage ?? 1,
    speed: 12,
    kind: "bullet",
    owner: "player",
    tick,
    index: bullets.length,
  });

  return {
    ...state,
    ammo: Math.max(0, (state.ammo ?? 0) - (weapon.ammoPerShot ?? 1)),
    bullets: [...bullets, nextBullet],
    player: {
      ...player,
      fireCooldownRemainingMs: weapon.fireCooldownMs,
    },
  };
}

function fireTankShell(state, tick, random) {
  const tank = state.tank ?? {};
  if (tank.occupiedBy !== "player" || (tank.shells ?? 0) <= 0) {
    return state;
  }

  if ((tank.fireCooldownRemainingMs ?? 0) > 0) {
    return {
      ...state,
      tank,
    };
  }

  const enemies = state.enemies ?? [];
  const fallbackTarget = {
    x: tank.position?.x ?? 0,
    y: 0,
  };
  const nearestEnemy = enemies.reduce((best, enemy) => {
    if (!best) {
      return enemy;
    }

    return distance(tank.position, enemy) < distance(tank.position, best) ? enemy : best;
  }, null);
  const target = nearestEnemy ?? fallbackTarget;
  const spread = typeof random === "function" ? random() : Math.random();
  const bullet = spawnBullet({
    origin: tank.position ?? fallbackTarget,
    target: {
      x: target.x + (spread - 0.5) * 12,
      y: target.y,
    },
    damage: TANK_STATS.shellDamage ?? 3,
    speed: TANK_STATS.shellSpeed,
    kind: "shell",
    owner: "player",
    tick,
    index: (state.bullets ?? []).length,
  });

  return {
    ...state,
    bullets: [...(state.bullets ?? []), bullet],
    tank: {
      ...tank,
      shells: Math.max(0, (tank.shells ?? 0) - 1),
      fireCooldownRemainingMs: TANK_STATS.fireCooldownMs,
    },
  };
}

function resolveBulletHits(state) {
  const remainingEnemies = [...(state.enemies ?? [])];
  const remainingBullets = [];
  let nextState = state;

  for (const bullet of state.bullets ?? []) {
    let hit = false;

    for (let index = 0; index < remainingEnemies.length; index += 1) {
      const enemy = remainingEnemies[index];
      if (distance(bullet, enemy) <= (bullet.radius ?? BULLET_RADIUS) + (enemy.radius ?? ENEMY_RADIUS)) {
        const nextHealth = (enemy.health ?? 1) - (bullet.damage ?? 1);
        hit = true;

        if (nextHealth <= 0) {
          remainingEnemies.splice(index, 1);
        } else {
          remainingEnemies[index] = {
            ...enemy,
            health: nextHealth,
          };
        }

        break;
      }
    }

    if (!hit) {
      remainingBullets.push(bullet);
    }
  }

  nextState = {
    ...nextState,
    bullets: remainingBullets,
    enemies: remainingEnemies,
  };

  for (const enemy of nextState.enemies ?? []) {
    if (distance(enemy, nextState.player?.position ?? { x: 0, y: 0 }) <= (enemy.radius ?? ENEMY_RADIUS) + PLAYER_RADIUS) {
      nextState = applyDamage(nextState, enemy.damage ?? 1);
      break;
    }
  }

  return nextState;
}

function queueNextWave(state, random) {
  const stageBounds = getStageBounds(state);
  const nextWave = completeWave(state);

  return {
    ...nextWave,
    enemies: spawnWaveEnemies({
      wave: nextWave.wave ?? 1,
      random,
      stageBounds,
    }),
  };
}

function spawnInitialWave(state, random) {
  const stageBounds = getStageBounds(state);

  return {
    ...state,
    enemies: spawnWaveEnemies({
      wave: state.wave ?? 1,
      random,
      stageBounds,
    }),
    waveSpawned: true,
  };
}

export function advanceRunnerFrame(state, input = {}, options = {}) {
  if (state.gameOver) {
    return state;
  }

  const random = options.random ?? Math.random;
  const frameTime = options.frameTime ?? FRAME_TIME;
  const step = frameTime / FRAME_TIME;
  const target = getTargetPosition(state, input);

  let nextState = {
    ...state,
    player: movePlayer(state.player ?? {}, target, step),
  };

  if (state.tank?.occupiedBy === "player") {
    nextState = {
      ...nextState,
      player: {
        ...nextState.player,
        position: { ...(state.tank.position ?? nextState.player.position) },
      },
    };
  }

  const playerFireRemaining = Math.max(0, (nextState.player?.fireCooldownRemainingMs ?? 0) - frameTime);
  nextState = {
    ...nextState,
    player: {
      ...nextState.player,
      fireCooldownRemainingMs: playerFireRemaining,
    },
    tank: {
      ...nextState.tank,
      fireCooldownRemainingMs: Math.max(0, (nextState.tank?.fireCooldownRemainingMs ?? 0) - frameTime),
    },
  };

  nextState = collectPickups(nextState);

  if (input.firingPressed) {
    nextState = firePlayerBullet(nextState, target, Math.floor((options.now ?? 0) / FRAME_TIME), random);
  }

  if (nextState.tank?.occupiedBy === "player") {
    nextState = fireTankShell(nextState, Math.floor((options.now ?? 0) / FRAME_TIME), random);
  }

  nextState = {
    ...nextState,
    enemies: moveEnemies(nextState.enemies ?? [], nextState.player?.position ?? target, step),
    bullets: moveBullets(nextState.bullets ?? [], step),
  };

  nextState = resolveBulletHits(nextState);

  if ((nextState.enemies ?? []).length === 0) {
    nextState = nextState.waveSpawned || (nextState.wave ?? 1) > 1
      ? queueNextWave(nextState, random)
      : spawnInitialWave(nextState, random);
  }

  return nextState;
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
