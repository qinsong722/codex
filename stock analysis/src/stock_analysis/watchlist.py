from __future__ import annotations

import csv
import json
import re
import subprocess
import time
from pathlib import Path

from pywinauto import Desktop

from .config import Settings
from .models import WatchlistItem


WATCHLIST_CONTAINER_TYPES = {"DataGrid", "Table", "List", "Pane"}
WATCHLIST_ROW_TYPES = {"DataItem", "ListItem", "Custom"}


def load_watchlist(settings: Settings) -> list[WatchlistItem]:
    source = settings.watchlist_source
    if source == "csv":
        return _load_csv(settings.watchlist_file)
    if source == "json":
        return _load_json(settings.watchlist_file)
    if source == "manual":
        return [WatchlistItem(symbol=symbol, name=symbol) for symbol in settings.manual_symbols]
    if source == "clipboard":
        return _load_clipboard(settings.clipboard_encoding)
    if source == "csc_app":
        return _load_csc_app(settings)
    if source == "csc_files":
        return _load_csc_files(settings)
    raise ValueError(f"Unsupported watchlist source: {source}")


def _load_csv(path: Path) -> list[WatchlistItem]:
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        return [
            WatchlistItem(
                symbol=(row.get("symbol") or row.get("code") or "").strip(),
                name=(row.get("name") or row.get("symbol") or "").strip() or None,
            )
            for row in reader
            if (row.get("symbol") or row.get("code") or "").strip()
        ]


def _load_json(path: Path) -> list[WatchlistItem]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return [
        WatchlistItem(
            symbol=str(item["symbol"]).strip(),
            name=str(item.get("name", item["symbol"])).strip(),
        )
        for item in raw
        if str(item.get("symbol", "")).strip()
    ]


def _load_clipboard(clipboard_encoding: str) -> list[WatchlistItem]:
    text = _read_clipboard_text(clipboard_encoding)
    items = _parse_watchlist_text(text)
    if not items:
        raise ValueError("Clipboard does not contain recognizable stock codes")
    return items


def _load_csc_app(settings: Settings) -> list[WatchlistItem]:
    window = _connect_broker_window(settings.broker_window_title)
    _focus_watchlist(window, settings.watchlist_tab_text)
    items = _extract_from_ui_tree(window)
    if items:
        return items

    text = _copy_watchlist_via_shortcut(window, settings.watchlist_copy_shortcut, settings.clipboard_encoding)
    items = _parse_watchlist_text(text)
    if items:
        return items
    raise ValueError("Could not extract watchlist from the broker app. Try running ui inspector first.")


def _load_csc_files(settings: Settings) -> list[WatchlistItem]:
    if not settings.broker_data_dir:
        raise ValueError("BROKER_DATA_DIR is required when WATCHLIST_SOURCE=csc_files")
    if not settings.broker_data_dir.exists():
        raise ValueError(f"Broker data directory does not exist: {settings.broker_data_dir}")

    candidates = _discover_watchlist_files(
        settings.broker_data_dir,
        settings.broker_watchlist_patterns,
    )
    if not candidates:
        raise ValueError(f"No candidate watchlist files found under: {settings.broker_data_dir}")

    best_items: list[WatchlistItem] = []
    best_path: Path | None = None
    for path in candidates:
        items = _parse_watchlist_file(path)
        if len(items) > len(best_items):
            best_items = items
            best_path = path

    if not best_items:
        raise ValueError(
            f"Found candidate files under {settings.broker_data_dir}, but none contained recognizable stock codes"
        )
    print(f"Using watchlist file: {best_path}")
    return best_items


def _connect_broker_window(title_keyword: str):
    windows = Desktop(backend="uia").windows()
    title_keyword = title_keyword.strip().lower()
    matches = [
        window
        for window in windows
        if title_keyword in (window.window_text() or "").lower()
    ]
    if not matches:
        raise ValueError(f"No desktop window contains title keyword: {title_keyword}")
    window = matches[0]
    wrapper = window.wrapper_object()
    try:
        wrapper.restore()
    except Exception:
        pass
    wrapper.set_focus()
    time.sleep(0.5)
    return wrapper


def _focus_watchlist(window, tab_text: str) -> None:
    keyword = tab_text.strip()
    for control in window.descendants():
        try:
            text = control.window_text().strip()
            friendly = control.friendly_class_name()
        except Exception:
            continue
        if keyword and keyword in text and friendly in {"TabItem", "Button", "Text", "Hyperlink"}:
            try:
                control.click_input()
                time.sleep(0.8)
                return
            except Exception:
                continue


def _extract_from_ui_tree(window) -> list[WatchlistItem]:
    best: list[WatchlistItem] = []
    for control in window.descendants():
        try:
            element_info = control.element_info
            control_type = getattr(element_info, "control_type", "")
        except Exception:
            continue
        if control_type not in WATCHLIST_CONTAINER_TYPES:
            continue

        items = _parse_items_from_container(control)
        if len(items) > len(best):
            best = items
    return best


def _parse_items_from_container(container) -> list[WatchlistItem]:
    rows = []
    try:
        for child in container.descendants():
            control_type = getattr(child.element_info, "control_type", "")
            if control_type in WATCHLIST_ROW_TYPES:
                rows.append(child)
    except Exception:
        return []

    items: list[WatchlistItem] = []
    seen: set[str] = set()
    for row in rows:
        parts = []
        try:
            texts = row.texts()
            parts.extend(text for text in texts if text and text.strip())
        except Exception:
            pass
        try:
            row_text = row.window_text()
            if row_text:
                parts.append(row_text)
        except Exception:
            pass
        merged = " | ".join(_unique_strings(parts))
        symbol = _extract_symbol(merged)
        if not symbol or symbol in seen:
            continue
        name = _extract_name(merged, symbol)
        items.append(WatchlistItem(symbol=symbol, name=name or symbol))
        seen.add(symbol)
    return items


def _copy_watchlist_via_shortcut(window, shortcuts: list[str], clipboard_encoding: str) -> str:
    window.set_focus()
    time.sleep(0.3)
    for key in shortcuts:
        window.type_keys(key, set_foreground=True)
        time.sleep(0.2)
    time.sleep(0.5)
    return _read_clipboard_text(clipboard_encoding)


def _read_clipboard_text(clipboard_encoding: str) -> str:
    completed = subprocess.run(
        ["powershell", "-NoProfile", "-Command", "Get-Clipboard -Raw"],
        capture_output=True,
        check=True,
    )
    return _decode_clipboard(completed.stdout, clipboard_encoding)


def _decode_clipboard(raw: bytes, clipboard_encoding: str) -> str:
    if clipboard_encoding != "auto":
        return raw.decode(clipboard_encoding, errors="ignore").strip()
    for encoding in ("utf-8", "gb18030", "utf-16le"):
        try:
            return raw.decode(encoding).strip()
        except UnicodeDecodeError:
            continue
    return raw.decode(errors="ignore").strip()


def _parse_watchlist_text(text: str) -> list[WatchlistItem]:
    items: list[WatchlistItem] = []
    seen: set[str] = set()
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        symbol = _extract_symbol(stripped)
        if not symbol or symbol in seen:
            continue
        name = _extract_name(stripped, symbol)
        items.append(WatchlistItem(symbol=symbol, name=name or symbol))
        seen.add(symbol)
    return items


def _discover_watchlist_files(base_dir: Path, patterns: list[str]) -> list[Path]:
    name_keywords = ("自选", "zxg", "blk", "ebk", "watch", "optional", "favor", "stock")
    candidates: list[Path] = []
    for pattern in patterns:
        for path in base_dir.rglob(pattern):
            lowered = path.name.lower()
            if any(keyword in lowered for keyword in name_keywords):
                candidates.append(path)
    return sorted(set(candidates), key=lambda item: (len(item.parts), item.name.lower()))


def _parse_watchlist_file(path: Path) -> list[WatchlistItem]:
    if path.suffix.lower() in {".blk", ".ebk"}:
        items = _parse_tdx_block_file(path)
        if items:
            return items
    for encoding in ("utf-8", "utf-8-sig", "gb18030", "utf-16le", "ansi"):
        try:
            text = path.read_text(encoding=encoding, errors="ignore")
            items = _parse_watchlist_text(text)
            if items:
                return items
        except LookupError:
            continue
        except OSError:
            return []
    return []


def _parse_tdx_block_file(path: Path) -> list[WatchlistItem]:
    items: list[WatchlistItem] = []
    seen: set[str] = set()
    for encoding in ("ascii", "utf-8", "gb18030"):
        try:
            lines = path.read_text(encoding=encoding, errors="ignore").splitlines()
            break
        except OSError:
            return []
    else:
        return []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        match = re.fullmatch(r"(\d)(\d{6})", stripped)
        if match:
            symbol = match.group(2)
        else:
            symbol = _extract_symbol(stripped)
        if not symbol or symbol in seen:
            continue
        items.append(WatchlistItem(symbol=symbol, name=symbol))
        seen.add(symbol)
    return items


def _extract_symbol(text: str) -> str | None:
    match = re.search(r"\b(\d{6})\b", text)
    return match.group(1) if match else None


def _extract_name(text: str, symbol: str) -> str:
    name = text.replace(symbol, " ")
    name = re.sub(r"\b(?:SH|SZ)\b", " ", name, flags=re.IGNORECASE)
    name = re.sub(r"[\d.%+-]+", " ", name)
    name = re.sub(r"\s+", " ", name)
    return name.strip(" \t,-|")


def _unique_strings(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        stripped = value.strip()
        if not stripped or stripped in seen:
            continue
        result.append(stripped)
        seen.add(stripped)
    return result
