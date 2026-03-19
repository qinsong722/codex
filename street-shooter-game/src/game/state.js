import { MAX_AMMO, MAX_HEALTH, LEVEL_UP_REQUIREMENTS, TANK_SHELL_LIMIT } from "./constants";
import { LANGUAGES } from "./i18n";
import { applyEnemyContact, getAmmoAfterPickup, getShellsAfterPickup, isWaveComplete } from "./rules";
import {
  createAmmoPickupPlacements,
  createStreetWorld,
  createTankShellPickupPlacements,
  createWeaponPickupPlacements,
} from "./world";

export const GROUND_Y = 0;
export const JUMP_VELOCITY = -14;
export const RUN_SPEED = 6;
export const FALL_RESET_Y = 0;
export const DEFAULT_SCREEN_X = 240;
export const JUMP_BUFFER_FRAMES = 6;
export const COYOTE_FRAMES = 5;

const MESSAGE_TABLE = {
  [LANGUAGES.ZH]: {
    start: "\u6218\u6597\u5f00\u59cb\uff0c\u51c6\u5907\u5f00\u706b\u3002",
    weaponPickup: "\u6362\u4e0a\u4e86\u65b0\u6b66\u5668\u3002",
    ammoPickup: "\u5f39\u836f\u8865\u5145\u5b8c\u6bd5\u3002",
    tankEnter: "\u5df2\u8fdb\u5165\u5766\u514b\u3002",
    shellPickup: "\u5766\u514b\u70ae\u5f39\u5df2\u88c5\u586b\u3002",
    damage: "\u53d7\u5230\u4f24\u5bb3\u3002",
    damageFatal: "\u53d7\u5230\u81f4\u547d\u4f24\u5bb3\u3002",
    waveClear: "\u4e0b\u4e00\u6ce2\u654c\u4eba\u6765\u88ad\u3002",
  },
  [LANGUAGES.EN]: {
    start: "Battle ready.",
    weaponPickup: "Weapon swapped.",
    ammoPickup: "Ammo topped up.",
    tankEnter: "Entered the tank.",
    shellPickup: "Tank shells loaded.",
    damage: "Took damage.",
    damageFatal: "Took lethal damage.",
    waveClear: "Next wave incoming.",
  },
};

function getMessage(messageKey, language) {
  return MESSAGE_TABLE[language]?.[messageKey] ?? MESSAGE_TABLE[LANGUAGES.ZH]?.[messageKey] ?? messageKey;
}

function createStatusPayload(state, messageKey, language = state.language) {
  const message = getMessage(messageKey, language);

  return {
    ...state,
    language,
    messageKey,
    message,
    statusMessage: message,
  };
}

function createInitialPickups() {
  return {
    weapons: createWeaponPickupPlacements(),
    ammo: createAmmoPickupPlacements(),
    shells: createTankShellPickupPlacements(),
  };
}

function removePickup(collection, pickup, matcher) {
  if (!pickup) {
    return collection;
  }

  return collection.filter((item) => !matcher(item, pickup));
}

function matchesWeaponPickup(item, pickup) {
  return item.weapon === pickup.weapon && item.x === pickup.x && item.y === pickup.y;
}

function matchesAmmoPickup(item, pickup) {
  return item.amount === pickup.amount && item.x === pickup.x && item.y === pickup.y;
}

function matchesShellPickup(item, pickup) {
  return item.amount === pickup.amount && item.x === pickup.x && item.y === pickup.y;
}

export function createInitialState(language = LANGUAGES.ZH, random = Math.random) {
  const world = createStreetWorld({ random });
  const centerX = world.stageBounds.width / 2;
  const centerY = world.stageBounds.height / 2;

  return {
    status: "running",
    gameOver: false,
    language,
    messageKey: "start",
    message: getMessage("start", language),
    statusMessage: getMessage("start", language),
    health: MAX_HEALTH,
    world,
    player: {
      position: { x: centerX, y: centerY },
      target: { x: centerX, y: centerY },
      health: MAX_HEALTH,
      alive: true,
      controlState: "onFoot",
    },
    currentWeapon: "pistol",
    ammo: Math.min(30, MAX_AMMO - 1),
    tank: {
      position: { ...world.tankPlacement },
      occupiedBy: null,
      shells: 0,
    },
    bullets: [],
    enemies: [],
    pickups: createInitialPickups(),
    wave: 1,
    kills: 0,
  };
}

export function applyWeaponPickup(state, pickup) {
  if (!pickup?.weapon) {
    return state;
  }

  return createStatusPayload(
    {
      ...state,
      currentWeapon: pickup.weapon,
      pickups: {
        ...state.pickups,
        weapons: removePickup(state.pickups?.weapons ?? [], pickup, matchesWeaponPickup),
      },
    },
    "weaponPickup",
  );
}

export function applyAmmoPickup(state, pickup) {
  const amount = pickup?.amount ?? 0;

  return createStatusPayload(
    {
      ...state,
      ammo: getAmmoAfterPickup({ ammo: state.ammo ?? 0, amount }),
      pickups: {
        ...state.pickups,
        ammo: removePickup(state.pickups?.ammo ?? [], pickup, matchesAmmoPickup),
      },
    },
    "ammoPickup",
  );
}

export function enterTank(state) {
  return createStatusPayload(
    {
      ...state,
      player: {
        ...state.player,
        controlState: "tank",
        position: { ...state.tank.position },
        target: { ...state.tank.position },
      },
      tank: {
        ...state.tank,
        occupiedBy: "player",
      },
    },
    "tankEnter",
  );
}

export function applyShellPickup(state, pickup) {
  const amount = pickup?.amount ?? 0;

  return createStatusPayload(
    {
      ...state,
      tank: {
        ...state.tank,
        shells: getShellsAfterPickup({ shells: state.tank?.shells ?? 0, amount }),
      },
      pickups: {
        ...state.pickups,
        shells: removePickup(state.pickups?.shells ?? [], pickup, matchesShellPickup),
      },
    },
    "shellPickup",
  );
}

export function applyDamage(state, damage = 1) {
  const nextHealth = applyEnemyContact({ health: state.player?.health ?? 0, damage });
  const nextState = {
    ...state,
    health: nextHealth,
    player: {
      ...state.player,
      health: nextHealth,
      alive: nextHealth > 0,
    },
  };

  if (nextHealth <= 0) {
    return createStatusPayload(
      {
        ...nextState,
        status: "gameover",
        gameOver: true,
      },
      "damageFatal",
    );
  }

  return createStatusPayload(nextState, "damage");
}

export function completeWave(state) {
  if (!isWaveComplete({ enemies: state.enemies ?? [] })) {
    return state;
  }

  return createStatusPayload(
    {
      ...state,
      wave: (state.wave ?? 0) + 1,
    },
    "waveClear",
  );
}

export function setLanguage(state, language) {
  return createStatusPayload(state, state.messageKey ?? "start", language);
}

// Legacy compatibility exports. They stay pure, but the new shooter state does not use them.
export function applyJump(state) {
  return state;
}

export function applyMovementTarget(state) {
  return state;
}

export function applyLevelUp(state) {
  return state;
}

export function resolveCatch(state) {
  return state;
}

export function resolveFallReset(state) {
  return state;
}

export { LEVEL_UP_REQUIREMENTS, MAX_AMMO, TANK_SHELL_LIMIT };
