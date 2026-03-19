# Street Shooter Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild the current `cat-box-game` prototype into a smooth top-down street shooter with mouse-follow movement, hold-to-fire shooting, weapon pickup, ammo pickups, wave-based enemies, and a drivable tank with separate shells.

**Architecture:** Keep the existing modular game structure, but replace the current runner rules with a continuous top-down combat loop. Model player, enemies, bullets, pickups, tank, and wave progression as pure state/rule modules so that movement, combat, and spawning remain testable. Render the street scene and HUD with lightweight DOM/CSS shapes to keep the first version fast and easy to iterate on.

**Tech Stack:** HTML, CSS, JavaScript, Vite, Electron, Vitest

---

## File Structure

- Modify: `C:/Users/qinso/Desktop/Codex/cat-box-game/src/main.js`
- Replace: `C:/Users/qinso/Desktop/Codex/cat-box-game/src/game/constants.js`
- Replace: `C:/Users/qinso/Desktop/Codex/cat-box-game/src/game/input.js`
- Replace: `C:/Users/qinso/Desktop/Codex/cat-box-game/src/game/i18n.js`
- Replace: `C:/Users/qinso/Desktop/Codex/cat-box-game/src/game/loop.js`
- Replace: `C:/Users/qinso/Desktop/Codex/cat-box-game/src/game/render.js`
- Replace: `C:/Users/qinso/Desktop/Codex/cat-box-game/src/game/rules.js`
- Replace: `C:/Users/qinso/Desktop/Codex/cat-box-game/src/game/state.js`
- Replace: `C:/Users/qinso/Desktop/Codex/cat-box-game/src/game/ui.js`
- Replace: `C:/Users/qinso/Desktop/Codex/cat-box-game/src/game/world.js`
- Replace: `C:/Users/qinso/Desktop/Codex/cat-box-game/src/styles.css`
- Modify: `C:/Users/qinso/Desktop/Codex/cat-box-game/README.md`
- Replace: `C:/Users/qinso/Desktop/Codex/cat-box-game/tests/input.test.js`
- Replace: `C:/Users/qinso/Desktop/Codex/cat-box-game/tests/i18n.test.js`
- Replace: `C:/Users/qinso/Desktop/Codex/cat-box-game/tests/loop.test.js`
- Replace: `C:/Users/qinso/Desktop/Codex/cat-box-game/tests/render.test.js`
- Replace: `C:/Users/qinso/Desktop/Codex/cat-box-game/tests/rules.test.js`
- Replace: `C:/Users/qinso/Desktop/Codex/cat-box-game/tests/state.test.js`
- Replace: `C:/Users/qinso/Desktop/Codex/cat-box-game/tests/ui.test.js`
- Replace: `C:/Users/qinso/Desktop/Codex/cat-box-game/tests/world.test.js`

## Chunk 1: Core Data and Combat Rules

### Task 1: Define shooter constants and bilingual labels

**Files:**
- Replace: `C:/Users/qinso/Desktop/Codex/cat-box-game/src/game/constants.js`
- Replace: `C:/Users/qinso/Desktop/Codex/cat-box-game/src/game/i18n.js`
- Replace: `C:/Users/qinso/Desktop/Codex/cat-box-game/tests/i18n.test.js`

- [ ] **Step 1: Write the failing tests for shooter text and labels**

Cover:
- Chinese HUD labels for health, ammo, wave, kills, tank
- English HUD labels for the same keys
- language toggle switches between Chinese and English

- [ ] **Step 2: Run the i18n tests to verify they fail**

Run: `npm run test -- tests/i18n.test.js`
Expected: FAIL because the runner text keys no longer match the shooter UI.

- [ ] **Step 3: Implement minimal shooter constants**

Define:
- player health and ammo limits
- weapon definitions for pistol, rifle, shotgun
- tank shell limit and tank stats
- wave counts and spawn tuning

- [ ] **Step 4: Implement minimal i18n helpers**

Expose:
- language constants
- translation lookup
- language toggle helper
- small helpers for weapon and status labels

- [ ] **Step 5: Run the focused tests**

Run: `npm run test -- tests/i18n.test.js`
Expected: PASS

### Task 2: Rewrite pure combat and pickup rules

**Files:**
- Replace: `C:/Users/qinso/Desktop/Codex/cat-box-game/src/game/rules.js`
- Replace: `C:/Users/qinso/Desktop/Codex/cat-box-game/tests/rules.test.js`

- [ ] **Step 1: Write the failing tests for shooter rule helpers**

Cover:
- weapon fire respects fire-rate timing
- ammo pickup clamps at the player max
- shell pickup clamps at the tank max
- enemy contact removes health
- tank cannon hit deals more damage than bullets
- wave completion detection returns true only when all enemies are gone

- [ ] **Step 2: Run the rule tests to verify they fail**

Run: `npm run test -- tests/rules.test.js`
Expected: FAIL because the old runner collision helpers do not match shooter rules.

- [ ] **Step 3: Implement minimal rule helpers**

Include pure helpers for:
- weapon fire timing
- ammo spending
- ammo pickup clamping
- shell pickup clamping
- enemy damage resolution
- wave completion checks
- simple distance and hit checks

- [ ] **Step 4: Run the focused tests**

Run: `npm run test -- tests/rules.test.js`
Expected: PASS

## Chunk 2: World Layout and State

### Task 3: Build the street world definition

**Files:**
- Replace: `C:/Users/qinso/Desktop/Codex/cat-box-game/src/game/world.js`
- Replace: `C:/Users/qinso/Desktop/Codex/cat-box-game/tests/world.test.js`

- [ ] **Step 1: Write the failing tests for the world layout**

Cover:
- street world includes weapon pickup points
- street world includes ammo pickup points
- street world includes one tank spawn
- tank shell pickup points are separate from normal ammo pickups
- enemy spawn lanes exist near the front/top side of the stage

- [ ] **Step 2: Run the world tests to verify they fail**

Run: `npm run test -- tests/world.test.js`
Expected: FAIL because the current world still generates runner platforms and mice.

- [ ] **Step 3: Implement minimal world builders**

Return:
- stage bounds
- street decoration anchors
- weapon pickup placements
- ammo pickup placements
- tank placement
- tank shell pickup placements
- enemy spawn lanes

- [ ] **Step 4: Run the focused tests**

Run: `npm run test -- tests/world.test.js`
Expected: PASS

### Task 4: Replace runner state with shooter state

**Files:**
- Replace: `C:/Users/qinso/Desktop/Codex/cat-box-game/src/game/state.js`
- Replace: `C:/Users/qinso/Desktop/Codex/cat-box-game/tests/state.test.js`

- [ ] **Step 1: Write the failing tests for initial shooter state**

Cover:
- player starts alive at the stage center
- current weapon starts empty or with the chosen default pickup expectation
- total ammo starts below the max
- tank starts on the map but unoccupied
- wave starts at 1
- game starts in running state with Chinese by default

- [ ] **Step 2: Run the state tests to verify they fail**

Run: `npm run test -- tests/state.test.js`
Expected: FAIL because the current state shape is for the runner cat game.

- [ ] **Step 3: Implement the minimal shooter state factory**

Track:
- player position, target position, health, occupied vehicle state
- current weapon and ammo pools
- tank position, occupancy, shell ammo, cooldown
- bullets and enemy lists
- pickup availability
- wave number and kill count
- status message and game status

- [ ] **Step 4: Write the failing tests for state transitions**

Cover:
- picking up a weapon swaps the current weapon
- ammo pickup increases ammo but not beyond max
- entering the tank changes control state
- shell pickup increases tank ammo
- taking lethal damage ends the game
- clearing a wave advances the wave counter

- [ ] **Step 5: Implement minimal pure state transition helpers**

Add helpers for:
- weapon pickup
- ammo pickup
- tank entry
- shell pickup
- damage application
- wave advancement

- [ ] **Step 6: Run the focused tests**

Run: `npm run test -- tests/state.test.js`
Expected: PASS

## Chunk 3: Input and Frame Loop

### Task 5: Replace jump input with movement and hold-to-fire input

**Files:**
- Replace: `C:/Users/qinso/Desktop/Codex/cat-box-game/src/game/input.js`
- Replace: `C:/Users/qinso/Desktop/Codex/cat-box-game/tests/input.test.js`

- [ ] **Step 1: Write the failing tests for input handling**

Cover:
- pointer move updates the player target coordinates
- pointer down starts firing
- pointer up stops firing
- language button request is still supported
- restart request is still supported

- [ ] **Step 2: Run the input tests to verify they fail**

Run: `npm run test -- tests/input.test.js`
Expected: FAIL because the old input module only supports jump and language toggle.

- [ ] **Step 3: Implement minimal input state and helpers**

Store:
- target x/y
- firing pressed state
- language toggle request
- restart request

- [ ] **Step 4: Run the focused tests**

Run: `npm run test -- tests/input.test.js`
Expected: PASS

### Task 6: Build the smooth frame update loop

**Files:**
- Replace: `C:/Users/qinso/Desktop/Codex/cat-box-game/src/game/loop.js`
- Replace: `C:/Users/qinso/Desktop/Codex/cat-box-game/tests/loop.test.js`

- [ ] **Step 1: Write the failing tests for frame updates**

Cover:
- player position moves closer to the pointer target each frame
- holding fire spawns bullets after the weapon cooldown
- enemies move toward the player each frame
- bullet hits remove enemies or reduce health
- occupied tank fires shells on its own cooldown
- empty waves queue the next wave

- [ ] **Step 2: Run the loop tests to verify they fail**

Run: `npm run test -- tests/loop.test.js`
Expected: FAIL because the current loop only supports runner movement.

- [ ] **Step 3: Implement the minimal real-time update loop**

Update:
- smooth player or tank movement
- firing timers and projectile creation
- enemy movement
- collisions and damage
- pickup overlap checks
- wave spawning and completion

- [ ] **Step 4: Run the focused tests**

Run: `npm run test -- tests/loop.test.js`
Expected: PASS

## Chunk 4: Rendering and UI Wiring

### Task 7: Replace the runner markup with the street shooter scene

**Files:**
- Replace: `C:/Users/qinso/Desktop/Codex/cat-box-game/src/game/render.js`
- Replace: `C:/Users/qinso/Desktop/Codex/cat-box-game/src/styles.css`
- Replace: `C:/Users/qinso/Desktop/Codex/cat-box-game/tests/render.test.js`

- [ ] **Step 1: Write the failing render tests**

Cover:
- HUD renders health, ammo, wave, kills
- stage renders street background elements
- weapon pickups and ammo pickups render
- tank renders when present
- game over state renders restart controls

- [ ] **Step 2: Run the render tests to verify they fail**

Run: `npm run test -- tests/render.test.js`
Expected: FAIL because the current markup is still for the runner game.

- [ ] **Step 3: Implement the minimal shooter renderer**

Render:
- HUD labels from i18n
- player, enemies, bullets, pickups, tank
- street background layers and decorative props
- result banner and restart button

- [ ] **Step 4: Implement the street-style CSS**

Style:
- asphalt road and markings
- barriers, crates, graffiti surfaces, wreck props
- distinct player, enemy, pickup, and tank visuals
- responsive layout that still reads on smaller screens

- [ ] **Step 5: Run the focused tests**

Run: `npm run test -- tests/render.test.js`
Expected: PASS

### Task 8: Wire DOM events and render updates into the app bootstrap

**Files:**
- Replace: `C:/Users/qinso/Desktop/Codex/cat-box-game/src/game/ui.js`
- Modify: `C:/Users/qinso/Desktop/Codex/cat-box-game/src/main.js`
- Replace: `C:/Users/qinso/Desktop/Codex/cat-box-game/tests/ui.test.js`

- [ ] **Step 1: Write the failing UI tests**

Cover:
- app bootstraps into the shooter UI
- pointer events update input state
- mouse hold starts and stops firing
- language toggle rerenders labels
- restart rebuilds the shooter state

- [ ] **Step 2: Run the UI tests to verify they fail**

Run: `npm run test -- tests/ui.test.js`
Expected: FAIL because the current UI bootstrap binds runner-specific actions.

- [ ] **Step 3: Implement the minimal UI bootstrap**

Wire:
- initial render
- pointer move/down/up handlers
- language button
- restart button
- loop lifecycle start/stop

- [ ] **Step 4: Run the focused tests**

Run: `npm run test -- tests/ui.test.js`
Expected: PASS

## Chunk 5: Final Verification and Docs

### Task 9: Update docs and verify the playable build

**Files:**
- Modify: `C:/Users/qinso/Desktop/Codex/cat-box-game/README.md`

- [ ] **Step 1: Update the README**

Document:
- mouse-follow movement
- hold-to-fire shooting
- weapon pickups
- ammo pickups
- tank entry and shell pickups
- test/build commands

- [ ] **Step 2: Run the full automated test suite**

Run: `npm run test`
Expected: PASS

- [ ] **Step 3: Run the production build**

Run: `npm run build`
Expected: PASS

- [ ] **Step 4: Run the desktop game manually**

Run: `npm run dev` or `run-cat-box-game.bat`
Expected: the street shooter opens, movement feels smooth, hold-to-fire works, pickups work, waves progress, and the tank can be entered and fired.

- [ ] **Step 5: Commit**

```bash
git add C:/Users/qinso/Desktop/Codex/cat-box-game C:/Users/qinso/Desktop/Codex/docs/superpowers/specs/2026-03-19-street-shooter-design.md C:/Users/qinso/Desktop/Codex/docs/superpowers/plans/2026-03-19-street-shooter-implementation.md
git commit -m "feat: turn cat box game into street shooter"
```
