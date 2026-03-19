import { MAX_HEALTH } from "./constants";
import { LANGUAGES, getHudLabel, getStatusLabel, getText, getWeaponLabel } from "./i18n";

const DEFAULT_STAGE_BOUNDS = { width: 1280, height: 720 };
const MAX_HEARTS = MAX_HEALTH;
const PLAYER_SIZE = 48;
const TANK_SIZE = 72;

function clampNumber(value, fallback = 0) {
  return Number.isFinite(value) ? value : fallback;
}

function roundPx(value, fallback = 0) {
  return `${Math.round(clampNumber(value, fallback))}px`;
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function biText(language, zh, en) {
  return language === LANGUAGES.ZH ? zh : en;
}

function getLanguage(state) {
  return state?.language ?? LANGUAGES.ZH;
}

function getStageBounds(state) {
  return state?.world?.stageBounds ?? DEFAULT_STAGE_BOUNDS;
}

function getPlayerPosition(state) {
  const bounds = getStageBounds(state);
  const player = state?.player ?? {};
  const fallback = {
    x: bounds.width / 2 - PLAYER_SIZE / 2,
    y: bounds.height * 0.62,
  };

  return {
    x: clampNumber(player.position?.x, fallback.x),
    y: clampNumber(player.position?.y, fallback.y),
  };
}

function getTankPosition(tank, bounds) {
  const fallback = {
    x: bounds.width * 0.5 - TANK_SIZE / 2,
    y: bounds.height * 0.54,
  };

  return {
    x: clampNumber(tank?.position?.x, fallback.x),
    y: clampNumber(tank?.position?.y, fallback.y),
  };
}

function renderHearts(health) {
  return Array.from({ length: MAX_HEARTS }, (_, index) => {
    const filled = index < Math.max(0, clampNumber(health, 0));
    return `<span class="heart ${filled ? "heart-filled" : "heart-empty"}" aria-hidden="true">${filled ? "\u2764\ufe0f" : "\u{1f90d}"}</span>`;
  }).join("");
}

function renderHudStat({ label, value, stat }) {
  return `
    <div class="hud-stat" data-stat="${stat}">
      <span class="hud-label">${escapeHtml(label)}</span>
      <strong class="hud-value">${value}</strong>
    </div>
  `;
}

function renderHud(state, language) {
  const ammo = state?.ammo ?? 0;
  const wave = state?.wave ?? 1;
  const kills = state?.kills ?? 0;
  const health = state?.health ?? state?.player?.health ?? 0;
  const nextLanguageLabel = language === LANGUAGES.ZH ? "EN" : "中文";

  return `
    <header class="game-hud">
      <div class="hud-stats">
        ${renderHudStat({
          label: getHudLabel("health", language),
          value: `<span class="hearts">${renderHearts(health)}</span>`,
          stat: "health",
        })}
        ${renderHudStat({
          label: getHudLabel("ammo", language),
          value: escapeHtml(ammo),
          stat: "ammo",
        })}
        ${renderHudStat({
          label: getHudLabel("wave", language),
          value: escapeHtml(wave),
          stat: "wave",
        })}
        ${renderHudStat({
          label: getHudLabel("kills", language),
          value: escapeHtml(kills),
          stat: "kills",
        })}
      </div>
      <button
        class="hud-language-button"
        type="button"
        data-action="language"
        aria-label="${escapeHtml(biText(language, "切换游戏语言", "Toggle game language"))}"
      >
        ${escapeHtml(biText(language, "切换语言", "Switch language"))} ${nextLanguageLabel}
      </button>
    </header>
  `;
}

function renderStreetBackdrop() {
  return `
    <div class="street-backdrop" aria-hidden="true">
      <div class="street-sky"></div>
      <div class="street-haze"></div>
      <div class="street-buildings"></div>
      <div class="street-road"></div>
      <div class="street-lane"></div>
      <div class="street-crosswalk"></div>
      <div class="street-foreground"></div>
    </div>
  `;
}

function renderDecoration(anchor, index) {
  const kind = anchor?.kind ?? "prop";

  return `
    <div
      class="street-decoration street-decoration-${escapeHtml(kind)}"
      data-decoration-kind="${escapeHtml(kind)}"
      data-decoration-index="${index}"
      style="left:${roundPx(anchor?.x)}; top:${roundPx(anchor?.y)};"
      aria-hidden="true"
    ></div>
  `;
}

function renderWeaponPickup(pickup, index, language) {
  return `
    <div
      class="street-pickup street-pickup-weapon weapon-pickup"
      data-weapon-pickup
      data-pickup-index="${index}"
      data-weapon="${escapeHtml(pickup?.weapon)}"
      style="left:${roundPx(pickup?.x)}; top:${roundPx(pickup?.y)};"
    >
      <span class="street-pickup-icon" aria-hidden="true">\u{1f52b}</span>
      <span class="street-pickup-label">${escapeHtml(getWeaponLabel(pickup?.weapon, language))}</span>
    </div>
  `;
}

function renderAmmoPickup(pickup, index, language) {
  return `
    <div
      class="street-pickup street-pickup-ammo ammo-pickup"
      data-ammo-pickup
      data-pickup-index="${index}"
      style="left:${roundPx(pickup?.x)}; top:${roundPx(pickup?.y)};"
    >
      <span class="street-pickup-icon" aria-hidden="true">\u{1f9f0}</span>
      <span class="street-pickup-label">${escapeHtml(getStatusLabel("ammo", language))} +${escapeHtml(pickup?.amount ?? 0)}</span>
    </div>
  `;
}

function renderShellPickup(pickup, index, language) {
  return `
    <div
      class="street-pickup street-pickup-shell shell-pickup"
      data-shell-pickup
      data-pickup-index="${index}"
      style="left:${roundPx(pickup?.x)}; top:${roundPx(pickup?.y)};"
    >
      <span class="street-pickup-icon" aria-hidden="true">\u{1f4a5}</span>
      <span class="street-pickup-label">${escapeHtml(getStatusLabel("tank", language))} +${escapeHtml(pickup?.amount ?? 0)}</span>
    </div>
  `;
}

function renderPlayer(state, language) {
  const player = state?.player ?? {};
  const position = getPlayerPosition(state);
  const facing = player.facing ?? player.direction ?? "east";
  const inTank = player.controlState === "tank";
  const sprite = inTank ? "\u{1f6e1}\ufe0f" : "\u{1f431}";

  return `
    <div
      class="street-player ${inTank ? "street-player-tank" : "street-player-foot"} player-entity"
      data-player
      data-player-state="${escapeHtml(player.controlState ?? "onFoot")}"
      data-facing="${escapeHtml(facing)}"
      style="left:${roundPx(position.x)}; top:${roundPx(position.y)};"
      aria-label="${escapeHtml(getText("stage.cat.name", language))}"
    >
      <span class="street-entity-icon player-icon" aria-hidden="true">${sprite}</span>
    </div>
  `;
}

function renderEnemy(enemy, index) {
  return `
    <div
      class="street-enemy enemy-entity enemy-${escapeHtml(enemy?.kind ?? "enemy")}"
      data-enemy
      data-enemy-index="${index}"
      data-enemy-kind="${escapeHtml(enemy?.kind ?? "enemy")}"
      style="left:${roundPx(enemy?.x)}; top:${roundPx(enemy?.y)};"
    >
      <span class="street-entity-icon enemy-icon" aria-hidden="true">\u{1f47e}</span>
      <span class="street-entity-hp" aria-hidden="true">${escapeHtml(enemy?.health ?? 0)}</span>
    </div>
  `;
}

function renderBullet(bullet, index) {
  return `
    <div
      class="street-bullet bullet-entity bullet-${escapeHtml(bullet?.kind ?? "bullet")}"
      data-bullet
      data-bullet-index="${index}"
      data-bullet-kind="${escapeHtml(bullet?.kind ?? "bullet")}"
      style="left:${roundPx(bullet?.x)}; top:${roundPx(bullet?.y)};"
      aria-hidden="true"
    ></div>
  `;
}

function renderTank(state, language) {
  if (!state?.tank) {
    return "";
  }

  const bounds = getStageBounds(state);
  const tank = state.tank;
  const position = getTankPosition(tank, bounds);
  const occupied = tank.occupiedBy === "player";

  return `
    <div
      class="street-tank ${occupied ? "street-tank-occupied" : "street-tank-idle"} tank-entity"
      data-tank
      data-tank-occupied="${occupied ? "true" : "false"}"
      style="left:${roundPx(position.x)}; top:${roundPx(position.y)};"
    >
      <span class="street-entity-icon tank-icon" aria-hidden="true">\u{1f6e1}\ufe0f</span>
      <span class="street-tank-shells">${escapeHtml(getStatusLabel("tank", language))}: ${escapeHtml(tank.shells ?? 0)}</span>
    </div>
  `;
}

function renderResultBanner(state, language) {
  const message = state?.gameOver
    ? state?.message ?? biText(language, "战斗结束。", "Battle over.")
    : state?.messageKey === "start" || !state?.message
      ? biText(language, "准备就绪。", "Battle ready.")
      : state.message;
  const resultClass = state?.gameOver ? "game-result-game-over" : "game-result-idle";
  const buttonMarkup = state?.gameOver
    ? `<button class="restart-button" type="button" data-action="restart">${escapeHtml(biText(language, "重新开始", "Restart"))}</button>`
    : "";

  return `
    <div class="game-result ${resultClass}" aria-live="polite">
      <div class="game-result-banner">${escapeHtml(message)}</div>
      ${buttonMarkup}
    </div>
  `;
}

function renderEntityLayer(state, language) {
  const decorations = (state?.world?.streetDecorationAnchors ?? []).map((anchor, index) => renderDecoration(anchor, index)).join("");
  const weapons = (state?.pickups?.weapons ?? []).map((pickup, index) => renderWeaponPickup(pickup, index, language)).join("");
  const ammo = (state?.pickups?.ammo ?? []).map((pickup, index) => renderAmmoPickup(pickup, index, language)).join("");
  const shells = (state?.pickups?.shells ?? []).map((pickup, index) => renderShellPickup(pickup, index, language)).join("");
  const enemies = (state?.enemies ?? []).map((enemy, index) => renderEnemy(enemy, index)).join("");
  const bullets = (state?.bullets ?? []).map((bullet, index) => renderBullet(bullet, index)).join("");

  return `
    <div class="street-decoration-layer" aria-hidden="true">${decorations}</div>
    <div class="street-entity-layer">
      ${renderPlayer(state, language)}
      ${enemies}
      ${bullets}
      ${weapons}
      ${ammo}
      ${shells}
      ${renderTank(state, language)}
    </div>
  `;
}

export function renderHeartMarkup(health) {
  return renderHearts(health);
}

export function getRenderStateSignature(state) {
  const language = getLanguage(state);
  const snapshot = {
    language,
    gameOver: Boolean(state?.gameOver),
    health: state?.health ?? state?.player?.health ?? 0,
    ammo: state?.ammo ?? 0,
    wave: state?.wave ?? 1,
    kills: state?.kills ?? 0,
    player: state?.player
      ? {
          x: Math.round(clampNumber(state.player.position?.x)),
          y: Math.round(clampNumber(state.player.position?.y)),
          controlState: state.player.controlState ?? "onFoot",
        }
      : null,
    tank: state?.tank
      ? {
          x: Math.round(clampNumber(state.tank.position?.x)),
          y: Math.round(clampNumber(state.tank.position?.y)),
          occupiedBy: state.tank.occupiedBy ?? null,
          shells: state.tank.shells ?? 0,
        }
      : null,
    bullets: (state?.bullets ?? []).map((bullet) => `${Math.round(clampNumber(bullet?.x))}:${Math.round(clampNumber(bullet?.y))}:${bullet?.kind ?? "bullet"}`).join("|"),
    enemies: (state?.enemies ?? []).map((enemy) => `${Math.round(clampNumber(enemy?.x))}:${Math.round(clampNumber(enemy?.y))}:${enemy?.health ?? 0}`).join("|"),
    pickups: {
      weapons: (state?.pickups?.weapons ?? []).map((pickup) => `${Math.round(clampNumber(pickup?.x))}:${Math.round(clampNumber(pickup?.y))}:${pickup?.weapon ?? ""}`).join("|"),
      ammo: (state?.pickups?.ammo ?? []).map((pickup) => `${Math.round(clampNumber(pickup?.x))}:${Math.round(clampNumber(pickup?.y))}:${pickup?.amount ?? 0}`).join("|"),
      shells: (state?.pickups?.shells ?? []).map((pickup) => `${Math.round(clampNumber(pickup?.x))}:${Math.round(clampNumber(pickup?.y))}:${pickup?.amount ?? 0}`).join("|"),
    },
    decorations: (state?.world?.streetDecorationAnchors ?? []).map((anchor) => `${Math.round(clampNumber(anchor?.x))}:${Math.round(clampNumber(anchor?.y))}:${anchor?.kind ?? "prop"}`).join("|"),
  };

  return JSON.stringify(snapshot);
}

export function renderGame(state) {
  const language = getLanguage(state);
  const bounds = getStageBounds(state);

  return `
    <main class="game-shell" data-game-state="${state?.gameOver ? "game-over" : "running"}">
      ${renderHud(state, language)}
      <section
        class="street-scene street-stage"
        data-stage="street"
        tabindex="0"
        aria-label="${escapeHtml(biText(language, "街头战场", "Street battlefield"))}"
        style="min-height:${roundPx(bounds.height)};"
      >
        ${renderStreetBackdrop()}
        <div class="street-world" style="width:${roundPx(bounds.width)}; height:${roundPx(bounds.height)};">
          ${renderEntityLayer(state, language)}
        </div>
        ${renderResultBanner(state, language)}
      </section>
    </main>
  `;
}
