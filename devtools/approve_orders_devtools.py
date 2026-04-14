from __future__ import annotations

import atexit
import ctypes
import os
import socket
import subprocess
import sys
import time
import traceback
import tkinter as tk
from pathlib import Path
from ctypes import wintypes
from tkinter import messagebox, simpledialog

from selenium import webdriver
from selenium.common.exceptions import (
    ElementClickInterceptedException,
    StaleElementReferenceException,
    TimeoutException,
    WebDriverException,
)
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.by import By
from selenium.webdriver.edge.options import Options as EdgeOptions
from selenium.webdriver.edge.service import Service as EdgeService
from selenium.webdriver.support.ui import WebDriverWait


SITE_URL = "https://b2bjoy.10086.cn/t100/#/home/index"
LOGIN_URL = "https://b2bjoy.10086.cn/t100/#/login"
AUDIT_URL = "https://b2bjoy.10086.cn/t100/#/travelApplyList?type=1&fromType=car"
CONFIG_FILE_NAME = "phone_number.txt"
WINDOW_WIDTH = 404
WINDOW_HEIGHT = 876
WINDOW_POS_X = 80
WINDOW_POS_Y = 0
POLL_INTERVAL_SECONDS = 300
HEARTBEAT_CHECK_INTERVAL_SECONDS = 3
IDLE_KEEPALIVE_INTERVAL_SECONDS = 20
IDLE_REFRESH_INTERVAL_SECONDS = 180
LOGIN_PAGE_READY_TIMEOUT_SECONDS = 60
SEND_CODE_READY_TIMEOUT_SECONDS = 25
SEND_CODE_CONFIRM_TIMEOUT_SECONDS = 6
SEND_CODE_SECOND_CLICK_SECONDS = 1.2
LOGIN_SUBMIT_GRACE_SECONDS = 20
LOGIN_RESUBMIT_INTERVAL_SECONDS = 8
LOGIN_RESUBMIT_MAX_ATTEMPTS = 2
SELECTION_REOPEN_MAX_ATTEMPTS = 3

CHROME_BINARY_CANDIDATES = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
]
EDGE_BINARY_CANDIDATES = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
]


def normalize_text(value: str | None) -> str:
    return " ".join((value or "").split())


def text_matches(target: str, actual: str | None) -> bool:
    return normalize_text(target) == normalize_text(actual)


def get_app_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


APP_DIR = get_app_dir()
CONFIG_FILE = APP_DIR / CONFIG_FILE_NAME
LOG_FILE = APP_DIR / "approve_orders.log"
LOCK_FILE = APP_DIR / ".approve_devtools.lock"
CHROME_PROFILE_ROOT = APP_DIR / "devtools-chrome-profiles"
EDGE_PROFILE_ROOT = APP_DIR / "devtools-edge-profiles"


def append_log(message: str) -> None:
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with LOG_FILE.open("a", encoding="utf-8") as fh:
        fh.write(f"[{timestamp}] [DT] {message}\n")


def get_text_prompt(title: str, prompt: str, validator) -> str:
    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    try:
        while True:
            value = simpledialog.askstring(title, prompt, parent=root)
            if value is None:
                raise RuntimeError("User canceled configuration input.")
            normalized = validator(value)
            if normalized is not None:
                return normalized
            messagebox.showerror("Invalid Input", "Please enter a valid value.", parent=root)
    finally:
        root.destroy()


def validate_phone(value: str) -> str | None:
    digits = "".join(ch for ch in value if ch.isdigit())
    return digits if len(digits) == 11 else None


def validate_approver(value: str) -> str | None:
    cleaned = value.strip()
    return cleaned or None


def parse_config_text(text: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            key, value = line.split("=", 1)
            result[key.strip().lower()] = value.strip()
    return result


def write_config(phone_number: str, approver_name: str) -> None:
    CONFIG_FILE.write_text(
        f"phone_number={phone_number}\napprover={approver_name}\n",
        encoding="utf-8",
    )


def load_runtime_config() -> tuple[str, str]:
    phone_number: str | None = None
    approver_name: str | None = None
    if CONFIG_FILE.exists():
        raw_text = CONFIG_FILE.read_text(encoding="utf-8").strip()
        parsed = parse_config_text(raw_text)
        if parsed:
            phone_number = validate_phone(parsed.get("phone_number", ""))
            approver_name = validate_approver(parsed.get("approver", ""))
        else:
            phone_number = validate_phone(raw_text)

    if phone_number is None:
        phone_number = get_text_prompt(
            "Phone Number",
            f"Please enter the login phone number for {CONFIG_FILE_NAME}:",
            validate_phone,
        )
    if approver_name is None:
        approver_name = get_text_prompt(
            "Approver",
            f"Please enter the default approver name for {CONFIG_FILE_NAME}:",
            validate_approver,
        )
    write_config(phone_number, approver_name)
    return phone_number, approver_name


def process_is_running(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def acquire_single_instance_lock() -> None:
    if LOCK_FILE.exists():
        raw = LOCK_FILE.read_text(encoding="utf-8").strip()
        try:
            existing_pid = int(raw)
        except ValueError:
            existing_pid = 0
        if existing_pid and process_is_running(existing_pid):
            raise RuntimeError(f"Another DevTools approver instance is already running (PID={existing_pid}).")
        LOCK_FILE.unlink(missing_ok=True)
    LOCK_FILE.write_text(str(os.getpid()), encoding="utf-8")


def release_single_instance_lock() -> None:
    if not LOCK_FILE.exists():
        return
    try:
        raw = LOCK_FILE.read_text(encoding="utf-8").strip()
    except OSError:
        return
    if raw == str(os.getpid()):
        LOCK_FILE.unlink(missing_ok=True)


def choose_browser_binary(excluded: set[str] | None = None) -> tuple[str, Path]:
    excluded = excluded or set()
    if "chrome" not in excluded:
        for candidate in CHROME_BINARY_CANDIDATES:
            path = Path(candidate)
            if path.exists():
                return "chrome", path
    if "edge" not in excluded:
        for candidate in EDGE_BINARY_CANDIDATES:
            path = Path(candidate)
            if path.exists():
                return "edge", path
    joined = ", ".join(CHROME_BINARY_CANDIDATES + EDGE_BINARY_CANDIDATES)
    raise FileNotFoundError(f"No supported browser binary found. Checked: {joined}")

def is_browser_first_run_page(title: str, body_text: str) -> bool:
    combined = normalize_text(f"{title} {body_text}")
    markers = [
        "隐私政策",
        "欢迎使用 chrome",
        "欢迎使用 edge",
        "设置为默认浏览器",
        "登录到 chrome",
        "登录到 edge",
    ]
    lowered = combined.lower()
    return any(marker.lower() in lowered for marker in markers)

def build_browser_launch_args(profile_dir: Path, debugging_port: int) -> list[str]:
    return [
        f"--remote-debugging-port={debugging_port}",
        f"--user-data-dir={profile_dir}",
        f"--window-size={WINDOW_WIDTH},{WINDOW_HEIGHT}",
        f"--window-position={WINDOW_POS_X},{WINDOW_POS_Y}",
        "--no-first-run",
        "--disable-default-apps",
        "--disable-sync",
        "--disable-features=msEdgeSidebarV2",
    ]


def pick_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def wait_for_port(host: str, port: int, timeout_seconds: float = 15.0) -> None:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(0.4)
            try:
                sock.connect((host, port))
                return
            except OSError:
                time.sleep(0.2)
    raise RuntimeError(f"DevTools port {port} did not become ready in time.")


class DevtoolsApproveBot:
    def __init__(self) -> None:
        self.phone_number, self.approver_name = load_runtime_config()
        self.browser_name, self.browser_binary = choose_browser_binary()
        self.profile_dir = self.prepare_profile_dir()
        self.debugging_port = pick_free_port()
        self.browser_process: subprocess.Popen | None = None
        self.driver = None
        self.wait = None
        self.keep_browser_open = False
        self.approver_selection_attempted = False
        self.last_validated_approver_name = ""
        self.last_validation_mode = ""
        self.last_clicked_approver_name = ""
        self.last_clicked_approver_text = ""
        atexit.register(self.close)

    def prepare_profile_dir(self) -> Path:
        profile_root = CHROME_PROFILE_ROOT if self.browser_name == "chrome" else EDGE_PROFILE_ROOT
        profile_root.mkdir(parents=True, exist_ok=True)
        profile_dir = profile_root / f"run-{int(time.time())}-{os.getpid()}"
        profile_dir.mkdir(parents=True, exist_ok=True)
        return profile_dir

    def log(self, message: str) -> None:
        try:
            print(message, flush=True)
        except (OSError, ValueError):
            pass
        append_log(message)

    def ensure_browser_window_visible(self) -> None:
        if self.browser_process is None or self.driver is None:
            return
        try:
            self.driver.maximize_window()
        except Exception:
            pass
        try:
            pid = self.browser_process.pid
        except Exception:
            return
        try:
            user32 = ctypes.windll.user32
            hwnds: list[int] = []

            def enum_windows_proc(hwnd, _lparam):
                try:
                    if not user32.IsWindowVisible(hwnd):
                        return True
                    found_pid = wintypes.DWORD()
                    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(found_pid))
                    if found_pid.value == pid:
                        hwnds.append(hwnd)
                except Exception:
                    pass
                return True

            enum_proc = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)(enum_windows_proc)
            user32.EnumWindows(enum_proc, 0)
            if hwnds:
                hwnd = hwnds[0]
                user32.ShowWindow(hwnd, 9)
                user32.SetForegroundWindow(hwnd)
                user32.BringWindowToTop(hwnd)
        except Exception:
            return

    def set_step(self, step: str) -> None:
        self.log(f"Step: {step}")

    def launch_browser_process(self) -> None:
        self.set_step("launch_browser")
        args = [str(self.browser_binary), *build_browser_launch_args(self.profile_dir, self.debugging_port), LOGIN_URL]
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        self.browser_process = subprocess.Popen(args, creationflags=creationflags)
        self.log(f"Waiting for DevTools port {self.debugging_port} to become ready.")
        wait_for_port("127.0.0.1", self.debugging_port)
        self.log(f"DevTools port {self.debugging_port} is ready.")

    def attach_driver(self) -> None:
        self.set_step("attach_driver")
        debugger_address = f"127.0.0.1:{self.debugging_port}"
        if self.browser_name == "chrome":
            options = ChromeOptions()
            options.add_experimental_option("debuggerAddress", debugger_address)
            service = ChromeService()
            service.creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            self.driver = webdriver.Chrome(options=options, service=service)
        else:
            options = EdgeOptions()
            options.add_experimental_option("debuggerAddress", debugger_address)
            service = EdgeService()
            service.creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            self.driver = webdriver.Edge(options=options, service=service)
        self.wait = WebDriverWait(self.driver, 25)
        try:
            self.driver.set_window_position(WINDOW_POS_X, WINDOW_POS_Y)
            self.driver.set_window_size(WINDOW_WIDTH, WINDOW_HEIGHT)
        except Exception:
            pass
        self.log("Driver attached successfully.")

    def close(self) -> None:
        try:
            if self.driver is not None and not self.keep_browser_open:
                self.driver.quit()
        except Exception:
            pass
        try:
            if self.browser_process is not None and not self.keep_browser_open:
                self.browser_process.terminate()
        except Exception:
            pass
        finally:
            self.driver = None
            self.browser_process = None

    def run(self) -> None:
        self.launch_browser_process()
        self.attach_driver()
        try:
            self.login()
            self.open_audit_page()
            self.watch_and_approve_forever()
        except Exception as exc:
            self.log(f"Unhandled error: {exc}")
            self.log(traceback.format_exc())
            self.keep_browser_open = True
            self.pause_for_manual_inspection()
            raise

    def pause_for_manual_inspection(self) -> None:
        self.log("An error occurred. The browser will stay open for inspection.")
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        try:
            messagebox.showerror(
                "DevTools Approver Paused",
                "The DevTools approver hit an error. The browser has been left open for inspection.",
                parent=root,
            )
        finally:
            root.destroy()

    def login(self) -> None:
        state = self.open_login_page()
        if state == "browser_first_run":
            if not self.try_fallback_browser():
                raise RuntimeError("Browser opened a first-run page and no fallback browser was available.")
            state = self.open_login_page()
        if state == "authenticated":
            self.log("Existing login detected. Skipping SMS login.")
            return
        self.prepare_login_page(send_code=True)
        self.focus_code_input()
        self.log("SMS code has been requested. Please enter the verification code manually.")
        self.wait_for_login_success()
        self.log("Login successful.")

    def current_page_snapshot(self) -> tuple[str, str]:
        try:
            title = self.driver.title or ""
        except WebDriverException:
            title = ""
        try:
            body_text = normalize_text(self.driver.find_element(By.TAG_NAME, "body").text)
        except WebDriverException:
            body_text = ""
        return title, body_text

    def try_fallback_browser(self) -> bool:
        try:
            browser_name, browser_binary = choose_browser_binary(excluded={self.browser_name})
        except FileNotFoundError:
            return False

        self.log(f"Detected a browser first-run page in {self.browser_name}; retrying with {browser_name}.")
        self.keep_browser_open = False
        self.close()
        self.browser_name = browser_name
        self.browser_binary = browser_binary
        self.profile_dir = self.prepare_profile_dir()
        self.debugging_port = pick_free_port()
        self.launch_browser_process()
        self.attach_driver()
        return True

    def open_login_page(self) -> str:
        self.set_step("open_login_page")
        for target in (LOGIN_URL, SITE_URL, AUDIT_URL):
            self.driver.get(target)
            state = self.wait_for_login_page_ready()
            if state:
                return state
        raise RuntimeError("Unable to open the login page.")

    def wait_for_login_page_ready(self) -> str | None:
        deadline = time.time() + LOGIN_PAGE_READY_TIMEOUT_SECONDS
        while time.time() < deadline:
            try:
                current_url = self.driver.current_url
                body_text = normalize_text(self.driver.find_element(By.TAG_NAME, "body").text)
                title, _ = self.current_page_snapshot()
                phone_input = next(
                    (
                        el
                        for el in self.driver.find_elements(By.TAG_NAME, "input")
                        if (el.get_attribute("type") or "").lower() == "tel" and self.is_clickable_candidate(el)
                    ),
                    None,
                )
                if is_browser_first_run_page(title, body_text):
                    return "browser_first_run"
                if "#/travelApplyList" in current_url or "申请单审批" in body_text or "待审批" in body_text:
                    return "authenticated"
                if phone_input is not None:
                    return "login"
                if "#/login" in current_url or "获取验证码" in body_text or "登录" in body_text:
                    return "login"
            except WebDriverException:
                pass
            time.sleep(0.5)
        return None

    def prepare_login_page(self, send_code: bool) -> float | None:
        self.set_step("prepare_login_page")
        phone_input = self.wait.until(
            lambda d: next(
                (
                    el
                    for el in d.find_elements(By.TAG_NAME, "input")
                    if (el.get_attribute("type") or "").lower() == "tel" and self.is_clickable_candidate(el)
                ),
                None,
            )
        )
        if phone_input is None:
            raise RuntimeError("Phone-number input was not found.")
        phone_input.clear()
        phone_input.send_keys(self.phone_number)
        self.ensure_agreement_checked()
        if send_code:
            return self.send_code_with_retry()
        return None

    def ensure_agreement_checked(self) -> None:
        if self.agreement_looks_checked():
            return
        try:
            clicked = bool(
                self.driver.execute_script(
                    """
                    const container = document.querySelector('.private-in');
                    if (!container) return false;
                    const target = container.querySelector(
                      'input[type="checkbox"], input[type="radio"], [role="checkbox"], [role="radio"], img, [class*="checkbox"], [class*="radio"], [class*="icon"]'
                    );
                    const rect = (target || container).getBoundingClientRect();
                    const x = rect.left + Math.min(Math.max(rect.width * 0.2, 8), Math.max(rect.width - 8, 8));
                    const y = rect.top + rect.height / 2;
                    const hit = document.elementFromPoint(x, y);
                    if (!hit) return false;
                    hit.dispatchEvent(new MouseEvent('mousemove', { bubbles: true, clientX: x, clientY: y }));
                    hit.dispatchEvent(new MouseEvent('mousedown', { bubbles: true, clientX: x, clientY: y }));
                    hit.dispatchEvent(new MouseEvent('mouseup', { bubbles: true, clientX: x, clientY: y }));
                    hit.dispatchEvent(new MouseEvent('click', { bubbles: true, clientX: x, clientY: y }));
                    return true;
                    """,
                )
            )
            if clicked:
                time.sleep(0.3)
                if "#/privatePolicy" in (self.driver.current_url or ""):
                    self.driver.back()
                    time.sleep(0.5)
                elif self.agreement_looks_checked():
                    return
        except Exception:
            pass
        self.log("Agreement checkbox could not be confirmed after one attempt; continuing and letting the send-code consent dialog handle it if needed.")

    def agreement_looks_checked(self) -> bool:
        try:
            return bool(
                self.driver.execute_script(
                    """
                    const container = document.querySelector('.private-in');
                    if (!container) return false;
                    const toggle = container.querySelector('input[type="checkbox"], input[type="radio"]');
                    if (toggle) return Boolean(toggle.checked);
                    if (container.matches('.checked, .active, .is-checked, .selected')) return true;
                    if (container.querySelector('.checked, .active, .is-checked, .selected, [aria-checked="true"]')) return true;
                    return false;
                    """,
                )
            )
        except WebDriverException:
            return False

    def find_send_code_button(self):
        selectors = [
            (By.XPATH, "//a[contains(@class,'get-code')][last()]"),
            (By.XPATH, "//*[self::button or self::span or self::a or self::div][normalize-space(.)='获取验证码']"),
        ]
        for locator in selectors:
            element = self.find_visible(locator, timeout=1)
            if element:
                return element
        return None

    def accept_send_code_consent_if_present(self) -> None:
        deadline = time.time() + 2
        while time.time() < deadline:
            consent = self.find_visible(
                (By.XPATH, "//*[self::button or self::span or self::a or self::div][contains(normalize-space(.),'同意并发送验证码')]"),
                timeout=1,
            )
            if consent:
                self.safe_click(consent)
                time.sleep(0.3)
                return
            time.sleep(0.2)

    def click_send_code_button(self) -> None:
        button = self.find_send_code_button()
        if not button:
            raise RuntimeError("Could not find the send-code button.")
        self.safe_click(button)
        self.accept_send_code_consent_if_present()

    def login_page_send_code_ready(self) -> bool:
        try:
            return bool(
                self.driver.execute_script(
                    """
                    const tel = Array.from(document.querySelectorAll('input')).find(
                      el => (el.type || '').toLowerCase() === 'tel' && el.offsetParent !== null
                    );
                    const container = document.querySelector('.private-in');
                    let agreement = null;
                    if (container) {
                      agreement = container.querySelector(
                        'img, input[type="checkbox"], input[type="radio"], [role="checkbox"], [role="radio"], [class*="checkbox"], [class*="radio"], [class*="icon"]'
                      );
                    }
                    const getCode = Array.from(document.querySelectorAll('a,button,span,div')).find(el => {
                      const text = (el.innerText || '').trim();
                      const rect = el.getBoundingClientRect();
                      return text.includes('获取验证码') && rect.width > 0 && rect.height > 0;
                    });
                    const telValue = ((tel && tel.value) || '').replace(/\\D/g, '');
                    return Boolean(getCode) && Boolean(agreement) && telValue.length === 11;
                    """,
                )
            )
        except WebDriverException:
            return False

    def login_code_send_confirmed(self) -> bool:
        try:
            return bool(
                self.driver.execute_script(
                    """
                    const bodyText = document.body ? document.body.innerText : '';
                    const getCode = Array.from(document.querySelectorAll('a,button,span,div')).find(el => {
                      const text = (el.innerText || '').trim();
                      const rect = el.getBoundingClientRect();
                      return text && rect.width > 0 && rect.height > 0 && (
                        /\\d+s/.test(text) || text.includes('重新获取') || text.includes('已发送')
                      );
                    });
                    return Boolean(getCode) || bodyText.includes('验证码已发送');
                    """,
                )
            )
        except WebDriverException:
            return False

    def send_code_with_retry(self) -> float:
        attempts = 3
        for attempt in range(1, attempts + 1):
            ready_deadline = time.time() + SEND_CODE_READY_TIMEOUT_SECONDS
            while time.time() < ready_deadline:
                if self.login_page_send_code_ready():
                    break
                time.sleep(0.3)
            else:
                if attempt < attempts:
                    self.driver.refresh()
                    self.wait_for_login_page_ready()
                    self.prepare_login_page(send_code=False)
                    continue
                raise RuntimeError("Login page did not become ready for sending the SMS code.")

            button = self.find_send_code_button()
            if not button:
                raise RuntimeError("Could not find the send-code button.")
            self.click_send_code_button()
            sent_at = time.time()
            confirm_deadline = sent_at + SEND_CODE_CONFIRM_TIMEOUT_SECONDS
            second_click_done = False
            while time.time() < confirm_deadline:
                if self.login_code_send_confirmed():
                    return sent_at
                if not second_click_done and time.time() - sent_at >= SEND_CODE_SECOND_CLICK_SECONDS:
                    try:
                        self.click_send_code_button()
                    except Exception:
                        pass
                    second_click_done = True
                time.sleep(0.3)
            if attempt < attempts:
                self.driver.refresh()
                self.wait_for_login_page_ready()
                self.prepare_login_page(send_code=False)
        raise RuntimeError("Failed to confirm that the SMS code was sent.")

    def focus_code_input(self) -> None:
        code_input = self.find_visible(
            (By.XPATH, "//input[@maxlength='6' or contains(@placeholder,'验证码')]"),
            timeout=3,
        )
        if not code_input:
            return
        try:
            self.driver.execute_script(
                """
                arguments[0].scrollIntoView({block:'center', inline:'nearest'});
                try { window.focus(); } catch (e) {}
                arguments[0].focus();
                if (typeof arguments[0].setSelectionRange === 'function') {
                    const len = (arguments[0].value || '').length;
                    arguments[0].setSelectionRange(len, len);
                }
                """,
                code_input,
            )
            self.safe_click(code_input)
            self.driver.execute_script(
                """
                arguments[0].focus();
                if (typeof arguments[0].setSelectionRange === 'function') {
                    const len = (arguments[0].value || '').length;
                    arguments[0].setSelectionRange(len, len);
                }
                """,
                code_input,
            )
        except WebDriverException:
            return

    def wait_for_login_success(self) -> None:
        self.set_step("wait_for_login_success")
        deadline = time.time() + 300
        submit_grace_deadline = 0.0
        login_clicked = False
        login_click_attempts = 0
        last_login_click_at = 0.0
        while time.time() < deadline:
            self.dismiss_noise()
            try:
                current_url = self.driver.current_url
                body_text = normalize_text(self.driver.find_element(By.TAG_NAME, "body").text)
                if "#/travelApplyList" in current_url or "申请单审批" in body_text or "待审批" in body_text:
                    return
                if "#/home" in current_url and "登录" not in body_text:
                    return
                code_input = self.find_visible(
                    (By.XPATH, "//input[@maxlength='6' or contains(@placeholder,'验证码')]"),
                    timeout=1,
                )
                code_value = ""
                if code_input:
                    try:
                        code_value = "".join(ch for ch in (code_input.get_attribute("value") or "") if ch.isdigit())
                    except StaleElementReferenceException:
                        code_value = ""
                if len(code_value) >= 6 and not login_clicked:
                    login_button = self.find_bottom_action_button("登录")
                    if login_button:
                        try:
                            self.safe_click(login_button)
                            login_clicked = True
                            login_click_attempts = 1
                            last_login_click_at = time.time()
                            submit_grace_deadline = time.time() + LOGIN_SUBMIT_GRACE_SECONDS
                            self.log("Detected 6-digit verification code and clicked login. Waiting for page transition.")
                        except Exception:
                            pass
                elif (
                    len(code_value) >= 6
                    and login_clicked
                    and login_click_attempts < LOGIN_RESUBMIT_MAX_ATTEMPTS
                    and time.time() - last_login_click_at >= LOGIN_RESUBMIT_INTERVAL_SECONDS
                    and ("#/login" in current_url or "获取验证码" in body_text or "登录" in body_text)
                ):
                    login_button = self.find_bottom_action_button("登录")
                    if login_button:
                        try:
                            self.safe_click(login_button)
                            login_click_attempts += 1
                            last_login_click_at = time.time()
                            submit_grace_deadline = time.time() + LOGIN_SUBMIT_GRACE_SECONDS
                            self.log("Still waiting on the login page after submitting the code; clicked login again.")
                        except Exception:
                            pass
                if submit_grace_deadline and time.time() < submit_grace_deadline:
                    time.sleep(0.5)
                    continue
            except WebDriverException:
                pass
            time.sleep(0.5)
        raise RuntimeError("Timed out waiting for manual login to complete.")

    def open_audit_page(self) -> None:
        self.set_step("open_audit_page")
        self.driver.get(AUDIT_URL)
        self.wait_for_page_ready(settle_seconds=0.2)
        self.dismiss_noise()
        if not self.audit_list_ready():
            self.switch_to_pending_approval_tab()
        self.log("Entered the ride-approval page.")

    def switch_to_pending_approval_tab(self) -> None:
        if not self.audit_list_ready():
            self.click_header_tab("申请单审批")
            time.sleep(0.2)
            self.dismiss_noise()
        if not self.pending_status_ready():
            for label in ("待审批", "审批中"):
                self.click_status_tab(label)
                time.sleep(0.2)
                self.dismiss_noise()
                if self.pending_status_ready():
                    break

    def audit_list_ready(self) -> bool:
        try:
            current_url = self.driver.current_url
            body_text = normalize_text(self.driver.find_element(By.TAG_NAME, "body").text)
        except WebDriverException:
            return False
        return (
            "#/travelApplyList" in current_url
            and "申请单审批" in body_text
            and ("待审批" in body_text or "审批中" in body_text)
        )

    def pending_status_ready(self) -> bool:
        try:
            body_text = normalize_text(self.driver.find_element(By.TAG_NAME, "body").text)
        except WebDriverException:
            return False
        return "待审批" in body_text or "审批中" in body_text or self.page_has_visible_approval_button() or bool(self.find_order_candidates())

    def watch_and_approve_forever(self) -> None:
        total_approved = 0
        while True:
            self.dismiss_noise()
            cycle_approved = self.approve_available_orders()
            total_approved += cycle_approved
            if cycle_approved > 0:
                self.log(f"Approved {cycle_approved} orders this round, {total_approved} total.")
            self.log("No pending orders right now. Waiting before refresh.")
            if self.wait_for_next_poll_window():
                continue
            self.refresh_audit_page()

    def session_alive(self) -> bool:
        try:
            _ = self.driver.current_url
            _ = self.driver.window_handles
            return True
        except WebDriverException:
            return False

    def login_screen_visible(self) -> bool:
        try:
            current_url = self.driver.current_url or ""
            body_text = normalize_text(self.driver.find_element(By.TAG_NAME, "body").text)
        except WebDriverException:
            return False
        if "#/login" in current_url:
            return True
        if "当前页面已超时" in body_text and "重新登录" in body_text:
            return True
        return "手机号" in body_text and "验证码" in body_text and ("获取验证码" in body_text or "登录" in body_text)

    def session_timeout_notice_visible(self) -> bool:
        try:
            body_text = normalize_text(self.driver.find_element(By.TAG_NAME, "body").text)
        except WebDriverException:
            return False
        return "当前页面已超时" in body_text and "重新登录" in body_text

    def recover_idle_session_if_needed(self) -> bool:
        if not self.session_alive():
            raise RuntimeError("Browser session is no longer alive during idle keepalive.")
        if self.session_timeout_notice_visible():
            self.log("Idle keepalive detected a session-timeout notice. Dismissing it and logging in again.")
            self.dismiss_noise()
            time.sleep(0.2)
            self.login()
            self.open_audit_page()
            return True
        if not self.login_screen_visible():
            return False
        self.log("Idle keepalive detected that the session dropped back to the login page. Logging in again.")
        self.login()
        self.open_audit_page()
        return True

    def perform_idle_keepalive(self) -> None:
        if not self.session_alive():
            raise RuntimeError("Browser session is no longer alive during idle keepalive.")
        try:
            self.driver.execute_script(
                """
                try {
                  window.scrollBy(0, 1);
                  window.scrollBy(0, -1);
                } catch (e) {}
                try {
                  fetch('/t100/', {
                    method: 'GET',
                    credentials: 'include',
                    cache: 'no-store',
                    headers: { 'X-Requested-With': 'XMLHttpRequest' }
                  }).catch(() => {});
                } catch (e) {}
                """
            )
        except WebDriverException:
            raise RuntimeError("Idle keepalive ping failed because the browser session became unavailable.")

    def wait_for_next_poll_window(self) -> bool:
        deadline = time.time() + POLL_INTERVAL_SECONDS
        last_keepalive_at = time.time()
        last_refresh_at = time.time()
        while time.time() < deadline:
            time.sleep(min(HEARTBEAT_CHECK_INTERVAL_SECONDS, max(deadline - time.time(), 0)))
            if self.recover_idle_session_if_needed():
                last_keepalive_at = time.time()
                last_refresh_at = time.time()
                continue
            if time.time() - last_keepalive_at >= IDLE_KEEPALIVE_INTERVAL_SECONDS:
                self.perform_idle_keepalive()
                last_keepalive_at = time.time()
            self.dismiss_noise()
            if self.page_has_visible_approval_button() or self.find_first_order_approval_button():
                self.log("Detected a pending order during idle wait; resuming approval immediately.")
                return True
            if self.find_order_candidates() and not self.has_no_pending_orders():
                self.log("Detected order cards during idle wait; resuming approval immediately.")
                return True
            if time.time() - last_refresh_at >= IDLE_REFRESH_INTERVAL_SECONDS:
                self.log("Idle keepalive refresh: reopening the ride-approval page.")
                self.refresh_audit_page()
                last_keepalive_at = time.time()
                last_refresh_at = time.time()
                if self.page_has_visible_approval_button() or self.find_first_order_approval_button():
                    self.log("Detected a pending order right after the idle keepalive refresh.")
                    return True
                if self.find_order_candidates() and not self.has_no_pending_orders():
                    self.log("Detected order cards right after the idle keepalive refresh.")
                    return True
        return False

    def refresh_audit_page(self) -> None:
        if self.recover_idle_session_if_needed():
            self.log("Recovered the session before refreshing the ride-approval page.")
            return
        refresh_url = f"{AUDIT_URL}&_ts={int(time.time() * 1000)}"
        try:
            self.driver.get(refresh_url)
            self.wait_for_page_ready(settle_seconds=0.2)
        except WebDriverException as exc:
            self.log(f"Idle keepalive reopen failed: {exc}")
            if self.recover_idle_session_if_needed():
                self.log("Recovered the session after the idle keepalive reopen failed.")
                return
            raise
        self.dismiss_noise()
        if self.login_screen_visible():
            self.log("Refresh landed on the login page. Logging in again before reopening the ride-approval page.")
            self.login()
            self.open_audit_page()
            return
        self.switch_to_pending_approval_tab()
        try:
            self.click_status_tab("已审批")
            time.sleep(0.2)
            self.dismiss_noise()
            self.click_status_tab("待审批")
            time.sleep(0.2)
            self.dismiss_noise()
        except Exception:
            pass
        try:
            visible_approvals = len(self.find_action_buttons(["审批"], exact=True))
        except Exception:
            visible_approvals = -1
        if visible_approvals >= 0:
            self.log(f"Refreshed the ride-approval page. Visible approval buttons: {visible_approvals}")
        else:
            self.log("Refreshed the ride-approval page.")

    def approve_available_orders(self) -> int:
        approved = 0
        while True:
            self.dismiss_noise()
            if self.has_no_pending_orders():
                return approved
            if not self.open_first_order():
                return approved
            self.dismiss_noise()
            self.click_agree()
            try:
                self.handle_submitter_selection_if_needed()
            except RuntimeError as exc:
                if "Manual cancel before submit." in str(exc):
                    self.log(
                        "Manual approval was canceled. Pausing for 30 seconds before returning to the list page."
                    )
                    self.pause_after_manual_cancel()
                    self.return_to_list_if_needed()
                    self.wait_for_page_ready(settle_seconds=0.2)
                    self.dismiss_noise()
                    return approved
            except RuntimeError as exc:
                if "Approver list is still loading and did not finish in time." in str(exc):
                    recovered = False
                    for attempt in range(1, SELECTION_REOPEN_MAX_ATTEMPTS + 1):
                        self.log(
                            f"Approver list stayed loading too long; returning to the list page and reopening the order "
                            f"(attempt {attempt}/{SELECTION_REOPEN_MAX_ATTEMPTS})."
                        )
                        if not self.retry_order_after_selection_timeout():
                            break
                        try:
                            self.handle_submitter_selection_if_needed()
                            recovered = True
                            break
                        except RuntimeError as retry_exc:
                            if "Approver list is still loading and did not finish in time." not in str(retry_exc):
                                raise
                    if not recovered:
                        raise
                else:
                    raise
            self.wait_for_submit_result()
            approved += 1
            self.return_to_list_if_needed()
            self.wait_for_page_ready(settle_seconds=0.2)
            self.dismiss_noise()
            time.sleep(1)

    def pause_after_manual_cancel(self) -> None:
        deadline = time.time() + 30
        while time.time() < deadline:
            if not self.session_alive():
                break
            time.sleep(1)

    def retry_order_after_selection_timeout(self) -> bool:
        self.return_to_list_if_needed()
        time.sleep(0.5)
        self.dismiss_noise()
        if self.has_no_pending_orders():
            return False
        if not self.open_first_order():
            return False
        self.dismiss_noise()
        self.click_agree()
        return True

    def has_no_pending_orders(self) -> bool:
        if self.page_has_visible_approval_button():
            return False
        if self.find_first_order_approval_button():
            return False
        if self.find_order_candidates():
            return False
        empty_xpaths = [
            "//*[contains(normalize-space(.), '没有匹配的申请单')]",
            "//*[contains(normalize-space(.), '暂无')]",
            "//*[contains(normalize-space(.), '无数据')]",
            "//*[contains(@class, 'empty')]",
        ]
        return any(self.find_visible((By.XPATH, xpath), timeout=1) for xpath in empty_xpaths)

    def find_order_candidates(self) -> list:
        selectors = [
            (By.CSS_SELECTOR, ".audit-list .item"),
            (By.CSS_SELECTOR, ".audit-item"),
            (By.CSS_SELECTOR, ".list-item"),
            (By.CSS_SELECTOR, ".application-item"),
            (By.CSS_SELECTOR, ".van-cell"),
            (By.XPATH, "//div[contains(@class,'item') or contains(@class,'cell') or contains(@class,'card')]"),
        ]
        for locator in selectors:
            elements = self.driver.find_elements(*locator)
            visible = [el for el in elements if self.is_clickable_candidate(el)]
            if visible:
                return visible
        return []

    def page_has_visible_approval_button(self) -> bool:
        try:
            return bool(
                self.driver.execute_script(
                    """
                    return Array.from(document.querySelectorAll('button,span,a,div'))
                      .some(el => {
                        const text = (el.innerText || '').trim();
                        const rect = el.getBoundingClientRect();
                        return text === '审批' && rect.width > 0 && rect.height > 0;
                      });
                    """
                )
            )
        except WebDriverException:
            return False

    def click_first_visible_approval_button(self) -> bool:
        try:
            return bool(
                self.driver.execute_script(
                    """
                    const isVisible = el => {
                      if (!el) return false;
                      const rect = el.getBoundingClientRect();
                      return rect.width > 0 && rect.height > 0;
                    };
                    const textOf = el => (el && (el.innerText || '').trim()) || '';
                    const rows = Array.from(document.querySelectorAll('div,li'))
                      .filter(el => {
                        if (!isVisible(el)) return false;
                        const text = textOf(el);
                        return /GDP\\d{8,}/.test(text) && text.includes('广州');
                      })
                      .sort((a, b) => {
                        const ra = a.getBoundingClientRect();
                        const rb = b.getBoundingClientRect();
                        return ra.top - rb.top || ra.left - rb.left;
                      });
                    for (const row of rows) {
                      const rowRect = row.getBoundingClientRect();
                      const button = Array.from(row.querySelectorAll('button,span,a,div'))
                        .filter(el => {
                          const text = textOf(el);
                          if (text !== '审批' || !isVisible(el)) return false;
                          const rect = el.getBoundingClientRect();
                          return rect.left >= rowRect.left + rowRect.width * 0.5;
                        })
                        .sort((a, b) => {
                          const ra = a.getBoundingClientRect();
                          const rb = b.getBoundingClientRect();
                          return rb.left - ra.left || ra.top - rb.top;
                        })[0];
                      if (button) {
                        button.click();
                        return true;
                      }
                      const x = Math.round(rowRect.right - 24);
                      const y = Math.round(rowRect.top + Math.min(rowRect.height / 2, 44));
                      const hit = document.elementFromPoint(x, y);
                      if (hit) {
                        const candidates = [hit, hit.closest('button'), hit.closest('a'), hit.closest('span'), hit.closest('div')].filter(Boolean);
                        for (const candidate of candidates) {
                          if (textOf(candidate) === '审批' && isVisible(candidate)) {
                            candidate.click();
                            return true;
                          }
                        }
                      }
                    }
                    const fallback = Array.from(document.querySelectorAll('button,span,a,div'))
                      .filter(el => {
                        const text = textOf(el);
                        const rect = el.getBoundingClientRect();
                        return text === '审批' && rect.width > 0 && rect.height > 0;
                      })
                      .sort((a, b) => {
                        const ra = a.getBoundingClientRect();
                        const rb = b.getBoundingClientRect();
                        return ra.top - rb.top || rb.left - ra.left;
                      })[0];
                    if (!fallback) return false;
                    fallback.click();
                    return true;
                    """
                )
            )
        except WebDriverException:
            return False

    def open_first_order(self) -> bool:
        for _ in range(3):
            if self.has_no_pending_orders():
                return False
            if self.click_first_visible_approval_button():
                self.ensure_browser_window_visible()
                if self.wait_for_order_opened():
                    return True
                time.sleep(0.25)
                if self.click_first_visible_approval_button() and self.wait_for_order_opened():
                    return True
                continue
            button = self.find_first_order_approval_button()
            if button:
                try:
                    self.ensure_browser_window_visible()
                    self.safe_click(button)
                    if self.wait_for_order_opened():
                        return True
                    time.sleep(0.25)
                    self.safe_click(button)
                    if self.wait_for_order_opened():
                        return True
                    continue
                except StaleElementReferenceException:
                    time.sleep(0.2)
                    continue
            time.sleep(0.2)
        return False

    def wait_for_order_opened(self) -> bool:
        deadline = time.time() + 6
        while time.time() < deadline:
            self.dismiss_noise()
            if self.selection_page_present() or self.find_bottom_action_button("同意") or self.find_bottom_action_button("提交"):
                return True
            try:
                current_url = self.driver.current_url
                body_text = normalize_text(self.driver.find_element(By.TAG_NAME, "body").text)
            except WebDriverException:
                current_url = ""
                body_text = ""
            if (
                "#/travelApplyList" not in current_url
                and "申请单审批" not in body_text
                and "待审批" not in body_text
                and not self.page_has_visible_approval_button()
            ):
                return True
            time.sleep(0.2)
        return False

    def click_agree(self) -> None:
        agree_button = self.find_bottom_action_button("同意")
        if not agree_button:
            if self.selection_page_present() or self.find_bottom_action_button("提交"):
                return
            raise RuntimeError("Clicked approval, but did not leave the list page or reach a detail action stage.")
        self.safe_click(agree_button)
        time.sleep(1)
        self.dismiss_noise()

    def handle_submitter_selection_if_needed(self) -> None:
        self.approver_selection_attempted = False
        self.last_validated_approver_name = ""
        self.last_validation_mode = ""
        self.last_clicked_approver_name = ""
        self.last_clicked_approver_text = ""
        self.wait_for_selection_stage_ready()
        if not self.selection_page_present():
            submit_button = self.find_bottom_action_button("提交")
            if submit_button:
                self.safe_click(submit_button)
            return
        if self.selection_loading_in_progress():
            raise RuntimeError("Approver list is still loading and did not finish in time.")
        selection_ok = self.select_approver_from_list(self.approver_name)
        visible_target = self.selection_page_contains_approver_name(self.approver_name)
        if (
            not selection_ok
            and not self.has_any_selected_approver()
            and not self.approver_selection_attempted
            and not visible_target
        ):
            raise RuntimeError(f"Approver '{self.approver_name}' was not found.")
        if not selection_ok and (self.approver_selection_attempted or visible_target):
            self.log(
                f"Could not automatically confirm the selected approver for '{self.approver_name}'. "
                "Falling back to manual confirmation."
            )
        time.sleep(0.4)
        self.confirm_selected_approver_before_submit(self.approver_name)
        submit_button = self.find_bottom_action_button("提交")
        if not submit_button:
            raise RuntimeError("The submit button was not found after choosing the approver.")
        self.safe_click(submit_button)

    def assess_selected_approver_audit(self, expected_name: str) -> dict[str, str]:
        binding_probe = self.probe_selected_approver_binding_value()
        binding_value = binding_probe["value"] if binding_probe else ""
        binding_source = binding_probe["source"] if binding_probe else ""
        actual_name = self.get_selected_approver_name()
        selected_text = normalize_text(self.get_selected_approver_text())
        target_row_selected = self.target_approver_row_looks_selected(expected_name)
        visible_target = self.selection_page_contains_approver_name(expected_name)
        validated_match = bool(
            self.last_validated_approver_name and text_matches(expected_name, self.last_validated_approver_name)
        )
        clicked_match = bool(
            getattr(self, "last_clicked_approver_name", "") and text_matches(expected_name, getattr(self, "last_clicked_approver_name", ""))
        )
        clicked_text_match = bool(
            getattr(self, "last_clicked_approver_text", "") and text_matches(expected_name, getattr(self, "last_clicked_approver_text", ""))
        )
        binding_match = bool(binding_value and text_matches(expected_name, binding_value))
        exact_text_match = bool(actual_name and text_matches(expected_name, actual_name))

        if binding_match:
            verdict = "通过"
            evidence = f"最终绑定值 '{binding_value}' 与目标一致。"
        elif binding_value:
            verdict = "未通过"
            evidence = f"最终绑定值是 '{binding_value}'，与目标 '{expected_name}' 不一致。"
        elif exact_text_match and target_row_selected:
            verdict = "通过"
            evidence = "页面识别到的选中姓名与目标一致，且目标行也处于选中状态。"
        elif exact_text_match and validated_match:
            verdict = "通过"
            evidence = "页面识别到的选中姓名与目标一致，且自动点击校验结果一致。"
        elif clicked_match and clicked_text_match:
            verdict = "待人工核对"
            if visible_target:
                evidence = "页面没有稳定回显选中态，但自动点击已命中目标审批人所在行，且页面仍可见该审批人。"
            else:
                evidence = "页面没有稳定回显选中态，但自动点击已命中目标审批人所在行。"
        elif exact_text_match:
            verdict = "待人工核对"
            evidence = "页面文本已匹配目标，但独立选中态证据还不够强。"
        elif target_row_selected or validated_match:
            verdict = "待人工核对"
            evidence = "自动点击或行内选中态有迹象，但页面文本没有形成独立闭环确认。"
        elif actual_name:
            verdict = "未通过"
            evidence = f"页面识别到当前选中审批人是 '{actual_name}'，与目标 '{expected_name}' 不一致。"
        else:
            verdict = "无法自动确认"
            evidence = "页面没有读取到足够明确的选中信息。"

        selection_state = "目标行右侧选择圈已选中" if target_row_selected else "未检测到目标行右侧选择圈"
        return {
            "verdict": verdict,
            "binding_value": binding_value,
            "binding_source": binding_source,
            "actual_name": actual_name,
            "selected_text": selected_text,
            "clicked_name": getattr(self, "last_clicked_approver_name", "") or "",
            "clicked_text": getattr(self, "last_clicked_approver_text", "") or "",
            "visible_target": "目标审批人仍可见" if visible_target else "未再看到目标审批人",
            "selection_state": selection_state,
            "evidence": evidence,
            "validation_mode": self.last_validation_mode or "",
        }

    def probe_selected_approver_binding_value(self) -> dict[str, str] | None:
        try:
            result = self.driver.execute_script(
                """
                const normalize = value => (value || '').replace(/\\s+/g, ' ').trim();
                const sectionMarker = Array.from(document.querySelectorAll('div,span,p,strong,h1,h2,h3'))
                  .find(el => normalize(el.innerText) === '下一审批人');
                if (!sectionMarker) return null;

                const flowMarker = Array.from(document.querySelectorAll('div,span,p,strong,h1,h2,h3'))
                  .find(el => normalize(el.innerText).includes('流程跟踪'));

                const sectionTop = sectionMarker.getBoundingClientRect().top - 8;
                const sectionBottom = flowMarker
                  ? flowMarker.getBoundingClientRect().top - 8
                  : window.innerHeight + 2000;

                const isInSection = el => {
                  const rect = el.getBoundingClientRect();
                  return rect.width > 0
                    && rect.height > 0
                    && rect.bottom >= sectionTop
                    && rect.top <= sectionBottom;
                };

                const selectedTokens = [
                  'checked',
                  'selected',
                  'is-checked',
                  'active',
                  'van-radio__icon--checked',
                  'van-checkbox__icon--checked',
                ];

                const looksSelected = el => {
                  if (!el || !isInSection(el)) return false;
                  const classes = String(el.className || '').toLowerCase();
                  const ariaChecked = String(el.getAttribute?.('aria-checked') || '').toLowerCase();
                  const checkedAttr = String(el.getAttribute?.('checked') || '').toLowerCase();
                  const role = String(el.getAttribute?.('role') || '').toLowerCase();
                  const type = String(el.getAttribute?.('type') || '').toLowerCase();
                  if (ariaChecked === 'true' || checkedAttr === 'true' || checkedAttr === 'checked') return true;
                  if (selectedTokens.some(token => classes.includes(token))) return true;
                  if ((role === 'radio' || role === 'checkbox' || type === 'radio' || type === 'checkbox') && el.checked) return true;
                  return false;
                };

                const pickValue = el => normalize(
                  el.value
                  || el.getAttribute?.('value')
                  || el.getAttribute?.('aria-label')
                  || el.getAttribute?.('data-value')
                  || el.getAttribute?.('title')
                  || el.innerText
                  || el.textContent
                );

                const candidates = Array.from(document.querySelectorAll('input,select,textarea,div,span,label,li,section'))
                  .filter(el => isInSection(el))
                  .sort((a, b) => {
                    const ra = a.getBoundingClientRect();
                    const rb = b.getBoundingClientRect();
                    return ra.top - rb.top || ra.left - rb.left;
                  });

                for (const el of candidates) {
                  const tag = String(el.tagName || '').toLowerCase();
                  const type = String(el.getAttribute?.('type') || '').toLowerCase();
                  const role = String(el.getAttribute?.('role') || '').toLowerCase();
                  const classes = String(el.className || '').toLowerCase();
                  const name = String(el.getAttribute?.('name') || '').toLowerCase();
                  const id = String(el.getAttribute?.('id') || '').toLowerCase();
                  const explicitControl = tag === 'input' || tag === 'select' || tag === 'textarea' || role === 'radio' || role === 'checkbox';
                  const hiddenControl = tag === 'input' && type === 'hidden';
                  const hasSelectionMark = looksSelected(el) || selectedTokens.some(token => classes.includes(token));
                  const hasBindingHint = /approver|submitter|next approver|next-approver|下一审批人|审批人/.test(`${name} ${id} ${classes}`);
                  if (!explicitControl && !hiddenControl && !hasSelectionMark && !hasBindingHint) continue;
                  const value = pickValue(el);
                  if (value) {
                    return {
                      value,
                      source: hiddenControl ? 'hidden-input' : (explicitControl ? tag : 'dom-node'),
                    };
                  }
                }

                return null;
                """
            )
        except WebDriverException:
            result = None
        if not isinstance(result, dict):
            flow_tracking_name = self.get_flow_tracking_active_approver_name()
            if flow_tracking_name:
                return {"value": flow_tracking_name, "source": "flow-tracking-active"}
            return None
        value = normalize_text(str(result.get("value") or ""))
        if not value:
            flow_tracking_name = self.get_flow_tracking_active_approver_name()
            if flow_tracking_name:
                return {"value": flow_tracking_name, "source": "flow-tracking-active"}
            return None
        source = normalize_text(str(result.get("source") or ""))
        return {"value": value, "source": source}

    def get_flow_tracking_active_approver_name(self) -> str | None:
        try:
            result = self.driver.execute_script(
                """
                const normalize = value => (value || '').replace(/\\s+/g, ' ').trim();
                const activeTitle = document.querySelector('.van-step__title--active');
                if (!activeTitle) return null;
                const approver = activeTitle.querySelector('.approverName');
                const value = normalize(approver?.innerText || approver?.textContent);
                return value || null;
                """
            )
        except WebDriverException:
            return None
        value = normalize_text(str(result or ""))
        return value or None

    def confirm_selected_approver_before_submit(self, expected_name: str) -> None:
        audit = self.assess_selected_approver_audit(expected_name)
        validation_status = f"自动核验：{audit['verdict']}"
        recommendation = {
            "通过": "建议：自动核验已通过，仍请确认右侧选择圈和目标姓名一致后再提交。",
            "待人工核对": "建议：请先核对右侧选择圈是否已选中目标审批人。",
            "未通过": "建议：请勿提交，先修正审批人。",
            "无法自动确认": "建议：请先人工核对右侧选择圈和页面状态。",
        }.get(audit["verdict"], "建议：请先人工核对右侧选择圈。")
        evidence_lines = [
            f"目标：{expected_name}",
            f"右侧选择圈：{audit['selection_state']}",
            f"识别：{audit['actual_name'] or '未识别'}",
            f"绑定：{audit['binding_value'] or '未识别'}（{audit['binding_source'] or '未记录'}）",
            f"点击：{audit['clicked_name'] or '未记录'} / {audit['clicked_text'] or '未记录'}",
            f"可见：{audit['visible_target']}",
        ]
        if audit["validation_mode"]:
            evidence_lines.append(f"自动点击依据：{audit['validation_mode']}")
        evidence_lines.append(f"说明：{audit['evidence']}")
        prompt = "\n".join([validation_status, recommendation, "", *evidence_lines, "", "确认右侧选择圈和姓名无误后点“确定”，否则点“取消”。"])
        self.log(f"Manual approval confirmation required. {validation_status}. {audit['evidence']}")
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        try:
            confirmed = messagebox.askokcancel(
                "确认提交",
                prompt,
                parent=root,
            )
        finally:
            root.destroy()
        if not confirmed:
            raise RuntimeError("Manual cancel before submit.")

    def get_selected_approver_name(self) -> str:
        selected_text = self.get_selected_approver_text()
        if not selected_text:
            flow_tracking_name = self.get_flow_tracking_active_approver_name()
            if flow_tracking_name:
                return flow_tracking_name
            return ""
        lines = [normalize_text(line) for line in selected_text.splitlines() if normalize_text(line)]
        return lines[0] if lines else normalize_text(selected_text)

    def has_any_selected_approver(self) -> bool:
        return bool(self.get_selected_approver_text())

    def wait_for_selection_stage_ready(self, timeout_seconds: float = 5.0) -> None:
        deadline = time.time() + timeout_seconds
        last_nudge_at = 0.0
        while time.time() < deadline:
            self.dismiss_noise()
            if not self.selection_page_present():
                if self.find_bottom_action_button("提交"):
                    return
                time.sleep(0.2)
                continue
            if self.selection_loading_in_progress():
                now = time.time()
                if now - last_nudge_at >= 3.0:
                    self.nudge_selection_loading()
                    last_nudge_at = now
                time.sleep(0.25)
                continue
            if self.find_approver_rows():
                return
            time.sleep(0.2)

    def nudge_selection_loading(self) -> None:
        try:
            self.driver.execute_script(
                """
                const marker = Array.from(document.querySelectorAll('div,section,li,span,p,strong'))
                  .find(el => (el.innerText || '').includes('下一审批人'));
                if (!marker) return;
                marker.scrollIntoView({block:'center', inline:'nearest'});
                const candidates = Array.from(document.querySelectorAll('div,ul,section'))
                  .filter(el => {
                    const rect = el.getBoundingClientRect();
                    const style = window.getComputedStyle(el);
                    return rect.width > 0 && rect.height > 0
                      && rect.top >= marker.getBoundingClientRect().top - 20
                      && rect.top <= marker.getBoundingClientRect().bottom + 260
                      && el.scrollHeight > el.clientHeight + 10
                      && (style.overflowY === 'auto' || style.overflowY === 'scroll');
                  })
                  .sort((a, b) => b.clientHeight - a.clientHeight);
                if (candidates.length) {
                  const list = candidates[0];
                  list.scrollTop = Math.max(0, list.scrollTop - 8);
                  list.scrollTop = Math.min(list.scrollHeight, list.scrollTop + 16);
                } else {
                  window.scrollBy(0, 8);
                  window.scrollBy(0, -8);
                }
                """
            )
        except WebDriverException:
            return

    def selection_loading_in_progress(self) -> bool:
        try:
            return bool(
                self.driver.execute_script(
                    """
                    const nextApproverSection = Array.from(document.querySelectorAll('div,section,li'))
                      .find(el => (el.innerText || '').includes('下一审批人'));
                    if (!nextApproverSection) return false;
                    const sectionRect = nextApproverSection.getBoundingClientRect();
                    const nodes = Array.from(document.querySelectorAll('div,section,li,span,p'));
                    const inSection = el => {
                      const rect = el.getBoundingClientRect();
                      return rect.width > 0 && rect.height > 0
                        && rect.top >= sectionRect.top - 8
                        && rect.top <= sectionRect.bottom + 320;
                    };
                    const spinner = nodes.find(el => {
                      const cls = el.className || '';
                      return inSection(el) && /van-loading|el-loading-mask|loading|toast--loading|spinner/i.test(String(cls));
                    });
                    const sectionText = nodes
                      .filter(inSection)
                      .map(el => (el.innerText || '').trim())
                      .join(' ');
                    const hasApproverName = /[\u4e00-\u9fa5]{2,}/.test(sectionText.replace('下一审批人', ''));
                    return Boolean(spinner) || !hasApproverName;
                    """
                )
            )
        except WebDriverException:
            return False

    def wait_for_submit_result(self) -> None:
        success_texts = ["成功", "提交成功", "审批成功", "操作成功"]
        deadline = time.time() + 20
        while time.time() < deadline:
            self.dismiss_noise()
            try:
                body_text = self.driver.find_element(By.TAG_NAME, "body").text
            except WebDriverException:
                body_text = ""
            if any(text in body_text for text in success_texts):
                return
            if self.is_back_on_list():
                return
            time.sleep(0.5)

    def return_to_list_if_needed(self) -> None:
        if self.is_back_on_list():
            return
        back_buttons = self.find_action_buttons(["返回", "关闭"])
        if back_buttons:
            self.safe_click(back_buttons[0])
            time.sleep(1)
            return
        self.driver.back()
        time.sleep(1)

    def is_back_on_list(self) -> bool:
        try:
            if "#/travelApplyList" in self.driver.current_url and self.find_order_candidates():
                return True
        except WebDriverException:
            return False
        list_markers = [
            (By.XPATH, "//*[contains(normalize-space(.), '申请单审批')]"),
            (By.XPATH, "//*[contains(normalize-space(.), '审批中')]"),
        ]
        return any(self.find_visible(locator, timeout=1) for locator in list_markers)

    def dismiss_noise(self) -> None:
        try:
            handled = self.driver.execute_script(
                """
                const labels = ['知道了', '我知道了', '关闭', '取消', '确定'];
                const modalRoots = Array.from(document.querySelectorAll(
                  '.van-dialog, .van-popup, .van-overlay, .el-dialog, .el-message-box, [role="dialog"], .modal, .dialog'
                )).filter(el => {
                  const rect = el.getBoundingClientRect();
                  return rect.width > 0 && rect.height > 0;
                });
                if (!modalRoots.length) return false;
                const nodes = modalRoots.flatMap(root => Array.from(root.querySelectorAll('button,span,a,div')));
                const target = nodes.find(el => {
                  const text = (el.innerText || '').trim();
                  const rect = el.getBoundingClientRect();
                  return labels.includes(text) && rect.width > 0 && rect.height > 0;
                });
                if (!target) return false;
                target.click();
                return true;
                """
            )
            if handled:
                time.sleep(0.1)
                return
        except WebDriverException:
            return
        try:
            handled_enterprise_notice = self.driver.execute_script(
                """
                const notice = Array.from(document.querySelectorAll('div,span,p'))
                  .find(el => (el.innerText || '').includes('您需在本企业系统中提交出差申请'));
                if (!notice) return false;
                const dialog = notice.closest('.van-dialog, .van-popup, [role="dialog"], .modal, .dialog') || document.body;
                const button = Array.from(dialog.querySelectorAll('button,span,a,div'))
                  .find(el => {
                    const text = (el.innerText || '').trim();
                    const rect = el.getBoundingClientRect();
                    return text === '知道了' && rect.width > 0 && rect.height > 0;
                  });
                if (!button) return false;
                button.click();
                return true;
                """
            )
            if handled_enterprise_notice:
                time.sleep(0.1)
                return
        except WebDriverException:
            return
        try:
            handled_network_notice = self.driver.execute_script(
                """
                const notice = Array.from(document.querySelectorAll('div,span,p'))
                  .find(el => {
                    const text = (el.innerText || '').trim();
                    return text.includes('网络不稳定');
                  });
                if (!notice) return false;
                const dialog = notice.closest('.van-dialog, .van-popup, [role="dialog"], .modal, .dialog') || document.body;
                const button = Array.from(dialog.querySelectorAll('button,span,a,div'))
                  .find(el => {
                    const text = (el.innerText || '').trim();
                    const rect = el.getBoundingClientRect();
                    return (text === '知道了' || text === '我知道了' || text === '确定')
                      && rect.width > 0
                      && rect.height > 0;
                  });
                if (!button) return false;
                button.click();
                return true;
                """
            )
            if handled_network_notice:
                time.sleep(0.1)
                return
        except WebDriverException:
            return

    def click_header_tab(self, label: str) -> None:
        self.click_top_tab_precisely(label)

    def click_status_tab(self, label: str) -> None:
        self.click_top_tab_precisely(label)

    def click_top_tab_precisely(self, label: str) -> None:
        try:
            clicked = bool(
                self.driver.execute_script(
                    """
                    const expected = arguments[0].trim();
                    const normalize = value => (value || '').replace(/\\s+/g, ' ').trim();
                    const viewportTopLimit = Math.max(window.innerHeight * 0.45, 220);
                    const candidates = Array.from(document.querySelectorAll('button,span,a,div'))
                      .filter(el => {
                        const rect = el.getBoundingClientRect();
                        const text = normalize(el.innerText);
                        return text === expected
                          && rect.width > 0
                          && rect.height > 0
                          && rect.top >= 0
                          && rect.bottom <= viewportTopLimit;
                      })
                      .sort((a, b) => {
                        const ra = a.getBoundingClientRect();
                        const rb = b.getBoundingClientRect();
                        return ra.top - rb.top || ra.left - rb.left;
                      });
                    if (!candidates.length) return false;
                    candidates[0].click();
                    return true;
                    """,
                    label,
                )
            )
            if clicked:
                return
        except WebDriverException:
            pass

        buttons = self.find_action_buttons([label], exact=True)
        top_buttons = [
            button
            for button in buttons
            if self.is_clickable_candidate(button) and button.rect.get("y", 99999) <= max(WINDOW_HEIGHT * 0.45, 220)
        ]
        if top_buttons:
            self.safe_click(top_buttons[0])

    def find_first_order_approval_button(self):
        row_selectors = [
            (By.CSS_SELECTOR, ".audit-list .item"),
            (By.CSS_SELECTOR, ".audit-item"),
            (By.CSS_SELECTOR, ".list-item"),
            (By.CSS_SELECTOR, ".application-item"),
            (By.CSS_SELECTOR, ".van-cell"),
            (By.XPATH, "//div[contains(@class,'item') or contains(@class,'cell') or contains(@class,'card')]"),
        ]
        for locator in row_selectors:
            for row in self.driver.find_elements(*locator):
                try:
                    if not self.is_clickable_candidate(row):
                        continue
                    button = self.find_labeled_child(row, "审批")
                    if button:
                        return button
                except StaleElementReferenceException:
                    continue
        return None

    def find_bottom_action_button(self, label: str):
        buttons = self.find_action_buttons([label])
        candidates = [button for button in buttons if self.is_clickable_candidate(button)]
        if not candidates:
            return None
        return max(candidates, key=lambda el: (el.rect.get("y", 0), el.rect.get("x", 0)))

    def find_action_buttons(self, labels: list[str], exact: bool = True) -> list:
        matches = []
        for label in labels:
            if exact:
                xpath = (
                    f"//*[self::button or self::span or self::a or self::div]"
                    f"[normalize-space(text())='{label}' or .//span[normalize-space(text())='{label}']]"
                )
            else:
                xpath = (
                    f"//*[self::button or self::span or self::a or self::div]"
                    f"[contains(normalize-space(.), '{label}')]"
                )
            for element in self.driver.find_elements(By.XPATH, xpath):
                if self.is_clickable_candidate(element):
                    matches.append(element)
        return matches

    def selection_page_present(self) -> bool:
        markers = [
            (By.XPATH, "//*[normalize-space(text())='下一审批人']"),
            (By.XPATH, "//*[normalize-space(text())='审批人']"),
            (By.XPATH, "//*[contains(normalize-space(.), '选择提交人')]"),
        ]
        return any(self.find_visible(locator, timeout=1) for locator in markers)

    def selection_page_contains_approver_name(self, name: str) -> bool:
        for row in self.find_approver_rows():
            if self.row_matches_approver(row, name):
                return True
        return False

    def approver_section_bounds(self) -> tuple[float | None, float | None]:
        try:
            top = self.driver.execute_script(
                """
                const marker = Array.from(document.querySelectorAll('div,span,p,strong,h1,h2,h3'))
                  .find(el => (el.innerText || '').trim() === '下一审批人');
                if (!marker) return null;
                return marker.getBoundingClientRect().top;
                """
            )
            bottom = self.driver.execute_script(
                """
                const marker = Array.from(document.querySelectorAll('div,span,p,strong,h1,h2,h3'))
                  .find(el => (el.innerText || '').includes('流程跟踪'));
                if (!marker) return null;
                return marker.getBoundingClientRect().top;
                """
            )
            top_value = float(top) if top is not None else None
            bottom_value = float(bottom) if bottom is not None else None
            return top_value, bottom_value
        except WebDriverException:
            return None, None

    def find_approver_rows(self) -> list:
        selectors = [
            (By.XPATH, "//*[contains(@class,'cell') or contains(@class,'item') or contains(@class,'row')]"),
            (By.XPATH, "//label[.//input or .//i or .//span]/.."),
            (By.XPATH, "//li | //label | //div[contains(@role,'radio') or contains(@role,'checkbox')]"),
        ]
        section_top, section_bottom = self.approver_section_bounds()
        rows = []
        seen_ids: set[str] = set()
        for locator in selectors:
            for row in self.driver.find_elements(*locator):
                if not self.is_clickable_candidate(row):
                    continue
                try:
                    rect = row.rect
                    if not isinstance(rect, dict):
                        continue
                    row_top = rect.get("y", 0)
                    row_bottom = row_top + rect.get("height", 0)
                except (StaleElementReferenceException, AttributeError, TypeError):
                    continue
                if section_top is not None and row_bottom <= section_top:
                    continue
                if section_bottom is not None and row_top >= section_bottom:
                    continue
                row_text = normalize_text(getattr(row, "text", ""))
                if not row_text:
                    continue
                key = getattr(row, "id", None) or f"{row_text}:{row.rect}"
                if key in seen_ids:
                    continue
                seen_ids.add(key)
                rows.append(row)
        return rows

    def row_matches_approver(self, row, name: str) -> bool:
        try:
            if text_matches(name, row.text):
                return True
            labels = row.find_elements(By.XPATH, ".//*")
        except StaleElementReferenceException:
            return False
        for label in labels:
            try:
                if text_matches(name, label.text):
                    return True
            except StaleElementReferenceException:
                return False
        return False

    def find_approver_click_target(self, row, name: str):
        candidates = []
        try:
            descendants = row.find_elements(By.XPATH, ".//*")
        except StaleElementReferenceException:
            return None
        row_rect = {}
        try:
            row_rect = row.rect or {}
        except (StaleElementReferenceException, AttributeError, TypeError):
            row_rect = {}
        row_left = row_rect.get("x", 0)
        row_right = row_left + row_rect.get("width", 0)
        for element in descendants:
            if not self.is_clickable_candidate(element):
                continue
            text = normalize_text(getattr(element, "text", ""))
            if text and text_matches(name, text):
                continue
            try:
                rect = element.rect or {}
                input_type = (element.get_attribute("type") or "").lower()
                classes = (element.get_attribute("class") or "").lower()
                role = (element.get_attribute("role") or "").lower()
            except StaleElementReferenceException:
                return None
            is_right_side = rect.get("x", 0) >= row_left + max((row_right - row_left) * 0.45, 24)
            is_iconish = rect.get("width", 0) <= 48 and rect.get("height", 0) <= 48 and not text and is_right_side
            if input_type in {"radio", "checkbox"}:
                candidates.append(element)
                continue
            if any(token in classes for token in ["radio", "checkbox", "check", "icon", "select", "choose"]):
                candidates.append(element)
                continue
            if role in {"radio", "checkbox"}:
                candidates.append(element)
                continue
            if is_iconish:
                candidates.append(element)
        if candidates:
            return max(candidates, key=lambda el: el.rect.get("x", 0))
        return None

    def select_approver_from_list(self, name: str) -> bool:
        if self.try_click_approver_checkbox(name):
            return True
        if self.approver_selection_attempted or self.selection_page_contains_approver_name(name):
            return False

        for _ in range(18):
            if not self.selection_page_present():
                return False
            self.scroll_approver_list()
            time.sleep(0.25)
            self.dismiss_noise()
            if self.try_click_approver_checkbox(name):
                return True
            if self.approver_selection_attempted or self.selection_page_contains_approver_name(name):
                return False

        return False

    def try_click_approver_checkbox(self, name: str) -> bool:
        if self.click_approver_radio_by_row_position(name):
            self.last_clicked_approver_name = name
            self.approver_selection_attempted = True
            if self.wait_for_expected_approver_selected(name):
                self.log(f"Clicked the right-side selector for approver '{name}' and confirmed the actual selection.")
                return True
            selected = self.get_selected_approver_text()
            self.log(f"Selection validation failed after clicking '{name}'. Current selected row: {selected or 'unknown'}")

        for row in self.find_approver_rows():
            if not self.row_matches_approver(row, name):
                continue
            target = self.find_approver_click_target(row, name)
            if not target:
                continue
            self.last_clicked_approver_name = name
            self.last_clicked_approver_text = normalize_text(getattr(row, "text", ""))
            self.safe_click(target)
            self.approver_selection_attempted = True
            if self.wait_for_expected_approver_selected(name):
                return True
            selected = self.get_selected_approver_text()
            self.log(f"Selection validation failed after clicking '{name}'. Current selected row: {selected or 'unknown'}")
        return False

    def select_approver_from_list_precisely(self, name: str) -> bool:
        if self.click_approver_radio_by_row_position(name):
            return self.wait_for_expected_approver_selected(name)
        return False

    def click_approver_radio_by_row_position(self, name: str) -> bool:
        label_selectors = [
            (By.XPATH, f"//*[normalize-space(text())='{name}']"),
            (By.XPATH, f"//span[normalize-space(text())='{name}']"),
            (By.XPATH, f"//div[normalize-space(text())='{name}']"),
        ]

        seen_ids: set[str] = set()
        for locator in label_selectors:
            for label in self.driver.find_elements(*locator):
                if not self.is_clickable_candidate(label):
                    continue
                label_id = getattr(label, "id", None)
                if label_id and label_id in seen_ids:
                    continue
                if label_id:
                    seen_ids.add(label_id)
                if self.click_right_side_of_label_row(label):
                    self.last_clicked_approver_name = name
                    self.last_clicked_approver_text = normalize_text(getattr(label, "text", ""))
                    if self.label_row_indicator_selected(label):
                        self.last_validated_approver_name = name
                        self.last_validation_mode = "目标姓名同行勾选框状态"
                    return True
        return False

    def click_right_side_of_label_row(self, label) -> bool:
        try:
            clicked = self.driver.execute_script(
                """
                const label = arguments[0];
                const row = label.closest('.approver-list') || label.closest('label') || label.closest('li') || label.parentElement || label;
                row.scrollIntoView({block:'center', inline:'nearest'});
                const rect = row.getBoundingClientRect();
                const y = Math.round(rect.top + rect.height / 2);
                const x = Math.max(Math.round(rect.right - 16), Math.round(rect.left + 1));
                const candidates = Array.from(row.querySelectorAll('*'))
                  .filter(el => {
                    const box = el.getBoundingClientRect();
                    if (!box.width || !box.height) return false;
                    if (box.right < rect.left + (rect.width * 0.45)) return false;
                    const text = String(el.innerText || el.textContent || '').replace(/\\s+/g, ' ').trim();
                    const classes = String(el.className || '').toLowerCase();
                    const role = String(el.getAttribute?.('role') || '').toLowerCase();
                    const type = String(el.getAttribute?.('type') || '').toLowerCase();
                    const cursor = String(window.getComputedStyle(el).cursor || '').toLowerCase();
                    return (
                      type === 'radio'
                      || type === 'checkbox'
                      || role === 'radio'
                      || role === 'checkbox'
                      || classes.includes('radio')
                      || classes.includes('checkbox')
                      || classes.includes('check')
                      || classes.includes('select')
                      || classes.includes('choose')
                      || classes.includes('icon')
                      || cursor === 'pointer'
                      || (box.width <= 48 && box.height <= 48 && !text)
                    );
                  })
                  .sort((a, b) => {
                    const ra = a.getBoundingClientRect();
                    const rb = b.getBoundingClientRect();
                    return rb.right - ra.right || ra.width * ra.height - rb.width * rb.height;
                  });
                for (const candidate of candidates) {
                    try {
                        candidate.click();
                        return true;
                    } catch (e) {}
                }
                let el = document.elementFromPoint(x, y);
                if (!el) return false;
                const fallback = [el, el.closest('label'), el.closest('[role="radio"]'), el.closest('[role="checkbox"]'), el.closest('div'), el.closest('span')].filter(Boolean);
                for (const candidate of fallback) {
                    try {
                        candidate.click();
                        return true;
                    } catch (e) {}
                }
                return false;
                """,
                label,
            )
        except WebDriverException:
            return False
        return bool(clicked)

    def wait_for_expected_approver_selected(self, name: str, timeout_seconds: float = 2.0) -> bool:
        deadline = time.time() + timeout_seconds
        while time.time() < deadline:
            if self.target_approver_row_looks_selected(name):
                self.last_validated_approver_name = name
                self.last_validation_mode = "目标姓名同行勾选框状态"
                return True
            selected_text = self.get_selected_approver_text()
            if selected_text and name in selected_text:
                self.last_validated_approver_name = name
                self.last_validation_mode = "页面已选文本"
                return True
            time.sleep(0.15)
        return False

    def target_approver_row_looks_selected(self, name: str) -> bool:
        label_selectors = [
            (By.XPATH, f"//*[normalize-space(text())='{name}']"),
            (By.XPATH, f"//span[normalize-space(text())='{name}']"),
            (By.XPATH, f"//div[normalize-space(text())='{name}']"),
        ]
        seen_ids: set[str] = set()
        for locator in label_selectors:
            for label in self.driver.find_elements(*locator):
                if not self.is_clickable_candidate(label):
                    continue
                label_id = getattr(label, "id", None)
                if label_id and label_id in seen_ids:
                    continue
                if label_id:
                    seen_ids.add(label_id)
                row = self.get_approver_row_container(label)
                if row and self.row_is_selected(row):
                    return True
                if self.label_row_indicator_selected(label):
                    return True
        return False

    def get_approver_row_container(self, label):
        try:
            return self.driver.execute_script(
                """
                const label = arguments[0];
                return label.closest('.approver-list') || label.closest('label') || label.closest('li') || label.parentElement || label;
                """,
                label,
            )
        except WebDriverException:
            return None

    def label_row_indicator_selected(self, label) -> bool:
        try:
            result = self.driver.execute_script(
                """
                const label = arguments[0];
                const selectedTokens = [
                  'checked',
                  'selected',
                  'is-checked',
                  'active',
                  'van-radio__icon--checked',
                  'van-checkbox__icon--checked',
                ];
                const looksSelected = el => {
                  if (!el) return false;
                  const classes = String(el.className || '').toLowerCase();
                  const ariaChecked = String(el.getAttribute?.('aria-checked') || '').toLowerCase();
                  const checkedAttr = String(el.getAttribute?.('checked') || '').toLowerCase();
                  const role = String(el.getAttribute?.('role') || '').toLowerCase();
                  const type = String(el.getAttribute?.('type') || '').toLowerCase();
                  if (ariaChecked === 'true' || checkedAttr === 'true' || checkedAttr === 'checked') return true;
                  if (selectedTokens.some(token => classes.includes(token))) return true;
                  if ((role === 'radio' || role === 'checkbox' || type === 'radio' || type === 'checkbox') && el.checked) return true;
                  const style = window.getComputedStyle(el);
                  const borderColor = `${style.borderTopColor} ${style.borderRightColor} ${style.borderBottomColor} ${style.borderLeftColor}`.toLowerCase();
                  const backgroundColor = String(style.backgroundColor || '').toLowerCase();
                  const color = String(style.color || '').toLowerCase();
                  const hasBlueTone = [borderColor, backgroundColor, color].some(value =>
                    value.includes('24, 144, 255')
                    || value.includes('30, 136, 229')
                    || value.includes('64, 158, 255')
                    || value.includes('#1989fa')
                    || value.includes('#409eff')
                    || value.includes('rgb(25, 137, 250)')
                  );
                  if (!hasBlueTone) return false;
                  const rect = el.getBoundingClientRect();
                  return rect.width <= 48 && rect.height <= 48;
                };

                const row = label.closest('.approver-list') || label.closest('label') || label.closest('li') || label.parentElement || label;
                row.scrollIntoView({block:'center', inline:'nearest'});
                const rect = row.getBoundingClientRect();
                const y = Math.round(rect.top + rect.height / 2);
                const x = Math.max(Math.round(rect.right - 16), Math.round(rect.left + 1));
                let hit = document.elementFromPoint(x, y);
                if (!hit) return false;
                const candidates = [
                  hit,
                  hit.closest('label'),
                  hit.closest('[role="radio"]'),
                  hit.closest('[role="checkbox"]'),
                  ...Array.from((hit.closest('label,div,li,section') || hit).querySelectorAll?.('*') || []),
                ].filter(Boolean);
                return candidates.some(looksSelected);
                """,
                label,
            )
        except WebDriverException:
            return False
        return bool(result)

    def scroll_approver_list(self) -> None:
        try:
            self.driver.execute_script(
                """
                const candidates = Array.from(document.querySelectorAll('div, ul'))
                  .filter(el => {
                    const style = window.getComputedStyle(el);
                    const overflowY = style.overflowY;
                    return el.scrollHeight > el.clientHeight + 20 &&
                      (overflowY === 'auto' || overflowY === 'scroll');
                  })
                  .sort((a, b) => b.clientHeight - a.clientHeight);
                if (candidates.length) {
                  const list = candidates[0];
                  const step = 32;
                  list.scrollTop = Math.min(list.scrollTop + step, list.scrollHeight);
                } else {
                  window.scrollBy(0, 32);
                }
                """
            )
        except WebDriverException:
            pass

    def get_selected_approver_text(self) -> str | None:
        dom_selected_text = self.get_selected_approver_text_from_dom()
        if dom_selected_text:
            return dom_selected_text
        for row in self.find_approver_rows():
            if not self.row_is_selected(row):
                continue
            text = normalize_text(getattr(row, "text", ""))
            if text:
                return text
        return None

    def get_selected_approver_text_from_dom(self) -> str | None:
        try:
            selected_text = self.driver.execute_script(
                """
                const normalize = value => (value || '').replace(/\\s+/g, ' ').trim();
                const sectionMarker = Array.from(document.querySelectorAll('div,span,p,strong,h1,h2,h3'))
                  .find(el => normalize(el.innerText) === '下一审批人');
                if (!sectionMarker) return null;

                const flowMarker = Array.from(document.querySelectorAll('div,span,p,strong,h1,h2,h3'))
                  .find(el => normalize(el.innerText).includes('流程跟踪'));

                const sectionTop = sectionMarker.getBoundingClientRect().top - 8;
                const sectionBottom = flowMarker
                  ? flowMarker.getBoundingClientRect().top - 8
                  : window.innerHeight + 2000;

                const isInSection = el => {
                  const rect = el.getBoundingClientRect();
                  return rect.width > 0
                    && rect.height > 0
                    && rect.bottom >= sectionTop
                    && rect.top <= sectionBottom;
                };

                const allNodes = Array.from(document.querySelectorAll('div,li,label,section,span,p,i,input'));
                const selectedTokens = [
                  'checked',
                  'selected',
                  'is-checked',
                  'active',
                  'van-radio__icon--checked',
                  'van-checkbox__icon--checked',
                ];

                const looksSelected = el => {
                  if (!el || !isInSection(el)) return false;
                  const classes = String(el.className || '').toLowerCase();
                  const ariaChecked = String(el.getAttribute?.('aria-checked') || '').toLowerCase();
                  const checkedAttr = String(el.getAttribute?.('checked') || '').toLowerCase();
                  const role = String(el.getAttribute?.('role') || '').toLowerCase();
                  const type = String(el.getAttribute?.('type') || '').toLowerCase();
                  if (ariaChecked === 'true' || checkedAttr === 'true' || checkedAttr === 'checked') return true;
                  if (selectedTokens.some(token => classes.includes(token))) return true;
                  if ((role === 'radio' || role === 'checkbox' || type === 'radio' || type === 'checkbox') && el.checked) return true;
                  const style = window.getComputedStyle(el);
                  const borderColor = `${style.borderTopColor} ${style.borderRightColor} ${style.borderBottomColor} ${style.borderLeftColor}`.toLowerCase();
                  const backgroundColor = String(style.backgroundColor || '').toLowerCase();
                  const color = String(style.color || '').toLowerCase();
                  const hasBlueTone = [borderColor, backgroundColor, color].some(value =>
                    value.includes('24, 144, 255')
                    || value.includes('30, 136, 229')
                    || value.includes('64, 158, 255')
                    || value.includes('#1989fa')
                    || value.includes('#409eff')
                    || value.includes('rgb(25, 137, 250)')
                  );
                  if (!hasBlueTone) return false;
                  const rect = el.getBoundingClientRect();
                  return rect.width <= 48 && rect.height <= 48;
                };

                const candidateRows = Array.from(document.querySelectorAll('div,li,label,section'))
                  .filter(el => {
                    if (!isInSection(el)) return false;
                    const text = normalize(el.innerText);
                    if (!text || text === '下一审批人') return false;
                    return /[\\u4e00-\\u9fa5]{2,}/.test(text);
                  })
                  .sort((a, b) => {
                    const ra = a.getBoundingClientRect();
                    const rb = b.getBoundingClientRect();
                    return ra.top - rb.top || ra.left - rb.left;
                  });

                for (const row of candidateRows) {
                  const rowRect = row.getBoundingClientRect();
                  const rowText = normalize(row.innerText);
                  if (!rowText) continue;
                  const rowNodes = [row, ...Array.from(row.querySelectorAll('*'))];
                  const rowSelected = rowNodes.some(node => {
                    if (!looksSelected(node)) return false;
                    const rect = node.getBoundingClientRect();
                    return rect.left >= rowRect.left - 12 && rect.right <= window.innerWidth + 12;
                  });
                  if (!rowSelected) continue;
                  return rowText;
                }

                const selectedNode = allNodes.find(looksSelected);
                if (!selectedNode) return null;
                const row = selectedNode.closest('label,li,section,div');
                return row ? normalize(row.innerText) : null;
                """
            )
        except WebDriverException:
            return None
        normalized = normalize_text(str(selected_text or ""))
        return normalized or None

    def row_is_selected(self, row) -> bool:
        try:
            if self.element_looks_selected(row):
                return True
            for element in row.find_elements(By.XPATH, ".//*"):
                if self.element_looks_selected(element):
                    return True
        except StaleElementReferenceException:
            return False
        return False

    def element_looks_selected(self, element) -> bool:
        try:
            classes = (element.get_attribute("class") or "").lower()
            aria_checked = (element.get_attribute("aria-checked") or "").lower()
            checked_attr = (element.get_attribute("checked") or "").lower()
            input_type = (element.get_attribute("type") or "").lower()
        except StaleElementReferenceException:
            return False

        if aria_checked == "true" or checked_attr in {"true", "checked"}:
            return True

        selected_tokens = [
            "checked",
            "selected",
            "is-checked",
            "active",
            "van-radio__icon--checked",
            "van-checkbox__icon--checked",
        ]
        if any(token in classes for token in selected_tokens):
            return True

        if input_type in {"radio", "checkbox"}:
            try:
                return bool(element.is_selected())
            except Exception:
                return False

        return False

    def find_labeled_child(self, container, label: str):
        selectors = [
            (
                By.XPATH,
                f".//*[self::button or self::span or self::a or self::div][normalize-space(text())='{label}' or .//span[normalize-space(text())='{label}']]",
            ),
            (By.XPATH, f".//*[normalize-space(text())='{label}']"),
        ]
        for locator in selectors:
            try:
                elements = container.find_elements(*locator)
            except StaleElementReferenceException:
                return None
            for element in elements:
                try:
                    if self.is_clickable_candidate(element):
                        return element
                except StaleElementReferenceException:
                    continue
        return None

    def find_visible(self, locator: tuple[str, str], timeout: int = 5):
        try:
            wait = WebDriverWait(self.driver, timeout)
            return wait.until(lambda d: self._visible_element(locator))
        except TimeoutException:
            return None

    def _visible_element(self, locator: tuple[str, str]):
        for element in self.driver.find_elements(*locator):
            if self.is_clickable_candidate(element):
                return element
        return None

    def safe_click(self, element) -> None:
        try:
            self.driver.execute_script(
                "arguments[0].scrollIntoView({block:'center', inline:'center'});",
                element,
            )
            time.sleep(0.1)
            element.click()
            return
        except (ElementClickInterceptedException, StaleElementReferenceException, WebDriverException):
            pass
        self.driver.execute_script("arguments[0].click();", element)

    def is_clickable_candidate(self, element) -> bool:
        try:
            if not element.is_displayed():
                return False
            rect = element.rect
            return rect.get("width", 0) > 0 and rect.get("height", 0) > 0
        except StaleElementReferenceException:
            return False

    def wait_for_page_ready(self, settle_seconds: float = 1.0) -> None:
        self.wait.until(lambda d: d.execute_script("return document.readyState") in {"interactive", "complete"})
        time.sleep(settle_seconds)


def main() -> None:
    acquire_single_instance_lock()
    try:
        bot = DevtoolsApproveBot()
        bot.run()
    except Exception:
        append_log(traceback.format_exc())
        raise
    finally:
        release_single_instance_lock()


if __name__ == "__main__":
    main()
