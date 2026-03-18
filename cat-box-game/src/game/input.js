const DEFAULT_PLAY_WIDTH = 0;

function clamp(value, min, max) {
  return Math.min(max, Math.max(min, value));
}

export function createInputState() {
  return {
    targetX: 0,
    jumpRequested: false,
    languageToggleRequested: false,
  };
}

export function applyPointerMove(input, event, bounds = {}) {
  const left = bounds.left ?? 0;
  const width = bounds.width ?? DEFAULT_PLAY_WIDTH;
  const localX = event.clientX - left;

  input.targetX = width > 0 ? clamp(localX, 0, width) : 0;
  return input.targetX;
}

export function requestJump(input) {
  input.jumpRequested = true;
  return input;
}

export function requestLanguageToggle(input) {
  input.languageToggleRequested = true;
  return input;
}

export function consumeInputRequests(input) {
  const requests = {
    jumpRequested: Boolean(input.jumpRequested),
    languageToggleRequested: Boolean(input.languageToggleRequested),
  };

  input.jumpRequested = false;
  input.languageToggleRequested = false;

  return requests;
}
