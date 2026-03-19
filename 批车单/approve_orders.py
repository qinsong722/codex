from __future__ import annotations

import atexit
import ctypes
import os
import subprocess
import sys
import time
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, simpledialog

import chromedriver_py
from selenium import webdriver
from selenium.common.exceptions import (
    ElementClickInterceptedException,
    NoSuchElementException,
    StaleElementReferenceException,
    TimeoutException,
    WebDriverException,
)
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.edge.options import Options as EdgeOptions
from selenium.webdriver.edge.service import Service as EdgeService
from selenium.webdriver.support.ui import WebDriverWait


SITE_URL = "https://b2bjoy.10086.cn/t100/#/home/index"
AUDIT_URL = "https://b2bjoy.10086.cn/t100/#/travelApplyList?type=1&fromType=car"
DEFAULT_PHONE_NUMBER = "13922200297"
DEFAULT_APPROVER = "覃嵩"
EDGE_BINARY_CANDIDATES = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files (x86)\Microsoft\EdgeCore\145.0.3800.97\msedge.exe",
    r"C:\Program Files (x86)\Microsoft\EdgeWebView\Application\145.0.3800.97\msedge.exe",
]
CHROME_BINARY_CANDIDATES = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
]
POLL_INTERVAL_SECONDS = 300
KEEPALIVE_INTERVAL_SECONDS = 60
HEARTBEAT_CHECK_INTERVAL_SECONDS = 3
MANUAL_CONFIRM_KEEPALIVE_SECONDS = 30
AUDIT_STUCK_RECOVERY_SECONDS = 20
AUDIT_STUCK_REFRESH_COOLDOWN_SECONDS = 60
LOGIN_STUCK_REFRESH_SECONDS = 60
CONFIG_FILE_NAME = "phone_number.txt"


def normalize_text(value: str | None) -> str:
    return " ".join((value or "").split())


def text_matches(target: str, actual: str | None) -> bool:
    return normalize_text(target) == normalize_text(actual)


def get_app_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


APP_DIR = get_app_dir()
LOCK_FILE = APP_DIR / ".approve_bot.lock"
CONFIG_FILE = APP_DIR / CONFIG_FILE_NAME
LOG_FILE = APP_DIR / "approve_orders.log"
EDGE_PROFILE_DIR = APP_DIR / "edge-profile"
CHROME_PROFILE_DIR = APP_DIR / "chrome-profile"


def append_log(message: str) -> None:
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with LOG_FILE.open("a", encoding="utf-8") as fh:
        fh.write(f"[{timestamp}] {message}\n")


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
    content = f"phone_number={phone_number}\napprover={approver_name}\n"
    CONFIG_FILE.write_text(content, encoding="utf-8")


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
            # Backward-compatible with the old one-line phone-only format.
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


def is_session_lost_error(exc: Exception) -> bool:
    text = str(exc).lower()
    keywords = [
        "invalid session id",
        "session deleted",
        "disconnected",
        "not connected to devtools",
        "web view not found",
        "target window already closed",
    ]
    return any(keyword in text for keyword in keywords)


def is_transient_driver_comm_error(exc: Exception) -> bool:
    text = str(exc).lower()
    keywords = [
        "httpconnectionpool",
        "read timed out",
        "connection aborted",
        "connection reset",
        "failed to establish a new connection",
        "max retries exceeded",
    ]
    return any(keyword in text for keyword in keywords)


class ApproveBot:
    def __init__(self) -> None:
        self.phone_number, self.approver_name = load_runtime_config()
        browser_name, browser_binary = get_browser_binary()
        self.browser_name = browser_name
        self.profile_dir = self.ensure_profile_dir(browser_name)
        self.keep_browser_open = False
        self.audit_stuck_since: float | None = None
        self.last_audit_stuck_refresh_at = 0.0
        atexit.register(self.cleanup_profile_dir)

        if browser_name == "chrome":
            options = ChromeOptions()
        else:
            options = EdgeOptions()

        options.binary_location = str(browser_binary)
        options.page_load_strategy = "eager"
        options.add_argument("--window-size=404,876")
        options.add_argument(f"--user-data-dir={self.profile_dir}")
        options.add_argument("--no-first-run")
        options.add_argument("--disable-background-networking")
        options.add_argument("--disable-default-apps")
        options.add_argument("--disable-sync")
        options.add_argument("--disable-features=msEdgeSidebarV2")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)
        options.add_experimental_option("detach", True)

        if browser_name == "chrome":
            service = ChromeService(executable_path=str(get_local_chromedriver_path()), log_output=os.devnull)
        else:
            service = EdgeService(log_output=os.devnull)
        service.creationflags = subprocess.CREATE_NO_WINDOW

        if browser_name == "chrome":
            self.driver = webdriver.Chrome(options=options, service=service)
        else:
            self.driver = webdriver.Edge(options=options, service=service)
        self.driver.set_window_position(80, 0)
        self.driver.set_window_size(404, 876)
        self.wait = WebDriverWait(self.driver, 25)

    def ensure_profile_dir(self, browser_name: str) -> Path:
        profile_dir = CHROME_PROFILE_DIR if browser_name == "chrome" else EDGE_PROFILE_DIR
        profile_dir.mkdir(parents=True, exist_ok=True)
        return profile_dir

    def cleanup_profile_dir(self) -> None:
        return

    def run(self) -> None:
        try:
            self.login()
            self.open_audit_page()
            self.watch_and_approve_forever()
        except WebDriverException as exc:
            if is_session_lost_error(exc):
                raise
            if is_transient_driver_comm_error(exc):
                raise
            self.keep_browser_open = True
            self.pause_for_manual_inspection()
            raise
        except Exception as exc:
            if is_transient_driver_comm_error(exc):
                raise
            self.keep_browser_open = True
            self.pause_for_manual_inspection()
            raise
        finally:
            if not self.keep_browser_open:
                try:
                    self.driver.quit()
                except Exception:
                    pass

    def log(self, message: str) -> None:
        print(message, flush=True)
        append_log(message)

    def pause_for_manual_inspection(self) -> None:
        self.log("发生异常，浏览器将保留在当前页面，等待人工查看。")

        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        try:
            messagebox.showerror(
                "脚本已暂停",
                "本次运行出现异常，浏览器已保留在当前页面，方便你检查现场。\n\n检查完成后点击“确定”结束本次运行。",
                parent=root,
            )
        finally:
            root.destroy()

    def login(self) -> None:
        if self.open_login_page() == "authenticated":
            self.log("检测到现有登录态，跳过登录。")
            return
        self.prepare_login_page(send_code=True)
        self.log("验证码已发送，请直接在当前输入框内输入验证码。")
        self.wait_for_login_success(sent_code_at=time.time())
        time.sleep(0.05)
        self.log("登录成功。")

    def open_login_page(self) -> str:
        last_error: Exception | None = None
        for _ in range(3):
            try:
                self.driver.get(SITE_URL)
                state = self.wait_for_login_page_ready()
                if state:
                    return state
            except WebDriverException as exc:
                last_error = exc
            try:
                self.driver.get(AUDIT_URL)
                state = self.wait_for_login_page_ready()
                if state:
                    return state
            except WebDriverException as exc:
                last_error = exc

        if last_error is not None:
            raise last_error
        raise RuntimeError("未能打开登录页面。")

    def wait_for_login_page_ready(self) -> str | None:
        deadline = time.time() + 15
        while time.time() < deadline:
            try:
                current_url = self.driver.current_url
                body = self.driver.find_element(By.TAG_NAME, "body")
                body_text = normalize_text(body.text)

                if "#/travelApplyList" in current_url or "申请单审批" in body_text or "待审批" in body_text:
                    return "authenticated"

                phone_input = next(
                    (
                        el
                        for el in self.driver.find_elements(By.TAG_NAME, "input")
                        if (el.get_attribute("type") or "").lower() == "tel" and el.is_displayed()
                    ),
                    None,
                )
                if phone_input is not None:
                    return "login"

                if "获取验证码" in body_text or "登录" in body_text:
                    return "login"

                if not body_text:
                    self.driver.refresh()
            except WebDriverException:
                pass
            time.sleep(0.3)
        return None

    def prepare_login_page(self, send_code: bool) -> None:
        phone_input = self.wait.until(
            lambda d: next(
                (
                    el
                    for el in d.find_elements(By.TAG_NAME, "input")
                    if (el.get_attribute("type") or "").lower() == "tel" and el.is_displayed()
                ),
                None,
            )
        )
        if phone_input is None:
            raise RuntimeError("未找到手机号输入框。")

        phone_input.clear()
        phone_input.send_keys(self.phone_number)
        self.ensure_agreement_checked()

        if send_code:
            self.click_first(
                [
                    (By.XPATH, "//a[contains(@class,'get-code')][last()]"),
                    (By.XPATH, "//a[contains(@class,'get-code') and normalize-space()]"),
                ]
            )

        self.focus_code_input()

    def ensure_agreement_checked(self) -> None:
        selectors = [
            (By.CSS_SELECTOR, ".private-in img"),
            (By.XPATH, "//div[contains(@class,'private-in')]//img"),
            (By.XPATH, "//div[contains(@class,'private-in')]"),
        ]
        for by, value in selectors:
            element = self.find_visible((by, value), timeout=2)
            if not element:
                continue
            try:
                self.safe_click(element)
                time.sleep(0.2)
                return
            except Exception:
                continue

        raise RuntimeError("未找到登录协议勾选区域。")

    def open_audit_page(self) -> None:
        self.driver.get(AUDIT_URL)
        self.wait_for_page_ready(settle_seconds=0.15)
        self.dismiss_noise()
        self.switch_to_pending_approval_tab()
        self.dismiss_noise()
        self.log("已进入申请单审批页面。")

    def switch_to_pending_approval_tab(self) -> None:
        self.click_header_tab("申请单审批")
        time.sleep(0.15)
        self.dismiss_noise()
        self.click_status_tab("审批中")
        time.sleep(0.15)
        self.dismiss_noise()

    def watch_and_approve_forever(self) -> None:
        total_approved = 0
        while True:
            self.ensure_logged_in()
            self.dismiss_noise()
            cycle_approved = self.approve_available_orders()
            total_approved += cycle_approved

            if cycle_approved > 0:
                self.log(f"本轮审批完成，已处理 {cycle_approved} 张申请单，累计处理 {total_approved} 张。")

            self.log("当前没有待审批申请单，停留在当前页面，5 分钟后自动刷新。")
            self.sleep_with_heartbeat(POLL_INTERVAL_SECONDS)
            self.refresh_audit_page()

    def approve_available_orders(self) -> int:
        approved = 0
        while True:
            self.dismiss_noise()
            if self.has_no_pending_orders():
                return approved

            self.log("检测到待审批车单，准备点击右侧“审批”。")
            if not self.open_first_order():
                return approved

            self.dismiss_noise()
            self.log("已确认离开待审批列表，准备查找详情页底部“同意”。")
            self.click_agree()
            self.log(f"已进入审批人选择页，准备查找审批人：{self.approver_name}")
            self.handle_submitter_selection_if_needed()
            self.wait_for_submit_result()
            approved += 1
            self.log(f"已审批第 {approved} 张申请单。")

            self.return_to_list_if_needed()
            self.wait_for_page_ready()
            self.dismiss_noise()
            time.sleep(1)

    def refresh_audit_page(self) -> None:
        self.ensure_logged_in()
        self.dismiss_noise()
        self.driver.get(AUDIT_URL)
        self.wait_for_page_ready(settle_seconds=0.3)
        self.dismiss_noise()
        self.switch_to_pending_approval_tab()
        self.log("审批页已刷新，开始检查是否有新的申请单。")

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
            "//*[contains(normalize-space(.), '空空如也')]",
            "//*[contains(@class, 'empty')]",
        ]
        for xpath in empty_xpaths:
            if self.find_visible((By.XPATH, xpath), timeout=2):
                return True
        return len(self.find_order_candidates()) == 0

    def find_order_candidates(self) -> list:
        selectors = [
            (By.CSS_SELECTOR, ".audit-list .item"),
            (By.CSS_SELECTOR, ".audit-item"),
            (By.CSS_SELECTOR, ".list-item"),
            (By.CSS_SELECTOR, ".application-item"),
            (By.CSS_SELECTOR, ".van-cell"),
            (
                By.XPATH,
                "//div[contains(@class,'item') or contains(@class,'cell') or contains(@class,'card')]"
                "[.//span or .//div][not(ancestor::*[contains(@style,'display: none')])]",
            ),
        ]
        for locator in selectors:
            elements = self.driver.find_elements(*locator)
            visible = [el for el in elements if self.is_clickable_candidate(el)]
            if visible:
                return visible
        return []

    def open_first_order(self) -> bool:
        if self.click_first_visible_approval_button():
            return self.wait_for_order_opened()

        button = self.find_first_order_approval_button()
        if button:
            self.safe_click(button)
            return self.wait_for_order_opened()

        candidates = self.find_order_candidates()
        if not candidates:
            self.log("未找到待审批申请单入口。")
            return False

        self.safe_click(candidates[0])
        return self.wait_for_order_opened()

    def page_has_visible_approval_button(self) -> bool:
        try:
            return bool(
                self.driver.execute_script(
                    """
                    return Array.from(document.querySelectorAll('button,span,a,div'))
                      .some(el => {
                        const text = (el.innerText || '').trim();
                        if (text !== '审批') return false;
                        const rect = el.getBoundingClientRect();
                        return rect.width > 0 && rect.height > 0;
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
                        if (text !== '审批') return false;
                        const rect = el.getBoundingClientRect();
                        return rect.width > 0 && rect.height > 0;
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

    def click_agree(self) -> None:
        self.wait_for_detail_action_ready()
        agree_button = self.find_bottom_action_button("同意")
        if not agree_button:
            if self.selection_page_present() or self.find_bottom_action_button("提交"):
                return
            raise RuntimeError("进入申请单后未找到“同意”按钮。")
        self.safe_click(agree_button)
        time.sleep(1)
        self.dismiss_noise()

    def wait_for_detail_action_ready(self, timeout_seconds: float = 12.0) -> None:
        deadline = time.time() + timeout_seconds
        while time.time() < deadline:
            self.dismiss_noise()
            if self.find_bottom_action_button("同意"):
                return
            if self.selection_page_present():
                return
            if self.find_bottom_action_button("提交"):
                return
            time.sleep(0.2)

    def wait_for_order_opened(self) -> bool:
        deadline = time.time() + 5
        while time.time() < deadline:
            try:
                self.driver.execute_script("return document.readyState")
            except WebDriverException:
                pass

            self.dismiss_noise()
            if self.selection_page_present():
                return True

            if self.find_bottom_action_button("同意"):
                return True

            if not self.is_back_on_list():
                return True

            time.sleep(0.15)

        self.log("点击“审批”后仍停留在列表页，未能进入申请单详情。")
        return False

    def handle_submitter_selection_if_needed(self) -> None:
        self.wait_for_selection_stage_ready()

        if not self.selection_page_present():
            submit_button = self.find_bottom_action_button("提交")
            if submit_button:
                self.log("当前单据无需选择审批人，直接提交。")
                self.safe_click(submit_button)
            return

        if not self.select_approver_from_list(self.approver_name):
            raise RuntimeError(f"未在名单中找到审批人：{self.approver_name}")

        time.sleep(0.5)
        submit_button = self.find_bottom_action_button("提交")
        if not submit_button:
            raise RuntimeError("已选中审批人，但未找到提交按钮。")
        self.wait_for_manual_submit_confirmation()
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

            if self.selection_list_loading():
                time.sleep(0.25)
                continue

            if self.find_approver_rows():
                return

            time.sleep(0.2)

    def selection_list_loading(self) -> bool:
        try:
            return self.driver.execute_script(
                """
                const bodyText = document.body ? document.body.innerText : '';
                const nextApproverSection = Array.from(document.querySelectorAll('div,section,li'))
                  .find(el => (el.innerText || '').includes('下一审批人'));
                const scope = nextApproverSection || document.body;
                const spinner = scope.querySelector('.van-loading, .el-loading-mask, .loading, .van-toast--loading');
                const hasApproverName = /[\u4e00-\u9fa5]{2,}/.test(bodyText.replace('下一审批人', ''));
                return Boolean(spinner) || !hasApproverName;
                """,
            )
        except WebDriverException:
            return False

    def selection_page_present(self) -> bool:
        markers = [
            (By.XPATH, "//*[normalize-space(text())='下一审批人']"),
            (By.XPATH, "//*[normalize-space(text())='审批人']"),
            (By.XPATH, "//*[contains(normalize-space(.), '选择提交人')]"),
        ]
        return any(self.find_visible(locator, timeout=1) for locator in markers)

    def wait_for_manual_submit_confirmation(self) -> None:
        self.log(f"已选中审批人“{self.approver_name}”，暂停在提交前，等待人工确认。")

        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        dialog = tk.Toplevel(root)
        dialog.title("确认提交")
        dialog.attributes("-topmost", True)
        dialog.resizable(False, False)

        result = {"confirmed": None}

        def confirm() -> None:
            result["confirmed"] = True
            dialog.destroy()

        def cancel() -> None:
            result["confirmed"] = False
            dialog.destroy()

        dialog.protocol("WM_DELETE_WINDOW", cancel)
        tk.Label(
            dialog,
            text=(
                f"已选中审批人：{self.approver_name}\n\n"
                "请先核对页面上的审批人是否正确。\n"
                "确认无误后点击“确定”，程序才会继续提交。\n\n"
                "等待确认期间，程序会自动做轻量保活。"
            ),
            justify="left",
            padx=18,
            pady=16,
        ).pack()

        button_frame = tk.Frame(dialog, padx=18, pady=0)
        button_frame.pack(fill="x")
        tk.Button(button_frame, text="确定", width=10, command=confirm).pack(side="left", padx=(0, 8))
        tk.Button(button_frame, text="取消", width=10, command=cancel).pack(side="left")

        status_var = tk.StringVar(value="状态：等待人工确认")
        tk.Label(dialog, textvariable=status_var, anchor="w", padx=18, pady=12).pack(fill="x")

        dialog.update_idletasks()
        width = dialog.winfo_width()
        height = dialog.winfo_height()
        screen_width = dialog.winfo_screenwidth()
        screen_height = dialog.winfo_screenheight()
        pos_x = max((screen_width - width) // 2, 0)
        pos_y = max((screen_height - height) // 3, 0)
        dialog.geometry(f"{width}x{height}+{pos_x}+{pos_y}")
        dialog.focus_force()
        dialog.grab_set()

        last_keepalive_at = 0.0
        last_selection_check_at = 0.0
        selection_error: str | None = None
        try:
            while result["confirmed"] is None:
                root.update_idletasks()
                root.update()
                now = time.time()
                if now - last_selection_check_at >= 1.0:
                    selected_text = self.get_selected_approver_text()
                    if not selected_text or self.approver_name not in selected_text:
                        selection_error = selected_text or "未知"
                        result["confirmed"] = False
                        status_var.set(f"状态：勾选已漂移，当前为 {selection_error}")
                        dialog.destroy()
                        break
                    status_var.set(f"状态：当前勾选为 {self.approver_name}，等待人工确认")
                    last_selection_check_at = now
                if now - last_keepalive_at >= MANUAL_CONFIRM_KEEPALIVE_SECONDS:
                    self.keep_session_alive_during_confirmation()
                    status_var.set(f"状态：已保活 {time.strftime('%H:%M:%S')}，并确认仍为 {self.approver_name}")
                    last_keepalive_at = now
                time.sleep(0.2)
        finally:
            if dialog.winfo_exists():
                dialog.destroy()
            root.destroy()

        confirmed = bool(result["confirmed"])
        if selection_error is not None:
            raise RuntimeError(f"等待确认期间勾选校验未通过，当前勾选为：{selection_error}")
        if not confirmed:
            raise RuntimeError("人工取消提交，程序已在提交前停止。")

    def keep_session_alive_during_confirmation(self) -> None:
        try:
            self.dismiss_noise()
            self.driver.execute_script(
                """
                window.scrollBy(0, 1);
                window.scrollBy(0, -1);
                if (!window.__codexKeepaliveAt || Date.now() - window.__codexKeepaliveAt > 1000) {
                    window.__codexKeepaliveAt = Date.now();
                    fetch(window.location.origin + '/t100/', {
                        method: 'GET',
                        credentials: 'include',
                        cache: 'no-store'
                    }).catch(() => {});
                }
                """,
            )
            self.ensure_logged_in()
        except WebDriverException as exc:
            if is_session_lost_error(exc):
                raise

    def select_approver_from_list(self, name: str) -> bool:
        if self.try_click_approver_checkbox(name):
            return True

        for _ in range(18):
            if not self.selection_page_present():
                return False
            self.scroll_approver_list()
            time.sleep(0.25)
            self.dismiss_noise()
            if self.try_click_approver_checkbox(name):
                return True

        return False

    def try_click_approver_checkbox(self, name: str) -> bool:
        if self.click_approver_radio_by_row_position(name):
            if self.wait_for_expected_approver_selected(name):
                self.log(f"已按姓名“{name}”所在行点击右侧选择框，并确认勾选正确。")
                return True
            selected = self.get_selected_approver_text()
            self.log(f"点击“{name}”后勾选校验未通过，当前勾选为：{selected or '未知'}")

        for row in self.find_approver_rows():
            if not self.row_matches_approver(row, name):
                continue

            target = self.find_approver_click_target(row, name)
            if not target:
                continue

            self.log(f"已定位审批人“{name}”，点击右侧选择框。")
            self.safe_click(target)
            if self.wait_for_expected_approver_selected(name):
                return True
            selected = self.get_selected_approver_text()
            self.log(f"点击“{name}”后勾选校验未通过，当前勾选为：{selected or '未知'}")
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
                if getattr(label, "id", None) and label.id in seen_ids:
                    continue
                if getattr(label, "id", None):
                    seen_ids.add(label.id)

                if self.click_right_side_of_label_row(label):
                    return True

        return False

    def click_right_side_of_label_row(self, label) -> bool:
        try:
            clicked = self.driver.execute_script(
                """
                const label = arguments[0];
                label.scrollIntoView({block:'center', inline:'nearest'});
                const rect = label.getBoundingClientRect();
                const y = Math.round(rect.top + rect.height / 2);
                const x = Math.round(window.innerWidth - 28);
                let el = document.elementFromPoint(x, y);
                if (!el) return false;

                const candidates = [el, el.closest('label'), el.closest('[role="radio"]'), el.closest('[role="checkbox"]'), el.closest('div'), el.closest('span')].filter(Boolean);
                for (const candidate of candidates) {
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
            selected_text = self.get_selected_approver_text()
            if selected_text and name in selected_text:
                return True
            time.sleep(0.15)
        return False

    def get_selected_approver_text(self) -> str | None:
        for row in self.find_approver_rows():
            if not self.row_is_selected(row):
                continue
            text = normalize_text(getattr(row, "text", ""))
            if text:
                return text
        return None

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

    def find_first_order_approval_button(self):
        row_selectors = [
            (By.CSS_SELECTOR, ".audit-list .item"),
            (By.CSS_SELECTOR, ".audit-item"),
            (By.CSS_SELECTOR, ".list-item"),
            (By.CSS_SELECTOR, ".application-item"),
            (By.CSS_SELECTOR, ".van-cell"),
            (
                By.XPATH,
                "//div[contains(@class,'item') or contains(@class,'cell') or contains(@class,'card')]",
            ),
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
                key = row.id if getattr(row, "id", None) else f"{row_text}:{row.rect}"
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

    def wait_for_submit_result(self) -> None:
        success_texts = ["成功", "提交成功", "审批成功", "操作成功"]
        deadline = time.time() + 20
        while time.time() < deadline:
            self.dismiss_noise()
            body_text = self.driver.find_element(By.TAG_NAME, "body").text
            if any(text in body_text for text in success_texts):
                return
            if self.is_back_on_list():
                return
            time.sleep(0.5)
        self.log("未明确捕获到成功提示，按流程继续。")

    def return_to_list_if_needed(self) -> None:
        if self.is_back_on_list():
            return

        back_buttons = self.find_action_buttons(["返回", "关闭"])
        if back_buttons:
            self.safe_click(back_buttons[0])
            time.sleep(1)
            return

        self.driver.back()
        time.sleep(1.5)

    def is_back_on_list(self) -> bool:
        if "#/travelApplyList" in self.driver.current_url and self.find_order_candidates():
            return True

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
                  if (!labels.includes(text)) return false;
                  const rect = el.getBoundingClientRect();
                  return rect.width > 0 && rect.height > 0;
                });
                if (!target) return false;
                target.click();
                return true;
                """,
            )
            if handled:
                time.sleep(0.1)
                return
        except WebDriverException:
            pass

        xpaths = [
            "//div[contains(@class,'dialog') or contains(@class,'popup') or contains(@class,'modal')]//*[normalize-space(text())='知道了']",
            "//div[contains(@class,'dialog') or contains(@class,'popup') or contains(@class,'modal')]//*[normalize-space(text())='我知道了']",
            "//*[normalize-space(text())='知道了']",
            "//*[normalize-space(text())='我知道了']",
            "//*[normalize-space(text())='关闭']",
            "//*[normalize-space(text())='取消']",
        ]
        clicked = False
        for xpath in xpaths:
            element = self.find_visible((By.XPATH, xpath), timeout=0.2)
            if not element:
                continue
            try:
                self.safe_click(element)
                clicked = True
                time.sleep(0.2)
            except Exception:
                continue

        if clicked:
            return

        try:
            self.driver.execute_script(
                """
                const texts = ['网络不稳定', '提示'];
                const dialogFound = Array.from(document.querySelectorAll('div,span,p')).some(
                  el => texts.includes((el.innerText || '').trim())
                );
                if (!dialogFound) return;
                const ok = Array.from(document.querySelectorAll('button,span,a,div')).find(
                  el => ['知道了', '我知道了', '关闭', '取消'].includes((el.innerText || '').trim())
                );
                if (ok) ok.click();
                """,
            )
        except WebDriverException:
            pass

    def click_header_tab(self, label: str) -> bool:
        xpaths = [
            f"//div[contains(@class,'tabs') or contains(@class,'tab')]//*[normalize-space(text())='{label}']",
            f"//*[normalize-space(text())='{label}']",
        ]
        for xpath in xpaths:
            element = self.find_visible((By.XPATH, xpath), timeout=2)
            if not element:
                continue
            self.safe_click(element)
            time.sleep(0.15)
            return True
        return False

    def click_status_tab(self, label: str) -> bool:
        xpaths = [
            f"//div[contains(@class,'tabs') or contains(@class,'tab')]//*[normalize-space(text())='{label}']",
            f"//*[normalize-space(text())='{label}']",
        ]
        for xpath in xpaths:
            element = self.find_visible((By.XPATH, xpath), timeout=2)
            if not element:
                continue
            self.safe_click(element)
            time.sleep(0.15)
            return True
        return False

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

    def click_first(self, selectors: list[tuple[str, str]]) -> None:
        for by, value in selectors:
            element = self.find_visible((by, value), timeout=3)
            if element:
                self.safe_click(element)
                return
        raise RuntimeError(f"未找到可点击元素: {selectors}")

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
        except (ElementClickInterceptedException, StaleElementReferenceException):
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
        self.wait.until(lambda d: d.execute_script("return document.readyState") == "complete")
        time.sleep(settle_seconds)

    def focus_code_input(self) -> None:
        code_input = self.find_visible(
            (By.XPATH, "//input[@maxlength='6' or contains(@placeholder,'验证码')]"),
            timeout=3,
        )
        if not code_input:
            return

        try:
            self.force_focus_input(code_input)
            self.driver.execute_script(
                """
                if (window.__codexAutoLoginTimer) {
                    window.clearInterval(window.__codexAutoLoginTimer);
                }
                window.__codexAutoLoginDone = false;
                window.__codexAutoLoginTimer = window.setInterval(() => {
                    if (window.__codexAutoLoginDone) return;
                    const liveInput =
                      document.querySelector("input[maxlength='6']") ||
                      Array.from(document.querySelectorAll('input')).find(el => (el.placeholder || '').includes('验证码'));
                    if (!liveInput) return;
                    const digits = (liveInput.value || '').replace(/\\D/g, '');
                    if (digits.length !== 6) return;
                    const loginButton = Array.from(document.querySelectorAll('button,span,a,div'))
                      .filter(el => (el.innerText || '').trim() === '登录')
                      .sort((a, b) => a.getBoundingClientRect().top - b.getBoundingClientRect().top)[0];
                    if (!loginButton) return;
                    window.__codexAutoLoginDone = true;
                    try { loginButton.click(); } catch (e) {}
                }, 200);
                """,
            )
        except WebDriverException:
            pass

    def keep_code_input_focused(self) -> None:
        code_input = self.find_visible(
            (By.XPATH, "//input[@maxlength='6' or contains(@placeholder,'验证码')]"),
            timeout=1,
        )
        if not code_input:
            return

        if not self.should_refocus_code_input(code_input):
            return

        try:
            self.force_focus_input(code_input)
        except WebDriverException:
            return

    def force_focus_input(self, input_element) -> None:
        self.activate_browser_window()

        for _ in range(3):
            try:
                self.driver.execute_script(
                    """
                    arguments[0].scrollIntoView({block: 'center', inline: 'nearest'});
                    arguments[0].focus();
                    if (typeof arguments[0].setSelectionRange === 'function') {
                        const len = (arguments[0].value || '').length;
                        arguments[0].setSelectionRange(len, len);
                    }
                    """,
                    input_element,
                )
                time.sleep(0.1)
                self.system_click_code_input(input_element)
                time.sleep(0.1)
                ActionChains(self.driver).move_to_element(input_element).pause(0.05).click(input_element).perform()
                self.driver.execute_script(
                    """
                    arguments[0].focus();
                    if (typeof arguments[0].setSelectionRange === 'function') {
                        const len = (arguments[0].value || '').length;
                        arguments[0].setSelectionRange(len, len);
                    }
                    """,
                    input_element,
                )
                if self.driver.execute_script("return document.activeElement === arguments[0];", input_element):
                    return
            except WebDriverException:
                time.sleep(0.15)

    def activate_browser_window(self) -> None:
        try:
            title = (self.driver.title or "").strip()
        except WebDriverException:
            return

        if not title:
            return

        try:
            user32 = ctypes.windll.user32
            matched_hwnd = None

            @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
            def enum_windows_proc(hwnd, lparam):
                nonlocal matched_hwnd
                if not user32.IsWindowVisible(hwnd):
                    return True

                length = user32.GetWindowTextLengthW(hwnd)
                if length <= 0:
                    return True

                buffer = ctypes.create_unicode_buffer(length + 1)
                user32.GetWindowTextW(hwnd, buffer, length + 1)
                window_title = buffer.value.strip()
                if not window_title:
                    return True

                if title in window_title and ("Microsoft Edge" in window_title or "Google Chrome" in window_title):
                    matched_hwnd = hwnd
                    return False
                return True

            user32.EnumWindows(enum_windows_proc, 0)
            if matched_hwnd:
                user32.ShowWindow(matched_hwnd, 5)
                user32.SetForegroundWindow(matched_hwnd)
        except Exception:
            return

    def system_click_code_input(self, code_input) -> None:
        try:
            point = self.driver.execute_script(
                """
                const rect = arguments[0].getBoundingClientRect();
                const topChrome = window.outerHeight - window.innerHeight;
                const leftChrome = window.outerWidth - window.innerWidth;
                const centerX = window.screenX + rect.left + rect.width / 2 + leftChrome / 2;
                const centerY = window.screenY + topChrome + rect.top + rect.height / 2;
                return {
                  x: Math.round(centerX),
                  y: Math.round(centerY)
                };
                """,
                code_input,
            )
        except WebDriverException:
            return

        if not point:
            return

        try:
            user32 = ctypes.windll.user32

            class POINT(ctypes.Structure):
                _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

            original = POINT()
            user32.GetCursorPos(ctypes.byref(original))
            user32.SetCursorPos(int(point["x"]), int(point["y"]))
            user32.mouse_event(0x0002, 0, 0, 0, 0)
            user32.mouse_event(0x0004, 0, 0, 0, 0)
            user32.SetCursorPos(original.x, original.y)
        except Exception:
            return

    def should_refocus_code_input(self, code_input) -> bool:
        try:
            if "#/login" not in self.driver.current_url:
                return False
        except WebDriverException:
            return False

        value = (code_input.get_attribute("value") or "").strip()
        digits = "".join(ch for ch in value if ch.isdigit())
        if len(digits) >= 6:
            return False

        try:
            return not bool(
                self.driver.execute_script("return document.activeElement === arguments[0];", code_input)
            )
        except WebDriverException:
            return False

    def sleep_with_heartbeat(self, seconds: int) -> None:
        remaining = seconds
        elapsed = 0
        while remaining > 0:
            self.ensure_logged_in()
            self.dismiss_noise()
            self.recover_if_audit_page_stuck()
            if self.has_pending_orders_ready():
                self.log("检测到新的待审批车单，立即结束等待并开始审批。")
                return
            step = min(HEARTBEAT_CHECK_INTERVAL_SECONDS, remaining)
            time.sleep(step)
            remaining -= step
            elapsed += step
            if elapsed > 0 and elapsed % KEEPALIVE_INTERVAL_SECONDS == 0:
                self.keep_session_alive()

    def wait_for_login_success(self, sent_code_at: float) -> None:
        deadline = time.time() + 300
        last_refresh_at = sent_code_at
        while time.time() < deadline:
            try:
                self.dismiss_noise()
                self.keep_code_input_focused()
                self.try_submit_login_when_code_ready()

                current_url = self.driver.current_url
                if "#/login" not in current_url:
                    return

                body_text = self.driver.find_element(By.TAG_NAME, "body").text
                if "首页" in body_text or "查看申请单" in body_text or "申请单审批" in body_text:
                    return

                waited_long_enough = time.time() - sent_code_at >= LOGIN_STUCK_REFRESH_SECONDS
                should_refresh = time.time() - last_refresh_at >= LOGIN_STUCK_REFRESH_SECONDS
                if waited_long_enough and should_refresh and self.login_page_looks_stuck():
                    self.log("登录页加载异常，正在自动刷新重试。")
                    self.driver.refresh()
                    self.prepare_login_page(send_code=True)
                    sent_code_at = time.time()
                    last_refresh_at = sent_code_at
            except (WebDriverException, NoSuchElementException, StaleElementReferenceException):
                time.sleep(1)
                continue

            time.sleep(1)

        raise TimeoutException("等待登录成功超时。")

    def try_submit_login_when_code_ready(self) -> None:
        if "#/login" not in self.driver.current_url:
            return

        code_input = self.find_visible(
            (By.XPATH, "//input[@maxlength='6' or contains(@placeholder,'验证码')]"),
            timeout=1,
        )
        if not code_input:
            return

        value = (code_input.get_attribute("value") or "").strip()
        digits = "".join(ch for ch in value if ch.isdigit())
        if len(digits) != 6:
            return

        login_button = self.find_login_submit_button()
        if not login_button:
            return

        self.safe_click(login_button)
        time.sleep(0.3)

    def find_login_submit_button(self):
        candidates = []
        selectors = [
            (By.XPATH, "//*[self::button or self::span or self::a or self::div][normalize-space(text())='登录']"),
            (By.XPATH, "//button[normalize-space(text())='登录']"),
        ]
        for locator in selectors:
            for element in self.driver.find_elements(*locator):
                if not self.is_clickable_candidate(element):
                    continue
                text = normalize_text(getattr(element, "text", ""))
                if text != "登录":
                    continue
                candidates.append(element)

        if not candidates:
            return None

        return min(candidates, key=lambda el: (el.rect.get("y", 0), -el.rect.get("width", 0)))

    def login_page_looks_stuck(self) -> bool:
        try:
            return self.driver.execute_script(
                """
                const bodyText = document.body ? document.body.innerText : '';
                const inputs = Array.from(document.querySelectorAll('input')).filter(el => el.offsetParent !== null);
                const spinner = document.querySelector('.van-loading, .el-loading-mask, .loading, .van-toast--loading');
                const ready = inputs.length >= 2 && bodyText.includes('获取验证码');
                return Boolean(spinner) || !ready;
                """,
            )
        except WebDriverException:
            return True

    def ensure_logged_in(self) -> None:
        try:
            current_url = self.driver.current_url
            body_text = self.driver.find_element(By.TAG_NAME, "body").text
        except WebDriverException:
            raise
        except Exception:
            return

        if "#/login" in current_url or "获取验证码" in body_text:
            self.log("检测到账号已退出，正在自动重新登录。")
            self.login()
            self.open_audit_page()

    def keep_session_alive(self) -> None:
        try:
            self.driver.execute_script("window.scrollTo(0, 0);")
            self.dismiss_noise()
            self.recover_if_audit_page_stuck()
            current_url = self.driver.current_url
            if "#/travelApplyList" in current_url:
                self.driver.refresh()
                self.wait_for_page_ready(settle_seconds=0.2)
                self.dismiss_noise()
                self.switch_to_pending_approval_tab()
                self.log("已执行一次保活刷新。")
        except WebDriverException as exc:
            if is_session_lost_error(exc):
                raise

    def has_pending_orders_ready(self) -> bool:
        try:
            current_url = self.driver.current_url
        except WebDriverException:
            return False

        if "#/travelApplyList" not in current_url:
            return False

        self.dismiss_noise()
        return not self.has_no_pending_orders() and self.find_first_order_approval_button() is not None

    def recover_if_audit_page_stuck(self) -> None:
        try:
            current_url = self.driver.current_url
        except WebDriverException:
            return

        if "#/travelApplyList" not in current_url:
            self.audit_stuck_since = None
            return

        if not self.audit_page_looks_stuck():
            self.audit_stuck_since = None
            return

        now = time.time()
        if self.audit_stuck_since is None:
            self.audit_stuck_since = now
            return

        if now - self.audit_stuck_since < AUDIT_STUCK_RECOVERY_SECONDS:
            return

        if now - self.last_audit_stuck_refresh_at < AUDIT_STUCK_REFRESH_COOLDOWN_SECONDS:
            return

        self.log("检测到审批页面加载转圈，立即刷新并回到审批界面。")
        self.last_audit_stuck_refresh_at = now
        self.audit_stuck_since = None
        self.driver.refresh()
        self.wait_for_page_ready(settle_seconds=0.2)
        self.dismiss_noise()
        self.switch_to_pending_approval_tab()

    def audit_page_looks_stuck(self) -> bool:
        try:
            return self.driver.execute_script(
                """
                const spinner = Array.from(document.querySelectorAll('.van-loading, .el-loading-mask, .loading, .van-toast--loading'))
                  .find(el => {
                    const rect = el.getBoundingClientRect();
                    return rect.width > 0 && rect.height > 0;
                  });
                const bodyText = document.body ? document.body.innerText : '';
                const hasApprovalTabs =
                  bodyText.includes('申请单审批') &&
                  (bodyText.includes('审批中') || bodyText.includes('待审批'));
                const isEmptyState =
                  bodyText.includes('没有匹配的申请单') ||
                  bodyText.includes('空空如也') ||
                  bodyText.includes('暂无') ||
                  bodyText.includes('无数据');
                const hasApprovalButton = Array.from(document.querySelectorAll('button,span,a,div'))
                  .some(el => (el.innerText || '').trim() === '审批');
                const hasOrderCode = /GDP\\d{6,}/.test(bodyText);
                return Boolean(spinner) && hasApprovalTabs && !isEmptyState && !hasApprovalButton && !hasOrderCode;
                """,
            )
        except WebDriverException:
            return False


def ensure_browser_exists() -> None:
    get_browser_binary()


def get_local_chromedriver_path() -> Path | None:
    candidates = [
        Path(chromedriver_py.binary_path),
        APP_DIR / ".drivers" / "chromedriver-win64" / "chromedriver-win64" / "chromedriver.exe",
        APP_DIR / ".drivers" / "chromedriver.exe",
    ]
    for path in candidates:
        if path.exists():
            return path
    return None


def get_browser_binary() -> tuple[str, Path]:
    standard_edge = EDGE_BINARY_CANDIDATES[:2]
    fallback_edge = EDGE_BINARY_CANDIDATES[2:]

    chrome_driver = get_local_chromedriver_path()
    if chrome_driver:
        for candidate in CHROME_BINARY_CANDIDATES:
            path = Path(candidate)
            if path.exists():
                return "chrome", path

    for candidate in standard_edge:
        path = Path(candidate)
        if path.exists():
            return "edge", path

    for candidate in fallback_edge:
        path = Path(candidate)
        if path.exists():
            return "edge", path

    joined = ", ".join(standard_edge + CHROME_BINARY_CANDIDATES + fallback_edge)
    raise FileNotFoundError(f"未找到可用的浏览器: {joined}")


def acquire_lock() -> None:
    if LOCK_FILE.exists():
        stale = True
        try:
            pid_text = LOCK_FILE.read_text(encoding="utf-8").strip()
            if pid_text.isdigit():
                pid = int(pid_text)
                try:
                    os.kill(pid, 0)
                    stale = False
                except OSError:
                    stale = True
        except OSError:
            stale = True

        if stale:
            try:
                LOCK_FILE.unlink()
            except OSError:
                pass
        else:
            raise RuntimeError("脚本已经在运行中，请先关闭之前启动的审批脚本。")

    try:
        LOCK_FILE.write_text(str(os.getpid()), encoding="utf-8")
    except OSError as exc:
        raise RuntimeError(f"无法创建锁文件: {LOCK_FILE}") from exc
    atexit.register(release_lock)


def release_lock() -> None:
    try:
        LOCK_FILE.unlink(missing_ok=True)
    except OSError:
        pass


def hide_console_window() -> None:
    try:
        kernel32 = ctypes.windll.kernel32
        user32 = ctypes.windll.user32
        hwnd = kernel32.GetConsoleWindow()
        if hwnd:
            user32.ShowWindow(hwnd, 0)
    except Exception:
        pass


def main() -> int:
    try:
        hide_console_window()
        ensure_browser_exists()
        acquire_lock()

        for attempt in range(1, 3):
            try:
                ApproveBot().run()
                return 0
            except WebDriverException as exc:
                append_log(f"WebDriverException: {exc}")
                if is_session_lost_error(exc):
                    append_log("检测到浏览器会话断开，本次停止运行。")
                    return 0
                if is_transient_driver_comm_error(exc) and attempt < 2:
                    append_log("检测到 WebDriver 本地通信超时，正在自动重试一次。")
                    time.sleep(2)
                    continue
                return 1
            except (NoSuchElementException, RuntimeError, TimeoutException) as exc:
                append_log(f"执行失败: {exc}")
                return 1
            except Exception as exc:
                append_log(f"未预期异常: {exc}")
                if is_transient_driver_comm_error(exc) and attempt < 2:
                    append_log("检测到本地通信超时，正在自动重试一次。")
                    time.sleep(2)
                    continue
                return 1
    except KeyboardInterrupt:
        append_log("脚本已手动停止。")
        return 130
    except Exception as exc:
        append_log(f"启动失败: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
