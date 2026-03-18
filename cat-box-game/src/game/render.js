import { MAX_HEALTH } from "./constants";
import { LANGUAGES, getText } from "./i18n";
import { getGrowthThresholdForLevel } from "./rules";

const FILLED_HEART = "\u2764\ufe0f";
const EMPTY_HEART = "\u{1f90d}";
const GROUND_HEIGHT = 40;
const VISIBLE_PLATFORM_MARGIN = 240;
const VISIBLE_PLATFORM_RANGE = 1600;

function getFeedbackKind(state) {
  switch (state.messageKey) {
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

function renderHearts(health) {
  return Array.from({ length: MAX_HEALTH }, (_, index) => {
    const filled = index < health;
    return `<span class="heart ${filled ? "heart-filled" : "heart-empty"}" aria-hidden="true">${filled ? FILLED_HEART : EMPTY_HEART}</span>`;
  }).join("");
}

function renderPlatform(platform, index, language) {
  const mouseMarkup = platform.mouse
    ? `
      <div class="runner-mouse" aria-label="${getText("runner.mouse", language)}">
        <span class="runner-mouse-emoji">\u{1f42d}</span>
        <span class="runner-mouse-level">${platform.mouse.level}\u7ea7</span>
      </div>
    `
    : `
      <div class="runner-box-badge" aria-label="${getText("box.safe", language)}">
        <span class="runner-box-emoji">\u{1f4e6}</span>
      </div>
    `;

  return `
    <div
      class="runner-platform"
      data-platform-index="${index}"
      style="left:${Math.round(platform.x)}px; bottom:${GROUND_HEIGHT - Math.round(platform.y)}px; width:${Math.round(platform.width)}px; height:${Math.round(platform.height)}px;"
    >
      <div class="runner-platform-box-face"></div>
      ${mouseMarkup}
    </div>
  `;
}

function renderGroundItem(item, index, language) {
  const overlay = item.mouse
    ? `
      <div class="runner-ground-mouse" aria-label="${getText("runner.mouse", language)}">
        <span class="runner-mouse-emoji">\u{1f42d}</span>
        <span class="runner-mouse-level">${item.mouse.level}\u7ea7</span>
      </div>
    `
    : `
      <div class="runner-ground-box" aria-label="${getText("box.safe", language)}">
        <span class="runner-box-emoji">\u{1f4e6}</span>
      </div>
    `;

  return `
    <div
      class="runner-ground-item"
      data-ground-item-index="${index}"
      style="left:${Math.round(item.x)}px; bottom:${GROUND_HEIGHT}px;"
    >
      <div class="runner-ground-box-face"></div>
      ${overlay}
    </div>
  `;
}

export function renderHeartMarkup(health) {
  return renderHearts(health);
}

export function getVisiblePlatforms(state) {
  const cameraX = Math.round(state.cameraX ?? 0);

  return (state.world?.platforms ?? []).filter(
    (platform) =>
      platform.x + platform.width >= cameraX - VISIBLE_PLATFORM_MARGIN &&
      platform.x <= cameraX + VISIBLE_PLATFORM_RANGE,
  );
}

export function getRenderStateSignature(state) {
  const language = state.language ?? LANGUAGES.ZH;
  const visiblePlatforms = getVisiblePlatforms(state)
    .map(
      (platform) =>
        `${Math.round(platform.x)}:${Math.round(platform.y)}:${Math.round(platform.width)}:${platform.mouse?.level ?? "none"}`,
    )
    .join("|");
  const visibleGroundMice = (state.world?.groundMice ?? [])
    .filter((item) => item.x >= (state.cameraX ?? 0) - VISIBLE_PLATFORM_MARGIN && item.x <= (state.cameraX ?? 0) + VISIBLE_PLATFORM_RANGE)
    .map((item) => `${Math.round(item.x)}:${item.mouse?.level ?? "box"}`)
    .join("|");

  return `${language}::${state.gameOver ? "gameover" : "running"}::${visiblePlatforms}::${visibleGroundMice}`;
}

export function renderGame(state) {
  const language = state.language ?? LANGUAGES.ZH;
  const growthTarget = getGrowthThresholdForLevel(state.cat.level);
  const healthMarkup = renderHearts(state.health);
  const feedbackKind = getFeedbackKind(state);
  const feedbackText = state.message ?? getText("runner.start", language);
  const groundHeight = state.world?.ground?.height ?? GROUND_HEIGHT;
  const cameraX = Math.round(state.cameraX ?? 0);
  const catLeft = Math.round(state.cat?.screenX ?? state.cat?.x ?? 0);
  const catBottom = Math.round(groundHeight - (state.cat?.y ?? 0));
  const catDirectionClass =
    state.cat?.vx < 0 ? "runner-cat-facing-left" : state.cat?.vx > 0 ? "runner-cat-facing-right" : "runner-cat-facing-forward";
  const visiblePlatformMarkup = getVisiblePlatforms(state)
    .map((platform, index) => renderPlatform(platform, index, language))
    .join("");
  const visibleGroundMiceMarkup = (state.world?.groundMice ?? [])
    .filter((item) => item.x >= cameraX - VISIBLE_PLATFORM_MARGIN && item.x <= cameraX + VISIBLE_PLATFORM_RANGE)
    .map((item, index) => renderGroundItem(item, index, language))
    .join("");

  return `
    <main class="runner-shell" data-feedback-kind="${feedbackKind}">
      <header class="runner-hud">
        <div class="runner-stats">
        <div class="runner-stat">
          <span class="runner-stat-label">${getText("runner.level", language)}</span>
          <strong class="runner-stat-value" data-stat="level">${state.level} \u7ea7</strong>
        </div>
        <div class="runner-stat">
          <span class="runner-stat-label">${getText("runner.health", language)}</span>
          <strong class="runner-stat-value hearts" data-stat="health">${healthMarkup}</strong>
        </div>
        <div class="runner-stat">
          <span class="runner-stat-label">${getText("runner.growth", language)}</span>
          <strong class="runner-stat-value" data-stat="growth">${state.growth}/${growthTarget}</strong>
        </div>
        <div class="runner-stat">
          <span class="runner-stat-label">${getText("runner.miceCaught", language)}</span>
          <strong class="runner-stat-value" data-stat="miceCaught">${state.miceCaught ?? 0}</strong>
        </div>
        </div>
        <button
          class="runner-language-button"
          type="button"
          data-action="language"
          aria-label="${getText("runner.languageToggleAria", language)}"
        >
          ${getText("runner.languageToggle", language)} ${state.language === LANGUAGES.ZH ? "EN" : "\u4e2d\u6587"}
        </button>
      </header>

      <section class="runner-stage" data-runner-stage tabindex="0" aria-label="${getText("runner.stage", language)}">
        <div class="runner-backdrop"></div>
        <div class="runner-skyline"></div>
        <div class="runner-ground"></div>
        <div class="runner-world" style="transform: translate3d(${-cameraX}px, 0, 0);">
          ${visibleGroundMiceMarkup}
          ${visiblePlatformMarkup}
        </div>
        <div
          class="runner-cat ${catDirectionClass}"
          style="left:${catLeft}px; bottom:${catBottom}px;"
          aria-label="${state.cat?.form?.name ?? getText("stage.kitten.name", language)}"
        >
          <span class="runner-cat-emoji">${state.cat?.form?.emoji ?? "\u{1f431}"}</span>
          <span class="runner-cat-name">${state.cat?.form?.name ?? ""}</span>
        </div>
        <div class="runner-feedback runner-feedback-${feedbackKind}" aria-live="polite">
          <span class="runner-feedback-pill">${feedbackText}</span>
          ${state.gameOver ? `<button class="restart-button" type="button" data-action="restart">${getText("runner.restart", language)}</button>` : ""}
        </div>
      </section>
    </main>
  `;
}
