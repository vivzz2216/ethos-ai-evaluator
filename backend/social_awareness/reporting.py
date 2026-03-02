"""
Social Awareness PDF Report Generator.

Produces two PDF types:
  generate_initial_report(results, model_name) — before transformation
  generate_final_report(initial, final, model_name) — before vs after comparison
"""

from __future__ import annotations

import io
from datetime import datetime, timezone
from typing import Any, Dict, List

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, HRFlowable,
)

# ── Palette ────────────────────────────────────────────────────────────────────
BRAND_DARK   = colors.HexColor("#1a1a2e")
BRAND_ACCENT = colors.HexColor("#6366f1")
GREEN        = colors.HexColor("#22c55e")
YELLOW       = colors.HexColor("#eab308")
ORANGE       = colors.HexColor("#f97316")
RED          = colors.HexColor("#ef4444")
GREY         = colors.HexColor("#6b7280")
LIGHT_BG     = colors.HexColor("#f8f9fa")
WHITE        = colors.white
BLACK        = colors.black

STYLE_COLORS = {
    "FORMAL":   colors.HexColor("#6366f1"),
    "INFORMAL": colors.HexColor("#f59e0b"),
    "MIXED":    colors.HexColor("#a855f7"),
    "HYBRID":   colors.HexColor("#a855f7"),
}


def _styles():
    ss = getSampleStyleSheet()
    for name, kwargs in [
        ("Title2",       dict(fontSize=22, leading=26, textColor=BRAND_DARK, spaceAfter=4)),
        ("Subtitle",     dict(fontSize=11, textColor=GREY, spaceAfter=12)),
        ("SectionHead",  dict(fontSize=14, textColor=BRAND_DARK, spaceBefore=16, spaceAfter=8)),
        ("CellText",     dict(fontSize=8,  leading=10, textColor=BLACK)),
        ("CellSmall",    dict(fontSize=7,  leading=9,  textColor=GREY)),
    ]:
        ss.add(ParagraphStyle(name, parent=ss["Normal"], **kwargs))
    return ss


def _doc(buf) -> SimpleDocTemplate:
    return SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=20*mm, rightMargin=20*mm,
        topMargin=20*mm, bottomMargin=20*mm,
    )


def _score_bar_table(label: str, value: float, bar_color, doc_width: float, styles):
    """Render a single horizontal progress bar as a mini Table row."""
    pct = max(0.0, min(value, 1.0))
    filled = doc_width * 0.45 * pct
    empty = doc_width * 0.45 * (1.0 - pct)
    bar_row = Table(
        [["", ""]],
        colWidths=[filled if filled > 0 else 0.1, empty if empty > 0 else 0.1],
    )
    bar_row.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, 0), bar_color),
        ("BACKGROUND", (1, 0), (1, 0), colors.HexColor("#e5e7eb")),
        ("TOPPADDING",    (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    label_para = Paragraph(f"<b>{label}</b>", styles["CellText"])
    pct_para   = Paragraph(f"<b>{pct * 100:.1f}%</b>", styles["CellText"])
    row_table  = Table([[label_para, bar_row, pct_para]],
                       colWidths=[doc_width * 0.18, doc_width * 0.45, doc_width * 0.12])
    row_table.setStyle(TableStyle([
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING",   (0, 0), (-1, -1), 0),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 4),
        ("TOPPADDING",    (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))
    return row_table


def _style_summary(results: List[Dict], doc_width: float, styles):
    """Compute per-style aggregate scores and return (counts, avg_formal, avg_informal, avg_mixed)."""
    n = max(len(results), 1)
    counts: Dict[str, int] = {}
    total_formal = total_informal = total_mixed = 0.0

    for r in results:
        label = r.get("detected_style", "UNKNOWN")
        # Normalize HYBRID → MIXED for display
        if label == "HYBRID":
            label = "MIXED"
        counts[label] = counts.get(label, 0) + 1
        scores = r.get("style_scores", {})
        total_formal   += scores.get("formal",   0.0)
        total_informal += scores.get("informal",  0.0)
        mixed_score = scores.get("formal", 0.0) if r.get("is_mixed") else 0.0
        total_mixed += mixed_score

    avg = {
        "formal":   total_formal   / n,
        "informal": total_informal / n,
        "mixed":    total_mixed    / n,
    }
    return counts, avg


def generate_initial_report(
    results: List[Dict],
    model_name: str,
) -> bytes:
    """
    Generate a PDF showing the initial social awareness test results.
    Only formal, informal, and mixed (hybrid) styles are reported.
    """
    buf = io.BytesIO()
    doc = _doc(buf)
    styles = _styles()
    story: list = []
    dw = doc.width

    n = len(results)
    counts, avg = _style_summary(results, dw, styles)
    dominant = max(counts, key=lambda k: counts[k], default="UNKNOWN")
    dominant_color = STYLE_COLORS.get(dominant, GREY)

    # ── Header ───────────────────────────────────────────────────────────────
    story.append(Paragraph("ETHOS Social Awareness — Initial Style Report", styles["Title2"]))
    story.append(Paragraph(
        f"Model: <b>{model_name}</b> &nbsp;|&nbsp; "
        f"Prompts Tested: <b>{n}</b> &nbsp;|&nbsp; "
        f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        styles["Subtitle"],
    ))
    story.append(HRFlowable(width="100%", thickness=1, color=BRAND_ACCENT))
    story.append(Spacer(1, 12))

    # ── Dominant Style Banner ─────────────────────────────────────────────────
    story.append(Paragraph("Dominant Communication Style", styles["SectionHead"]))
    banner = Table([[
        Paragraph(
            f'<font color="{dominant_color.hexval()}" size="28"><b>{dominant}</b></font>',
            styles["Normal"],
        ),
        Paragraph(
            f'<font size="11" color="#6b7280">Responses analysed: {n}</font>',
            styles["CellText"],
        ),
    ]], colWidths=[dw * 0.6, dw * 0.4])
    banner.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), LIGHT_BG),
        ("BOX", (0, 0), (-1, -1), 1.5, dominant_color),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING",   (0, 0), (-1, -1), 14),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 14),
        ("TOPPADDING",    (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
    ]))
    story.append(banner)
    story.append(Spacer(1, 14))

    # ── Style Distribution ────────────────────────────────────────────────────
    story.append(Paragraph("Style Distribution (% of responses)", styles["SectionHead"]))
    dist_header = ["Style", "Responses", "Percentage"]
    dist_rows = [dist_header]
    for style, count in sorted(counts.items(), key=lambda x: -x[1]):
        dist_rows.append([
            style,
            str(count),
            f"{count / n * 100:.1f}%",
        ])
    dist_table = Table(dist_rows, colWidths=[dw * 0.4, dw * 0.3, dw * 0.3])
    dist_style_ts = [
        ("BACKGROUND", (0, 0), (-1, 0), BRAND_ACCENT),
        ("TEXTCOLOR",  (0, 0), (-1, 0), WHITE),
        ("FONTNAME",   (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",   (0, 0), (-1, -1), 10),
        ("ALIGN",      (1, 0), (-1, -1), "CENTER"),
        ("BOX",        (0, 0), (-1, -1), 0.5, GREY),
        ("INNERGRID",  (0, 0), (-1, -1), 0.25, colors.HexColor("#d1d5db")),
        ("TOPPADDING",    (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]
    for i, (style, _) in enumerate(sorted(counts.items(), key=lambda x: -x[1]), start=1):
        sc = STYLE_COLORS.get(style, GREY)
        dist_style_ts.append(("TEXTCOLOR", (0, i), (0, i), sc))
        dist_style_ts.append(("FONTNAME",  (0, i), (0, i), "Helvetica-Bold"))
    dist_table.setStyle(TableStyle(dist_style_ts))
    story.append(dist_table)
    story.append(Spacer(1, 14))

    # ── Average Score Bars ────────────────────────────────────────────────────
    story.append(Paragraph("Average Style Scores (across all responses)", styles["SectionHead"]))
    story.append(_score_bar_table("Formal",   avg["formal"],   STYLE_COLORS["FORMAL"],   dw, styles))
    story.append(Spacer(1, 4))
    story.append(_score_bar_table("Informal", avg["informal"], STYLE_COLORS["INFORMAL"], dw, styles))
    story.append(Spacer(1, 4))
    story.append(Spacer(1, 14))

    # ── Per-Response Detail ───────────────────────────────────────────────────
    story.append(PageBreak())
    story.append(Paragraph("Per-Response Style Detail", styles["SectionHead"]))

    rec_header = ["#", "Prompt (preview)", "Response (preview)", "Style", "Formal%", "Informal%", "Violations"]
    rec_rows = [rec_header]
    for i, r in enumerate(results, 1):
        label = r.get("detected_style", "?")
        if label == "HYBRID":
            label = "MIXED"
        sc = r.get("style_scores", {})
        violations = ", ".join(r.get("violations", [])) or "—"
        rec_rows.append([
            str(i),
            (r.get("prompt", "")[:60] + "...") if len(r.get("prompt", "")) > 60 else r.get("prompt", "—"),
            (r.get("input_text", "")[:80] + "...") if len(r.get("input_text", "")) > 80 else r.get("input_text", "—"),
            label,
            f"{sc.get('formal', 0) * 100:.0f}%",
            f"{sc.get('informal', 0) * 100:.0f}%",
            violations[:40],
        ])
    col_ws = [dw * 0.04, dw * 0.17, dw * 0.22, dw * 0.11, dw * 0.09, dw * 0.09, dw * 0.14]
    rec_table = Table(
        [[Paragraph(str(cell), styles["CellText"]) for cell in row] for row in rec_rows],
        colWidths=col_ws,
    )
    rec_ts = [
        ("BACKGROUND",    (0, 0), (-1, 0), BRAND_ACCENT),
        ("TEXTCOLOR",     (0, 0), (-1, 0), WHITE),
        ("FONTNAME",      (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",      (0, 0), (-1, -1), 7),
        ("BOX",           (0, 0), (-1, -1), 0.5, GREY),
        ("INNERGRID",     (0, 0), (-1, -1), 0.25, colors.HexColor("#d1d5db")),
        ("TOPPADDING",    (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
    ]
    for ri in range(1, len(rec_rows)):
        rec_ts.append(("BACKGROUND", (0, ri), (-1, ri), LIGHT_BG if ri % 2 == 1 else WHITE))
    rec_table.setStyle(TableStyle(rec_ts))
    story.append(rec_table)

    # ── Footer ────────────────────────────────────────────────────────────────
    story.append(Spacer(1, 20))
    story.append(HRFlowable(width="100%", thickness=0.5, color=GREY))
    story.append(Paragraph(
        f'<font color="#9ca3af" size="8">ETHOS AI Evaluator — Social Awareness Initial Report — '
        f'{datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")}</font>',
        styles["Normal"],
    ))

    doc.build(story)
    return buf.getvalue()


def generate_final_report(
    initial_results: List[Dict],
    final_results: List[Dict],
    target_style: str,
    model_name: str,
) -> bytes:
    """
    Generate a before-vs-after comparison PDF after style transformation.
    """
    buf = io.BytesIO()
    doc = _doc(buf)
    styles = _styles()
    story: list = []
    dw = doc.width

    i_counts, i_avg = _style_summary(initial_results, dw, styles)
    f_counts, f_avg = _style_summary(final_results,   dw, styles)
    n = len(initial_results)
    target_color = STYLE_COLORS.get(target_style.upper(), BRAND_ACCENT)

    # ── Header ────────────────────────────────────────────────────────────────
    story.append(Paragraph("ETHOS Social Awareness — Before vs After Report", styles["Title2"]))
    story.append(Paragraph(
        f"Model: <b>{model_name}</b> &nbsp;|&nbsp; "
        f"Target Style: <b>{target_style.upper()}</b> &nbsp;|&nbsp; "
        f"Prompts: <b>{n}</b> &nbsp;|&nbsp; "
        f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        styles["Subtitle"],
    ))
    story.append(HRFlowable(width="100%", thickness=1, color=target_color))
    story.append(Spacer(1, 12))

    # ── Comparison Summary Table ──────────────────────────────────────────────
    story.append(Paragraph("Style Distribution Change", styles["SectionHead"]))
    all_styles = sorted(set(list(i_counts.keys()) + list(f_counts.keys())))
    cmp_header = ["Style", "Before (count)", "Before (%)", "After (count)", "After (%)", "Δ Change"]
    cmp_rows = [cmp_header]
    for style in all_styles:
        bc = i_counts.get(style, 0)
        ac = f_counts.get(style, 0)
        bp = bc / n * 100
        ap = ac / n * 100
        delta = ap - bp
        delta_str = f"+{delta:.1f}%" if delta >= 0 else f"{delta:.1f}%"
        cmp_rows.append([style, str(bc), f"{bp:.1f}%", str(ac), f"{ap:.1f}%", delta_str])
    cmp_table = Table(cmp_rows, colWidths=[dw*0.20, dw*0.14, dw*0.14, dw*0.14, dw*0.14, dw*0.14])
    cmp_ts = [
        ("BACKGROUND", (0, 0), (-1, 0), BRAND_ACCENT),
        ("TEXTCOLOR",  (0, 0), (-1, 0), WHITE),
        ("FONTNAME",   (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",   (0, 0), (-1, -1), 9),
        ("ALIGN",      (1, 0), (-1, -1), "CENTER"),
        ("BOX",        (0, 0), (-1, -1), 0.5, GREY),
        ("INNERGRID",  (0, 0), (-1, -1), 0.25, colors.HexColor("#d1d5db")),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]
    for ri in range(1, len(cmp_rows)):
        cmp_ts.append(("BACKGROUND", (0, ri), (-1, ri), LIGHT_BG if ri % 2 == 1 else WHITE))
        style_lbl = cmp_rows[ri][0]
        sc = STYLE_COLORS.get(style_lbl, GREY)
        cmp_ts.append(("TEXTCOLOR",  (0, ri), (0, ri), sc))
        delta_val = float(cmp_rows[ri][5].replace("+", "").replace("%", ""))
        if style_lbl.upper() == target_style.upper():
            d_color = GREEN if delta_val > 0 else RED
        else:
            d_color = RED if delta_val > 0 else GREEN
        cmp_ts.append(("TEXTCOLOR", (5, ri), (5, ri), d_color))
    cmp_table.setStyle(TableStyle(cmp_ts))
    story.append(cmp_table)
    story.append(Spacer(1, 14))

    # ── Average Score Comparison Bars ─────────────────────────────────────────
    story.append(Paragraph("Average Score Comparison (Formal | Informal)", styles["SectionHead"]))
    for metric, label, bar_col in [
        ("formal",   "Formal",   STYLE_COLORS["FORMAL"]),
        ("informal", "Informal", STYLE_COLORS["INFORMAL"]),
    ]:
        before_v = i_avg.get(metric, 0.0)
        after_v  = f_avg.get(metric, 0.0)
        story.append(Paragraph(f"<b>{label}</b>", styles["CellText"]))
        story.append(Spacer(1, 2))
        story.append(_score_bar_table("Before", before_v, GREY,     dw, styles))
        story.append(_score_bar_table("After",  after_v,  bar_col,  dw, styles))
        story.append(Spacer(1, 8))

    # ── Per-Response Comparison ───────────────────────────────────────────────
    story.append(PageBreak())
    story.append(Paragraph("Per-Response Comparison (Before → After)", styles["SectionHead"]))
    cpr_header = ["#", "Original Response (preview)", "Style Before", "Transformed Response (preview)", "Style After", "Similarity"]
    cpr_rows = [cpr_header]
    for i, (ir, fr) in enumerate(zip(initial_results, final_results), 1):
        i_label = ir.get("detected_style", "?")
        f_label = fr.get("detected_style", "?")
        if i_label == "HYBRID": i_label = "MIXED"
        if f_label == "HYBRID": f_label = "MIXED"
        tx = fr.get("transformed") or {}
        orig_text    = (ir.get("input_text") or "—")[:80]
        transf_text  = (tx.get("transformed") or fr.get("input_text") or "—")[:80]
        sim          = tx.get("similarity_score")
        sim_str = f"{sim * 100:.0f}%" if sim is not None else "—"
        cpr_rows.append([str(i), orig_text + "…", i_label, transf_text + "…", f_label, sim_str])

    cpr_col_ws = [dw*0.04, dw*0.24, dw*0.10, dw*0.24, dw*0.10, dw*0.08]
    cpr_table = Table(
        [[Paragraph(str(cell), styles["CellText"]) for cell in row] for row in cpr_rows],
        colWidths=cpr_col_ws,
    )
    cpr_ts = [
        ("BACKGROUND", (0, 0), (-1, 0), BRAND_ACCENT),
        ("TEXTCOLOR",  (0, 0), (-1, 0), WHITE),
        ("FONTNAME",   (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",   (0, 0), (-1, -1), 7),
        ("BOX",        (0, 0), (-1, -1), 0.5, GREY),
        ("INNERGRID",  (0, 0), (-1, -1), 0.25, colors.HexColor("#d1d5db")),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("VALIGN",     (0, 0), (-1, -1), "TOP"),
    ]
    for ri in range(1, len(cpr_rows)):
        cpr_ts.append(("BACKGROUND", (0, ri), (-1, ri), LIGHT_BG if ri % 2 == 1 else WHITE))
        style_before = cpr_rows[ri][2]
        style_after  = cpr_rows[ri][4]
        cpr_ts.append(("TEXTCOLOR", (2, ri), (2, ri), STYLE_COLORS.get(style_before, GREY)))
        cpr_ts.append(("TEXTCOLOR", (4, ri), (4, ri), STYLE_COLORS.get(style_after, GREY)))
    cpr_table.setStyle(TableStyle(cpr_ts))
    story.append(cpr_table)

    # ── Footer ────────────────────────────────────────────────────────────────
    story.append(Spacer(1, 20))
    story.append(HRFlowable(width="100%", thickness=0.5, color=GREY))
    story.append(Paragraph(
        f'<font color="#9ca3af" size="8">ETHOS AI Evaluator — Social Awareness Transformation Report — '
        f'{datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")}</font>',
        styles["Normal"],
    ))

    doc.build(story)
    return buf.getvalue()
