from __future__ import annotations

from datetime import datetime
from pathlib import Path

from .config import Settings
from .feishu import send_file_message, send_text_message
from .pdf_report import build_pdf_from_markdown


def main() -> int:
    settings = Settings.load()
    report_path = Path("output/codex_scored_report.md")
    if not report_path.exists():
        raise ValueError(f"Missing report file: {report_path}")

    content = report_path.read_text(encoding="utf-8")
    pdf_path = build_pdf_from_markdown(content, Path("output") / _report_filename())
    if settings.feishu_send_mode == "app":
        send_file_message(settings, pdf_path)
        print(f"Sent PDF report from {pdf_path}")
        return 0

    summary = _build_webhook_summary(content, pdf_path)
    send_text_message(settings, summary)
    print(f"Sent webhook summary for report {pdf_path}")
    return 0


def _report_filename() -> str:
    today = datetime.now().strftime("%Y-%m-%d")
    return f"【{today}】自选股分析.pdf"


def _build_webhook_summary(content: str, pdf_path: Path) -> str:
    ranking_lines: list[str] = []
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith(("1. ", "2. ", "3. ", "4. ", "5. ")):
            ranking_lines.append(stripped)
        if len(ranking_lines) >= 5:
            break

    return "\n".join(
        [
            "Codex 股票评分结果",
            "",
            "今日优先关注：",
            *ranking_lines,
            "",
            f"完整PDF已生成：{pdf_path}",
        ]
    )


if __name__ == "__main__":
    raise SystemExit(main())
