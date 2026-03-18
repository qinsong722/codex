from __future__ import annotations

import re
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import HRFlowable, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def build_pdf_from_markdown(markdown_text: str, output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    _register_font()

    styles = _build_styles()
    lines = markdown_text.splitlines()
    story = []
    in_overview = True

    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            story.append(Spacer(1, 5))
            continue

        if _is_stock_section_heading(line):
            in_overview = False
            if story:
                story.append(PageBreak())
            story.append(Paragraph(_escape(line[3:].strip()), styles["stock_heading"]))
            story.append(Spacer(1, 4))
            story.append(HRFlowable(width="100%", color=colors.HexColor("#D7E3F4"), thickness=1.2, spaceAfter=10))
            continue

        if line.startswith("# "):
            story.append(Paragraph(_escape(line[2:].strip()), styles["title"]))
            story.append(Spacer(1, 6))
            continue

        if line.startswith("## "):
            story.append(Paragraph(_escape(line[3:].strip()), styles["heading2"]))
            story.append(Spacer(1, 4))
            if in_overview and "排序结果" in line:
                story.append(HRFlowable(width="40%", color=colors.HexColor("#234B7D"), thickness=1.5, spaceAfter=8))
            continue

        if line.startswith("### "):
            story.append(Paragraph(_escape(line[4:].strip()), styles["heading3"]))
            continue

        if _looks_like_ranking_row(line):
            story.append(_ranking_table_row(line, styles))
            continue

        if line.startswith("- "):
            story.append(Paragraph(f"• {_escape(line[2:].strip())}", styles["bullet"]))
            continue

        if line == "---":
            story.append(Spacer(1, 4))
            story.append(HRFlowable(width="100%", color=colors.HexColor("#D9DDE3"), thickness=0.8, spaceBefore=4, spaceAfter=8))
            continue

        story.append(Paragraph(_escape(line), styles["body"]))

    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        leftMargin=16 * mm,
        rightMargin=16 * mm,
        topMargin=16 * mm,
        bottomMargin=14 * mm,
        title="Codex 股票评分报告",
    )
    doc.build(story, onFirstPage=_draw_page, onLaterPages=_draw_page)
    return output_path


def _build_styles() -> dict[str, ParagraphStyle]:
    styles = getSampleStyleSheet()
    base = ParagraphStyle(
        "ChineseBody",
        parent=styles["BodyText"],
        fontName="SimSun",
        fontSize=10.5,
        leading=16,
        textColor=colors.HexColor("#1F2937"),
        spaceAfter=6,
    )
    return {
        "body": base,
        "bullet": ParagraphStyle(
            "BulletCN",
            parent=base,
            leftIndent=10,
            firstLineIndent=0,
            bulletIndent=0,
            spaceAfter=4,
        ),
        "title": ParagraphStyle(
            "TitleCN",
            parent=base,
            fontSize=22,
            leading=28,
            textColor=colors.HexColor("#163A63"),
            spaceAfter=10,
        ),
        "heading2": ParagraphStyle(
            "Heading2CN",
            parent=base,
            fontSize=14,
            leading=20,
            textColor=colors.HexColor("#234B7D"),
            spaceAfter=6,
        ),
        "heading3": ParagraphStyle(
            "Heading3CN",
            parent=base,
            fontSize=11.5,
            leading=18,
            textColor=colors.HexColor("#3A4A5A"),
            spaceBefore=6,
            spaceAfter=4,
        ),
        "stock_heading": ParagraphStyle(
            "StockHeadingCN",
            parent=base,
            fontSize=17,
            leading=24,
            textColor=colors.HexColor("#0F3558"),
            spaceAfter=6,
        ),
        "table_cell": ParagraphStyle(
            "TableCellCN",
            parent=base,
            fontSize=10,
            leading=14,
            spaceAfter=0,
        ),
    }


def _ranking_table_row(line: str, styles: dict[str, ParagraphStyle]) -> Table:
    left, right = _split_ranking_row(line)
    table = Table([[Paragraph(_escape(left), styles["table_cell"]), Paragraph(_escape(right), styles["table_cell"])]], colWidths=[82 * mm, 88 * mm])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F7FAFC")),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#D8E2EC")),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E5EAF0")),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )
    return table


def _split_ranking_row(line: str) -> tuple[str, str]:
    parts = line.split("：", 1)
    if len(parts) == 2:
        return parts[0], parts[1]
    return line, ""


def _looks_like_ranking_row(line: str) -> bool:
    return bool(re.match(r"^\d+\.\s", line))


def _is_stock_section_heading(line: str) -> bool:
    return bool(re.match(r"^##\s+\d+\.\s", line))


def _draw_page(canvas, doc) -> None:
    canvas.saveState()
    canvas.setFont("SimSun", 9)
    canvas.setFillColor(colors.HexColor("#708090"))
    canvas.drawString(doc.leftMargin, A4[1] - 10 * mm, "Codex 股票评分报告")
    canvas.drawRightString(A4[0] - doc.rightMargin, 10 * mm, f"第 {doc.page} 页")
    canvas.restoreState()


def _register_font() -> None:
    if "SimSun" in pdfmetrics.getRegisteredFontNames():
        return
    font_path = Path(r"C:\Windows\Fonts\simsun.ttc")
    if not font_path.exists():
        raise ValueError(f"Missing font file: {font_path}")
    pdfmetrics.registerFont(TTFont("SimSun", str(font_path)))


def _escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
