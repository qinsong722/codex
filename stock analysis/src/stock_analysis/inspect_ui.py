from __future__ import annotations

from pywinauto import Desktop

from .config import Settings


def main() -> int:
    settings = Settings.load()
    keyword = settings.broker_window_title.strip().lower()
    windows = Desktop(backend="uia").windows()
    matches = [
        window
        for window in windows
        if keyword in (window.window_text() or "").lower()
    ]
    if not matches:
        print(f"No window matched keyword: {settings.broker_window_title}")
        print("Top-level windows:")
        for index, window in enumerate(windows, start=1):
            title = (window.window_text() or "").strip()
            if not title:
                continue
            print(f"{index:03d}. {title}")
        return 1

    window = matches[0].wrapper_object()
    print(f"Matched window: {window.window_text()}")
    for index, control in enumerate(window.descendants(), start=1):
        try:
            text = control.window_text().strip()
            control_type = getattr(control.element_info, "control_type", "")
            name = getattr(control.element_info, "name", "")
            auto_id = getattr(control.element_info, "automation_id", "")
        except Exception:
            continue
        if not any([text, name, auto_id]):
            continue
        print(
            f"{index:04d} type={control_type:<10} class={control.friendly_class_name():<12} "
            f"name={name!r} text={text!r} auto_id={auto_id!r}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
