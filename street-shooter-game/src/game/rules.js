import {
  MAX_AMMO,
  TANK_SHELL_LIMIT,
} from "./constants";

export function canFireWeapon({ lastFireAt, now, weapon }) {
  return now - lastFireAt >= weapon.fireCooldownMs;
}

export function getAmmoAfterPickup({ ammo, amount }) {
  return Math.min(MAX_AMMO, ammo + amount);
}

export function getShellsAfterPickup({ shells, amount }) {
  return Math.min(TANK_SHELL_LIMIT, shells + amount);
}

export function applyEnemyContact({ health, damage = 1 }) {
  return Math.max(0, health - damage);
}

export function getDamageForHit({ hitType }) {
  return hitType === "tankCannon" ? 3 : 1;
}

export function isWaveComplete({ enemies }) {
  return enemies.length === 0;
}
