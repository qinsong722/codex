# Cat Mouse Box Game Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a cute desktop mini-game where a growing cat chooses between a safer box and a riskier box, eats weaker mice, loses health to stronger mice, and evolves visually over time.

**Architecture:** Build a single-window desktop game using a small web app wrapped for desktop. Keep the first version to one gameplay screen with a simple state machine for choosing a box, revealing a mouse, resolving the result, and ending the run. Use clear, isolated files for game rules, state updates, rendering, and art assets so later polish does not tangle with gameplay logic.

**Tech Stack:** HTML, CSS, JavaScript, Vite, Electron, Vitest

---

## File Structure

- Create: `C:/Users/qinso/Desktop/Codex/cat-box-game/package.json`
- Create: `C:/Users/qinso/Desktop/Codex/cat-box-game/vite.config.js`
- Create: `C:/Users/qinso/Desktop/Codex/cat-box-game/index.html`
- Create: `C:/Users/qinso/Desktop/Codex/cat-box-game/src/main.js`
- Create: `C:/Users/qinso/Desktop/Codex/cat-box-game/src/game/constants.js`
- Create: `C:/Users/qinso/Desktop/Codex/cat-box-game/src/game/state.js`
- Create: `C:/Users/qinso/Desktop/Codex/cat-box-game/src/game/rules.js`
- Create: `C:/Users/qinso/Desktop/Codex/cat-box-game/src/game/render.js`
- Create: `C:/Users/qinso/Desktop/Codex/cat-box-game/src/game/ui.js`
- Create: `C:/Users/qinso/Desktop/Codex/cat-box-game/src/styles.css`
- Create: `C:/Users/qinso/Desktop/Codex/cat-box-game/src/assets/README.md`
- Create: `C:/Users/qinso/Desktop/Codex/cat-box-game/electron/main.js`
- Create: `C:/Users/qinso/Desktop/Codex/cat-box-game/tests/rules.test.js`
- Create: `C:/Users/qinso/Desktop/Codex/cat-box-game/tests/state.test.js`
- Create: `C:/Users/qinso/Desktop/Codex/cat-box-game/README.md`

## Chunk 1: Project Setup

### Task 1: Create desktop app scaffold

**Files:**
- Create: `C:/Users/qinso/Desktop/Codex/cat-box-game/package.json`
- Create: `C:/Users/qinso/Desktop/Codex/cat-box-game/vite.config.js`
- Create: `C:/Users/qinso/Desktop/Codex/cat-box-game/index.html`
- Create: `C:/Users/qinso/Desktop/Codex/cat-box-game/src/main.js`
- Create: `C:/Users/qinso/Desktop/Codex/cat-box-game/electron/main.js`
- Create: `C:/Users/qinso/Desktop/Codex/cat-box-game/README.md`

- [ ] **Step 1: Write the initial package and script definitions**

Add scripts for `dev`, `build`, `test`, and `electron`.

- [ ] **Step 2: Run install to fetch dependencies**

Run: `npm install`
Expected: dependencies install without errors.

- [ ] **Step 3: Create the minimal browser entry**

Render a placeholder heading and one root element in `src/main.js`.

- [ ] **Step 4: Create the Electron window bootstrap**

Open a fixed-size cute game window that loads the Vite app.

- [ ] **Step 5: Run the app shell**

Run: `npm run dev`
Expected: a local game page opens with the placeholder UI.

- [ ] **Step 6: Commit**

```bash
git add cat-box-game
git commit -m "feat: scaffold cat box desktop game"
```

## Chunk 2: Core Rules

### Task 2: Write and pass rule tests for mice encounters

**Files:**
- Create: `C:/Users/qinso/Desktop/Codex/cat-box-game/src/game/constants.js`
- Create: `C:/Users/qinso/Desktop/Codex/cat-box-game/src/game/rules.js`
- Create: `C:/Users/qinso/Desktop/Codex/cat-box-game/tests/rules.test.js`

- [ ] **Step 1: Write the failing test for winning an encounter**

```javascript
import { resolveEncounter } from "../src/game/rules";

test("cat eats mouse when cat level is high enough", () => {
  expect(resolveEncounter({ catLevel: 2, mouseLevel: 2 })).toEqual({
    outcome: "eat",
    healthLoss: 0,
    growthGain: 1,
  });
});
```

- [ ] **Step 2: Run the single test to verify it fails**

Run: `npm run test -- tests/rules.test.js`
Expected: FAIL because `resolveEncounter` does not exist yet.

- [ ] **Step 3: Implement the minimal rule logic**

Handle:
- cat level greater than or equal to mouse level -> eat mouse
- cat level lower than mouse level -> bounce back and lose 1 health

- [ ] **Step 4: Add failing tests for safe and risky box generation**

Test that safe boxes skew toward lower mouse levels and risky boxes allow higher levels.

- [ ] **Step 5: Implement minimal mouse generation rules**

Expose a function that returns a mouse level based on box type and current cat level.

- [ ] **Step 6: Run the rules tests**

Run: `npm run test -- tests/rules.test.js`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add cat-box-game/tests/rules.test.js cat-box-game/src/game/constants.js cat-box-game/src/game/rules.js
git commit -m "feat: add encounter and box rules"
```

### Task 3: Write and pass state tests for growth and game over

**Files:**
- Create: `C:/Users/qinso/Desktop/Codex/cat-box-game/src/game/state.js`
- Create: `C:/Users/qinso/Desktop/Codex/cat-box-game/tests/state.test.js`
- Modify: `C:/Users/qinso/Desktop/Codex/cat-box-game/src/game/constants.js`

- [ ] **Step 1: Write the failing test for cat growth**

```javascript
import { applyEncounterResult, createInitialState } from "../src/game/state";

test("cat grows after eating enough mice", () => {
  let state = createInitialState();
  state = applyEncounterResult(state, { outcome: "eat", growthGain: 1, healthLoss: 0 });
  state = applyEncounterResult(state, { outcome: "eat", growthGain: 1, healthLoss: 0 });
  expect(state.cat.level).toBe(2);
});
```

- [ ] **Step 2: Run the state test to verify it fails**

Run: `npm run test -- tests/state.test.js`
Expected: FAIL because state helpers are missing.

- [ ] **Step 3: Implement minimal game state**

Track:
- cat level
- growth progress
- health
- total mice eaten
- current form stage
- game over flag

- [ ] **Step 4: Add failing test for health reaching zero**

Verify that repeated failed encounters trigger game over.

- [ ] **Step 5: Implement health loss and end-of-run logic**

Set `gameOver` when health reaches zero.

- [ ] **Step 6: Run the state tests**

Run: `npm run test -- tests/state.test.js`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add cat-box-game/tests/state.test.js cat-box-game/src/game/state.js cat-box-game/src/game/constants.js
git commit -m "feat: add cat growth and run state"
```

## Chunk 3: Playable Screen

### Task 4: Build the main game UI

**Files:**
- Create: `C:/Users/qinso/Desktop/Codex/cat-box-game/src/game/render.js`
- Create: `C:/Users/qinso/Desktop/Codex/cat-box-game/src/game/ui.js`
- Create: `C:/Users/qinso/Desktop/Codex/cat-box-game/src/styles.css`
- Modify: `C:/Users/qinso/Desktop/Codex/cat-box-game/src/main.js`

- [ ] **Step 1: Render the static layout**

Show:
- top status bar
- cat area
- left safe box
- right risky box
- message area

- [ ] **Step 2: Run the app and verify the layout appears**

Run: `npm run dev`
Expected: both boxes and the cat area are visible.

- [ ] **Step 3: Wire box click events**

Clicking a box should:
- generate a mouse
- resolve encounter
- update state
- re-render UI

- [ ] **Step 4: Show clear result messages**

Examples:
- `Cat ate Lv1 mouse`
- `Mouse was too strong! Lost 1 heart`
- `Cat evolved to Lv3`

- [ ] **Step 5: Disable box choices after game over**

Show a restart button or restart action.

- [ ] **Step 6: Run tests and manual smoke test**

Run:
- `npm run test`
- `npm run dev`

Expected:
- tests PASS
- manual play loop works from start to game over

- [ ] **Step 7: Commit**

```bash
git add cat-box-game/src/main.js cat-box-game/src/game/render.js cat-box-game/src/game/ui.js cat-box-game/src/styles.css
git commit -m "feat: add playable box selection loop"
```

## Chunk 4: Cute Visual Feedback

### Task 5: Add cartoon look and growth stages

**Files:**
- Modify: `C:/Users/qinso/Desktop/Codex/cat-box-game/src/styles.css`
- Modify: `C:/Users/qinso/Desktop/Codex/cat-box-game/src/game/render.js`
- Create: `C:/Users/qinso/Desktop/Codex/cat-box-game/src/assets/README.md`

- [ ] **Step 1: Define the first-pass visual language**

Choose:
- warm background
- rounded panels
- cute cat colors
- heart icons for health

- [ ] **Step 2: Add visual differences for cat forms**

At minimum, show 3 form stages:
- tiny kitten
- growing cat
- fancy evolved cat

- [ ] **Step 3: Add lightweight animations**

Animate:
- box pop
- mouse reveal
- cat success bounce
- cat failure recoil

- [ ] **Step 4: Add placeholder art notes**

Document what future art assets are needed in `src/assets/README.md`.

- [ ] **Step 5: Run manual verification**

Run: `npm run dev`
Expected: the game feels cute, readable, and clear without added art files.

- [ ] **Step 6: Commit**

```bash
git add cat-box-game/src/styles.css cat-box-game/src/game/render.js cat-box-game/src/assets/README.md
git commit -m "feat: add first-pass cartoon presentation"
```

## Chunk 5: Desktop Packaging and Finish

### Task 6: Verify desktop run and document controls

**Files:**
- Modify: `C:/Users/qinso/Desktop/Codex/cat-box-game/package.json`
- Modify: `C:/Users/qinso/Desktop/Codex/cat-box-game/README.md`
- Modify: `C:/Users/qinso/Desktop/Codex/cat-box-game/electron/main.js`

- [ ] **Step 1: Add a desktop run command**

Ensure one command starts the desktop shell against the local app.

- [ ] **Step 2: Verify the desktop window behavior**

Run: `npm run electron`
Expected: a desktop window opens and the game is playable.

- [ ] **Step 3: Document how to start and play**

Explain:
- how to install
- how to run
- how the safe and risky boxes work
- how growth and health work

- [ ] **Step 4: Run final verification**

Run:
- `npm run test`
- `npm run dev`
- `npm run electron`

Expected:
- tests PASS
- browser mode works
- desktop mode works

- [ ] **Step 5: Commit**

```bash
git add cat-box-game/package.json cat-box-game/README.md cat-box-game/electron/main.js
git commit -m "docs: finalize desktop run instructions"
```
