# Ride Approver DevTools Design

Date: 2026-03-21

## Goal

Add a third automation entrypoint based on a DevTools-controlled browser without replacing the existing Selenium and Playwright versions.

The new version should:

- auto-detect Chrome or Edge, preferring Chrome
- launch its own browser instance with a remote debugging port
- open the login page and send the SMS code automatically
- wait for the user to manually enter the verification code and finish login
- continue into the ride approval page and keep auto-approving requests
- preserve logs, single-instance protection, and manual inspection behavior

## Files

New files:

- `approve_orders_devtools.py`
- `start_approval_devtools.bat`

Existing files reused without behavior changes:

- `phone_number.txt`
- `approve_orders.log`
- `approve_orders.py`
- `approve_orders_playwright.py`

## Approach

The DevTools version will use a browser launched with a remote debugging port and an isolated profile directory. The script will then attach to that browser through Selenium's `debuggerAddress` option, which keeps the browser startup and session ownership DevTools-based while letting the existing DOM automation patterns stay maintainable.

This gives us:

- stable browser startup on the local machine
- a dedicated browser profile for the automation
- simpler reuse of current selectors and approval logic
- a clear migration path from the existing Selenium version

## Runtime Flow

1. Acquire a single-instance lock for the DevTools bot.
2. Load or prompt for the phone number and approver name.
3. Detect an installed browser, preferring Chrome and then Edge.
4. Start the browser with:
   - `--remote-debugging-port=<port>`
   - isolated `--user-data-dir`
   - fixed window size and position
5. Attach a WebDriver session through `debuggerAddress`.
6. Open the login page.
7. Fill the phone number, check the agreement box, and click the send-code button.
8. Wait for the user to enter the verification code and finish login manually.
9. Detect login success and navigate to the audit page.
10. Loop through pending approvals:
    - find the next pending request
    - click agree
    - if an approver-selection dialog appears, choose the configured approver
    - submit
11. If no request is available, stay on the page and refresh periodically.

## Main Components

### Configuration

Reuse the current config format in `phone_number.txt`:

- `phone_number=<11-digit number>`
- `approver=<name>`

Backward compatibility with the older one-line phone-only format should remain.

### Browser Launcher

Responsibilities:

- find Chrome or Edge
- select a debugging port
- create an isolated DevTools profile directory
- launch the browser process
- detect startup failures clearly

### DevTools Bot

Responsibilities:

- attach to the launched browser
- drive login-page preparation
- monitor login completion
- run the approval loop
- emit step-based logs

### Recovery / Diagnostics

Responsibilities:

- refresh when the login page is blank or stuck
- refresh when the audit page stops progressing
- preserve the browser for manual inspection on unexpected failures
- keep a traceable log of the current step and reason for pause

## Error Handling

Expected cases:

- browser binary not found
- remote debugging port unavailable
- attach-to-browser failure
- login page blank or half-loaded
- session timeout after login
- approval page selector drift

Handling policy:

- retry safe page-refresh scenarios
- stop and preserve the browser for manual inspection when recovery is uncertain
- always write the latest step and error reason into `approve_orders.log`

## Testing Plan

Verification should cover:

- script starts and launches a dedicated browser instance
- phone number and approver prompts/config load correctly
- send-code flow reaches the manual-login waiting state
- login success detection navigates into the audit page
- approval loop handles both:
  - normal approve flow
  - approver-selection dialog flow
- no-pending-item state leaves the bot waiting and refreshing

## Non-Goals

This change does not:

- remove or rewrite the existing Selenium script
- replace the Playwright prototype
- automate SMS code entry
- package a new `.exe` in the same change

## Recommended Implementation Order

1. Add the new DevTools script with shared config and logging conventions.
2. Implement browser launch and attach flow.
3. Port login preparation and manual-login waiting.
4. Port the approval loop and approver-selection handling.
5. Add the dedicated batch entrypoint.
6. Run a real startup verification on this machine.
