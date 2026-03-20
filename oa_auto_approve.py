from __future__ import annotations

import argparse
import logging
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from selenium import webdriver
from selenium.common.exceptions import (
    ElementClickInterceptedException,
    NoSuchElementException,
    NoSuchFrameException,
    TimeoutException,
    WebDriverException,
)
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.webdriver import WebDriver as ChromeDriver
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


LOGIN_URL = "http://oa.hq.cmcc"
TODO_URL = "http://todo.hq.cmcc/backlog/cmit/web/index/todo?menu=DB&group=province&company=GD&role=ALL"
TARGET_STAGE = "部门落实"
DEFAULT_HEADLESS = False
WAIT_SHORT = 5
WAIT_MEDIUM = 10
WAIT_LONG = 20

BROWSER_CONFIGS = {
    "chrome": {
        "process": "chrome.exe",
        "executables": [
            Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
            Path(r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"),
        ],
        "default_user_data_dir": Path("Google") / "Chrome" / "User Data",
    },
    "edge": {
        "process": "msedge.exe",
        "executables": [
            Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
            Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"),
        ],
        "default_user_data_dir": Path("Microsoft") / "Edge" / "User Data",
    },
}


def resource_path(relative_path: str) -> Path:
    base = getattr(sys, "_MEIPASS", Path(__file__).resolve().parent)
    return Path(base) / relative_path


def setup_logging(log_path: Path) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    handlers = [
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(log_path, encoding="utf-8"),
    ]
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=handlers,
    )


def pause_before_exit(message: str) -> None:
    print(message)
    if sys.stdin and sys.stdin.isatty():
        try:
            input("按回车退出...")
        except EOFError:
            pass


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description='自动处理 OA 待办列表中“当前环节”为“部门落实”的单据。'
    )
    parser.add_argument(
        "--browser",
        choices=["chrome", "edge"],
        default="chrome",
        help='指定启动浏览器，默认是 "chrome"。',
    )
    parser.add_argument(
        "--manual-login",
        action="store_true",
        help="只打开登录页，方便人工检查登录状态。",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        default=DEFAULT_HEADLESS,
        help="无头模式运行。默认关闭，便于观察执行过程。",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="最多处理多少条，0 表示不限。",
    )
    parser.add_argument(
        "--user-data-dir",
        default="",
        help="指定浏览器用户数据目录；默认使用程序自己的独立配置目录。",
    )
    parser.add_argument(
        "--profile",
        default="Default",
        help='指定浏览器配置名称，默认是 "Default"。',
    )
    parser.add_argument(
        "--keep-browser",
        action="store_true",
        help="启动前不主动关闭现有浏览器进程。默认会先关闭，避免配置目录被占用。",
    )
    return parser.parse_args()


def get_browser_config(browser: str) -> dict:
    return BROWSER_CONFIGS[browser]


def force_close_browser_processes(browser: str) -> None:
    process_name = get_browser_config(browser)["process"]
    subprocess.run(
        ["taskkill", "/IM", process_name, "/F"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    time.sleep(2)


def resolve_user_data_dir(browser: str, cli_value: str) -> Path:
    if cli_value:
        return Path(cli_value)

    # Use an isolated profile by default so old Chrome versions start reliably
    # and do not depend on the user's system browser profile state.
    app_dir = Path(__file__).resolve().parent
    profile_root = app_dir / "browser-profile" / browser
    profile_root.mkdir(parents=True, exist_ok=True)
    return profile_root


def find_browser_exe(browser: str) -> Path:
    for candidate in get_browser_config(browser)["executables"]:
        if candidate.exists():
            return candidate
    raise FileNotFoundError(f"未找到 {browser} 安装路径。")


def find_chromedriver() -> Path:
    candidates = [
        resource_path("drivers/chromedriver-138/chromedriver.exe"),
        resource_path("drivers/chromedriver.exe"),
        resource_path("drivers/chromedriver-win64/chromedriver.exe"),
        Path(__file__).resolve().parent / "drivers" / "chromedriver-unpacked-138" / "chromedriver-win64" / "chromedriver.exe",
        Path(__file__).resolve().parent / "drivers" / "chromedriver.exe",
        Path(__file__).resolve().parent / "drivers" / "chromedriver-win64" / "chromedriver.exe",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise FileNotFoundError("未找到 chromedriver.exe。")


def build_driver(*, browser: str, headless: bool, user_data_dir: Path, profile_name: str) -> WebDriver:
    browser_exe = find_browser_exe(browser)
    chromedriver_exe = find_chromedriver()

    options = Options()
    options.binary_location = str(browser_exe)
    options.add_argument("--start-maximized")
    options.add_argument(f"--user-data-dir={user_data_dir}")
    options.add_argument(f"--profile-directory={profile_name}")
    options.add_argument("--remote-debugging-port=0")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--no-first-run")
    options.add_argument("--no-default-browser-check")
    options.add_argument("--disable-popup-blocking")
    options.add_argument("--disable-notifications")
    options.add_argument("--disable-background-networking")
    options.add_argument("--disable-features=Translate,OptimizationHints")
    if headless:
        options.add_argument("--headless=new")

    service = Service(executable_path=str(chromedriver_exe))
    driver = ChromeDriver(service=service, options=options)
    driver.set_page_load_timeout(WAIT_LONG)
    return driver


def save_debug_snapshot(driver: WebDriver, name: str) -> None:
    debug_dir = Path(__file__).resolve().parent / "debug"
    debug_dir.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    png_path = debug_dir / f"{stamp}-{name}.png"
    html_path = debug_dir / f"{stamp}-{name}.html"
    try:
        driver.save_screenshot(str(png_path))
    except Exception:  # noqa: BLE001
        pass
    try:
        html_path.write_text(driver.page_source, encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass


def append_debug_text(name: str, content: str) -> None:
    debug_dir = Path(__file__).resolve().parent / "debug"
    debug_dir.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    (debug_dir / f"{stamp}-{name}.txt").write_text(content, encoding="utf-8")


def iter_frame_paths(driver: WebDriver, max_depth: int = 3) -> list[list[int]]:
    paths: list[list[int]] = [[]]

    def walk(path: list[int], depth: int) -> None:
        if depth >= max_depth:
            return
        driver.switch_to.default_content()
        for frame_index in path:
            frames = driver.find_elements(By.TAG_NAME, "iframe") + driver.find_elements(By.TAG_NAME, "frame")
            if frame_index >= len(frames):
                return
            driver.switch_to.frame(frames[frame_index])

        frames = driver.find_elements(By.TAG_NAME, "iframe") + driver.find_elements(By.TAG_NAME, "frame")
        for index in range(len(frames)):
            child_path = [*path, index]
            paths.append(child_path)
            walk(child_path, depth + 1)

    walk([], 0)
    return paths


def switch_to_frame_path(driver: WebDriver, path: list[int]) -> None:
    driver.switch_to.default_content()
    for frame_index in path:
        frames = driver.find_elements(By.TAG_NAME, "iframe") + driver.find_elements(By.TAG_NAME, "frame")
        driver.switch_to.frame(frames[frame_index])


def body_text(driver: WebDriver) -> str:
    try:
        return driver.execute_script("return (document.body && document.body.innerText) || '';") or ""
    except WebDriverException:
        return ""


def wait_for_todo_table(driver: WebDriver, allow_goto: bool = True) -> None:
    if allow_goto:
        driver.get(TODO_URL)
    deadline = time.time() + WAIT_LONG
    markers = ["公文待办", "当前环节", "标题", "接收日期", "每页", "共"]

    while time.time() < deadline:
        for path in iter_frame_paths(driver):
            try:
                switch_to_frame_path(driver, path)
                text = body_text(driver)
                if any(marker in text for marker in markers):
                    driver.switch_to.default_content()
                    return
                rows = driver.find_elements(By.TAG_NAME, "tr")
                if len(rows) > 1:
                    driver.switch_to.default_content()
                    return
            except (NoSuchFrameException, WebDriverException):
                continue
            finally:
                driver.switch_to.default_content()
        time.sleep(1)

    save_debug_snapshot(driver, "todo-detect-failed")
    raise TimeoutException("未识别到待办列表页标记。")


def click_element(driver: WebDriver, element) -> None:
    try:
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
    except WebDriverException:
        pass
    try:
        element.click()
    except (ElementClickInterceptedException, WebDriverException):
        driver.execute_script("arguments[0].click();", element)


def get_target_rows(driver: WebDriver) -> list[tuple[list[int], object]]:
    matches: list[tuple[list[int], object]] = []
    stage_markers = [TARGET_STAGE, "部门落实", "落实"]
    debug_lines: list[str] = []

    candidate_xpaths = [
        "//tr",
        "//*[@role='row']",
        "//tbody/*",
        "//ul/li",
        "//div[contains(@class, 'row')]",
        "//div[contains(@class, 'list') or contains(@class, 'table')]//*[self::div or self::li][.//a]",
    ]

    for path in iter_frame_paths(driver):
        try:
            switch_to_frame_path(driver, path)
            seen_ids: set[str] = set()
            rows = []
            for xpath in candidate_xpaths:
                for element in driver.find_elements(By.XPATH, xpath):
                    try:
                        element_id = element.id
                    except WebDriverException:
                        continue
                    if element_id not in seen_ids:
                        seen_ids.add(element_id)
                        rows.append(element)

            for index, row in enumerate(rows):
                try:
                    text = row.text
                except WebDriverException:
                    continue
                text = (text or "").strip()
                if text:
                    compact = " ".join(text.split())
                    debug_lines.append(f"path={path} idx={index} text={compact[:500]}")
                if any(marker in text for marker in stage_markers):
                    matches.append((path, row))
        except WebDriverException:
            continue
        finally:
            driver.switch_to.default_content()
    if debug_lines:
        append_debug_text("row-scan", "\n".join(debug_lines[:400]))
    return matches


def find_row_title(row) -> str:
    try:
        links = row.find_elements(By.TAG_NAME, "a")
        for link in links:
            text = link.text.strip()
            if text:
                return text
    except WebDriverException:
        pass
    try:
        cells = row.find_elements(By.TAG_NAME, "td")
        for cell in cells:
            text = cell.text.strip()
            if text:
                return text
    except WebDriverException:
        pass
    return "<未识别标题>"


def open_row_detail(driver: WebDriver, frame_path: list[int], row) -> None:
    switch_to_frame_path(driver, frame_path)
    try:
        links = row.find_elements(By.TAG_NAME, "a")
        for link in links:
            if link.text.strip():
                click_element(driver, link)
                return
        cells = row.find_elements(By.TAG_NAME, "td")
        for cell in cells:
            if cell.text.strip():
                click_element(driver, cell)
                return
    finally:
        driver.switch_to.default_content()
    raise RuntimeError("未找到可点击的待办标题。")


def click_text_like(driver: WebDriver, texts: list[str], label: str) -> None:
    deadline = time.time() + WAIT_LONG
    xpaths = []
    for text in texts:
        xpaths.extend(
            [
                f"//button[contains(normalize-space(.), '{text}')]",
                f"//a[contains(normalize-space(.), '{text}')]",
                f"//span[contains(normalize-space(.), '{text}')]",
                f"//div[contains(normalize-space(.), '{text}')]",
            ]
        )

    while time.time() < deadline:
        for path in iter_frame_paths(driver):
            try:
                switch_to_frame_path(driver, path)
                for xpath in xpaths:
                    elements = driver.find_elements(By.XPATH, xpath)
                    for element in elements:
                        if element.is_displayed():
                            click_element(driver, element)
                            driver.switch_to.default_content()
                            return
            except WebDriverException:
                continue
            finally:
                driver.switch_to.default_content()
        time.sleep(1)

    save_debug_snapshot(driver, f"missing-{label}")
    raise RuntimeError(f'未找到“{label}”按钮，已在 debug 目录保存现场截图。')


def click_submit_button(driver: WebDriver) -> None:
    click_text_like(driver, ["一键提交", "提交处理"], "一键提交")


def confirm_submit(driver: WebDriver) -> None:
    click_text_like(driver, ["提交", "确定"], "提交")


def click_pending_more(driver: WebDriver) -> None:
    deadline = time.time() + WAIT_LONG
    container_xpaths = [
        "//*[contains(normalize-space(.), '待办授权') and contains(normalize-space(.), '我的关注')]",
        "//*[contains(normalize-space(.), '待办提醒') and contains(normalize-space(.), '刷新')]",
        "//*[contains(normalize-space(.), '待办') and contains(normalize-space(.), '已办') and contains(normalize-space(.), '已阅')]",
        "//*[contains(normalize-space(.), '公文待办') and contains(normalize-space(.), '合同待办')]",
    ]
    local_more_xpaths = [
        ".//a[normalize-space(.)='更多']",
        ".//span[normalize-space(.)='更多']",
        ".//div[normalize-space(.)='更多']",
        ".//*[contains(@class, 'more') and contains(normalize-space(.), '更多')]",
    ]

    while time.time() < deadline:
        for path in iter_frame_paths(driver):
            try:
                switch_to_frame_path(driver, path)
                containers = []
                for xpath in container_xpaths:
                    containers.extend(driver.find_elements(By.XPATH, xpath))
                for container in containers:
                    if not container.is_displayed():
                        continue
                    for xpath in local_more_xpaths:
                        elements = container.find_elements(By.XPATH, xpath)
                        for element in elements:
                            if element.is_displayed():
                                existing_handles = list(driver.window_handles)
                                click_element(driver, element)
                                switched = switch_to_new_window(driver, existing_handles)
                                if switched:
                                    driver.switch_to.default_content()
                                    return
                                time.sleep(1)
                                current_url = (driver.current_url or "").lower()
                                current_title = (driver.title or "").lower()
                                if "todo" in current_url or "待办" in current_title or "工作台" not in current_title:
                                    driver.switch_to.default_content()
                                    return
                                driver.switch_to.default_content()
                                return
            except WebDriverException:
                continue
            finally:
                driver.switch_to.default_content()
        time.sleep(1)

    append_debug_text("pending-more-meta", f"title={driver.title}\nurl={driver.current_url}")
    save_debug_snapshot(driver, "missing-pending-more")
    raise RuntimeError('未找到门户首页待办区域里的“更多”入口，已在 debug 目录保存现场截图。')


def switch_to_new_window(driver: WebDriver, old_handles: list[str], timeout: int = WAIT_MEDIUM) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            current_handles = driver.window_handles
        except WebDriverException:
            time.sleep(0.5)
            continue
        new_handles = [handle for handle in current_handles if handle not in old_handles]
        if new_handles:
            driver.switch_to.window(new_handles[-1])
            return True
        time.sleep(0.5)
    return False


def wait_return_to_list(driver: WebDriver) -> None:
    deadline = time.time() + WAIT_LONG
    last_error = ""
    while time.time() < deadline:
        try:
            wait_for_todo_table(driver, allow_goto=False)
            return
        except Exception as exc:  # noqa: BLE001
            last_error = str(exc)
            time.sleep(1)
    try:
        wait_for_todo_table(driver, allow_goto=True)
        return
    except Exception as exc:  # noqa: BLE001
        last_error = str(exc)
    raise RuntimeError(f"提交后未返回待办列表页: {last_error or '未知错误'}")


def process_one(driver: WebDriver) -> tuple[bool, str]:
    rows = get_target_rows(driver)
    if not rows:
        append_debug_text(
            "page-meta",
            f"title={driver.title}\nurl={driver.current_url}\nhandles={driver.window_handles}",
        )
        save_debug_snapshot(driver, "no-target-rows")
        return False, '当前页没有可处理的“部门落实”单据。'

    frame_path, row = rows[0]
    title = find_row_title(row)
    logging.info("开始处理: %s", title)
    open_row_detail(driver, frame_path, row)
    time.sleep(2)
    save_debug_snapshot(driver, "detail-page")
    click_submit_button(driver)
    time.sleep(1)
    save_debug_snapshot(driver, "after-click-submit")
    confirm_submit(driver)
    wait_return_to_list(driver)
    logging.info("处理完成: %s", title)
    return True, title


def main() -> int:
    args = parse_args()
    setup_logging(Path(__file__).resolve().parent / "logs" / "oa_auto_approve.log")

    driver = None
    try:
        user_data_dir = resolve_user_data_dir(args.browser, args.user_data_dir)
        if not user_data_dir.exists():
            raise RuntimeError(f"未找到浏览器用户数据目录: {user_data_dir}")

        if not args.keep_browser and args.user_data_dir:
            logging.info("正在关闭现有 %s 进程，确保可以复用登录配置。", args.browser)
            force_close_browser_processes(args.browser)
        elif not args.user_data_dir:
            logging.info("使用程序独立的 %s 配置目录启动浏览器。", args.browser)

        driver = build_driver(
            browser=args.browser,
            headless=args.headless,
            user_data_dir=user_data_dir,
            profile_name=args.profile,
        )

        driver.get(LOGIN_URL)
        logging.info("已打开 OA 登录页，请先手工完成登录。")
        if args.manual_login:
            input("登录完成后按回车结束...")
            return 0
        input("请在打开的浏览器窗口中手工登录 OA，登录完成后按回车继续...")

        click_pending_more(driver)
        wait_for_todo_table(driver, allow_goto=False)
        logging.info("待办列表已加载，开始自动审批。")

        processed = 0
        while True:
            if args.limit and processed >= args.limit:
                logging.info("达到处理上限 %s，程序结束。", args.limit)
                break
            has_item, message = process_one(driver)
            if not has_item:
                logging.info(message)
                break
            processed += 1

        logging.info("本次共处理 %s 条。", processed)
        return 0
    except KeyboardInterrupt:
        logging.warning("收到中断，程序结束。")
        return 130
    except Exception as exc:  # noqa: BLE001
        logging.exception("执行失败: %s", exc)
        pause_before_exit(
            "程序执行失败。\n"
            f"{exc}\n"
            "如果报错提到按钮或待办列表未找到，请把 debug 目录里的最新截图发给我。"
        )
        return 1
    finally:
        if driver is not None:
            driver.quit()


if __name__ == "__main__":
    raise SystemExit(main())
