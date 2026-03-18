import { MAX_HEALTH, FORM_STAGES, LEVEL_UP_REQUIREMENTS } from "./constants";
import { LANGUAGES, getStageDisplay, getText } from "./i18n";
import { getGrowthThresholdForLevel, resolveRunnerEncounter } from "./rules";
import { createWorld } from "./world";

export const GROUND_Y = 0;
export const JUMP_VELOCITY = -14;
export const RUN_SPEED = 6;
export const FALL_RESET_Y = 0;
export const DEFAULT_SCREEN_X = 240;
export const JUMP_BUFFER_FRAMES = 6;
export const COYOTE_FRAMES = 5;

function getCatForm(level, language = LANGUAGES.ZH) {
  let currentStage = FORM_STAGES[0];

  for (const stage of FORM_STAGES) {
    if (level >= stage.minLevel) {
      currentStage = stage;
    }
  }

  return {
    ...currentStage,
    ...getStageDisplay(currentStage.id, language),
  };
}

function createCat(level, language) {
  return {
    x: DEFAULT_SCREEN_X,
    screenX: DEFAULT_SCREEN_X,
    y: GROUND_Y,
    vx: 0,
    vy: 0,
    onGround: true,
    jumpBufferFrames: 0,
    coyoteFramesRemaining: COYOTE_FRAMES,
    level,
    growth: 0,
    form: getCatForm(level, language),
  };
}

function createMessage(messageKey, language) {
  return getText(messageKey, language);
}

function syncDerivedState(state) {
  return {
    ...state,
    cat: {
      ...state.cat,
      level: state.level,
      growth: state.growth,
      form: getCatForm(state.level, state.language),
      screenX: state.cat.screenX ?? DEFAULT_SCREEN_X,
      jumpBufferFrames: state.cat.jumpBufferFrames ?? 0,
      coyoteFramesRemaining: state.cat.coyoteFramesRemaining ?? 0,
    },
  };
}

export function createInitialState(language = LANGUAGES.ZH, random = Math.random) {
  const level = 1;

  return syncDerivedState({
    status: "running",
    gameOver: false,
    language,
    cameraX: 0,
    messageKey: "runner.start",
    message: createMessage("runner.start", language),
    health: MAX_HEALTH,
    score: 0,
    miceCaught: 0,
    level,
    growth: 0,
    cat: createCat(level, language),
    world: createWorld({ catX: 0, level, random }),
  });
}

export function applyJump(state) {
  const canJump = state.cat.onGround || (state.cat.coyoteFramesRemaining ?? 0) > 0;
  if (state.gameOver || !canJump) {
    return state;
  }

  return syncDerivedState({
    ...state,
    messageKey: "runner.jump",
    message: createMessage("runner.jump", state.language),
    cat: {
      ...state.cat,
      vy: JUMP_VELOCITY,
      onGround: false,
      jumpBufferFrames: 0,
      coyoteFramesRemaining: 0,
    },
  });
}

export function applyMovementTarget(state, target) {
  if (state.gameOver) {
    return state;
  }

  const vx = target === "left" ? -RUN_SPEED : target === "right" ? RUN_SPEED : 0;

  return syncDerivedState({
    ...state,
    cat: {
      ...state.cat,
      vx,
    },
  });
}

export function applyLevelUp(state) {
  let nextState = {
    ...state,
    cat: {
      ...state.cat,
    },
  };

  while (nextState.growth >= getGrowthThresholdForLevel(nextState.level)) {
    nextState = {
      ...nextState,
      level: nextState.level + 1,
      growth: nextState.growth - getGrowthThresholdForLevel(nextState.level),
      messageKey: "runner.levelUp",
      message: createMessage("runner.levelUp", nextState.language),
      world: createWorld({
        catX: nextState.cat.x,
        level: nextState.level + 1,
      }),
    };
  }

  return syncDerivedState(nextState);
}

export function resolveCatch(state, mouse) {
  if (state.gameOver) {
    return state;
  }

  const encounter = resolveRunnerEncounter({
    catLevel: state.level,
    mouseLevel: mouse.level,
  });

  let nextState = {
    ...state,
    cat: {
      ...state.cat,
    },
  };

  if (encounter.outcome === "eat") {
    nextState = {
      ...nextState,
      miceCaught: nextState.miceCaught + 1,
      growth: nextState.growth + encounter.growthGain,
      score: nextState.score + 10,
      messageKey: "runner.catch",
      message: createMessage("runner.catch", nextState.language),
    };
  } else {
    nextState = {
      ...nextState,
      health: nextState.health - encounter.healthLoss,
      messageKey: "runner.hit",
      message: createMessage("runner.hit", nextState.language),
    };
  }

  if (nextState.health <= 0) {
    return syncDerivedState({
      ...nextState,
      health: 0,
      gameOver: true,
      status: "gameover",
      messageKey: "runner.gameOver",
      message: createMessage("runner.gameOver", nextState.language),
    });
  }

  return applyLevelUp(nextState);
}

export function resolveFallReset(state) {
  if (state.gameOver) {
    return state;
  }

  const nextHealth = state.health - 1;
  if (nextHealth <= 0) {
    return syncDerivedState({
      ...state,
      health: 0,
      gameOver: true,
      status: "gameover",
      messageKey: "runner.gameOver",
      message: createMessage("runner.gameOver", state.language),
      cat: {
        ...state.cat,
        y: FALL_RESET_Y,
        vy: 0,
        onGround: true,
      },
    });
  }

  return syncDerivedState({
    ...state,
    health: nextHealth,
    messageKey: "runner.fall",
    message: createMessage("runner.fall", state.language),
    cat: {
      ...state.cat,
      y: FALL_RESET_Y,
      vy: 0,
      onGround: true,
    },
  });
}

export function setLanguage(state, language) {
  return syncDerivedState({
    ...state,
    language,
    message: createMessage(state.messageKey, language),
  });
}

export { LEVEL_UP_REQUIREMENTS };
