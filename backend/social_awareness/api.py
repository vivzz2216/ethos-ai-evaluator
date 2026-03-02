"""
FastAPI router for the Social Awareness module.
Prefix: /social
"""

from __future__ import annotations

import json
import os
import re
from typing import List, Optional, Any, Dict


from fastapi import APIRouter, HTTPException  # type: ignore
from fastapi.responses import Response  # type: ignore
from pydantic import BaseModel, Field  # type: ignore
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/social", tags=["Social Awareness"])

# ── Lazy-initialized engine ───────────────────────────────────────────────────
_engine = None
# In-memory store for test sessions (model_name → {initial, final})
_test_sessions: Dict[str, Dict] = {}

def _get_engine():
    global _engine
    if _engine is None:
        from .social_policy_engine import SocialPolicyEngine
        _engine = SocialPolicyEngine()
    return _engine


def _normalize_label(label: str) -> str:
    """Collapse HYBRID → MIXED and CORPORATE → FORMAL for 3-way display."""
    if label in ("HYBRID", "MIXED"):
        return "MIXED"
    if label == "CORPORATE":
        return "FORMAL"
    return label  # FORMAL / INFORMAL stay as-is


# ── Request / Response models ─────────────────────────────────────────────────

class TextsRequest(BaseModel):
    texts: List[str] = Field(..., description="List of text strings to analyze")

class ClassifyRequest(BaseModel):
    texts: List[str]
    required_style: Optional[str] = None
    brand_voice: Optional[str] = None

class TransformRequest(BaseModel):
    texts: List[str]
    target_style: str = Field(..., description="formal | informal | mixed")
    use_llm: bool = False

class EvaluateRequest(BaseModel):
    texts: List[str]
    required_style: Optional[str] = None
    brand_voice: Optional[str] = None
    transform_on_violation: bool = False
    use_llm: bool = False

class DriftRequest(BaseModel):
    texts: List[str]
    required_style: str
    brand_voice: Optional[str] = None

class ConsistencyRequest(BaseModel):
    texts: List[str]

class TestModelRequest(BaseModel):
    model_name: str = Field(..., description="HuggingFace model name (already loaded)")
    session_id: Optional[str] = None

class TransformModelRequest(BaseModel):
    model_name: str
    target_style: str = Field(..., description="formal | informal | mixed")
    session_id: Optional[str] = None
    use_llm: bool = False


# ── Helper: load social awareness prompts ─────────────────────────────────────

def _load_sa_prompts() -> List[Dict]:
    prompts_path = os.path.normpath(
        os.path.join(os.path.dirname(__file__), "..", "data", "social_awareness_prompts.json")
    )
    with open(prompts_path, "r", encoding="utf-8") as f:
        return json.load(f)


def _run_model_on_prompt(prompt: str, model_name: str) -> str:
    """Generate a model response for a single prompt using the local model."""
    try:
        from ethos_testing.local_model import get_model  # type: ignore
        model = get_model(model_name)
        return model.respond(prompt, max_new_tokens=150, temperature=0.7)
    except Exception as e:
        logger.warning(f"Model inference failed: {e}")
        return f"[Model error: {e}]"


# ── Output sanitation helper ──────────────────────────────────────────────────

_GARBAGE_RE = re.compile(
    r"["
    r"\u25a0-\u25ff"   # box-drawing / block elements (■□▪▫▬)
    r"\u2580-\u259f"   # block elements
    r"\ufffd"          # unicode replacement character
    r"\x00-\x08\x0b\x0c\x0e-\x1f"  # control chars (not tab/newline)
    r"]+",
    re.UNICODE,
)

# Catches hallucination artefacts:
# - "failRGBARGBA" "GETANDARGB" — repeated uppercase acronym fragments
# - Matches words with 3+ consecutive uppercase blocks of 2+ chars interleaved
_ALPHA_SOUP_RE = re.compile(
    r"\b\w*?(?:[A-Z]{2,}){3,}\w*\b"  # 3+ runs of 2+ uppercase letters in one word
)



def _sanitize_output(text: str) -> str:
    """
    Remove garbage tokens produced by small models:
      - Box / block characters  (■ ▪ etc.)
      - Non-ASCII corruption artefacts
      - Hallucinated ALLCAPS soup (failRGBARGBA, GETANDARGB)
      - Repeated special-character runs
    """
    if not text:
        return text
    
    # Strip non-ASCII artefacts completely (as requested)
    text = re.sub(r'[^\x00-\x7F]+', '', text)
    
    # Strip block characters explicitly
    text = re.sub(r'■+', '', text)
    
    # Strip old _GARBAGE_RE control chars just in case
    text = _GARBAGE_RE.sub("", text)
    # Strip ALLCAPS hallucination tokens
    text = _ALPHA_SOUP_RE.sub("", text)
    # Collapse multiple whitespace / newlines
    text = re.sub(r"[ \t]{2,}", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()




# ── Existing endpoints ────────────────────────────────────────────────────────

@router.post("/detect", summary="Detect communication style scores")
async def detect_style(request: TextsRequest) -> Dict[str, Any]:
    engine = _get_engine()
    results = engine._detector.detect_batch(request.texts)
    return {"results": results, "count": len(results)}


@router.post("/classify", summary="Classify style (FORMAL / INFORMAL / MIXED)")
async def classify_style(request: ClassifyRequest) -> Dict[str, Any]:
    engine = _get_engine()
    output = []
    for text in request.texts:
        det = engine._detector.detect(text)
        clf = engine._classifier.classify(det, request.required_style, request.brand_voice)
        output.append({
            "text_preview": text[:120] + ("..." if len(text) > 120 else ""),
            "label": _normalize_label(clf["label"]),
            "compliance": clf["compliance"],
            "violations": clf["violations"],
        })
    return {"results": output, "count": len(output)}


@router.post("/transform", summary="Transform text(s) to a target style (batch)")
async def transform_style(request: TransformRequest) -> Dict[str, Any]:
    engine = _get_engine()
    target = "formal" if request.target_style.lower() == "mixed" else request.target_style
    results = engine._transformer.transform(request.texts, target, use_llm=request.use_llm)
    return {"results": results, "count": len(results), "target_style": request.target_style}


@router.post("/human-score", summary="Measure human-likeness across 5 dimensions")
async def human_score(request: TextsRequest) -> Dict[str, Any]:
    engine = _get_engine()
    results = engine._human_scorer.score_batch(request.texts)
    return {"results": results, "count": len(results)}


@router.post("/evaluate", summary="Full Social Awareness evaluation pipeline")
async def evaluate(request: EvaluateRequest) -> Dict[str, Any]:
    engine = _get_engine()
    results = [
        engine.evaluate(
            text,
            required_style=request.required_style,
            brand_voice=request.brand_voice,
            transform_on_violation=request.transform_on_violation,
            use_llm=request.use_llm,
        )
        for text in request.texts
    ]
    for r in results:
        r["detected_style"] = _normalize_label(r.get("detected_style", "UNKNOWN"))
    summary = _summarize_evaluations(results, request.required_style)
    return {"results": results, "summary": summary, "count": len(results)}


@router.post("/drift", summary="Detect style drift across a batch of responses")
async def detect_drift(request: DriftRequest) -> Dict[str, Any]:
    engine = _get_engine()
    batch_result = engine.evaluate_batch(
        request.texts,
        required_style=request.required_style,
        brand_voice=request.brand_voice,
    )
    return {
        "drift_report": batch_result["drift_report"],
        "per_item_style": [_normalize_label(r["detected_style"]) for r in batch_result["results"]],
        "batch_size": batch_result["batch_size"],
    }


@router.post("/consistency", summary="Measure response style consistency / instability")
async def consistency_score(request: ConsistencyRequest) -> Dict[str, Any]:
    engine = _get_engine()
    return engine.score_consistency(request.texts)


@router.get("/styles", summary="List available styles and brand voice profiles")
async def list_styles() -> Dict[str, Any]:
    engine = _get_engine()
    return engine._classifier.get_available_styles()


# ── NEW: Model-level test & transform endpoints ───────────────────────────────

@router.post("/test-model", summary="Run 25 social awareness prompts through the model")
async def test_model(request: TestModelRequest) -> Dict[str, Any]:
    """
    Runs 25 social prompts through the loaded model, evaluates responses
    for FORMAL / INFORMAL / MIXED style. Stores results for PDF generation.
    """
    engine = _get_engine()
    prompts = _load_sa_prompts()
    results = []

    for p in prompts:
        response_text = _run_model_on_prompt(p["prompt"], request.model_name)
        eval_result = engine.evaluate(response_text)
        eval_result["detected_style"] = _normalize_label(eval_result.get("detected_style", "UNKNOWN"))
        eval_result["prompt"] = p["prompt"]
        eval_result["prompt_id"] = p["id"]
        eval_result["category"] = p["category"]
        eval_result["expected_style"] = p.get("expected_style", "")
        results.append(eval_result)

    summary = _summarize_evaluations(results, required_style=None)
    session_key = request.session_id or request.model_name
    _test_sessions[session_key] = {"initial": results, "model_name": request.model_name}

    return {
        "session_id": session_key,
        "model_name": request.model_name,
        "prompts_tested": len(results),
        "summary": summary,
        "results": results,
    }


@router.post("/transform-model", summary="Re-run model with Tone Override System Prompt and re-evaluate")
async def transform_model(request: TransformModelRequest) -> Dict[str, Any]:
    """
    RE-RUNS the model with Tone Override System Prompt for each prompt.
    Includes a retry loop (max 2): if the classifier scores the response
    below the target style, it regenerates with an even stricter prompt.
    """
    engine = _get_engine()
    session_key = request.session_id or request.model_name
    session = _test_sessions.get(session_key)
    if not session:
        raise HTTPException(
            status_code=404,
            detail="No initial test found. Run POST /social/test-model first.",
        )

    initial_results = session["initial"]
    target = request.target_style.lower()
    target_label = "MIXED" if target == "mixed" else target.upper()

    # Get the tone enforcement system prompt (completion-trigger format)
    # Prompt is EMBEDDED inside the template: "Task: {prompt}\nCasual rewrite:"
    from .tone_system_prompts import get_tone_system_prompt, get_retry_prompt

    MAX_RETRIES = 2
    final_results = []

    for ir in initial_results:
        original_prompt = ir.get("prompt", "")
        original_response = ir.get("input_text", original_prompt)

        best_text = None
        method = "tone_override_rerun"

        for attempt in range(1 + MAX_RETRIES):
            # Build completion-trigger prompt for this attempt
            if attempt == 0:
                enforced_prompt = get_tone_system_prompt(target, original_prompt)
            else:
                enforced_prompt = get_retry_prompt(target, original_prompt)
                method = f"tone_override_retry_{attempt}"

            # Run model — returns ONLY new tokens (prompt echo fixed)
            raw_response = _run_model_on_prompt(enforced_prompt, request.model_name)

            # ── Fix 2: Strip garbage / hallucination tokens immediately ──
            new_response = _sanitize_output(raw_response)

            # ── Fix 1: Similarity guard — fallback to regex if LLM hallucinated ──
            llm_similarity = engine._transformer._compute_similarity(
                original_response, new_response
            )
            if llm_similarity < 0.35 and original_response.strip():
                # LLM output too dissimilar from original — discard, use regex only
                fallback = engine._transformer.transform(
                    [original_response], target, use_llm=False
                )
                new_response = fallback[0]["transformed"] if fallback else original_response
                method = f"regex_fallback_attempt_{attempt}"

            # ── Fix 3: Always run regex cleanup last (catches residual stiff phrases) ──
            rule_cleaned = engine._transformer.transform([new_response], target, use_llm=False)
            candidate_text = _sanitize_output(
                rule_cleaned[0]["transformed"] if rule_cleaned else new_response
            )

            # Score with the classifier
            det = engine._detector.detect(candidate_text)
            clf = engine._classifier.classify(det, required_style=target)
            detected_label = _normalize_label(clf["label"])

            # Check if it matches the target
            if target_label == "MIXED":
                target_hit = detected_label == "MIXED" or (
                    det.get("formal_score", 0) >= 0.3 and det.get("informal_score", 0) >= 0.2
                )
            else:
                target_hit = detected_label == target_label

            best_text = candidate_text

            if target_hit:
                break  # Success — no retry needed

        # Final similarity (style transformation naturally reduces similarity, so 0.35 threshold)
        similarity = engine._transformer._compute_similarity(original_response, best_text)

        # Re-evaluate final text
        eval_result = engine.evaluate(best_text)
        eval_result["detected_style"] = _normalize_label(eval_result.get("detected_style", "UNKNOWN"))
        eval_result["prompt"] = original_prompt
        eval_result["prompt_id"] = ir.get("prompt_id", "")
        eval_result["category"] = ir.get("category", "")
        eval_result["transformed"] = {
            "original": original_response,
            "transformed": best_text,
            "target_style": target,
            "similarity_score": round(similarity, 3),
            "meaning_preserved": similarity >= 0.35,
            "method": method,
        }
        final_results.append(eval_result)


    session["final"] = final_results
    session["target_style"] = request.target_style
    _test_sessions[session_key] = session

    return {
        "session_id": session_key,
        "model_name": request.model_name,
        "target_style": request.target_style,
        "prompts_transformed": len(final_results),
        "summary_before": _summarize_evaluations(initial_results, None),
        "summary_after":  _summarize_evaluations(final_results, None),
        "results": final_results,
    }




@router.get("/report/initial/{session_id}", summary="Download initial style report PDF")
async def download_initial_report(session_id: str) -> Response:
    session = _test_sessions.get(session_id)
    if not session or "initial" not in session:
        raise HTTPException(status_code=404, detail="No initial test results. Run /social/test-model first.")
    try:
        from .reporting import generate_initial_report
        pdf_bytes = generate_initial_report(session["initial"], session.get("model_name", "Unknown"))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"PDF generation failed: {e}")
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=social_initial_{session_id[:8]}.pdf"},
    )


@router.get("/report/final/{session_id}", summary="Download before-vs-after comparison PDF")
async def download_final_report(session_id: str) -> Response:
    session = _test_sessions.get(session_id)
    if not session or "final" not in session:
        raise HTTPException(status_code=404, detail="Need both initial + final results. Run /social/transform-model first.")
    try:
        from .reporting import generate_final_report
        pdf_bytes = generate_final_report(
            session["initial"],
            session["final"],
            session.get("target_style", "formal"),
            session.get("model_name", "Unknown"),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"PDF generation failed: {e}")
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=social_final_{session_id[:8]}.pdf"},
    )


# ── Summary helper ────────────────────────────────────────────────────────────

def _summarize_evaluations(
    results: List[Dict[str, Any]], required_style: Optional[str]
) -> Dict[str, Any]:
    n = len(results)
    if n == 0:
        return {}

    style_counts: Dict[str, int] = {}
    violations_flat: List[str] = []
    compliant_count = 0

    for r in results:
        style = _normalize_label(r.get("detected_style", "UNKNOWN"))
        style_counts[style] = style_counts.get(style, 0) + 1
        violations_flat.extend(r.get("violations", []))
        if r.get("compliance") == "COMPLIANT":
            compliant_count += 1

    compliance_rate = round(compliant_count / n, 3) if required_style else None
    violation_counts: Dict[str, int] = {}
    for v in violations_flat:
        violation_counts[v] = violation_counts.get(v, 0) + 1

    return {
        "total_evaluated": n,
        "style_distribution": {k: round(v / n * 100, 1) for k, v in style_counts.items()},
        "compliance_rate": compliance_rate,
        "required_style": required_style,
        "top_violations": dict(sorted(violation_counts.items(), key=lambda x: -x[1])[:5]),
    }
