import { createAudioController } from "./audio";
import { applyPointerMove, createInputState, setFiringPressed } from "./input";
import { toggleLanguage } from "./i18n";
import { startRunnerLoop } from "./loop";
import { createInitialState, setLanguage } from "./state";
import { renderGame } from "./render";

function isStreetStage(target) {
  return Boolean(target?.closest?.('[data-stage="street"]'));
}

const AUTO_RESTART_DELAY_MS = 1500;

export function initGame(root) {
  let input = createInputState();
  let state = createInitialState();
  let stopLoop = null;
  let restartTimeout = null;
  const windowTarget = globalThis.window;
  const audio = createAudioController();

  function syncInputTargetToPlayer() {
    input.targetX = state.player?.position?.x ?? input.targetX;
    input.targetY = state.player?.position?.y ?? input.targetY;
  }

  function render() {
    root.innerHTML = renderGame(state);
  }

  function clearPendingRestart() {
    if (restartTimeout !== null) {
      clearTimeout(restartTimeout);
      restartTimeout = null;
    }
  }

  function restartRound() {
    clearPendingRestart();
    input = createInputState();
    state = createInitialState(state.language);
    syncInputTargetToPlayer();
    render();
    startLoop();
  }

  function updateState(nextState) {
    const previousMessageKey = state.messageKey;
    const wasGameOver = state.gameOver;
    state = nextState;
    render();

    if (state.messageKey !== previousMessageKey) {
      audio.play(state.messageKey);
    }

    if (!wasGameOver && state.gameOver) {
      clearPendingRestart();
      restartTimeout = setTimeout(() => {
        restartRound();
      }, AUTO_RESTART_DELAY_MS);
    }
  }

  function startLoop() {
    stopLoop?.();
    stopLoop = startRunnerLoop({
      getState: () => state,
      setState: updateState,
      input,
    });
  }

  syncInputTargetToPlayer();
  render();
  startLoop();

  root.addEventListener("pointermove", (event) => {
    const stage = event.target?.closest?.('[data-stage="street"]');
    if (!stage) {
      return;
    }

    applyPointerMove(input, event, stage.getBoundingClientRect(), state.world?.stageBounds);
  });

  root.addEventListener("pointerdown", (event) => {
    if (state.gameOver || !isStreetStage(event.target)) {
      return;
    }

    setFiringPressed(input, true);
  });

  function stopFiring() {
    setFiringPressed(input, false);
  }

  const removeGlobalListeners = [];
  if (windowTarget?.addEventListener) {
    const releaseEvents = ["pointerup", "pointercancel", "blur"];
    for (const eventName of releaseEvents) {
      windowTarget.addEventListener(eventName, stopFiring);
      removeGlobalListeners.push(() => windowTarget.removeEventListener?.(eventName, stopFiring));
    }
  }

  root.addEventListener("pointerup", stopFiring);
  root.addEventListener("pointercancel", stopFiring);
  root.addEventListener("pointerleave", stopFiring);

  root.addEventListener("click", (event) => {
    const languageButton = event.target?.closest?.('[data-action="language"]');
    if (languageButton) {
      state = setLanguage(state, toggleLanguage(state.language));
      render();
      return;
    }

    const restartButton = event.target?.closest?.('[data-action="restart"]');
    if (restartButton) {
      restartRound();
    }
  });

  return () => {
    clearPendingRestart();
    for (const removeListener of removeGlobalListeners) {
      removeListener();
    }
    stopLoop?.();
  };
}
