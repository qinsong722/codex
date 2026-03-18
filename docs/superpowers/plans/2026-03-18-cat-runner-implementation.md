# Cat Runner Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild the current cat-box prototype into a runner game where the cat keeps moving, jumps with mouse clicks, catches mice on platforms, loses health on failures, and supports Chinese/English UI switching.

**Architecture:** Replace the turn-based box selection loop with a real-time game loop. Keep game state, physics, world generation, UI text, and rendering separated so movement and collisions stay simple to reason about. Reuse the existing Electron/Vite shell while rebuilding the gameplay screen around a continuously updating runner scene.

**Tech Stack:** HTML, CSS, JavaScript, Vite, Electron, Vitest

---

## File Structure

- Modify: `C:/Users/qinso/Desktop/Codex/cat-box-game/src/main.js`
- Create: `C:/Users/qinso/Desktop/Codex/cat-box-game/src/game/loop.js`
- Create: `C:/Users/qinso/Desktop/Codex/cat-box-game/src/game/input.js`
- Create: `C:/Users/qinso/Desktop/Codex/cat-box-game/src/game/world.js`
- Create: `C:/Users/qinso/Desktop/Codex/cat-box-game/src/game/i18n.js`
- Modify: `C:/Users/qinso/Desktop/Codex/cat-box-game/src/game/constants.js`
- Modify: `C:/Users/qinso/Desktop/Codex/cat-box-game/src/game/rules.js`
- Replace: `C:/Users/qinso/Desktop/Codex/cat-box-game/src/game/state.js`
- Replace: `C:/Users/qinso/Desktop/Codex/cat-box-game/src/game/render.js`
- Replace: `C:/Users/qinso/Desktop/Codex/cat-box-game/src/game/ui.js`
- Modify: `C:/Users/qinso/Desktop/Codex/cat-box-game/src/styles.css`
- Modify: `C:/Users/qinso/Desktop/Codex/cat-box-game/tests/rules.test.js`
- Replace: `C:/Users/qinso/Desktop/Codex/cat-box-game/tests/state.test.js`
- Create: `C:/Users/qinso/Desktop/Codex/cat-box-game/tests/i18n.test.js`
- Create: `C:/Users/qinso/Desktop/Codex/cat-box-game/tests/world.test.js`

## Chunk 1: Core Rules and Text

### Task 1: Rewrite rules for runner collisions and language labels

**Files:**
- Modify: `C:/Users/qinso/Desktop/Codex/cat-box-game/src/game/constants.js`
- Modify: `C:/Users/qinso/Desktop/Codex/cat-box-game/src/game/rules.js`
- Create: `C:/Users/qinso/Desktop/Codex/cat-box-game/src/game/i18n.js`
- Modify: `C:/Users/qinso/Desktop/Codex/cat-box-game/tests/rules.test.js`
- Create: `C:/Users/qinso/Desktop/Codex/cat-box-game/tests/i18n.test.js`

- [ ] **Step 1: Write the failing tests for runner encounter outcomes**

Add tests for:
- cat catches mouse when cat level is high enough
- cat loses health when mouse level is higher
- cat loses health when falling off a platform

- [ ] **Step 2: Run the rule tests to verify they fail**

Run: `npm run test -- tests/rules.test.js tests/i18n.test.js`
Expected: FAIL because runner rules and i18n helpers do not exist yet.

- [ ] **Step 3: Implement minimal runner rule helpers**

Include helpers for:
- mouse encounter resolution
- fall damage resolution
- growth threshold lookup

- [ ] **Step 4: Write the failing tests for Chinese/English text switching**

Verify:
- Chinese labels return Chinese text
- English labels return English text
- language toggle flips between the two modes

- [ ] **Step 5: Implement minimal i18n module**

Expose:
- language constants
- translation table
- text lookup helper
- toggle helper

- [ ] **Step 6: Run the focused tests**

Run: `npm run test -- tests/rules.test.js tests/i18n.test.js`
Expected: PASS

## Chunk 2: Runner State and World

### Task 2: Build real-time state and platform generation

**Files:**
- Replace: `C:/Users/qinso/Desktop/Codex/cat-box-game/src/game/state.js`
- Create: `C:/Users/qinso/Desktop/Codex/cat-box-game/src/game/world.js`
- Create: `C:/Users/qinso/Desktop/Codex/cat-box-game/tests/world.test.js`
- Replace: `C:/Users/qinso/Desktop/Codex/cat-box-game/tests/state.test.js`

- [ ] **Step 1: Write the failing tests for initial runner state**

Cover:
- cat starts on the ground
- health starts at 3
- language defaults to Chinese
- game starts in running state

- [ ] **Step 2: Run the state tests to verify they fail**

Run: `npm run test -- tests/state.test.js tests/world.test.js`
Expected: FAIL because the old turn-based state shape no longer matches.

- [ ] **Step 3: Implement minimal runner state factory**

Track:
- cat position and velocity
- current level and growth
- health
- score / mice caught count
- language
- game over status
- message key

- [ ] **Step 4: Write the failing tests for world generation**

Cover:
- platforms are generated ahead of the cat
- some platforms include mice
- mice levels scale from easy to harder over time

- [ ] **Step 5: Implement minimal world generation**

Create helpers that return:
- ground area
- elevated platforms
- optional mice on platforms

- [ ] **Step 6: Add state update tests for fall damage and mouse catches**

Verify:
- catching weak mouse increases count/growth
- stronger mouse reduces health
- falling resets cat to safe ground and removes 1 health

- [ ] **Step 7: Implement state update helpers**

Add pure functions for:
- apply jump
- apply movement target
- resolve catch
- resolve fall reset
- apply level up

- [ ] **Step 8: Run the state/world tests**

Run: `npm run test -- tests/state.test.js tests/world.test.js`
Expected: PASS

## Chunk 3: Input and Game Loop

### Task 3: Add mouse input and frame updates

**Files:**
- Create: `C:/Users/qinso/Desktop/Codex/cat-box-game/src/game/input.js`
- Create: `C:/Users/qinso/Desktop/Codex/cat-box-game/src/game/loop.js`
- Modify: `C:/Users/qinso/Desktop/Codex/cat-box-game/src/main.js`
- Replace: `C:/Users/qinso/Desktop/Codex/cat-box-game/src/game/ui.js`

- [ ] **Step 1: Write the failing tests for input helpers**

Cover:
- mouse move updates target x position
- click requests a jump
- language button click toggles language

- [ ] **Step 2: Run the relevant tests to verify they fail**

Run: `npm run test -- tests/state.test.js tests/i18n.test.js`
Expected: FAIL or missing helpers for the new input flow.

- [ ] **Step 3: Implement minimal input helpers**

Convert pointer input into:
- horizontal target position
- jump request
- language toggle action

- [ ] **Step 4: Implement the frame loop**

Each frame should:
- move the cat forward
- steer toward mouse target x position
- apply gravity and jump velocity
- scroll the camera
- update platforms ahead
- resolve catches and fall damage

- [ ] **Step 5: Wire the loop into the UI bootstrap**

Ensure the runner starts automatically when the app loads.

- [ ] **Step 6: Run tests**

Run: `npm run test`
Expected: PASS

## Chunk 4: Runner Rendering and Bilingual UI

### Task 4: Replace the old box UI with a runner scene

**Files:**
- Replace: `C:/Users/qinso/Desktop/Codex/cat-box-game/src/game/render.js`
- Modify: `C:/Users/qinso/Desktop/Codex/cat-box-game/src/styles.css`

- [ ] **Step 1: Render the static runner HUD**

Show:
- level
- health
- growth
- mice caught
- language toggle button

- [ ] **Step 2: Render the game scene**

Show:
- moving cat
- ground
- raised boxes/platforms
- mice on top of platforms

- [ ] **Step 3: Render bilingual text through i18n**

All visible labels should come from the translation helper.

- [ ] **Step 4: Add basic feedback states**

Show text for:
- catch success
- hit by stronger mouse
- fall damage
- game over

- [ ] **Step 5: Add restart flow**

When game over:
- stop updates
- show restart button
- restart keeps current language choice

- [ ] **Step 6: Run manual smoke check and automated tests**

Run:
- `npm run test`
- `npm run build`

Expected:
- tests PASS
- build PASS

## Chunk 5: Final Verification

### Task 5: Verify desktop runner behavior

**Files:**
- Modify: `C:/Users/qinso/Desktop/Codex/cat-box-game/README.md`
- Modify: `C:/Users/qinso/Desktop/Codex/cat-box-game/run-cat-box-game.bat`

- [ ] **Step 1: Update launch instructions**

Explain:
- mouse move controls horizontal positioning
- click triggers jump
- language button switches Chinese / English

- [ ] **Step 2: Verify browser build**

Run: `npm run build`
Expected: PASS

- [ ] **Step 3: Verify desktop run**

Run: `run-cat-box-game.bat`
Expected: the runner window opens with bilingual UI and moving gameplay.

- [ ] **Step 4: Run final tests**

Run: `npm run test`
Expected: PASS
