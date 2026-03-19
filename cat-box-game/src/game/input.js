const DEFAULT_PLAY_WIDTH = 0;
const DEFAULT_PLAY_HEIGHT = 0;

function clamp(value, min, max) {
  return Math.min(max, Math.max(min, value));
}

export function createInputState() {
  return {
    targetX: 0,
    targetY: 0,
    firingPressed: false,
    languageToggleRequested: false,
    restartRequested: false,
  };
}

export function applyPointerMove(input, event, bounds = {}) {
  const left = bounds.left ?? 0;
  const top = bounds.top ?? 0;
  const width = bounds.width ?? DEFAULT_PLAY_WIDTH;
  const height = bounds.height ?? DEFAULT_PLAY_HEIGHT;
  const localX = event.clientX - left;
  const localY = event.clientY - top;

  input.targetX = width > 0 ? clamp(localX, 0, width) : 0;
  input.targetY = height > 0 ? clamp(localY, 0, height) : 0;

  return input.targetX;
}

export function setFiringPressed(input, isPressed) {
  input.firingPressed = Boolean(isPressed);
  return input;
}

export function requestLanguageToggle(input) {
  input.languageToggleRequested = true;
  return input;
}

export function requestRestart(input) {
  input.restartRequested = true;
  return input;
}

export function consumeInputRequests(input) {
  const requests = {
    languageToggleRequested: Boolean(input.languageToggleRequested),
    restartRequested: Boolean(input.restartRequested),
  };

  input.languageToggleRequested = false;
  input.restartRequested = false;

  return requests;
}
