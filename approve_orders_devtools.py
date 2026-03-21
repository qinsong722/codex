from __future__ import annotations

import atexit
import os
import socket
import subprocess
import sys
import time
import tkinter as tk
from pathlib import Path
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
LOGIN_PAGE_READY_TIMEOUT_SECONDS = 60
SEND_CODE_READY_TIMEOUT_SECONDS = 25
SEND_CODE_CONFIRM_TIMEOUT_SECONDS = 6

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

    def set_step(self, step: str) -> None:
        self.log(f"Step: {step}")

    def launch_browser_process(self) -> None:
        self.set_step("launch_browser")
        args = [str(self.browser_binary), *build_browser_launch_args(self.profile_dir, self.debugging_port), LOGIN_URL]
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        self.browser_process = subprocess.Popen(args, creationflags=creationflags)
        wait_for_port("127.0.0.1", self.debugging_port)

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
        except Exception:
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
        image_selectors = [
            (By.CSS_SELECTOR, ".private-in img"),
            (By.XPATH, "//div[contains(@class,'private-in')]//img"),
        ]
        image = None
        for locator in image_selectors:
            image = self.find_visible(locator, timeout=2)
            if image:
                break
        if not image:
            raise RuntimeError("Could not find the login agreement checkbox image.")

        before_src = image.get_attribute("src") or ""
        self.safe_click(image)
        time.sleep(0.2)

        current_url = self.driver.current_url
        if "#/privatePolicy" in current_url:
            raise RuntimeError("Agreement click opened the privacy-policy page instead of toggling the checkbox.")

        try:
            refreshed = self.find_visible((By.CSS_SELECTOR, ".private-in img"), timeout=1)
        except Exception:
            refreshed = None
        after_src = (refreshed or image).get_attribute("src") or ""

        if before_src == after_src and "#/login" not in self.driver.current_url:
            raise RuntimeError("Agreement checkbox did not stay on the login page after clicking.")

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
            (By.XPATH, "//*[self::button or self::span or self::a or self::div][contains(normalize-space(.), '获取验证码')]"),
        ]
        for locator in selectors:
            element = self.find_visible(locator, timeout=1)
            if element:
                return element
        return None

    def login_page_send_code_ready(self) -> bool:
        try:
            return bool(
                self.driver.execute_script(
                    """
                    const tel = Array.from(document.querySelectorAll('input')).find(
                      el => (el.type || '').toLowerCase() === 'tel' && el.offsetParent !== null
                    );
                    const agreement = document.querySelector('.private-in img, .private-in');
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
            self.safe_click(button)
            sent_at = time.time()
            confirm_deadline = sent_at + SEND_CODE_CONFIRM_TIMEOUT_SECONDS
            while time.time() < confirm_deadline:
                if self.login_code_send_confirmed():
                    return sent_at
                time.sleep(0.3)
            if attempt < attempts:
                self.driver.refresh()
                self.wait_for_login_page_ready()
                self.prepare_login_page(send_code=False)
        raise RuntimeError("Failed to confirm that the SMS code was sent.")

    def focus_code_input(self) -> None:
        code_input = self.find_visible(
            (By.XPATH, "//input[@maxlength='6' or contains(@placeholder,'???')]") ,
            timeout=3,
        )
        if not code_input:
            return
        try:
            self.driver.execute_script(
                """
                arguments[0].scrollIntoView({block:'center', inline:'nearest'});
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
        while time.time() < deadline:
            self.dismiss_noise()
            try:
                current_url = self.driver.current_url
                body_text = normalize_text(self.driver.find_element(By.TAG_NAME, "body").text)
                if "#/travelApplyList" in current_url or "申请单审批" in body_text or "待审批" in body_text:
                    return
                if "#/home" in current_url and "登录" not in body_text:
                    return
            except WebDriverException:
                pass
            time.sleep(0.5)
        raise RuntimeError("Timed out waiting for manual login to complete.")

    def open_audit_page(self) -> None:
        self.set_step("open_audit_page")
        self.driver.get(AUDIT_URL)
        self.wait_for_page_ready(settle_seconds=0.2)
        self.dismiss_noise()
        self.switch_to_pending_approval_tab()
        self.log("Entered the ride-approval page.")

    def switch_to_pending_approval_tab(self) -> None:
        self.click_header_tab("申请单审批")
        time.sleep(0.2)
        self.dismiss_noise()
        self.click_status_tab("审批中")
        time.sleep(0.2)
        self.dismiss_noise()

    def watch_and_approve_forever(self) -> None:
        total_approved = 0
        while True:
            self.dismiss_noise()
            cycle_approved = self.approve_available_orders()
            total_approved += cycle_approved
            if cycle_approved > 0:
                self.log(f"Approved {cycle_approved} orders this round, {total_approved} total.")
            self.log("No pending orders right now. Waiting before refresh.")
            time.sleep(POLL_INTERVAL_SECONDS)
            self.refresh_audit_page()

    def refresh_audit_page(self) -> None:
        self.driver.get(AUDIT_URL)
        self.wait_for_page_ready(settle_seconds=0.2)
        self.dismiss_noise()
        self.switch_to_pending_approval_tab()

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
            self.handle_submitter_selection_if_needed()
            self.wait_for_submit_result()
            approved += 1
            self.return_to_list_if_needed()
            self.wait_for_page_ready(settle_seconds=0.2)
            self.dismiss_noise()
            time.sleep(1)

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
                    const candidates = Array.from(document.querySelectorAll('button,span,a,div'))
                      .filter(el => {
                        const text = (el.innerText || '').trim();
                        const rect = el.getBoundingClientRect();
                        return text === '审批' && rect.width > 0 && rect.height > 0;
                      })
                      .sort((a, b) => {
                        const ra = a.getBoundingClientRect();
                        const rb = b.getBoundingClientRect();
                        return ra.top - rb.top || ra.left - rb.left;
                      });
                    if (!candidates.length) return false;
                    candidates[0].click();
                    return true;
                    """
                )
            )
        except WebDriverException:
            return False

    def open_first_order(self) -> bool:
        if self.click_first_visible_approval_button():
            return self.wait_for_order_opened()
        button = self.find_first_order_approval_button()
        if button:
            self.safe_click(button)
            return self.wait_for_order_opened()
        candidates = self.find_order_candidates()
        if not candidates:
            return False
        self.safe_click(candidates[0])
        return self.wait_for_order_opened()

    def wait_for_order_opened(self) -> bool:
        deadline = time.time() + 6
        while time.time() < deadline:
            self.dismiss_noise()
            if self.selection_page_present() or self.find_bottom_action_button("同意"):
                return True
            if not self.is_back_on_list():
                return True
            time.sleep(0.2)
        return False

    def click_agree(self) -> None:
        agree_button = self.find_bottom_action_button("同意")
        if not agree_button:
            if self.selection_page_present() or self.find_bottom_action_button("提交"):
                return
            raise RuntimeError("Could not find the 'Agree' button on the detail page.")
        self.safe_click(agree_button)
        time.sleep(1)
        self.dismiss_noise()

    def handle_submitter_selection_if_needed(self) -> None:
        self.wait_for_selection_stage_ready()
        if not self.selection_page_present():
            submit_button = self.find_bottom_action_button("提交")
            if submit_button:
                self.safe_click(submit_button)
            return
        if not self.select_approver_from_list(self.approver_name):
            raise RuntimeError(f"Approver '{self.approver_name}' was not found.")
        time.sleep(0.4)
        submit_button = self.find_bottom_action_button("提交")
        if not submit_button:
            raise RuntimeError("The submit button was not found after choosing the approver.")
        self.safe_click(submit_button)

    def wait_for_selection_stage_ready(self, timeout_seconds: float = 12.0) -> None:
        deadline = time.time() + timeout_seconds
        while time.time() < deadline:
            self.dismiss_noise()
            if not self.selection_page_present():
                if self.find_bottom_action_button("提交"):
                    return
                time.sleep(0.2)
                continue
            if self.find_approver_rows():
                return
            time.sleep(0.2)

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
                const labels = ['知道了', '我知道了', '关闭', '取消'];
                const nodes = Array.from(document.querySelectorAll('button,span,a,div'));
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
        except WebDriverException:
            return

    def click_header_tab(self, label: str) -> None:
        buttons = self.find_action_buttons([label], exact=False)
        if buttons:
            self.safe_click(buttons[0])

    def click_status_tab(self, label: str) -> None:
        buttons = self.find_action_buttons([label], exact=False)
        if buttons:
            self.safe_click(buttons[0])

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
                if not self.is_clickable_candidate(row):
                    continue
                button = self.find_labeled_child(row, "审批")
                if button:
                    return button
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

    def find_approver_rows(self) -> list:
        selectors = [
            (By.XPATH, "//*[contains(@class,'cell') or contains(@class,'item') or contains(@class,'row')]"),
            (By.XPATH, "//label[.//input or .//i or .//span]/.."),
            (By.XPATH, "//li | //label | //div[contains(@role,'radio') or contains(@role,'checkbox')]"),
        ]
        rows = []
        seen_ids: set[str] = set()
        for locator in selectors:
            for row in self.driver.find_elements(*locator):
                if not self.is_clickable_candidate(row):
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
        for element in descendants:
            if not self.is_clickable_candidate(element):
                continue
            text = normalize_text(getattr(element, "text", ""))
            if text and text_matches(name, text):
                continue
            try:
                input_type = (element.get_attribute("type") or "").lower()
                classes = (element.get_attribute("class") or "").lower()
                role = (element.get_attribute("role") or "").lower()
            except StaleElementReferenceException:
                return None
            if input_type in {"radio", "checkbox"}:
                candidates.append(element)
                continue
            if any(token in classes for token in ["radio", "checkbox", "check", "icon", "select", "choose"]):
                candidates.append(element)
                continue
            if role in {"radio", "checkbox"}:
                candidates.append(element)
        if candidates:
            return max(candidates, key=lambda el: el.rect.get("x", 0))
        return None

    def select_approver_from_list(self, name: str) -> bool:
        for row in self.find_approver_rows():
            if not self.row_matches_approver(row, name):
                continue
            target = self.find_approver_click_target(row, name) or row
            self.safe_click(target)
            return True
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
            for element in container.find_elements(*locator):
                if self.is_clickable_candidate(element):
                    return element
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
    finally:
        release_single_instance_lock()


if __name__ == "__main__":
    main()
