import { toggleLanguage } from "./i18n";
import { createAudioController } from "./audio";
import {
  applyPointerMove,
  consumeInputRequests,
  createInputState,
  requestJump,
  requestLanguageToggle,
} from "./input";
import { startRunnerLoop } from "./loop";
import { createInitialState, setLanguage } from "./state";
import { getRenderStateSignature, renderGame, renderHeartMarkup } from "./render";
import { getGrowthThresholdForLevel } from "./rules";

function getFeedbackKind(messageKey) {
  switch (messageKey) {
    case "runner.catch":
      return "success";
    case "runner.hit":
      return "danger";
    case "runner.fall":
      return "warning";
    case "runner.gameOver":
      return "gameover";
    case "runner.levelUp":
      return "levelup";
    case "runner.jump":
      return "jump";
    default:
      return "idle";
  }
}

function bindDom(root) {
  return {
    shell: root.querySelector(".runner-shell"),
    levelValue: root.querySelector("[data-stat='level']"),
    healthValue: root.querySelector("[data-stat='health']"),
    growthValue: root.querySelector("[data-stat='growth']"),
    miceCaughtValue: root.querySelector("[data-stat='miceCaught']"),
    world: root.querySelector(".runner-world"),
    cat: root.querySelector(".runner-cat"),
    catEmoji: root.querySelector(".runner-cat-emoji"),
    catName: root.querySelector(".runner-cat-name"),
    feedback: root.querySelector(".runner-feedback"),
    feedbackPill: root.querySelector(".runner-feedback-pill"),
  };
}

export function initGame(root) {
  let input = createInputState();
  let state = createInitialState();
  let stopLoop = null;
  let dom = null;
  let renderSignature = "";
  let lastHudSnapshot = "";
  const audio = createAudioController();

  function renderFull() {
    root.innerHTML = renderGame(state);
    dom = typeof root.querySelector === "function" ? bindDom(root) : null;
    renderSignature = getRenderStateSignature(state);
    lastHudSnapshot = `${state.level}|${state.health}|${state.growth}|${state.miceCaught ?? 0}|${state.messageKey}|${state.message}|${state.language}`;
  }

  function patchFrame() {
    if (!dom) {
      renderFull();
      return;
    }

    const nextSignature = getRenderStateSignature(state);
    if (nextSignature !== renderSignature) {
      renderFull();
      return;
    }

    const nextHudSnapshot = `${state.level}|${state.health}|${state.growth}|${state.miceCaught ?? 0}|${state.messageKey}|${state.message}|${state.language}`;
    if (nextHudSnapshot !== lastHudSnapshot) {
      dom.shell?.setAttribute("data-feedback-kind", getFeedbackKind(state.messageKey));
      if (dom.levelValue) {
        dom.levelValue.textContent = `${state.level} 级`;
      }
      if (dom.healthValue) {
        dom.healthValue.innerHTML = renderHeartMarkup(state.health);
      }
      if (dom.growthValue) {
        dom.growthValue.textContent = `${state.growth}/${getGrowthThresholdForLevel(state.level)}`;
      }
      if (dom.miceCaughtValue) {
        dom.miceCaughtValue.textContent = String(state.miceCaught ?? 0);
      }
      if (dom.feedbackPill) {
        dom.feedbackPill.textContent = state.message ?? "";
      }
      if (dom.feedback) {
        dom.feedback.className = `runner-feedback runner-feedback-${getFeedbackKind(state.messageKey)}`;
      }
      lastHudSnapshot = nextHudSnapshot;
    }

    if (dom.world) {
      dom.world.style.transform = `translate3d(${-Math.round(state.cameraX ?? 0)}px, 0, 0)`;
    }
    if (dom.cat) {
      const directionClass =
        state.cat?.vx < 0
          ? "runner-cat-facing-left"
          : state.cat?.vx > 0
            ? "runner-cat-facing-right"
            : "runner-cat-facing-forward";
      dom.cat.className = `runner-cat ${directionClass}`;
      dom.cat.style.left = `${Math.round(state.cat?.screenX ?? state.cat?.x ?? 0)}px`;
      dom.cat.style.bottom = `${Math.round((state.world?.ground?.height ?? 40) - (state.cat?.y ?? 0))}px`;
      dom.cat.setAttribute("aria-label", state.cat?.form?.name ?? "");
    }
    if (dom.catEmoji) {
      dom.catEmoji.textContent = state.cat?.form?.emoji ?? "\u{1f431}";
    }
    if (dom.catName) {
      dom.catName.textContent = state.cat?.form?.name ?? "";
    }
  }

  function updateState(nextState) {
    const previousMessageKey = state.messageKey;
    state = nextState;
    patchFrame();

    if (state.messageKey !== previousMessageKey) {
      audio.play(state.messageKey);
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

  renderFull();
  startLoop();

  root.addEventListener("pointermove", (event) => {
    const stage = event.target?.closest?.("[data-runner-stage]");
    if (!stage) {
      return;
    }

    applyPointerMove(input, event, stage.getBoundingClientRect());
  });

  root.addEventListener("pointerdown", (event) => {
    if (event.target?.closest?.("[data-runner-stage]") && !state.gameOver) {
      requestJump(input);
    }
  });

  root.addEventListener("click", (event) => {
    const languageButton = event.target?.closest?.("[data-action='language']");
    if (languageButton) {
      requestLanguageToggle(input);
      consumeInputRequests(input);
      state = setLanguage(state, toggleLanguage(state.language));
      renderFull();
      return;
    }

    const restartButton = event.target?.closest?.("[data-action='restart']");
    if (restartButton) {
      input = createInputState();
      state = createInitialState(state.language);
      renderFull();
      startLoop();
      return;
    }
  });

  return () => {
    stopLoop?.();
  };
}
