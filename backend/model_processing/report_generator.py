"""
ETHOS AI Ethics Report — PDF Generator

Generates a professional PDF report with:
- Model info & verdict banner
- Overall score & pass rate
- Violation severity breakdown
- Category-level results
- Detailed prompt/response/failure table
"""

import io
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch, mm
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    PageBreak,
    HRFlowable,
)

logger = logging.getLogger(__name__)

# ── Colour palette ──────────────────────────────────────────────────
BRAND_DARK = colors.HexColor("#1a1a2e")
BRAND_ACCENT = colors.HexColor("#6366f1")
GREEN = colors.HexColor("#22c55e")
YELLOW = colors.HexColor("#eab308")
ORANGE = colors.HexColor("#f97316")
RED = colors.HexColor("#ef4444")
GREY = colors.HexColor("#6b7280")
LIGHT_BG = colors.HexColor("#f8f9fa")
WHITE = colors.white
BLACK = colors.black

SEVERITY_COLORS = {
    "critical": RED,
    "high": ORANGE,
    "medium": YELLOW,
    "low": GREEN,
}

VERDICT_COLORS = {
    "APPROVE": GREEN,
    "APPROVED": GREEN,
    "WARN": YELLOW,
    "NEEDS_FIX": ORANGE,
    "REJECT": RED,
    "REJECTED": RED,
}

VERDICT_LABELS = {
    "APPROVE": "APPROVED",
    "APPROVED": "APPROVED",
    "WARN": "WARNING",
    "NEEDS_FIX": "NEEDS FIX",
    "REJECT": "REJECTED",
    "REJECTED": "REJECTED",
}

CATEGORY_LABELS = {
    "jailbreak": "Jailbreak Attempts",
    "harm": "Harmful Instructions",
    "bias": "Bias & Discrimination",
    "privacy": "Privacy Violations",
    "misinfo": "Misinformation",
}


def _styles():
    """Build custom paragraph styles."""
    ss = getSampleStyleSheet()
    ss.add(ParagraphStyle(
        "Title2",
        parent=ss["Title"],
        fontSize=22,
        leading=26,
        textColor=BRAND_DARK,
        spaceAfter=4,
    ))
    ss.add(ParagraphStyle(
        "Subtitle",
        parent=ss["Normal"],
        fontSize=11,
        textColor=GREY,
        spaceAfter=12,
    ))
    ss.add(ParagraphStyle(
        "SectionHead",
        parent=ss["Heading2"],
        fontSize=14,
        textColor=BRAND_DARK,
        spaceBefore=16,
        spaceAfter=8,
        borderWidth=0,
    ))
    ss.add(ParagraphStyle(
        "CellText",
        parent=ss["Normal"],
        fontSize=8,
        leading=10,
        textColor=BLACK,
    ))
    ss.add(ParagraphStyle(
        "CellTextSmall",
        parent=ss["Normal"],
        fontSize=7,
        leading=9,
        textColor=GREY,
    ))
    ss.add(ParagraphStyle(
        "VerdictBig",
        parent=ss["Normal"],
        fontSize=28,
        leading=32,
        alignment=1,
        spaceAfter=2,
    ))
    ss.add(ParagraphStyle(
        "PassRate",
        parent=ss["Normal"],
        fontSize=36,
        leading=40,
        alignment=1,
        textColor=BRAND_ACCENT,
    ))
    return ss


def generate_report_pdf(result: Dict[str, Any]) -> bytes:
    """
    Generate a PDF report from a processing result dict.

    Args:
        result: The dict returned by ModelProcessingStateMachine.get_result()

    Returns:
        PDF file contents as bytes.
    """
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
        topMargin=20 * mm,
        bottomMargin=20 * mm,
    )
    styles = _styles()
    story: list = []

    ctx = result.get("context", {})
    verdict_data = ctx.get("verdict") or {}
    classification = ctx.get("classification") or {}
    test_summary = ctx.get("test_summary") or {}
    records: List[Dict] = test_summary.get("records", [])
    purification = ctx.get("purification_result")
    errors = ctx.get("errors", [])
    duration = ctx.get("duration_seconds", 0)
    state = result.get("state", "UNKNOWN")

    verdict_key = verdict_data.get("verdict", state)
    verdict_color = VERDICT_COLORS.get(verdict_key, GREY)
    verdict_label = VERDICT_LABELS.get(verdict_key, verdict_key)

    # ── Header ───────────────────────────────────────────────────────
    story.append(Paragraph("ETHOS AI Ethics Evaluation Report", styles["Title2"]))
    model_name = classification.get("model_type", "Unknown")
    hf_name = classification.get("architecture") or ""
    timestamp = ctx.get("started_at", datetime.now(timezone.utc).isoformat())
    story.append(Paragraph(
        f"Model: <b>{hf_name or model_name}</b> &nbsp;|&nbsp; "
        f"Generated: {timestamp[:19].replace('T', ' ')} UTC &nbsp;|&nbsp; "
        f"Duration: {duration:.1f}s",
        styles["Subtitle"],
    ))
    story.append(HRFlowable(width="100%", thickness=1, color=BRAND_ACCENT))
    story.append(Spacer(1, 12))

    # ── Verdict Banner ───────────────────────────────────────────────
    pass_rate = verdict_data.get("pass_rate", 0)
    total_tests = verdict_data.get("total_tests", 0)
    pass_count = verdict_data.get("pass_count", 0)
    reason = verdict_data.get("reason", "")

    verdict_table_data = [
        [
            Paragraph(f'<font color="{verdict_color.hexval()}" size="24"><b>{verdict_label}</b></font>', styles["Normal"]),
            Paragraph(f'<font size="30"><b>{pass_rate}%</b></font>', styles["PassRate"]),
        ],
        [
            Paragraph(f'<font color="#6b7280">{reason}</font>', styles["CellText"]),
            Paragraph(f'<font color="#6b7280">Pass Rate ({pass_count}/{total_tests})</font>', styles["CellTextSmall"]),
        ],
    ]
    verdict_table = Table(verdict_table_data, colWidths=[doc.width * 0.65, doc.width * 0.35])
    verdict_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), LIGHT_BG),
        ("BOX", (0, 0), (-1, -1), 1, verdict_color),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 12),
        ("RIGHTPADDING", (0, 0), (-1, -1), 12),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("ALIGN", (1, 0), (1, -1), "CENTER"),
        ("ROUNDEDCORNERS", [6, 6, 6, 6]),
    ]))
    story.append(verdict_table)
    story.append(Spacer(1, 14))

    # ── Quick Stats ──────────────────────────────────────────────────
    violations = verdict_data.get("violations", {})
    stats_data = [
        ["Tests Run", "Passed", "Critical", "High", "Medium", "Low"],
        [
            str(total_tests),
            str(pass_count),
            str(violations.get("critical", 0)),
            str(violations.get("high", 0)),
            str(violations.get("medium", 0)),
            str(violations.get("low", 0)),
        ],
    ]
    col_w = doc.width / 6
    stats_table = Table(stats_data, colWidths=[col_w] * 6)
    stats_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), BRAND_ACCENT),
        ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
        ("FONTSIZE", (0, 0), (-1, 0), 9),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("BACKGROUND", (0, 1), (-1, 1), LIGHT_BG),
        ("FONTSIZE", (0, 1), (-1, 1), 14),
        ("FONTNAME", (0, 1), (-1, 1), "Helvetica-Bold"),
        ("TEXTCOLOR", (2, 1), (2, 1), RED),
        ("TEXTCOLOR", (3, 1), (3, 1), ORANGE),
        ("TEXTCOLOR", (4, 1), (4, 1), YELLOW),
        ("TEXTCOLOR", (5, 1), (5, 1), GREEN),
        ("BOX", (0, 0), (-1, -1), 0.5, GREY),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#d1d5db")),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(stats_table)
    story.append(Spacer(1, 14))

    # ── Category Breakdown ───────────────────────────────────────────
    cat_breakdown = verdict_data.get("category_breakdown", {})
    if cat_breakdown:
        story.append(Paragraph("Category Breakdown", styles["SectionHead"]))

        cat_header = ["Category", "Total", "Pass", "Warn", "Fail", "Pass Rate"]
        cat_rows = [cat_header]
        for cat, stats in cat_breakdown.items():
            label = CATEGORY_LABELS.get(cat, cat.title())
            t = stats.get("total", 0)
            p = stats.get("pass", 0)
            w = stats.get("warn", 0)
            f = stats.get("fail", 0)
            rate = f"{(p / t * 100):.0f}%" if t > 0 else "N/A"
            cat_rows.append([label, str(t), str(p), str(w), str(f), rate])

        cat_table = Table(cat_rows, colWidths=[
            doc.width * 0.30, doc.width * 0.12, doc.width * 0.12,
            doc.width * 0.12, doc.width * 0.12, doc.width * 0.22,
        ])
        cat_style = [
            ("BACKGROUND", (0, 0), (-1, 0), BRAND_ACCENT),
            ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("ALIGN", (1, 0), (-1, -1), "CENTER"),
            ("BOX", (0, 0), (-1, -1), 0.5, GREY),
            ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#d1d5db")),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]
        # Alternate row colours
        for i in range(1, len(cat_rows)):
            bg = LIGHT_BG if i % 2 == 1 else WHITE
            cat_style.append(("BACKGROUND", (0, i), (-1, i), bg))
        cat_table.setStyle(TableStyle(cat_style))
        story.append(cat_table)
        story.append(Spacer(1, 10))

    # ── Purification Result (if any) ─────────────────────────────────
    if purification:
        story.append(Paragraph("Purification Result", styles["SectionHead"]))
        pur_data = [
            ["Retested", "Fixed", "Still Failing", "Fix Rate", "Passed"],
            [
                str(purification.get("total_retested", 0)),
                str(purification.get("fixed", 0)),
                str(purification.get("still_failing", 0)),
                f"{purification.get('fix_rate', 0)}%",
                "Yes" if purification.get("passed") else "No",
            ],
        ]
        pur_table = Table(pur_data, colWidths=[doc.width / 5] * 5)
        pur_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), BRAND_ACCENT),
            ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("BOX", (0, 0), (-1, -1), 0.5, GREY),
            ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#d1d5db")),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("BACKGROUND", (0, 1), (-1, 1), LIGHT_BG),
        ]))
        story.append(pur_table)
        story.append(Spacer(1, 10))

    # ── Detailed Test Records ────────────────────────────────────────
    if records:
        story.append(PageBreak())
        story.append(Paragraph("Detailed Test Results", styles["SectionHead"]))
        story.append(Paragraph(
            f"Showing {len(records)} of {total_tests} test records.",
            styles["Subtitle"],
        ))

        for idx, rec in enumerate(records):
            verdict_rec = rec.get("verdict", "?")
            scores = rec.get("scores", {})
            severity = scores.get("severity", "low")
            sev_color = SEVERITY_COLORS.get(severity, GREY)

            # Verdict colour
            if verdict_rec == "PASS":
                v_color = GREEN
            elif verdict_rec == "WARN":
                v_color = YELLOW
            else:
                v_color = RED

            prompt_text = rec.get("prompt", "")[:200]
            response_text = rec.get("response", "")[:300]
            explanation = scores.get("explanation", "")[:200]
            category = CATEGORY_LABELS.get(rec.get("category", ""), rec.get("category", ""))

            # Build record mini-table
            rec_data = [
                [
                    Paragraph(f'<b>#{idx + 1}</b> &nbsp; <font color="{v_color.hexval()}"><b>[{verdict_rec}]</b></font> &nbsp; <font color="#6b7280">{category}</font>', styles["CellText"]),
                    Paragraph(f'Severity: <font color="{sev_color.hexval()}"><b>{severity.upper()}</b></font> &nbsp; Harm: {scores.get("harm", 0):.2f} &nbsp; Bias: {scores.get("bias", 0):.2f}', styles["CellTextSmall"]),
                ],
                [
                    Paragraph(f'<b>Prompt:</b> {_escape(prompt_text)}', styles["CellText"]),
                    "",
                ],
                [
                    Paragraph(f'<b>Response:</b> {_escape(response_text)}', styles["CellText"]),
                    "",
                ],
            ]

            if explanation:
                rec_data.append([
                    Paragraph(f'<b>Explanation:</b> <i>{_escape(explanation)}</i>', styles["CellTextSmall"]),
                    "",
                ])

            rec_table = Table(rec_data, colWidths=[doc.width * 0.55, doc.width * 0.45])
            rec_style = [
                ("SPAN", (0, 1), (1, 1)),
                ("SPAN", (0, 2), (1, 2)),
                ("BOX", (0, 0), (-1, -1), 0.5, sev_color),
                ("BACKGROUND", (0, 0), (-1, 0), LIGHT_BG),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
            if len(rec_data) > 3:
                rec_style.append(("SPAN", (0, 3), (1, 3)))
            rec_table.setStyle(TableStyle(rec_style))
            story.append(rec_table)
            story.append(Spacer(1, 6))

    # ── Errors ───────────────────────────────────────────────────────
    if errors:
        story.append(Spacer(1, 10))
        story.append(Paragraph("Errors Encountered", styles["SectionHead"]))
        for err in errors:
            story.append(Paragraph(
                f'<font color="#ef4444">• {_escape(err)}</font>',
                styles["CellText"],
            ))

    # ── Footer ───────────────────────────────────────────────────────
    story.append(Spacer(1, 20))
    story.append(HRFlowable(width="100%", thickness=0.5, color=GREY))
    story.append(Paragraph(
        f'<font color="#9ca3af" size="8">'
        f'ETHOS AI Evaluator — Ethics Testing Report — '
        f'{datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")}'
        f'</font>',
        styles["Normal"],
    ))

    doc.build(story)
    return buf.getvalue()


def _escape(text: str) -> str:
    """Escape XML special characters for ReportLab paragraphs."""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
