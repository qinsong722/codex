# Ride Approver DevTools Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a DevTools-based ride approver entrypoint that launches its own browser, waits for manual SMS-code login, and continues automatic approval.

**Architecture:** Build a new standalone Python script that reuses the existing config/logging conventions while launching Chrome or Edge with a remote debugging port and attaching Selenium through `debuggerAddress`. Keep Selenium and Playwright versions unchanged, and add a dedicated batch launcher for the new DevTools flow.

**Tech Stack:** Python 3.13, Selenium 4, Chrome/Edge remote debugging, Tkinter prompts, Windows batch launcher

---

## Chunk 1: DevTools Script Skeleton And Runtime Plumbing

### Task 1: Create the new entrypoint with shared runtime conventions

**Files:**
- Create: `C:\Users\qinso\Desktop\批车单-20260319优化版\approve_orders_devtools.py`
- Test: manual startup in `C:\Users\qinso\Desktop\批车单-20260319优化版`

- [ ] **Step 1: Create the new script skeleton**
- [ ] **Step 2: Add app-dir, config-file, log-file, and lock-file path handling**
- [ ] **Step 3: Reuse phone-number and approver config parsing and prompting**
- [ ] **Step 4: Add append-log and step logging helpers**
- [ ] **Step 5: Add single-instance lock acquire/release helpers**

### Task 2: Add browser detection and DevTools launch support

**Files:**
- Modify: `C:\Users\qinso\Desktop\批车单-20260319优化版\approve_orders_devtools.py`
- Test: manual startup in `C:\Users\qinso\Desktop\批车单-20260319优化版`

- [ ] **Step 1: Add Chrome/Edge binary candidate lists with Chrome preference**
- [ ] **Step 2: Add isolated profile-dir management for DevTools browser sessions**
- [ ] **Step 3: Add remote-debugging port selection and availability checks**
- [ ] **Step 4: Add browser-process launch code with Windows-friendly arguments**
- [ ] **Step 5: Add Selenium attach flow through `debuggerAddress`**

## Chunk 2: Login And Approval Automation

### Task 3: Port login preparation and manual-login waiting

**Files:**
- Modify: `C:\Users\qinso\Desktop\批车单-20260319优化版\approve_orders_devtools.py`
- Reference: `C:\Users\qinso\Desktop\批车单-20260319优化版\approve_orders.py`
- Reference: `C:\Users\qinso\Desktop\批车单-20260319优化版\approve_orders_playwright.py`

- [ ] **Step 1: Add login-page navigation and readiness helpers**
- [ ] **Step 2: Fill phone number, check agreement, and click send-code**
- [ ] **Step 3: Add blank-page or stuck-page refresh handling**
- [ ] **Step 4: Wait for manual verification-code login success**
- [ ] **Step 5: Route to the audit page after login**

### Task 4: Port the approval loop and dialog handling

**Files:**
- Modify: `C:\Users\qinso\Desktop\批车单-20260319优化版\approve_orders_devtools.py`
- Reference: `C:\Users\qinso\Desktop\批车单-20260319优化版\approve_orders.py`

- [ ] **Step 1: Add page text helpers and selector wrappers**
- [ ] **Step 2: Add pending-order discovery and agree-button flow**
- [ ] **Step 3: Add approver-selection dialog handling**
- [ ] **Step 4: Add submit, keepalive, and no-work refresh behavior**
- [ ] **Step 5: Preserve browser state for manual inspection on unexpected failures**

## Chunk 3: Launching And Verification

### Task 5: Add the dedicated batch launcher

**Files:**
- Create: `C:\Users\qinso\Desktop\批车单-20260319优化版\start_approval_devtools.bat`

- [ ] **Step 1: Add a Windows batch launcher for `approve_orders_devtools.py`**
- [ ] **Step 2: Keep existing batch launchers unchanged**

### Task 6: Verify on this machine

**Files:**
- Test: `C:\Users\qinso\Desktop\批车单-20260319优化版\approve_orders_devtools.py`
- Test: `C:\Users\qinso\Desktop\批车单-20260319优化版\start_approval_devtools.bat`

- [ ] **Step 1: Run the new script directly**
- [ ] **Step 2: Confirm browser launch, send-code flow, and manual-login wait state**
- [ ] **Step 3: Run the batch launcher**
- [ ] **Step 4: Confirm logs and lock-file behavior**
