from __future__ import annotations

import argparse
import logging
import socket
import subprocess
import sys
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


LOGIN_URL = "http://oa.hq.cmcc/portal-new/login"
TODO_URL = "http://todo.hq.cmcc/backlog/cmit/web/index/todo?menu=DB&group=province&company=GD&role=ALL"
TARGET_STAGES = ("部门落实", "主办部门内部落实", "阅知部门内部落实")
DEFAULT_HEADLESS = False
WAIT_SHORT = 5
WAIT_MEDIUM = 10
WAIT_LONG = 20
WAIT_IDLE_RETRY = 15
WAIT_TODO_LOAD = 60
WAIT_TODO_TAB_GRACE = 20
DEFAULT_DEBUGGER_ADDRESS = "127.0.0.1:9222"

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


def app_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


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
        description='自动处理 OA 待办列表中“当前环节”为“部门落实”“主办部门内部落实”或“阅知部门内部落实”的单据。'
    )
    parser.add_argument(
        "--browser",
        choices=["chrome", "edge"],
        default="chrome",
        help='指定启动浏览器，默认是 "chrome"。',
    )
    parser.add_argument(
        "--attach-debugger",
        default="",
        help=f'附着到已打开浏览器的 DevTools 地址，例如 "{DEFAULT_DEBUGGER_ADDRESS}"。',
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


def wait_for_debugger_endpoint(debugger_address: str, timeout: int = WAIT_LONG) -> None:
    host, port_text = debugger_address.split(":", 1)
    port = int(port_text)
    deadline = time.time() + timeout
    last_error = ""

    while time.time() < deadline:
        try:
            with socket.create_connection((host, port), timeout=2):
                return
        except OSError as exc:
            last_error = str(exc)
            time.sleep(1)

    raise RuntimeError(f"等待浏览器调试端口 {debugger_address} 超时: {last_error or '端口未就绪'}")


def start_browser_for_attach(browser: str, debugger_address: str) -> None:
    browser_exe = find_browser_exe(browser)
    host, port = debugger_address.split(":", 1)
    user_data_dir = resolve_user_data_dir(browser, "")
    force_close_browser_processes(browser)
    subprocess.Popen(
        [
            str(browser_exe),
            f"--remote-debugging-address={host}",
            f"--remote-debugging-port={port}",
            f"--user-data-dir={user_data_dir}",
            "--profile-directory=Default",
            "--no-first-run",
            "--no-default-browser-check",
            LOGIN_URL,
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    wait_for_debugger_endpoint(debugger_address, timeout=30)


def resolve_user_data_dir(browser: str, cli_value: str) -> Path:
    if cli_value:
        return Path(cli_value)

    # Use an isolated profile by default so old Chrome versions start reliably
    # and do not depend on the user's system browser profile state.
    app_dir = app_base_dir()
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


def attach_to_debugger(*, browser: str, debugger_address: str) -> WebDriver:
    wait_for_debugger_endpoint(debugger_address, timeout=5)
    chromedriver_exe = find_chromedriver()
    options = Options()
    options.add_experimental_option("debuggerAddress", debugger_address)
    if browser == "edge":
        browser_exe = find_browser_exe(browser)
        options.binary_location = str(browser_exe)
    service = Service(executable_path=str(chromedriver_exe))
    driver = ChromeDriver(service=service, options=options)
    driver.set_page_load_timeout(WAIT_LONG)
    return driver


def save_debug_snapshot(driver: WebDriver, name: str) -> None:
    debug_dir = app_base_dir() / "debug"
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
    debug_dir = app_base_dir() / "debug"
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


def current_page_meta(driver: WebDriver) -> str:
    try:
        title = driver.title
    except WebDriverException:
        title = ""
    try:
        url = driver.current_url
    except WebDriverException:
        url = ""
    text = normalize_cell_text(body_text(driver))[:2000]
    return f"title={title}\nurl={url}\ntext={text}"


def wait_for_loading_complete(driver: WebDriver, timeout: int = WAIT_TODO_LOAD) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            loading_masks = driver.find_elements(
                By.XPATH,
                "//*[contains(@class, 'el-loading-mask') or contains(@class, 'is-loading') or contains(normalize-space(.), '加载中')]",
            )
            visible_masks = [mask for mask in loading_masks if mask.is_displayed()]
            if not visible_masks:
                return
        except WebDriverException:
            return
        time.sleep(1)


def wait_for_todo_table(driver: WebDriver, allow_goto: bool = True) -> None:
    if allow_goto:
        driver.get(TODO_URL)
    wait_for_loading_complete(driver, timeout=WAIT_TODO_LOAD)
    deadline = time.time() + WAIT_TODO_LOAD
    markers = ["公文待办", "当前环节", "标题", "接收日期", "每页", "共"]

    while time.time() < deadline:
        for path in iter_frame_paths(driver):
            try:
                switch_to_frame_path(driver, path)
                text = body_text(driver)
                if any(marker in text for marker in markers):
                    driver.switch_to.default_content()
                    return
                element_tables = driver.find_elements(By.XPATH, "//table[contains(@class, 'el-table__body')]")
                if element_tables:
                    headers = driver.find_elements(
                        By.XPATH,
                        "//table[contains(@class, 'el-table__header')]//*[self::th or self::td]//div[contains(@class, 'cell')]",
                    )
                    header_texts = [normalize_cell_text(header.text) for header in headers if normalize_cell_text(header.text)]
                    if "标题" in header_texts and "当前环节" in header_texts:
                        driver.switch_to.default_content()
                        return
                component_rows = driver.find_elements(
                    By.XPATH,
                    "//*[contains(@class, 'el-table__row')]//*[contains(@class, 'activityName')]"
                    + "/*[" + stage_xpath_predicate() + "]",
                )
                if component_rows:
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

    append_debug_text("todo-detect-failed-meta", current_page_meta(driver))
    save_debug_snapshot(driver, "todo-detect-failed")
    if is_login_page(driver):
        raise TimeoutException("未识别到待办列表页标记，当前仍停留在登录页，可能登录状态未保留。")
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


def click_submit_button_by_geometry(driver: WebDriver, row) -> bool:
    try:
        clicked = driver.execute_script(
            """
            const row = arguments[0];
            if (!row) return false;
            const rowRect = row.getBoundingClientRect();
            const rowMidY = rowRect.top + rowRect.height / 2;
            const rowRightX = rowRect.right;

            const candidates = Array.from(document.querySelectorAll('button, a, span, div'))
              .filter((el) => {
                const text = (el.innerText || el.textContent || '').trim();
                if (text !== '提交') return false;
                const style = window.getComputedStyle(el);
                if (style.visibility === 'hidden' || style.display === 'none') return false;
                const rect = el.getBoundingClientRect();
                if (rect.width <= 0 || rect.height <= 0) return false;
                if (rect.right <= rowRightX) return false;
                return true;
              })
              .map((el) => {
                const rect = el.getBoundingClientRect();
                const midY = rect.top + rect.height / 2;
                const score = Math.abs(midY - rowMidY) + Math.max(0, rowRightX - rect.left) * 0.01;
                return { el, rect, score };
              })
              .sort((a, b) => a.score - b.score);

            const best = candidates[0];
            if (!best) return false;

            best.el.scrollIntoView({ block: 'center', inline: 'center' });
            best.el.click();
            return true;
            """,
            row,
        )
        return bool(clicked)
    except WebDriverException:
        return False


def normalize_cell_text(text: str) -> str:
    return " ".join((text or "").split())


def extract_table_headers(table) -> list[str]:
    header_rows = table.find_elements(By.XPATH, ".//thead/tr")
    if not header_rows:
        header_rows = table.find_elements(By.XPATH, ".//tr[th]")
    if not header_rows:
        return []

    headers: list[str] = []
    for cell in header_rows[0].find_elements(By.XPATH, "./th|./td"):
        headers.append(normalize_cell_text(cell.text))
    return headers


def find_column_index(headers: list[str], target: str) -> int:
    for index, header in enumerate(headers):
        if normalize_cell_text(header) == target:
            return index
    return -1


def stage_xpath_predicate() -> str:
    return " or ".join([f"normalize-space(.)='{stage}'" for stage in TARGET_STAGES])


def find_clickable_title_in_row(row):
    try:
        exact_targets = row.find_elements(
            By.XPATH,
            ".//*[contains(@class, 'item-title--click') or contains(@class, 'content-container') or contains(@class, 'itemTitle')]",
        )
        for target in exact_targets:
            if normalize_cell_text(target.text):
                return target
    except WebDriverException:
        pass

    try:
        exact_links = row.find_elements(
            By.XPATH,
            ".//*[contains(@class, 'link') and normalize-space(.)!='']",
        )
        for target in exact_links:
            if normalize_cell_text(target.text):
                return target
    except WebDriverException:
        pass

    try:
        links = row.find_elements(By.TAG_NAME, "a")
        for link in links:
            if normalize_cell_text(link.text):
                return link
    except WebDriverException:
        pass

    try:
        title_candidates = row.find_elements(
            By.XPATH,
            ".//*[self::span or self::div][normalize-space(.)!='' "
            "and not(contains(normalize-space(.), '部门落实')) "
            "and not(contains(normalize-space(.), '主办部门内部落实')) "
            "and not(contains(normalize-space(.), '阅知部门内部落实'))]",
        )
        for candidate in title_candidates:
            if normalize_cell_text(candidate.text):
                return candidate
    except WebDriverException:
        pass

    return None


def get_target_rows_from_generic_layout(
    driver: WebDriver,
    path: list[int],
    excluded_titles: set[str] | None = None,
) -> list[tuple[list[int], object, int]]:
    matches: list[tuple[list[int], object, int]] = []
    excluded_titles = excluded_titles or set()
    stage_elements = driver.find_elements(
        By.XPATH,
        "//*[self::td or self::div or self::span][" + stage_xpath_predicate() + "]",
    )

    seen_ids: set[str] = set()
    for stage_element in stage_elements:
        try:
            row = stage_element.find_element(
                By.XPATH,
                "./ancestor::*[@role='row' or self::tr or contains(@class, 'row') or contains(@class, 'table-row')][1]",
            )
        except WebDriverException:
            continue

        try:
            row_id = row.id
        except WebDriverException:
            continue
        if row_id in seen_ids:
            continue
        seen_ids.add(row_id)

        title_target = find_clickable_title_in_row(row)
        title_text = normalize_cell_text(find_row_title(row))
        if title_target is not None and title_text not in excluded_titles:
            matches.append((path, row, -1))

    return matches


def get_target_rows(driver: WebDriver, excluded_titles: set[str] | None = None) -> list[tuple[list[int], object, int]]:
    matches: list[tuple[list[int], object, int]] = []
    debug_lines: list[str] = []
    excluded_titles = excluded_titles or set()

    for path in iter_frame_paths(driver):
        try:
            switch_to_frame_path(driver, path)
            tables = driver.find_elements(By.TAG_NAME, "table")
            for table_index, table in enumerate(tables):
                headers = extract_table_headers(table)
                if not headers:
                    continue

                title_index = find_column_index(headers, "标题")
                stage_index = find_column_index(headers, "当前环节")
                if title_index < 0 or stage_index < 0:
                    continue

                rows = table.find_elements(By.XPATH, ".//tbody/tr")
                if not rows:
                    rows = table.find_elements(By.XPATH, ".//tr[td]")

                for row_index, row in enumerate(rows):
                    cells = row.find_elements(By.XPATH, "./td")
                    if not cells or max(title_index, stage_index) >= len(cells):
                        continue

                    row_text = normalize_cell_text(row.text)
                    if row_text:
                        debug_lines.append(
                            f"path={path} table={table_index} row={row_index} text={row_text[:500]}"
                        )

                    stage_text = normalize_cell_text(cells[stage_index].text)
                    title_text = normalize_cell_text(cells[title_index].text)
                    if stage_text in TARGET_STAGES and title_text and title_text not in excluded_titles:
                        matches.append((path, row, title_index))

            if not matches:
                generic_matches = get_target_rows_from_generic_layout(driver, path, excluded_titles)
                for match in generic_matches:
                    try:
                        debug_lines.append(
                            f"path={path} generic-row text={normalize_cell_text(match[1].text)[:500]}"
                        )
                    except WebDriverException:
                        pass
                matches.extend(generic_matches)
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


def open_row_detail(driver: WebDriver, frame_path: list[int], row, title_index: int) -> None:
    switch_to_frame_path(driver, frame_path)
    try:
        cells = row.find_elements(By.XPATH, "./td")
        if title_index < len(cells):
            title_cell = cells[title_index]
            exact_targets = title_cell.find_elements(
                By.XPATH,
                ".//*[contains(@class, 'item-title--click') or contains(@class, 'content-container') or contains(@class, 'link')]",
            )
            for target in exact_targets:
                if normalize_cell_text(target.text):
                    click_element(driver, target)
                    return

            links = title_cell.find_elements(By.TAG_NAME, "a")
            for link in links:
                if normalize_cell_text(link.text):
                    click_element(driver, link)
                    return
            if normalize_cell_text(title_cell.text):
                click_element(driver, title_cell)
                return

        if title_index < 0:
            title_target = find_clickable_title_in_row(row)
            if title_target is not None:
                click_element(driver, title_target)
                return

        links = row.find_elements(By.TAG_NAME, "a")
        for link in links:
            if normalize_cell_text(link.text):
                click_element(driver, link)
                return
        for cell in cells:
            if normalize_cell_text(cell.text):
                click_element(driver, cell)
                return
    finally:
        driver.switch_to.default_content()
    raise RuntimeError("未找到可点击的待办标题。")


def open_row_detail_and_switch(driver: WebDriver, frame_path: list[int], row, title_index: int) -> None:
    old_handles = list(driver.window_handles)
    open_row_detail(driver, frame_path, row, title_index)
    if switch_to_new_window(driver, old_handles, timeout=WAIT_LONG):
        return
    raise RuntimeError("点击待办标题后未检测到新打开的详情标签页。")


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
    deadline = time.time() + WAIT_LONG
    toolbar_xpaths = [
        "//*[contains(@class, 'toolbar')]",
        "//*[contains(@class, 'tool-bar')]",
        "//*[contains(@class, 'header')]",
        "//*[contains(@class, 'nav')]",
        "//*[contains(@class, 'action')]",
        "//body",
    ]
    target_xpaths = [
        ".//button[normalize-space(.)='一键提交']",
        ".//a[normalize-space(.)='一键提交']",
        ".//span[normalize-space(.)='一键提交']/ancestor::*[self::button or self::a or self::div][1]",
        ".//*[contains(@class, 'btn') and normalize-space(.)='一键提交']",
    ]

    while time.time() < deadline:
        for path in iter_frame_paths(driver):
            try:
                switch_to_frame_path(driver, path)
                for toolbar_xpath in toolbar_xpaths:
                    for container in driver.find_elements(By.XPATH, toolbar_xpath):
                        if not container.is_displayed():
                            continue
                        for target_xpath in target_xpaths:
                            for element in container.find_elements(By.XPATH, target_xpath):
                                if element.is_displayed() and normalize_cell_text(element.text) == "一键提交":
                                    click_element(driver, element)
                                    driver.switch_to.default_content()
                                    return
            except WebDriverException:
                continue
            finally:
                driver.switch_to.default_content()
        time.sleep(1)

    save_debug_snapshot(driver, "missing-一键提交")
    raise RuntimeError('未在详情页导航栏中找到“一键提交”按钮，已在 debug 目录保存现场截图。')


def cdp_click_dialog_submit(driver: WebDriver) -> tuple[bool, str]:
    expression = r"""
(() => {
  const isVisible = (el) => {
    if (!el) return false;
    const doc = el.ownerDocument || document;
    const view = doc.defaultView || window;
    const style = view.getComputedStyle(el);
    if (style.display === 'none' || style.visibility === 'hidden' || style.opacity === '0') return false;
    const rect = el.getBoundingClientRect();
    return rect.width > 0 && rect.height > 0;
  };

  const textOf = (el) => ((el?.innerText || el?.textContent || '').replace(/\s+/g, ' ').trim());

  const rectOf = (el) => el ? el.getBoundingClientRect() : null;

  const clickableOf = (el) => {
    if (!el) return null;
    return el.closest('button, a, [role="button"], .el-button, .el-link, .ant-btn') || el;
  };

  const clickEl = (el) => {
    const clickable = clickableOf(el);
    if (!clickable || !isVisible(clickable)) return false;
    clickable.scrollIntoView({ block: 'center', inline: 'center' });
    const rect = rectOf(clickable);
    if (!rect || rect.width <= 0 || rect.height <= 0) return false;
    const centerX = Math.max(rect.left + 1, Math.min(rect.right - 1, rect.left + rect.width / 2));
    const centerY = Math.max(rect.top + 1, Math.min(rect.bottom - 1, rect.top + rect.height / 2));
    const doc = clickable.ownerDocument || document;
    const view = doc.defaultView || window;
    const topEl = doc.elementFromPoint(centerX, centerY);
    const target = clickableOf(topEl) || clickable;
    target.focus?.();
    ['pointerover', 'pointerenter', 'mouseover', 'mouseenter', 'pointerdown', 'mousedown', 'pointerup', 'mouseup', 'click'].forEach((type) => {
      const EventCtor = type.startsWith('pointer') ? (view.PointerEvent || view.MouseEvent) : view.MouseEvent;
      target.dispatchEvent(new EventCtor(type, {
        bubbles: true,
        cancelable: true,
        composed: true,
        pointerId: 1,
        isPrimary: true,
        button: 0,
        buttons: 1,
        clientX: centerX,
        clientY: centerY,
        view,
      }));
    });
    if (typeof target.click === 'function') target.click();
    return true;
  };

  const docEntries = [];
  const collectDocs = (doc, depth = 0) => {
    if (!doc || depth > 4) return;
    docEntries.push(doc);
    const frames = Array.from(doc.querySelectorAll('iframe, frame'));
    for (const frame of frames) {
      try {
        if (frame.contentDocument) collectDocs(frame.contentDocument, depth + 1);
      } catch (error) {
        // Ignore cross-origin frames.
      }
    }
  };
  collectDocs(document);

  const dialogEntries = [];
  for (const doc of docEntries) {
    const dialogs = Array.from(doc.querySelectorAll('.el-dialog, [role="dialog"], .dialog, .modal'))
      .filter((el) => isVisible(el) && (textOf(el).includes('下一步操作') || textOf(el).includes('一键提交')));
    if (dialogs.length) {
      dialogEntries.push(...dialogs.map((el) => ({ el, doc })));
    }
  }

  const dialog = (dialogEntries[0] || { el: document.body, doc: document });
  const root = dialog.el;
  const rootDoc = dialog.doc;
  const rootRect = rectOf(root) || { left: 0, right: rootDoc.defaultView?.innerWidth || window.innerWidth };

  const cardBodies = Array.from(root.querySelectorAll('.jdf-onekey-submit-config-dialog .jdf-card__body, .jdf-onekey-submit-config .jdf-card__body, .jdf-card__body'))
    .filter((card) => isVisible(card));
  const targetCard = cardBodies.find((card) => {
    const cols = Array.from(card.querySelectorAll('.jdf-card-table__body > .jdf-card-table__cell'));
    if (cols[2] && textOf(cols[2]) === '结束办理') return true;
    return textOf(card).includes('结束办理');
  });
  if (targetCard) {
    const targetButton = Array.from(targetCard.querySelectorAll('button.onekey-submit-button, .onekey-submit-button, button, [role="button"]'))
      .map((el) => clickableOf(el))
      .find((el) => !!el && isVisible(el) && textOf(el).includes('提交'));
    if (targetButton && clickEl(targetButton)) {
      return {
        ok: true,
        mode: 'card-body-onekey-submit',
        cardCount: cardBodies.length,
        cardText: textOf(targetCard).slice(0, 500),
        buttonText: textOf(targetButton),
      };
    }
    return {
      ok: false,
      reason: 'card-target-found-but-button-not-clickable',
      cardCount: cardBodies.length,
      cardText: textOf(targetCard).slice(0, 500),
    };
  }

  const rowCandidates = Array.from(root.querySelectorAll('tbody tr, .el-table__row, tr'))
    .filter((row) => isVisible(row) && textOf(row).includes('结束办理'));
  const targetRows = rowCandidates
    .map((row) => ({ row, rect: rectOf(row), text: textOf(row), doc: row.ownerDocument || rootDoc }))
    .filter((item) => item.rect && item.rect.width > 0 && item.rect.height > 0)
    .sort((a, b) => a.rect.top - b.rect.top);

  if (!targetRows.length) {
    return {
      ok: false,
      reason: 'target-row-not-found',
      docCount: docEntries.length,
      dialogCount: dialogEntries.length,
      rowCount: rowCandidates.length,
      dialogText: textOf(root).slice(0, 1200),
    };
  }

  const target = targetRows[0];
  const rowMidY = target.rect.top + target.rect.height / 2;
  const rightBoundary = Math.max(target.rect.right, rootRect.left + (rootRect.right - rootRect.left) * 0.72);

  const rawCandidates = [];
  for (const doc of docEntries) {
    for (const node of Array.from(doc.querySelectorAll('button, a, [role="button"], .el-button, .el-link, span, div'))) {
      const clickable = clickableOf(node);
      if (!clickable || rawCandidates.includes(clickable)) continue;
      rawCandidates.push(clickable);
    }
  }

  const submitCandidates = rawCandidates
    .filter((el) => {
      if (!isVisible(el)) return false;
      const text = textOf(el);
      if (!text.includes('提交')) return false;
      const rect = rectOf(el);
      if (!rect || rect.width <= 0 || rect.height <= 0) return false;
      const verticallyNear = Math.abs((rect.top + rect.height / 2) - rowMidY) <= Math.max(target.rect.height * 1.2, 60);
      const horizontallyRight = rect.left >= rightBoundary || rect.right >= rootRect.right - 120;
      return verticallyNear || horizontallyRight;
    })
    .map((el) => {
      const rect = rectOf(el);
      const centerY = rect.top + rect.height / 2;
      const score = Math.abs(centerY - rowMidY) + (rect.left < rightBoundary ? 10000 : 0);
      return { el, rect, score, text: textOf(el), owner: el.ownerDocument === rootDoc ? 'root' : 'frame' };
    })
    .sort((a, b) => a.score - b.score);

  if (submitCandidates[0] && clickEl(submitCandidates[0].el)) {
    return {
      ok: true,
      mode: 'right-side-nearest-submit',
      rowText: target.text,
      buttonText: submitCandidates[0].text,
      buttonOwner: submitCandidates[0].owner,
      score: submitCandidates[0].score,
      buttonLeft: submitCandidates[0].rect.left,
      buttonTop: submitCandidates[0].rect.top,
    };
  }

  return {
    ok: false,
    reason: 'target-row-found-but-submit-not-clickable',
    rowText: target.text,
    docCount: docEntries.length,
    dialogCount: dialogEntries.length,
    submitCount: submitCandidates.length,
    dialogText: textOf(root).slice(0, 1200),
  };
})()
"""
    try:
        result = driver.execute_cdp_cmd(
            "Runtime.evaluate",
            {
                "expression": expression,
                "returnByValue": True,
                "awaitPromise": True,
            },
        )
        value = (result or {}).get("result", {}).get("value", {})
        if isinstance(value, dict):
            return bool(value.get("ok")), str(value)
        return False, str(value)
    except WebDriverException as exc:
        return False, f"cdp-error: {exc}"


def confirm_submit(driver: WebDriver) -> None:
    deadline = time.time() + WAIT_LONG

    while time.time() < deadline:
        ok, detail = cdp_click_dialog_submit(driver)
        append_debug_text("dialog-submit-attempt", detail)
        if ok:
            return
        time.sleep(1)

    save_debug_snapshot(driver, "missing-dialog-submit")
    raise RuntimeError('未在弹窗中找到“下一步操作”为“结束办理”的提交按钮，已在 debug 目录保存现场截图。')


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


def score_todo_tab(driver: WebDriver, handle: str) -> int:
    try:
        driver.switch_to.window(handle)
        current_url = (driver.current_url or "").lower()
        current_title = normalize_cell_text(driver.title).lower()
        current_text = normalize_cell_text(body_text(driver))[:1000].lower()
    except WebDriverException:
        return -1

    score = 0
    todo_url = TODO_URL.lower()
    if current_url == todo_url:
        score += 200
    elif current_url.startswith(todo_url):
        score += 180
    elif "todo.hq.cmcc/backlog/cmit/web/index/todo" in current_url:
        score += 160
    elif "todo.hq.cmcc" in current_url:
        score += 120

    if current_title == "待办工作":
        score += 120
    elif "待办工作" in current_title:
        score += 100
    elif "待办" in current_title:
        score += 30

    if "当前环节" in current_text and "标题" in current_text:
        score += 20
    if "公文待办" in current_text or "每页" in current_text:
        score += 20

    return score


def find_best_todo_tab_handle(driver: WebDriver, preferred_handle: str | None = None) -> str | None:
    try:
        handles = list(driver.window_handles)
    except WebDriverException:
        return None
    if not handles:
        return None

    best_handle = None
    best_score = -1
    for handle in handles:
        score = score_todo_tab(driver, handle)
        if score < 0:
            continue
        if preferred_handle and handle == preferred_handle and score >= 120:
            score += 50
        if score > best_score:
            best_score = score
            best_handle = handle

    if best_score < 120:
        return None
    return best_handle


def ensure_todo_tab(driver: WebDriver, preferred_handle: str | None = None) -> str:
    handle = find_best_todo_tab_handle(driver, preferred_handle)
    if not handle:
        raise RuntimeError("未找到可用的“待办工作”标签页。")
    driver.switch_to.window(handle)
    return handle


def switch_to_existing_todo_tab(driver: WebDriver, preferred_handle: str | None = None) -> bool:
    handle = find_best_todo_tab_handle(driver, preferred_handle)
    if not handle:
        return False
    try:
        driver.switch_to.window(handle)
    except WebDriverException:
        return False
    return True


def is_login_page(driver: WebDriver) -> bool:
    try:
        current_url = (driver.current_url or "").lower()
    except WebDriverException:
        return False
    return "/portal-new/login" in current_url


def wait_for_login_completion(driver: WebDriver, timeout: int = 600, preferred_todo_handle: str | None = None) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            if switch_to_existing_todo_tab(driver, preferred_todo_handle):
                return True
            if not is_login_page(driver):
                return True
        except WebDriverException:
            pass
        time.sleep(1)
    return False


def wait_for_existing_todo_tab(driver: WebDriver, timeout: int = 300, preferred_todo_handle: str | None = None) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if switch_to_existing_todo_tab(driver, preferred_todo_handle):
            return True
        time.sleep(1)
    return False


def wait_return_to_list(driver: WebDriver, todo_handle: str | None = None) -> str:
    deadline = time.time() + WAIT_LONG
    last_error = ""

    while time.time() < deadline:
        try:
            active_handle = ensure_todo_tab(driver, todo_handle)
            wait_for_todo_table(driver, allow_goto=False)
            return active_handle
        except Exception as exc:  # noqa: BLE001
            last_error = str(exc)
            time.sleep(1)
    try:
        active_handle = ensure_todo_tab(driver, todo_handle)
        wait_for_todo_table(driver, allow_goto=True)
        return active_handle
    except Exception as exc:  # noqa: BLE001
        last_error = str(exc)
    raise RuntimeError(f"提交后未返回待办列表页: {last_error or '未知错误'}")


def refresh_todo_list(driver: WebDriver, todo_handle: str | None = None) -> str:
    active_handle = ensure_todo_tab(driver, todo_handle)
    logging.info("已返回待办页，正在刷新列表。")
    try:
        driver.refresh()
    except WebDriverException:
        driver.get(TODO_URL)
    wait_for_todo_table(driver, allow_goto=False)
    time.sleep(2)
    return ensure_todo_tab(driver, active_handle)


def process_one(
    driver: WebDriver,
    excluded_titles: set[str] | None = None,
    todo_handle: str | None = None,
) -> tuple[bool, str, str | None]:
    active_todo_handle = ensure_todo_tab(driver, todo_handle)
    rows = get_target_rows(driver, excluded_titles)
    if not rows:
        append_debug_text(
            "page-meta",
            f"title={driver.title}\nurl={driver.current_url}\nhandles={driver.window_handles}",
        )
        save_debug_snapshot(driver, "no-target-rows")
        return False, '当前页没有可处理的目标单据。', active_todo_handle

    frame_path, row, title_index = rows[0]
    title = find_row_title(row)
    logging.info("开始处理: %s", title)
    open_row_detail_and_switch(driver, frame_path, row, title_index)
    time.sleep(2)
    save_debug_snapshot(driver, "detail-page")
    click_submit_button(driver)
    time.sleep(1)
    save_debug_snapshot(driver, "after-click-submit")
    confirm_submit(driver)
    active_todo_handle = wait_return_to_list(driver, active_todo_handle)
    active_todo_handle = refresh_todo_list(driver, active_todo_handle)
    logging.info("处理完成: %s", title)
    return True, title, active_todo_handle


def collect_visible_target_titles(driver: WebDriver, todo_handle: str | None = None) -> tuple[set[str], str]:
    active_todo_handle = ensure_todo_tab(driver, todo_handle)
    titles: set[str] = set()
    for path, row, _title_index in get_target_rows(driver):
        try:
            title = normalize_cell_text(find_row_title(row))
        except WebDriverException:
            continue
        if title:
            titles.add(title)
    return titles, active_todo_handle


def main() -> int:
    args = parse_args()
    setup_logging(app_base_dir() / "logs" / "oa_auto_approve.log")

    driver = None
    todo_handle: str | None = None
    try:
        if args.attach_debugger:
            logging.info("正在附着到已打开的浏览器调试端口 %s。", args.attach_debugger)
            try:
                driver = attach_to_debugger(browser=args.browser, debugger_address=args.attach_debugger)
            except Exception:
                logging.info("未检测到可附着的浏览器，正在自动启动 %s。", args.browser)
                start_browser_for_attach(args.browser, args.attach_debugger)
                driver = attach_to_debugger(browser=args.browser, debugger_address=args.attach_debugger)
            print("请在打开的浏览器中手工登录 OA；登录完成后程序会自动进入待办页。")
            if not wait_for_login_completion(driver, preferred_todo_handle=todo_handle):
                raise RuntimeError("等待登录完成超时，请确认你已成功登录 OA。")
            logging.info("已检测到登录完成，准备进入待办页。当前页面信息：%s", current_page_meta(driver).replace("\n", " | "))
            if wait_for_existing_todo_tab(driver, timeout=WAIT_TODO_TAB_GRACE, preferred_todo_handle=todo_handle):
                logging.info("检测到你已手工打开待办页，准备直接接管。")
                wait_for_todo_table(driver, allow_goto=False)
                todo_handle = ensure_todo_tab(driver, todo_handle)
            else:
                logging.info("未检测到手工打开的待办页，程序将自动进入待办页。")
                wait_for_todo_table(driver, allow_goto=True)
                todo_handle = ensure_todo_tab(driver, todo_handle)
        else:
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
            driver.get(TODO_URL)
            wait_for_todo_table(driver, allow_goto=False)
            todo_handle = ensure_todo_tab(driver, todo_handle)
        logging.info("待办列表已加载，开始自动审批。")

        processed = 0
        excluded_titles: set[str] = set()
        while True:
            if args.limit and processed >= args.limit:
                logging.info("达到处理上限 %s，程序结束。", args.limit)
                break
            try:
                visible_titles, todo_handle = collect_visible_target_titles(driver, todo_handle)
                excluded_titles.intersection_update(visible_titles)
            except Exception:  # noqa: BLE001
                pass
            has_item, message, todo_handle = process_one(driver, excluded_titles, todo_handle)
            if not has_item:
                logging.info("%s %s 秒后继续监控。", message, WAIT_IDLE_RETRY)
                time.sleep(WAIT_IDLE_RETRY)
                try:
                    todo_handle = wait_return_to_list(driver, todo_handle)
                except Exception:  # noqa: BLE001
                    wait_for_todo_table(driver, allow_goto=True)
                    todo_handle = ensure_todo_tab(driver, todo_handle)
                continue
            processed += 1
            excluded_titles.add(message)

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
