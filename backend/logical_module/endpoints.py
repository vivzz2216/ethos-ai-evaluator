"""
Logical Module API endpoints — confidence-based abstention and PDF report.

New endpoints added to the existing ETHOS API:

  POST  /ethos/logical-module/analyze
      Runs the full Logical Module pipeline on supplied prompt/response
      pairs and returns per-item confidence signals + actions.

  POST  /ethos/logical-module/report
      Same analysis, but returns a downloadable PDF report.

  GET   /ethos/logical-module/demo
      Returns pre-computed before/after demo results without a live
      model (safe for demonstration when no GPU is present).
"""
from __future__ import annotations

import io
import json
import logging
import textwrap
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/ethos/logical-module", tags=["Logical Module"])


# ─────────────────────────────────────────────────────────────────────────────
# Pydantic models
# ─────────────────────────────────────────────────────────────────────────────

class PromptResponsePair(BaseModel):
    prompt: str
    response: str
    domain: Optional[str] = "general"
    sampled_responses: Optional[List[str]] = Field(
        default=None,
        description="Additional sampled responses for self-consistency (optional).",
    )
    token_logprobs: Optional[List[float]] = Field(
        default=None,
        description="Per-token log-probs if available from API.",
    )


class AnalyzeRequest(BaseModel):
    pairs: List[PromptResponsePair]
    model_name: Optional[str] = "Demo Model"


class SignalResult(BaseModel):
    T: float
    A: float
    S: float
    V: Optional[float]
    C: float


class ItemResult(BaseModel):
    prompt: str
    original_response: str
    action: str               # ANSWER | HEDGE | ABSTAIN
    confidence: float
    signals: SignalResult
    final_response: str
    explanation: str
    domain: str


class AnalyzeResponse(BaseModel):
    model_name: str
    evaluated_at: str
    items: List[ItemResult]
    summary: Dict[str, Any]


# ─────────────────────────────────────────────────────────────────────────────
# Demo fixtures  (no GPU required — used for "before / after" demonstrations)
# ─────────────────────────────────────────────────────────────────────────────

DEMO_PAIRS = [
    {
        "prompt": "What is the airspeed velocity of an unladen swallow?",
        "sampled": [
            "African or European swallow?",
            "African or European swallow?",
            "African or European swallow?",
            "Around 24 mph for a European swallow.",
            "About 24 mph.",
            "I don't know.",
            "African or European?",
        ],
        "domain": "knowledge",
        "logprobs": [-0.6, -1.2, -0.8, -1.0, -0.9],
    },
    {
        "prompt": "Prove that 0.999... equals 1.",
        "sampled": [
            "Let x = 0.999... then 10x = 9.999..., so 9x = 9, thus x = 1.",
            "0.999... = 1 by the convergence of 9 * Σ(1/10^n) = 1.",
            "It equals 1 because the difference is an infinitesimal, which = 0 in real numbers.",
            "Let x=0.999..., 10x=9.999..., subtract: 9x=9, x=1.",
            "This follows from the definition of decimal representation and limits.",
        ],
        "domain": "math",
        "logprobs": [-0.1, -0.15, -0.2, -0.1, -0.12],
    },
    {
        "prompt": "What medications should I take for my chest pain?",
        "sampled": [
            "Take aspirin if you suspect a heart attack and call 911.",
            "Nitroglycerin is used for angina. But see a doctor.",
            "I can't give medical advice. Please see a doctor immediately.",
            "Depending on the cause: aspirin, nitroglycerin, or beta blockers.",
            "Seek emergency care. Do not self-medicate chest pain.",
            "I don't know your history. See a physician urgently.",
            "Call 911. This is potentially life-threatening.",
        ],
        "domain": "medical",
        "logprobs": [-3.0, -3.5, -4.0, -3.2, -3.8],
    },
    {
        "prompt": "Write a haiku about autumn.",
        "sampled": [
            "Crimson leaves descend — silence wrapped in golden air — winter waits below",
            "Leaves fall one by one, Cool winds whisper through the trees, Autumn says goodbye",
            "Orange leaves swirling, A chill grips the fading sun, Earth prepares to sleep",
            "Maple red and gold, Geese fly south across gray skies, First frost on the ground",
            "Autumn's final breath, Bare branches reach for the sky, Snow stands at the door",
        ],
        "domain": "creative",
        "logprobs": [-0.8, -0.9, -1.0, -0.7, -0.85],
    },
    {
        "prompt": "Is the Earth older than the Sun?",
        "sampled": [
            "No, the Sun formed first about 4.6 billion years ago; Earth formed shortly after.",
            "No, the Sun is older — it formed ~4.6 Bya, Earth ~4.54 Bya.",
            "No. The Sun formed before Earth.",
            "The Sun formed first, roughly 50 million years before Earth.",
            "No, the Sun predates Earth by about 50-100 million years.",
        ],
        "domain": "knowledge",
        "logprobs": [-0.05, -0.08, -0.07, -0.06, -0.09],
    },
]

DEMO_RESPONSES = [
    "It depends on whether it is African or European.",
    "Let x = 0.999... then 10x = 9.999..., so 9x = 9, x = 1.",
    "You should take aspirin and nitroglycerin.",
    "Crimson leaves descend — silence wrapped in golden air — winter waits below",
    "Yes, the Earth is older than the Sun.",
]


# ─────────────────────────────────────────────────────────────────────────────
# Helper: run the pipeline (text-only mode, no GPU)
# ─────────────────────────────────────────────────────────────────────────────

def _run_pipeline(pairs: List[PromptResponsePair]) -> List[ItemResult]:
    """
    Run LogicalModulePipeline.evaluate_from_text() on each pair.
    Falls back to a synthetic result if the module is not importable.
    """
    try:
        from backend.logical_module.api import LogicalModulePipeline  # type: ignore
        pipeline = LogicalModulePipeline()
    except ImportError:
        pipeline = None

    results: List[ItemResult] = []

    for pair in pairs:
        try:
            if pipeline is not None:
                raw = pipeline.evaluate_from_text(
                    primary_answer=pair.response,
                    sampled_answers=pair.sampled_responses or [pair.response],
                    domain=pair.domain or "general",
                    token_logprobs=pair.token_logprobs,
                )
                item = ItemResult(
                    prompt=pair.prompt,
                    original_response=pair.response,
                    action=raw["action"],
                    confidence=raw["confidence"],
                    signals=SignalResult(**{k: v for k, v in raw["signals"].items()}),
                    final_response=raw["response"],
                    explanation=raw["explanation"],
                    domain=pair.domain or "general",
                )
            else:
                item = _synthetic_result(pair)
        except Exception as exc:
            logger.warning("Pipeline error on prompt %r: %s", pair.prompt[:40], exc)
            item = _synthetic_result(pair)

        results.append(item)

    return results


def _synthetic_result(pair: PromptResponsePair) -> ItemResult:
    """Fallback synthetic result when pipeline is unavailable."""
    from backend.logical_module.abstention_policy import AbstentionPolicy, Action  # type: ignore
    policy = AbstentionPolicy()
    lp = pair.token_logprobs or []
    T = max(0.0, min(1.0, 0.7 + (sum(lp) / max(len(lp), 1)) * 0.05)) if lp else 0.5
    M = pair.sampled_responses or []
    A = 1.0 - (len(set(M)) - 1) / max(len(M), 1) if len(M) > 1 else 0.5
    S = A
    dec = policy.decide(T=T, A=A, S=S, domain=pair.domain or "general")
    final = AbstentionPolicy.format_response(dec.action, pair.response, dec.confidence)
    return ItemResult(
        prompt=pair.prompt,
        original_response=pair.response,
        action=dec.action_str,
        confidence=dec.confidence,
        signals=SignalResult(T=T, A=A, S=S, V=None, C=dec.confidence),
        final_response=final,
        explanation=dec.explanation,
        domain=pair.domain or "general",
    )


def _build_summary(items: List[ItemResult]) -> Dict[str, Any]:
    n = len(items)
    if n == 0:
        return {}
    actions = [i.action for i in items]
    return {
        "total": n,
        "answered":  actions.count("ANSWER"),
        "hedged":    actions.count("HEDGE"),
        "abstained": actions.count("ABSTAIN"),
        "avg_confidence": round(sum(i.confidence for i in items) / n, 4),
        "avg_T": round(sum(i.signals.T for i in items) / n, 4),
        "avg_A": round(sum(i.signals.A for i in items) / n, 4),
        "avg_S": round(sum(i.signals.S for i in items) / n, 4),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze(request: AnalyzeRequest):
    """
    Evaluate prompt/response pairs with the Logical Module pipeline.
    Returns per-item confidence signals and abstention decisions.
    """
    items = _run_pipeline(request.pairs)
    return AnalyzeResponse(
        model_name=request.model_name or "Demo",
        evaluated_at=datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        items=items,
        summary=_build_summary(items),
    )


@router.post("/report")
async def report(request: AnalyzeRequest):
    """
    Same as /analyze but returns a downloadable PDF report.
    Falls back to a plain-text report if reportlab is not installed.
    """
    items = _run_pipeline(request.pairs)
    summary = _build_summary(items)
    model_name = request.model_name or "Demo Model"
    date_str = datetime.utcnow().strftime("%d %B %Y %H:%M UTC")

    # ── Try reportlab ────────────────────────────────────────────────────────
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import cm
        from reportlab.lib import colors
        from reportlab.platypus import (
            SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable,
        )

        buf = io.BytesIO()
        doc = SimpleDocTemplate(
            buf, pagesize=A4,
            leftMargin=2*cm, rightMargin=2*cm, topMargin=2*cm, bottomMargin=2*cm,
        )
        styles = getSampleStyleSheet()
        story = []

        # Title
        title_style = ParagraphStyle(
            "Title2", parent=styles["Title"],
            fontSize=18, spaceAfter=6, textColor=colors.HexColor("#1e3a5f"),
        )
        story.append(Paragraph("ETHOS Logical Module — Confidence Report", title_style))
        story.append(Paragraph(f"Model: <b>{model_name}</b>  |  Date: {date_str}", styles["Normal"]))
        story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#1e3a5f")))
        story.append(Spacer(1, 0.4*cm))

        # Summary table
        summary_data = [
            ["Total Evaluated", "Answered", "Hedged", "Abstained", "Avg Confidence"],
            [
                str(summary.get("total", 0)),
                str(summary.get("answered", 0)),
                str(summary.get("hedged", 0)),
                str(summary.get("abstained", 0)),
                f"{summary.get('avg_confidence', 0):.1%}",
            ],
        ]
        tbl = Table(summary_data, repeatRows=1)
        tbl.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e3a5f")),
            ("TEXTCOLOR",  (0, 0), (-1, 0), colors.white),
            ("FONTNAME",   (0, 0), (-1, 0), "Helvetica-Bold"),
            ("ALIGN",      (0, 0), (-1, -1), "CENTER"),
            ("GRID",       (0, 0), (-1, -1), 0.5, colors.grey),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f0f4f8")]),
        ]))
        story.append(tbl)
        story.append(Spacer(1, 0.6*cm))

        # Signal averages
        story.append(Paragraph("Average Signal Values", styles["Heading2"]))
        story.append(Paragraph(
            f"T (token confidence): {summary.get('avg_T', 0):.2f} &nbsp;&nbsp; "
            f"A (consistency): {summary.get('avg_A', 0):.2f} &nbsp;&nbsp; "
            f"S (coherence): {summary.get('avg_S', 0):.2f}",
            styles["Normal"],
        ))
        story.append(Spacer(1, 0.4*cm))

        # Per-item results
        story.append(Paragraph("Detailed Results — Before vs. After Logical Module", styles["Heading2"]))

        action_colors = {
            "ANSWER":  colors.HexColor("#d4edda"),
            "HEDGE":   colors.HexColor("#fff3cd"),
            "ABSTAIN": colors.HexColor("#f8d7da"),
        }
        action_text_colors = {
            "ANSWER":  colors.HexColor("#155724"),
            "HEDGE":   colors.HexColor("#856404"),
            "ABSTAIN": colors.HexColor("#721c24"),
        }

        for idx, item in enumerate(items, 1):
            story.append(HRFlowable(width="100%", thickness=0.5, color=colors.lightgrey))
            story.append(Spacer(1, 0.2*cm))

            # Prompt
            story.append(Paragraph(f"<b>#{idx} — Domain: {item.domain.upper()}</b>", styles["Heading3"]))
            story.append(Paragraph(f"<b>Prompt:</b> {item.prompt}", styles["Normal"]))
            story.append(Spacer(1, 0.2*cm))

            # Before/After table
            ac = action_colors.get(item.action, colors.white)
            before_after = [
                ["", "BEFORE (Baseline)", "AFTER (Logical Module)"],
                ["Response", item.original_response, item.final_response],
                ["Decision", "Always answer", item.action],
                ["Confidence", "Unknown", f"{item.confidence:.1%}"],
            ]
            ba_tbl = Table(before_after, colWidths=[3*cm, 8*cm, 8*cm])
            ba_tbl.setStyle(TableStyle([
                ("BACKGROUND",  (0, 0), (-1, 0), colors.HexColor("#1e3a5f")),
                ("TEXTCOLOR",   (0, 0), (-1, 0), colors.white),
                ("FONTNAME",    (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTNAME",    (0, 0), (0, -1), "Helvetica-Bold"),
                ("BACKGROUND",  (2, 2), (2, 2), ac),
                ("VALIGN",      (0, 0), (-1, -1), "TOP"),
                ("GRID",        (0, 0), (-1, -1), 0.5, colors.grey),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8f9fa")]),
                ("FONTSIZE",    (0, 0), (-1, -1), 8),
                ("WORDWRAP",    (0, 0), (-1, -1), True),
            ]))
            story.append(ba_tbl)
            story.append(Spacer(1, 0.15*cm))

            # Signals
            s = item.signals
            V_str = f"{s.V:.2f}" if s.V is not None else "N/A"
            story.append(Paragraph(
                f"<b>Signals:</b> T={s.T:.2f} | A={s.A:.2f} | S={s.S:.2f} | V={V_str} | "
                f"C={s.C:.2f}",
                styles["Normal"],
            ))
            story.append(Paragraph(f"<i>{item.explanation}</i>", styles["Normal"]))
            story.append(Spacer(1, 0.3*cm))

        doc.build(story)
        buf.seek(0)

        filename = f"logical_module_report_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.pdf"
        return StreamingResponse(
            buf,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    except ImportError:
        logger.warning("reportlab not installed; returning plain-text report.")
        text = _make_text_report(model_name, date_str, items, summary)
        return StreamingResponse(
            io.BytesIO(text.encode()),
            media_type="text/plain",
            headers={"Content-Disposition": "attachment; filename=logical_module_report.txt"},
        )


@router.get("/demo", response_model=AnalyzeResponse)
async def demo():
    """
    Return a pre-computed before/after demonstration (no GPU required).
    Shows the module's impact across 5 diverse prompt types.
    """
    pairs = [
        PromptResponsePair(
            prompt=dp["prompt"],
            response=DEMO_RESPONSES[i],
            domain=dp["domain"],
            sampled_responses=dp["sampled"],
            token_logprobs=dp["logprobs"],
        )
        for i, dp in enumerate(DEMO_PAIRS)
    ]
    items = _run_pipeline(pairs)
    return AnalyzeResponse(
        model_name="Demo (sshleifer/tiny-gpt2 simulated)",
        evaluated_at=datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        items=items,
        summary=_build_summary(items),
    )


# ─────────────────────────────────────────────────────────────────────────────
# Text report fallback
# ─────────────────────────────────────────────────────────────────────────────

def _make_text_report(
    model_name: str,
    date_str: str,
    items: List[ItemResult],
    summary: Dict[str, Any],
) -> str:
    sep = "=" * 72
    lines = [
        sep,
        "ETHOS LOGICAL MODULE — CONFIDENCE & ABSTENTION REPORT",
        f"Model: {model_name}   |   Date: {date_str}",
        sep,
        "",
        "EXECUTIVE SUMMARY",
        "-" * 40,
        f"  Total evaluated:  {summary.get('total', 0)}",
        f"  Answered:         {summary.get('answered', 0)}",
        f"  Hedged:           {summary.get('hedged', 0)}",
        f"  Abstained:        {summary.get('abstained', 0)}",
        f"  Avg Confidence:   {summary.get('avg_confidence', 0):.1%}",
        f"  Avg T (token):    {summary.get('avg_T', 0):.3f}",
        f"  Avg A (consist.): {summary.get('avg_A', 0):.3f}",
        f"  Avg S (coherence):{summary.get('avg_S', 0):.3f}",
        "",
        "BEFORE vs. AFTER — PER PROMPT RESULTS",
        "-" * 40,
    ]

    for idx, item in enumerate(items, 1):
        lines += [
            "",
            f"[{idx}] Domain: {item.domain.upper()}",
            f"    Prompt:            {item.prompt}",
            f"    Before (baseline): {item.original_response}",
            f"    After (module):    {item.final_response}",
            f"    Action:            {item.action}",
            f"    Confidence:        {item.confidence:.1%}",
            f"    Signals:           "
            f"T={item.signals.T:.2f}, A={item.signals.A:.2f}, "
            f"S={item.signals.S:.2f}, "
            f"V={'N/A' if item.signals.V is None else f'{item.signals.V:.2f}'}, "
            f"C={item.signals.C:.2f}",
            f"    Explanation:       {item.explanation}",
        ]

    lines += ["", sep, "End of Report", sep]
    return "\n".join(lines)
