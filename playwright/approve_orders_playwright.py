from __future__ import annotations

import ctypes
import json
import os
import shutil
import sys
import time
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, simpledialog

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright


SITE_URL = "https://b2bjoy.10086.cn/t100/#/home/index"
LOGIN_URL = "https://b2bjoy.10086.cn/t100/#/login"
AUDIT_URL = "https://b2bjoy.10086.cn/t100/#/travelApplyList?type=1&fromType=car"
CONFIG_FILE_NAME = "phone_number.txt"
CHROME_BINARY_CANDIDATES = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
]
PLAYWRIGHT_PROFILE_DIR_NAME = "playwright-chrome-profile"
WINDOW_WIDTH = 404
WINDOW_HEIGHT = 876
WINDOW_POS_X = 80
WINDOW_POS_Y = 0
POLL_INTERVAL_SECONDS = 300
KEEPALIVE_INTERVAL_SECONDS = 60


def get_app_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


APP_DIR = get_app_dir()
CONFIG_FILE = APP_DIR / CONFIG_FILE_NAME
LOG_FILE = APP_DIR / "approve_orders.log"
PLAYWRIGHT_PROFILE_DIR = APP_DIR / PLAYWRIGHT_PROFILE_DIR_NAME
PLAYWRIGHT_DEBUG_DIR = APP_DIR / "playwright-debug"
LOCK_FILE = APP_DIR / ".approve_playwright.lock"


def append_log(message: str) -> None:
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    with LOG_FILE.open("a", encoding="utf-8") as fh:
        fh.write(f"[{timestamp}] [PW] {message}\n")


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
            raise RuntimeError(f"已有 Playwright 实例在运行，PID={existing_pid}。请先关闭旧实例后再重试。")
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


def hide_console_window() -> None:
    try:
        kernel32 = ctypes.windll.kernel32
        user32 = ctypes.windll.user32
        hwnd = kernel32.GetConsoleWindow()
        if hwnd:
            user32.ShowWindow(hwnd, 0)
    except Exception:
        pass


def get_text_prompt(title: str, prompt: str, validator) -> str:
    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    try:
        while True:
            value = simpledialog.askstring(title, prompt, parent=root)
            if value is None:
                raise RuntimeError("用户取消了配置录入。")
            normalized = validator(value)
            if normalized is not None:
                return normalized
            messagebox.showerror("输入无效", "请按提示重新输入。", parent=root)
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
            "输入手机号",
            f"未找到或未正确配置 {CONFIG_FILE_NAME} 中的手机号，请输入登录手机号：",
            validate_phone,
        )
    if approver_name is None:
        approver_name = get_text_prompt(
            "输入审批人",
            f"未找到或未正确配置 {CONFIG_FILE_NAME} 中的审批人，请输入审批人姓名：",
            validate_approver,
        )
    write_config(phone_number, approver_name)
    return phone_number, approver_name


def get_chrome_binary() -> Path:
    for candidate in CHROME_BINARY_CANDIDATES:
        path = Path(candidate)
        if path.exists():
            return path
    joined = ", ".join(CHROME_BINARY_CANDIDATES)
    raise FileNotFoundError(f"未找到可用的 Chrome 浏览器: {joined}")


def normalize_text(value: str | None) -> str:
    return " ".join((value or "").split())


class PlaywrightApproveBot:
    def __init__(self) -> None:
        self.phone_number, self.approver_name = load_runtime_config()
        self.chrome_binary = get_chrome_binary()
        self.profile_dir = self.prepare_profile_dir()
        self.debug_dir = self.prepare_debug_dir()
        self.playwright = None
        self.browser_context = None
        self.page = None
        self.current_step = "init"
        self.last_keepalive_at = 0.0
        self.last_refresh_at = 0.0
        self.last_submitted_code = ""
        self.last_submit_at = 0.0

    def prepare_profile_dir(self) -> Path:
        if PLAYWRIGHT_PROFILE_DIR.exists():
            shutil.rmtree(PLAYWRIGHT_PROFILE_DIR, ignore_errors=True)
        PLAYWRIGHT_PROFILE_DIR.mkdir(parents=True, exist_ok=True)
        return PLAYWRIGHT_PROFILE_DIR

    def prepare_debug_dir(self) -> Path:
        PLAYWRIGHT_DEBUG_DIR.mkdir(parents=True, exist_ok=True)
        return PLAYWRIGHT_DEBUG_DIR

    def log(self, message: str) -> None:
        print(message, flush=True)
        append_log(message)

    def set_step(self, step: str) -> None:
        self.current_step = step
        self.log(f"步骤: {step}")

    def pause_for_manual_inspection(self, reason: str) -> None:
        self.log(f"发生异常，浏览器将保留在当前页面，等待人工查看。原因：{reason}")
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        try:
            messagebox.showerror(
                "脚本已暂停",
                f"Playwright 原型运行出现异常，浏览器已保留现场。\n\n原因：{reason}\n\n检查完成后点击“确定”。",
                parent=root,
            )
        finally:
            root.destroy()

    def launch(self) -> None:
        self.set_step("launch_browser")
        self.playwright = sync_playwright().start()
        self.browser_context = self.playwright.chromium.launch_persistent_context(
            user_data_dir=str(self.profile_dir),
            channel="chrome",
            executable_path=str(self.chrome_binary),
            headless=False,
            no_viewport=True,
            args=[
                f"--window-size={WINDOW_WIDTH},{WINDOW_HEIGHT}",
                f"--window-position={WINDOW_POS_X},{WINDOW_POS_Y}",
                "--disable-default-apps",
                "--disable-sync",
                "--no-first-run",
            ],
        )
        if self.browser_context.pages:
            self.page = self.browser_context.pages[0]
        else:
            self.page = self.browser_context.new_page()
        self.page.set_default_timeout(20_000)
        self.browser_context.tracing.start(screenshots=True, snapshots=True, sources=True)

    def close(self) -> None:
        try:
            if self.browser_context is not None:
                trace_path = self.debug_dir / "last-trace.zip"
                try:
                    self.browser_context.tracing.stop(path=str(trace_path))
                except Exception:
                    pass
            if self.browser_context is not None:
                self.browser_context.close()
        finally:
            if self.playwright is not None:
                self.playwright.stop()

    def run(self) -> None:
        self.launch()
        try:
            self.set_step("login")
            self.login()
            self.open_audit_page()
            self.last_keepalive_at = time.time()
            self.last_refresh_at = time.time()
            self.monitor_pending_orders()
        except Exception as exc:
            self.capture_debug_artifacts(exc)
            self.pause_for_manual_inspection(str(exc))
            raise

    def capture_debug_artifacts(self, exc: Exception) -> None:
        timestamp = time.strftime("%Y%m%d-%H%M%S")
        prefix = self.debug_dir / f"{timestamp}-{self.current_step}"
        metadata = {
            "step": self.current_step,
            "reason": str(exc),
            "url": "",
            "title": "",
            "body_text": "",
            "visible_texts": [],
        }

        if self.page is None:
            (prefix.with_suffix(".json")).write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
            return

        try:
            metadata["url"] = self.page.url
        except Exception:
            pass
        try:
            metadata["title"] = self.page.title()
        except Exception:
            pass
        try:
            metadata["body_text"] = self.page_text()[:4000]
        except Exception:
            pass
        try:
            metadata["visible_texts"] = self.page.evaluate(
                """
                () => Array.from(document.querySelectorAll('button, a, span, div'))
                  .map(el => {
                    const text = (el.innerText || '').trim();
                    const rect = el.getBoundingClientRect();
                    return { text, x: rect.x, y: rect.y, w: rect.width, h: rect.height };
                  })
                  .filter(item => item.text && item.w > 0 && item.h > 0)
                  .slice(0, 80)
                """
            )
        except Exception:
            pass

        try:
            self.page.screenshot(path=str(prefix.with_suffix(".png")), full_page=True)
        except Exception:
            pass
        try:
            if self.browser_context is not None:
                self.browser_context.tracing.stop(path=str(prefix.with_suffix(".zip")))
                self.browser_context.tracing.start(screenshots=True, snapshots=True, sources=True)
        except Exception:
            pass
        try:
            prefix.with_suffix(".html").write_text(self.page.content(), encoding="utf-8")
        except Exception:
            pass
        try:
            prefix.with_suffix(".json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass

    def page_text(self) -> str:
        return normalize_text(self.page.locator("body").inner_text())

    def open_login_page(self) -> str:
        self.set_step("open_login_page")
        last_error: Exception | None = None
        for target in (LOGIN_URL, SITE_URL, AUDIT_URL):
            try:
                self.page.goto(target, wait_until="commit", timeout=20_000)
                state = self.wait_for_login_page_ready()
                if state:
                    return state
                current_url = self.page.url
                if current_url.startswith("https://b2bjoy.10086.cn/t100/#/"):
                    return "login"
            except Exception as exc:
                last_error = exc
        if last_error is not None:
            raise last_error
        raise RuntimeError("未能打开登录页面。")

    def wait_for_login_page_ready(self) -> str | None:
        deadline = time.time() + 60
        last_soft_wait_log_at = 0.0
        while time.time() < deadline:
            try:
                current_url = self.page.url
                body_text = self.page_text()
                body_html = self.page.locator("body").inner_html(timeout=1_000)
                if "#/login" in current_url:
                    return "login"
                if "#/travelApplyList" in current_url and ("申请单审批" in body_text or "待审批" in body_text):
                    return "authenticated"
                phone_input = self.page.locator("input[type='tel']").first
                if phone_input.count() > 0 and phone_input.is_visible():
                    return "login"
                if "获取验证码" in body_text or "登录" in body_text:
                    return "login"
                if any(marker in body_html for marker in ("请输入11位手机号码", "请输入验证码", "获取验证码", "登录")):
                    return "login"
                # 这个站点首屏经常先只渲染应用壳子，body 一段时间内会接近空白。
                # 这里先耐心等，不要过早 reload 把它自己的启动过程打断。
                if not body_text.strip():
                    now = time.time()
                    if now - last_soft_wait_log_at >= 8:
                        self.log("登录页首屏仍在渲染，继续等待。")
                        last_soft_wait_log_at = now
                    if self.login_page_needs_hard_reload(body_text=body_text):
                        self.log("登录页处于空白/错误态，执行一次重载。")
                        self.page.reload(wait_until="commit", timeout=20_000)
                        time.sleep(0.8)
            except PlaywrightError:
                pass
            time.sleep(0.5)
        return None

    def wait_for_login_dom_ready(self) -> None:
        deadline = time.time() + 60
        last_wait_log_at = 0.0
        while time.time() < deadline:
            try:
                phone_input = self.page.locator("input[type='tel'], input[placeholder*='手机']").first
                if phone_input.count() > 0 and phone_input.is_visible():
                    return
                body_html = self.page.locator("body").inner_html(timeout=1_000)
                if "获取验证码" in body_html or "验证码" in body_html or "登录" in body_html:
                    return
            except PlaywrightError:
                pass
            now = time.time()
            if now - last_wait_log_at >= 10:
                self.log("登录页 DOM 仍在渲染，继续等待。")
                last_wait_log_at = now
            time.sleep(0.5)
        raise RuntimeError("登录页已打开，但输入控件长时间未渲染完成。")

    def login(self) -> None:
        self.open_login_page()
        self.wait_for_login_dom_ready()
        self.set_step("prepare_login_page")
        self.prepare_login_page()
        self.log("验证码已发送，请直接在当前输入框内输入验证码。")
        self.set_step("wait_for_login_success")
        self.wait_for_login_success()
        self.log("登录成功。")

    def prepare_login_page(self) -> None:
        self.refill_login_form()
        self.wait_for_login_form_ready()
        self.send_code_with_retry()
        self.focus_code_input()

    def refill_login_form(self) -> None:
        phone_input = self.page.locator("input[type='tel']").first
        phone_input.wait_for(state="visible")
        phone_input.click()
        phone_input.fill(self.phone_number)
        self.ensure_agreement_checked()

    def wait_for_login_form_ready(self) -> None:
        deadline = time.time() + 25
        spinner_seen = False
        while time.time() < deadline:
            if not self.login_page_looks_stuck():
                return
            try:
                spinner_seen = spinner_seen or self.page.locator(
                    ".van-loading:visible, .el-loading-mask:visible, .loading:visible"
                ).count() > 0
            except PlaywrightError:
                pass
            time.sleep(0.3)

        if not self.login_page_needs_hard_reload():
            if spinner_seen:
                self.log("登录页仍在转圈，继续等待，不再提前点击获取验证码。")
            else:
                self.log("登录页加载较慢，继续等待，不再频繁刷新。")
            return

        self.log("检测到登录页进入空白/错误态，执行一次硬刷新。")
        self.page.reload(wait_until="commit", timeout=20_000)
        time.sleep(0.5)
        self.refill_login_form()

    def login_spinner_visible(self) -> bool:
        try:
            return self.page.locator(".van-loading:visible, .el-loading-mask:visible, .loading:visible").count() > 0
        except PlaywrightError:
            return False

    def wait_for_spinner_to_clear(self, timeout_seconds: float = 20.0) -> bool:
        deadline = time.time() + timeout_seconds
        while time.time() < deadline:
            if not self.login_spinner_visible():
                return True
            time.sleep(0.3)
        return False

    def soft_reload_login_page(self) -> None:
        self.log("登录页长时间转圈，执行一次受控重载后重试。")
        self.page.reload(wait_until="commit", timeout=20_000)
        time.sleep(0.8)
        self.wait_for_login_dom_ready()
        self.refill_login_form()
        self.wait_for_login_form_ready()

    def ensure_agreement_checked(self) -> None:
        selectors = [
            ".private-in img",
            "xpath=//div[contains(@class,'private-in')]//img",
            "xpath=//div[contains(@class,'private-in')]",
        ]
        for selector in selectors:
            locator = self.page.locator(selector).first
            if locator.count() == 0:
                continue
            try:
                locator.click(timeout=1_500)
                time.sleep(0.2)
                return
            except PlaywrightError:
                continue
        raise RuntimeError("未找到登录协议勾选区域。")

    def click_get_code(self) -> None:
        candidates = [
            "xpath=//a[contains(@class,'get-code')][last()]",
            "text=获取验证码",
        ]
        for selector in candidates:
            locator = self.page.locator(selector).first
            if locator.count() == 0:
                continue
            try:
                locator.click(timeout=2_000)
                return
            except PlaywrightError:
                continue
        raise RuntimeError("未找到“获取验证码”按钮。")

    def send_code_with_retry(self) -> None:
        for attempt in range(2):
            if not self.wait_for_spinner_to_clear(timeout_seconds=20):
                if attempt < 1:
                    self.soft_reload_login_page()
                    continue
                raise RuntimeError("登录页长时间转圈，未进入可发送验证码状态。")
            self.click_get_code()
            if self.wait_for_code_sent_ready():
                return
            if attempt < 1 and self.login_page_needs_hard_reload():
                self.log("获取验证码后页面进入错误态，自动重载登录页后重试。")
                self.page.reload(wait_until="commit", timeout=20_000)
                time.sleep(0.5)
                phone_input = self.page.locator("input[type='tel']").first
                phone_input.wait_for(state="visible")
                phone_input.click()
                phone_input.fill(self.phone_number)
                self.ensure_agreement_checked()
        raise RuntimeError("已尝试获取验证码，但页面始终未进入可输入状态。")

    def wait_for_code_sent_ready(self) -> bool:
        deadline = time.time() + 12
        while time.time() < deadline:
            try:
                body_text = self.page_text()
                get_code_texts = self.page.locator("a.get-code, text=获取验证码").all_inner_texts()
                normalized = [normalize_text(text) for text in get_code_texts if text.strip()]
                if any(any(ch.isdigit() for ch in text) for text in normalized):
                    return True
                if "验证码已发送" in body_text:
                    return True
                if any(text and text != "获取验证码" for text in normalized):
                    return True
                if self.login_spinner_visible():
                    time.sleep(0.3)
                    continue
            except PlaywrightError:
                pass
            time.sleep(0.3)
        return False

    def focus_code_input(self) -> None:
        locator = self.page.locator("input[maxlength='6'], input[placeholder*='验证码']").first
        if locator.count() == 0:
            return
        try:
            self.page.bring_to_front()
        except PlaywrightError:
            pass
        try:
            locator.scroll_into_view_if_needed(timeout=2_000)
        except PlaywrightError:
            pass
        try:
            locator.evaluate(
                """node => {
                    node.focus();
                    if (typeof node.setSelectionRange === 'function') {
                        const len = node.value ? node.value.length : 0;
                        node.setSelectionRange(len, len);
                    }
                }"""
            )
        except PlaywrightError:
            pass
        try:
            box = locator.bounding_box()
            if box:
                self.page.mouse.click(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
        except PlaywrightError:
            pass
        try:
            locator.click(timeout=2_000)
        except PlaywrightError:
            pass
        try:
            focused = locator.evaluate("node => document.activeElement === node")
            if not focused:
                locator.press("Tab", timeout=500)
        except PlaywrightError:
            pass

    def ensure_code_input_focused(self) -> None:
        locator = self.page.locator("input[maxlength='6'], input[placeholder*='验证码']").first
        if locator.count() == 0:
            return
        try:
            focused = locator.evaluate("node => document.activeElement === node")
        except PlaywrightError:
            focused = False
        if not focused:
            self.focus_code_input()

    def wait_for_login_success(self) -> None:
        deadline = time.time() + 300
        last_refresh_at = time.time()
        while time.time() < deadline:
            try:
                code_ready = self.get_entered_code()
                if len(code_ready) < 6:
                    self.ensure_code_input_focused()
                submitted = self.try_submit_login_when_code_ready(code_ready)
                current_url = self.page.url
                body_text = self.page_text()
                if "#/login" not in current_url:
                    return
                if "首页" in body_text or "查看申请单" in body_text or "申请单审批" in body_text:
                    return
                if submitted:
                    self.log("检测到验证码已输满，已点击登录，等待页面跳转。")
                if time.time() - last_refresh_at >= 90 and self.login_page_needs_hard_reload():
                    self.log("登录页进入错误态，正在自动重载重试。")
                    self.page.reload(wait_until="commit", timeout=20_000)
                    self.last_submitted_code = ""
                    self.last_submit_at = 0.0
                    self.prepare_login_page()
                    last_refresh_at = time.time()
            except PlaywrightError:
                pass
            time.sleep(0.2 if self.last_submit_at and time.time() - self.last_submit_at < 15 else 1)
        raise RuntimeError("等待登录成功超时。")

    def login_page_looks_stuck(self) -> bool:
        body_text = self.page_text()
        visible_inputs = self.page.locator("input:visible").count()
        spinner = self.page.locator(".van-loading:visible, .el-loading-mask:visible, .loading:visible").count()
        return bool(spinner) or not (visible_inputs >= 2 and "获取验证码" in body_text)

    def login_page_needs_hard_reload(self, body_text: str | None = None) -> bool:
        body_text = self.page_text() if body_text is None else body_text
        current_url = self.page.url
        if current_url.startswith("chrome-error://"):
            return True
        if "ERR_NAME_NOT_RESOLVED" in body_text or "无法访问此网站" in body_text:
            return True
        return False

    def get_entered_code(self) -> str:
        locator = self.page.locator("input[maxlength='6'], input[placeholder*='验证码']").first
        if locator.count() == 0:
            return ""
        try:
            value = locator.input_value(timeout=500)
        except PlaywrightError:
            return ""
        return "".join(ch for ch in value if ch.isdigit())

    def try_submit_login_when_code_ready(self, digits: str | None = None) -> bool:
        digits = digits if digits is not None else self.get_entered_code()
        if len(digits) != 6:
            return False
        login_button = self.page.locator("text=登录").first
        if login_button.count() == 0:
            return False
        now = time.time()
        if self.last_submitted_code == digits and now - self.last_submit_at < 20:
            return False
        try:
            login_button.click(timeout=1_000)
            self.last_submitted_code = digits
            self.last_submit_at = now
        except PlaywrightError:
            return False
        return True

    def open_audit_page(self) -> None:
        self.set_step("open_audit_page")
        self.page.goto(AUDIT_URL, wait_until="commit", timeout=20_000)
        self.wait_for_page_stable()
        self.set_step("switch_to_pending_tab")
        self.switch_to_pending_approval_tab()
        self.log("已进入申请单审批页面。")

    def is_empty_pending_page(self, body_text: str | None = None) -> bool:
        text = body_text if body_text is not None else self.page_text()
        return any(marker in text for marker in ("没有匹配的申请单", "空空如也", "暂无申请单", "暂无数据"))

    def has_pending_approval_button(self) -> bool:
        if self.is_empty_pending_page():
            return False
        try:
            code_rows = self.page.locator(
                "xpath=//*[contains(text(),'GDP')]/ancestor::*[self::div or self::li][1]"
            )
            count = code_rows.count()
            for index in range(count):
                row = code_rows.nth(index)
                if not row.is_visible():
                    continue
                button = row.get_by_text("审批", exact=True)
                if button.count() > 0 and button.first.is_visible():
                    return True
        except PlaywrightError:
            pass
        try:
            buttons = self.page.get_by_text("审批", exact=True)
            count = buttons.count()
            for index in range(count):
                button = buttons.nth(index)
                if not button.is_visible():
                    continue
                box = button.bounding_box()
                if box and box["x"] >= 250 and box["width"] <= 120 and box["height"] <= 60:
                    return True
        except PlaywrightError:
            pass
        return False

    def keepalive_audit_page(self) -> None:
        try:
            self.page.bring_to_front()
        except PlaywrightError:
            pass
        try:
            self.page.mouse.wheel(0, 200)
            time.sleep(0.1)
            self.page.mouse.wheel(0, -200)
        except PlaywrightError:
            pass
        self.log("已执行一次保活。")

    def monitor_pending_orders(self) -> None:
        while True:
            self.set_step("wait_pending_list")
            self.wait_for_pending_list_ready()
            self.set_step("click_first_approval")
            if self.has_pending_approval_button():
                if self.click_first_approval_button():
                    self.log("已点击首张申请单的“审批”按钮。")
                    return
                raise RuntimeError("页面显示有待审批按钮，但点击后未能进入详情页。")

            if self.is_empty_pending_page():
                self.log("当前没有待审批申请单，停留在当前页面等待。")
            else:
                self.log("当前未发现可用的“审批”按钮，继续等待页面刷新。")

            self.wait_in_pending_page()

    def wait_in_pending_page(self) -> None:
        while True:
            now = time.time()
            if now - self.last_keepalive_at >= KEEPALIVE_INTERVAL_SECONDS:
                self.keepalive_audit_page()
                self.last_keepalive_at = now
            if now - self.last_refresh_at >= POLL_INTERVAL_SECONDS:
                self.log("到达刷新间隔，重新打开审批页检查新单。")
                self.open_audit_page()
                self.last_refresh_at = time.time()
                return
            if self.has_pending_approval_button():
                self.log("检测到新的待审批单，准备进入审批流程。")
                return
            time.sleep(1)

    def wait_for_page_stable(self, seconds: float = 0.3) -> None:
        self.page.wait_for_load_state("domcontentloaded")
        time.sleep(seconds)

    def is_audit_shell_ready(self, body_text: str | None = None) -> bool:
        text = body_text if body_text is not None else self.page_text()
        if any(marker in text for marker in ("申请单审批", "待审批", "已审批", "没有匹配的申请单", "空空如也")):
            return True
        return False

    def wait_for_audit_shell_ready(self, timeout_seconds: float = 12.0) -> bool:
        deadline = time.time() + timeout_seconds
        while time.time() < deadline:
            body_text = self.page_text()
            if self.is_audit_shell_ready(body_text):
                return True
            time.sleep(0.3)
        return False

    def ensure_audit_shell_ready(self) -> None:
        if self.wait_for_audit_shell_ready(timeout_seconds=8.0):
            return
        self.page.goto(AUDIT_URL, wait_until="commit", timeout=20_000)
        self.wait_for_page_stable()
        if not self.wait_for_audit_shell_ready(timeout_seconds=12.0):
            raise RuntimeError("审批页正文长时间未加载完成。")

    def switch_to_pending_approval_tab(self) -> None:
        self.ensure_audit_shell_ready()
        body_text = self.page_text()

        if "待审批" in body_text and (
            "申请单审批" in body_text or "已审批" in body_text or "没有匹配的申请单" in body_text or "空空如也" in body_text
        ):
            return

        if "申请单审批" in body_text:
            self.click_text_any(["申请单审批"])
            time.sleep(0.2)
            body_text = self.page_text()

        if "待审批" in body_text or "审批中" in body_text:
            self.click_text_any(["待审批", "审批中"])
            time.sleep(0.2)
            return

        raise RuntimeError("审批页已打开，但未识别到待审批标签。")

    def click_text_any(self, texts: list[str]) -> None:
        last_error: Exception | None = None
        for text in texts:
            candidates = [
                self.page.get_by_text(text, exact=True),
                self.page.get_by_text(text),
                self.page.locator(f"text={text}"),
            ]
            for locator in candidates:
                try:
                    count = locator.count()
                except PlaywrightError as exc:
                    last_error = exc
                    continue
                for index in range(count):
                    node = locator.nth(index)
                    try:
                        node.wait_for(state="visible", timeout=1_500)
                        box = node.bounding_box()
                        if not box or box["width"] < 20 or box["height"] < 12:
                            continue
                        node.click(timeout=2_000)
                        return
                    except PlaywrightError as exc:
                        last_error = exc
                        continue
        joined = " / ".join(texts)
        raise RuntimeError(f"未找到可点击文本：{joined}") from last_error

    def wait_for_pending_list_ready(self) -> None:
        deadline = time.time() + 25
        while time.time() < deadline:
            body_text = self.page_text()
            if "审批" in body_text or "没有匹配的申请单" in body_text or "空空如也" in body_text:
                return
            spinner = self.page.locator(".van-loading:visible, .el-loading-mask:visible, .loading:visible").count()
            if not spinner and ("申请单审批" in body_text or "待审批" in body_text):
                return
            time.sleep(0.3)
        raise RuntimeError("待审批列表长时间未加载完成。")

    def click_first_approval_button(self) -> bool:
        self.set_step("scan_order_rows")
        if self.is_empty_pending_page():
            return False
        code_rows = self.page.locator(
            "xpath=//*[contains(text(),'GDP')]/ancestor::*[self::div or self::li][1]"
        )
        code_row_count = code_rows.count()
        for index in range(code_row_count):
            row = code_rows.nth(index)
            try:
                if not row.is_visible():
                    continue
                button = row.get_by_text("审批", exact=True).last
                if button.count() == 0 or not button.is_visible():
                    continue
                button.click(timeout=2_000)
                self.wait_for_order_opened()
                return True
            except PlaywrightError:
                continue

        row_selectors = [
            ".audit-list .item",
            ".audit-item",
            ".list-item",
            ".application-item",
            ".van-cell",
        ]
        for selector in row_selectors:
            rows = self.page.locator(selector)
            count = rows.count()
            for index in range(count):
                row = rows.nth(index)
                try:
                    if not row.is_visible():
                        continue
                    button = row.get_by_text("审批", exact=True).last
                    if button.count() == 0 or not button.is_visible():
                        continue
                    button.click(timeout=2_000)
                    self.wait_for_order_opened()
                    return True
                except PlaywrightError:
                    continue

        buttons = self.page.get_by_text("审批", exact=True)
        count = buttons.count()
        for index in range(count):
            button = buttons.nth(index)
            try:
                if not button.is_visible():
                    continue
                box = button.bounding_box()
                if not box or box["x"] < 250 or box["width"] > 120 or box["height"] > 60:
                    continue
                button.click(timeout=2_000)
                self.wait_for_order_opened()
                return True
            except PlaywrightError:
                continue
        return False

    def wait_for_order_opened(self) -> None:
        self.set_step("wait_for_order_opened")
        deadline = time.time() + 12
        while time.time() < deadline:
            body_text = self.page_text()
            current_url = self.page.url
            if "同意" in body_text or "下一审批人" in body_text or "提交" in body_text:
                return
            if "#/travelApplyList" not in current_url:
                return
            time.sleep(0.2)
        raise RuntimeError("点击“审批”后仍未进入申请详情页。")


def main() -> None:
    hide_console_window()
    acquire_single_instance_lock()
    try:
        bot = PlaywrightApproveBot()
        bot.run()
    finally:
        release_single_instance_lock()


if __name__ == "__main__":
    main()
