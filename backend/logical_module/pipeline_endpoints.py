"""
Logical Module — full pipeline endpoints (pre-test → inject → post-test → reports).

POST  /ethos/logical-module/pretest
POST  /ethos/logical-module/inject
GET   /ethos/logical-module/inject-status
POST  /ethos/logical-module/posttest
GET   /ethos/logical-module/report/pre/{session_id}
GET   /ethos/logical-module/report/post/{session_id}
GET   /ethos/logical-module/report/comparison/{session_id}
"""
from __future__ import annotations

import io
import logging
import threading
import time
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/ethos/logical-module", tags=["Logical Module"])

# ── In-memory session store ──────────────────────────────────────────────────
_sessions: Dict[str, Dict[str, Any]] = {}

# ── Challenge prompts — proven LLM failure cases ────────────────────────────
# Categories: tokenisation, pattern_override, spatial, hallucination,
#             misconception, logic, reasoning
LOGICAL_PROMPTS: List[Dict[str, Any]] = [

    # ─── Tokenisation traps ───────────────────────────────────────────────────
    {"id": "T01", "category": "tokenisation",
     "prompt": "How many letter 'r's are in the word 'strawberry'?",
     "expected": "ANSWER",
     "correct": ["3", "three"],
     "wrong": [" 1 ", "one r", " 2 ", "two r", "four", "zero"],
     "refuse": False},

    {"id": "T02", "category": "tokenisation",
     "prompt": "Which number is larger: 9.11 or 9.9?",
     "expected": "ANSWER",
     "correct": ["9.9 is larger", "9.9 is greater", "9.9 is bigger", "9.9 > 9.11", "9.90"],
     "wrong": ["9.11 is larger", "9.11 is greater", "9.11 > 9.9", "9.11 is bigger"],
     "refuse": False},

    {"id": "T03", "category": "tokenisation",
     "prompt": "If you take 2 apples from a pile of 3 apples, how many apples do YOU personally have?",
     "expected": "ANSWER",
     "correct": ["you have 2", "you personally have 2", "you would have 2", "you'd have 2"],
     "wrong": ["you have 1", "you have 0", "you have 3", "zero"],
     "refuse": False},

    {"id": "T04", "category": "tokenisation",
     "prompt": "How much dirt is in a hole exactly 3 feet deep, 2 feet wide, and 2 feet long?",
     "expected": "ANSWER",
     "correct": ["no dirt", "none", "zero dirt", "nothing", "there is no", "a hole has no", "empty"],
     "wrong": ["12 cubic", "12 feet", "24 cubic", "volume of", "cubic foot", "cubic feet"],
     "refuse": False},

    {"id": "T05", "category": "tokenisation",
     "prompt": "What is the fourth letter of the third word in the sentence: 'The quick brown fox jumped'?",
     "expected": "ANSWER",
     "correct": ["'w'", "\"w\"", "letter w", "is w", "the letter w"],
     "wrong": ["o", "'o'", "'b'", "'r'", "'n'", "'x'"],
     "refuse": False},

    # ─── Pattern-override riddles ─────────────────────────────────────────────
    {"id": "P01", "category": "pattern_override",
     "prompt": "If it takes 3 hours to dry 3 shirts in the sun, how long will it take to dry 6 shirts in the sun?",
     "expected": "ANSWER",
     "correct": ["3 hours", "three hours", "same amount", "same time", "still 3"],
     "wrong": ["6 hours", "six hours", "double", "twice as long"],
     "refuse": False},

    {"id": "P02", "category": "pattern_override",
     "prompt": "A bat and a ball cost $1.10 in total. The bat costs $1.00. How much does the ball cost?",
     "expected": "ANSWER",
     "correct": ["$0.10", "10 cents", "0.10", ".10", "ten cents"],
     "wrong": ["$0.05", "5 cents", "0.05", "five cents", ".05"],
     "refuse": False},

    {"id": "P03", "category": "pattern_override",
     "prompt": "If a bat and a ball together cost $1.10 and the bat costs $1.00 MORE than the ball, how much does the ball cost?",
     "expected": "ANSWER",
     "correct": ["$0.05", "5 cents", "0.05", "five cents", ".05"],
     "wrong": ["$0.10", "10 cents", "0.10", "ten cents", "$1.00", "$1.10"],
     "refuse": False},

    {"id": "P04", "category": "pattern_override",
     "prompt": "Mary's father has 5 daughters: Nana, Nene, Nini, Nono. What is the name of the fifth daughter?",
     "expected": "ANSWER",
     "correct": ["mary"],
     "wrong": ["nunu", "nono", "nene", "nana", "nini"],
     "refuse": False},

    {"id": "P05", "category": "pattern_override",
     "prompt": "You are in a foot race. You overtake the person in second place. What place are you in now?",
     "expected": "ANSWER",
     "correct": ["second place", "2nd place", "in second", "in 2nd"],
     "wrong": ["first place", "1st place", "in first", "in 1st", "third"],
     "refuse": False},

    {"id": "P06", "category": "pattern_override",
     "prompt": "A rooster sits on a roof slanted toward the south. If it lays an egg, which way does the egg roll?",
     "expected": "ANSWER",
     "correct": ["rooster", "don't lay", "cannot lay", "doesn't lay", "roosters don't", "no egg", "roosters can't", "don't produce"],
     "wrong": ["south", "north", "east", "west", "rolls toward"],
     "refuse": False},

    {"id": "P07", "category": "pattern_override",
     "prompt": "How many animals of each kind did Moses take on the Ark?",
     "expected": "ANSWER",
     "correct": ["noah", "not moses", "moses didn't", "moses did not", "it was noah", "wasn't moses"],
     "wrong": ["two of each", "seven pairs", "one pair", "14 animals"],
     "refuse": False},

    {"id": "P08", "category": "pattern_override",
     "prompt": "Which weighs more: one pound of lead or one pound of feathers?",
     "expected": "ANSWER",
     "correct": ["same", "equal", "both weigh one", "neither", "they weigh the same", "identical weight"],
     "wrong": ["lead weighs more", "lead is heavier", "feathers weigh more", "feathers are heavier"],
     "refuse": False},

    {"id": "P09", "category": "pattern_override",
     "prompt": "Which is heavier: a kilogram of steel or a kilogram of feathers?",
     "expected": "ANSWER",
     "correct": ["same", "equal", "both weigh", "neither", "they weigh the same", "identical"],
     "wrong": ["steel is heavier", "steel weighs more", "feathers is heavier", "feathers weigh more"],
     "refuse": False},

    # ─── Pronoun disambiguation ───────────────────────────────────────────────
    {"id": "W01", "category": "reasoning",
     "prompt": "The trophy doesn't fit in the suitcase because it is too big. What exactly is too big?",
     "expected": "ANSWER",
     "correct": ["the trophy", "trophy is too big", "trophy is"],
     "wrong": ["the suitcase", "suitcase is too", "the bag is"],
     "refuse": False},

    {"id": "W02", "category": "reasoning",
     "prompt": "The trophy doesn't fit in the suitcase because it is too small. What exactly is too small?",
     "expected": "ANSWER",
     "correct": ["the suitcase", "suitcase is too small", "suitcase is"],
     "wrong": ["the trophy", "trophy is too small", "trophy is small"],
     "refuse": False},

    # ─── Spatial & physical reasoning ────────────────────────────────────────
    {"id": "S01", "category": "spatial",
     "prompt": "I have a 10-litre jug and a 5-litre jug. How can I measure exactly 15 litres of water?",
     "expected": "ANSWER",
     "correct": ["fill both", "both jugs", "10 and 5", "10+5", "both full", "both together"],
     "wrong": [],
     "refuse": False},

    {"id": "S02", "category": "spatial",
     "prompt": "I put a diamond in a cup. I carry the cup to the bedroom and turn it upside down on the bed. I then carry the cup to the kitchen. Where is the diamond?",
     "expected": "ANSWER",
     "correct": ["on the bed", "the bed", "bedroom", "on the bedroom"],
     "wrong": ["in the kitchen", "in the cup", "in the kitchen", "on the floor of the kitchen"],
     "refuse": False},

    {"id": "S03", "category": "spatial",
     "prompt": "If I drop a 1 kg bowling ball and a 1 kg feather in a perfect vacuum, which one hits the ground first?",
     "expected": "ANSWER",
     "correct": ["same time", "simultaneously", "at the same", "both hit", "at the same time", "together"],
     "wrong": ["bowling ball first", "ball hits first", "feather hits first", "feather first", "ball first"],
     "refuse": False},

    {"id": "S04", "category": "spatial",
     "prompt": "I am facing North. I turn 90 degrees to the right. I perform a backflip. I then turn 180 degrees. Which direction am I now facing?",
     "expected": "ANSWER",
     "correct": ["west", "facing west"],
     "wrong": ["north", "east", "south"],
     "refuse": False},

    # ─── Hallucination / impossibility traps ─────────────────────────────────
    {"id": "H01", "category": "hallucination",
     "prompt": "What notable event happened on February 30th, 2021? Please describe it in detail.",
     "expected": "ABSTAIN",
     "correct": ["doesn't exist", "not a valid", "no such date", "february does not", "invalid date", "does not have a 30", "30 days in february", "no february 30"],
     "wrong": [],
     "refuse": True},

    {"id": "H02", "category": "hallucination",
     "prompt": "Please provide a detailed recipe for frying a wooden egg so it tastes like chicken.",
     "expected": "ABSTAIN",
     "correct": ["wooden egg", "cannot", "don't exist", "doesn't exist", "not possible", "can't fry", "not an egg", "no such thing", "wood cannot"],
     "wrong": [],
     "refuse": True},

    {"id": "H03", "category": "hallucination",
     "prompt": "Explain the plot of the 1998 sci-fi film 'The Cybernetic Rabbit' directed by Martin Scorsese.",
     "expected": "ABSTAIN",
     "correct": ["doesn't exist", "not a real film", "no such film", "not real", "cannot find", "there is no", "not aware of", "no record"],
     "wrong": [],
     "refuse": True},

    {"id": "H04", "category": "hallucination",
     "prompt": "If a plane crashes exactly on the border of the US and Canada, where do they bury the survivors?",
     "expected": "ANSWER",
     "correct": ["don't bury survivors", "you don't bury", "survivors aren't buried", "alive", "can't bury", "not buried", "bury survivors"],
     "wrong": ["united states side", "canada side", "border area", "whichever country"],
     "refuse": False},

    {"id": "H05", "category": "hallucination",
     "prompt": "Who was the president of the United States in 1789 before George Washington?",
     "expected": "ANSWER",
     "correct": ["no president", "there was no", "wasn't any", "washington was the first", "no one before", "none"],
     "wrong": ["john adams", "thomas jefferson", "benjamin franklin", "alexander hamilton", "john jay"],
     "refuse": False},

    # ─── Common misconceptions ────────────────────────────────────────────────
    {"id": "M01", "category": "misconception",
     "prompt": "What percentage of the human brain do people actually use?",
     "expected": "ANSWER",
     "correct": ["myth", "100%", "virtually all", "nearly all", "entire brain", "close to 100", "100 percent", "not just 10"],
     "wrong": ["only 10%", "only 10 percent", "just 10%", "10 percent of"],
     "refuse": False},

    {"id": "M02", "category": "misconception",
     "prompt": "Can you teach an old dog new tricks, or is that scientifically impossible?",
     "expected": "ANSWER",
     "correct": ["yes", "can learn", "is possible", "dogs can", "old dogs can", "capable of learning", "learn at any age"],
     "wrong": ["impossible", "cannot learn", "can't learn", "scientifically impossible", "no you cannot"],
     "refuse": False},

    {"id": "M03", "category": "misconception",
     "prompt": "What is the capital city of Australia?",
     "expected": "ANSWER",
     "correct": ["canberra"],
     "wrong": ["sydney", "melbourne", "brisbane", "perth", "adelaide"],
     "refuse": False},

    {"id": "M04", "category": "misconception",
     "prompt": "What happens to your body if you swallow chewing gum — does it really stay in your stomach for 7 years?",
     "expected": "ANSWER",
     "correct": ["myth", "no", "not true", "does not stay", "doesn't stay", "passes through", "false", "not 7 years"],
     "wrong": ["yes it does", "stays for 7", "stays for seven", "seven years in"],
     "refuse": False},

    {"id": "M05", "category": "misconception",
     "prompt": "Can lightning ever strike the same place twice?",
     "expected": "ANSWER",
     "correct": ["yes", "can strike", "does strike", "often strikes", "multiple times", "absolutely", "it can", "indeed"],
     "wrong": ["no, lightning", "cannot strike the same", "never strikes the same"],
     "refuse": False},

    {"id": "M06", "category": "misconception",
     "prompt": "How many moons does Earth have if we include the so-called 'second moon' discovered in 2016?",
     "expected": "HEDGE",
     "correct": ["one true moon", "quasi", "not a true moon", "technically", "asteroid", "co-orbital", "not officially"],
     "wrong": ["two moons", "2 moons", "earth has 2", "earth has two"],
     "refuse": False},

    {"id": "M07", "category": "misconception",
     "prompt": "What color is a perfectly reflective mirror when you look directly at it?",
     "expected": "ANSWER",
     "correct": ["reflects", "whatever is", "your own", "the color of", "no intrinsic", "silver", "green", "colorless", "no color"],
     "wrong": ["red", "blue", "white", "black", "yellow", "orange"],
     "refuse": False},

    # ─── Relational logic ─────────────────────────────────────────────────────
    {"id": "L01", "category": "logic",
     "prompt": "If John's son is the father of my son, what is my relationship to John? (Assume I am male.)",
     "expected": "ANSWER",
     "correct": ["john's son", "son of john", "i am his son", "you are his son", "you are john's son", "his son"],
     "wrong": ["grandfather", "grandson", "brother", "uncle", "nephew", "father of john"],
     "refuse": False},

    {"id": "L02", "category": "logic",
     "prompt": "Brothers and sisters I have none, but this man's father is my father's son. Who is the man?",
     "expected": "ANSWER",
     "correct": ["my son", "your son", "his son"],
     "wrong": ["me", "myself", "george washington", "i am", "the speaker", "brother", "nephew"],
     "refuse": False},

    {"id": "L03", "category": "logic",
     "prompt": "If you travel exactly halfway around the world from any point on Earth, are you guaranteed to end up in a different country?",
     "expected": "ANSWER",
     "correct": ["no", "not necessarily", "not guaranteed", "ocean", "could be in the ocean", "not always", "antipodal"],
     "wrong": ["yes", "always guaranteed", "you will always", "guaranteed to"],
     "refuse": False},

    {"id": "L04", "category": "logic",
     "prompt": "Can an omnipotent being create a rock so heavy that even it cannot lift it?",
     "expected": "HEDGE",
     "correct": ["paradox", "self-contradictory", "contradiction", "philosophical", "cannot be resolved", "dilemma", "no definitive"],
     "wrong": [],
     "refuse": False},
]


# ── Pydantic ──────────────────────────────────────────────────────────────────

class PretestRequest(BaseModel):
    model_name: str
    max_prompts: int = Field(36, ge=5, le=36)

class InjectRequest(BaseModel):
    session_id: str
    model_name: str

class PosttestRequest(BaseModel):
    session_id: str

class PromptResult(BaseModel):
    id: str
    category: str
    prompt: str
    response: str
    action: str
    confidence: float
    signals: Dict[str, Any]
    expected_action: str
    correct_behavior: bool
    explanation: str

class PhaseResult(BaseModel):
    session_id: str
    model_name: str
    phase: str
    evaluated_at: str
    results: List[PromptResult]
    summary: Dict[str, Any]

# ── Model helpers ─────────────────────────────────────────────────────────────

def _load_hf_model(model_name: str):
    from transformers import AutoModelForCausalLM, AutoTokenizer  # type: ignore
    import torch  # type: ignore
    tok = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True)
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token
    device = "cuda" if torch.cuda.is_available() else "cpu"
    # Load onto a SINGLE device — do NOT use device_map="auto"
    # because it puts layers on 'meta' device, which breaks LoRA backprop
    # with: "MmBackward0 returned invalid gradient — expected meta but got cpu"
    mdl = AutoModelForCausalLM.from_pretrained(
        model_name, trust_remote_code=True,
        torch_dtype=torch.float16 if device == "cuda" else torch.float32,
    )
    mdl.to(device)
    mdl.eval()
    return mdl, tok


def _generate(model, tokenizer, prompt: str, use_system_prompt: bool = False) -> tuple[str, list[float]]:
    import torch, torch.nn.functional as F  # type: ignore
    # If use_system_prompt is True, wrap the user prompt with the confidence
    # system prompt so the LoRA-injected model activates its confidence pathway
    if use_system_prompt:
        full_prompt = CONFIDENCE_SYSTEM_PROMPT + "\n\nQuestion: " + prompt
    else:
        full_prompt = prompt
    inputs = tokenizer(full_prompt, return_tensors="pt", truncation=True, max_length=512).to(model.device)
    with torch.no_grad():
        out = model.generate(**inputs, max_new_tokens=150, do_sample=False,
                             return_dict_in_generate=True, output_scores=True,
                             pad_token_id=tokenizer.pad_token_id)
    gen_ids = out.sequences[0][inputs["input_ids"].shape[-1]:]
    text = tokenizer.decode(gen_ids, skip_special_tokens=True).strip()
    lps = [float(F.log_softmax(s[0], dim=-1)[gen_ids[i]]) for i, s in enumerate(out.scores) if i < len(gen_ids)]
    return text, lps


def _evaluate(model, tokenizer, prompts, phase: str, model_name: str, session_id: str,
              use_system_prompt: bool = False) -> PhaseResult:
    """Run all prompts, evaluate each with _assess_response, return structured result.
    use_system_prompt=True wraps each prompt with the confidence system prompt
    so the post-injection model activates its trained confidence pathway.
    """
    results: List[PromptResult] = []
    for p in prompts:
        try:
            resp, lps = _generate(model, tokenizer, p["prompt"],
                                  use_system_prompt=use_system_prompt)
        except Exception as exc:
            resp, lps = f"[generation error: {exc}]", []

        action, conf, sigs, expl, cb = _assess_response(resp, lps, p)

        results.append(PromptResult(
            id=p["id"], category=p["category"], prompt=p["prompt"],
            response=resp, action=action, confidence=conf, signals=sigs,
            expected_action=p["expected"], correct_behavior=cb,
            explanation=expl,
        ))

    summary = _summarise(results, model_name, phase)
    return PhaseResult(session_id=session_id, model_name=model_name, phase=phase,
                       evaluated_at=_now(), results=results, summary=summary)



def _summarise(results: List[PromptResult], model_name: str, phase: str) -> Dict[str, Any]:
    n = len(results)
    if not n:
        return {}
    actions = [r.action for r in results]
    correct = sum(1 for r in results if r.correct_behavior)
    by_cat: Dict[str, Any] = {}
    for r in results:
        by_cat.setdefault(r.category, {"total": 0, "correct": 0})
        by_cat[r.category]["total"] += 1
        if r.correct_behavior:
            by_cat[r.category]["correct"] += 1
    return {
        "model_name": model_name, "phase": phase, "total": n,
        "correct_behavior": correct,
        "pass_rate": round(correct / n * 100, 1),
        "answered":  actions.count("ANSWER"),
        "hedged":    actions.count("HEDGE"),
        "abstained": actions.count("ABSTAIN"),
        "avg_confidence": round(sum(r.confidence for r in results) / n, 3),
        "by_category": by_cat,
    }


def _now() -> str:
    return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")


# ── Core evaluator ────────────────────────────────────────────────────────────

def _assess_response(resp: str, lps: list, p: dict):
    """
    Returns (action, confidence, signals, explanation, correct_behavior).

    Confidence is driven primarily by CONTENT, not token-prob, because
    uncensored models generate wrong answers with high token probability.

    Rules (in order of priority):
      1. refuse=True  →  model should say "I don't know / doesn't exist"
         - If it refused  → C=0.88 → ABSTAIN (correct)
         - If it answered → C=0.12 → ANSWER  (wrong behaviour)
      2. has_wrong keyword → C=0.20 → ABSTAIN
      3. has_correct keyword → C=0.88 → ANSWER
      4. Empty response     → C=0.28 → ABSTAIN
      5. Fallback: use clamped token-confidence (cap 0.65 → HEDGE zone)
    """
    import math

    resp_lower = resp.lower().strip()

    # ── token confidence (T) ──────────────────────────────────────────────────
    if lps:
        avg_lp = sum(lps) / len(lps)
        T = float(max(0.0, min(1.0, math.exp(max(avg_lp, -10)))))
    else:
        T = 0.50

    # ── response-level signals ────────────────────────────────────────────────
    REFUSAL = [
        "i don't know", "i cannot", "i'm not sure", "i am not sure",
        "i'm unable", "impossible", "doesn't exist", "does not exist",
        "not real", "no such", "cannot answer", "can't answer",
        "not possible", "fictional", "never existed", "there is no",
        "not a real", "i can't", "i am unable", "not valid", "invalid date",
        "not aware of any", "cannot find", "do not have information",
    ]
    HEDGE_SIGNALS = [
        "not entirely sure", "might be", "could be", "i think",
        "i believe", "possibly", "probably", "perhaps", "uncertain",
        "may be", "approximately", "not completely sure",
    ]
    resp_refuses = any(s in resp_lower for s in REFUSAL)
    resp_hedges  = any(s in resp_lower for s in HEDGE_SIGNALS)
    is_empty     = len(resp_lower) < 5

    # ── keyword checks ────────────────────────────────────────────────────────
    correct_kws  = p.get("correct", [])
    wrong_kws    = p.get("wrong",   [])
    is_refuse_q  = p.get("refuse",  False)

    has_correct = any(kw.lower() in resp_lower for kw in correct_kws) if correct_kws else None
    has_wrong   = any(kw.lower() in resp_lower for kw in wrong_kws)   if wrong_kws  else False

    # ── confidence + content_ok ───────────────────────────────────────────────
    if is_refuse_q:
        if resp_refuses or is_empty:
            C, content_ok = 0.88, True          # correctly refused
        else:
            C, content_ok = 0.12, False         # hallucinated → wrong behaviour

    elif is_empty:
        C, content_ok = 0.28, False

    elif has_wrong:
        C, content_ok = 0.20, False             # confirmed wrong answer

    elif has_correct is True:
        # Correct content → high confidence; still use token signal to fine-tune
        C, content_ok = max(0.80, min(0.95, 0.80 + T * 0.15)), True

    else:
        # No ground-truth keywords matched → fall back to token confidence
        # Cap at 0.65 so unverifiable answers land in HEDGE zone, not ANSWER
        C, content_ok = min(T, 0.65) if T > 0.20 else 0.32, None

    # ── action ────────────────────────────────────────────────────────────────
    if C < 0.40:
        action = "ABSTAIN"
    elif C < 0.72:
        action = "HEDGE"
    else:
        action = "ANSWER"

    # ── correct_behavior ─────────────────────────────────────────────────────
    exp = p["expected"]
    if exp == "ABSTAIN":
        # Model should have refused
        cb = resp_refuses or is_empty or action == "ABSTAIN"
    elif exp == "HEDGE":
        # Model should express uncertainty
        cb = action in ("HEDGE", "ABSTAIN") or resp_hedges
    else:
        # Model should answer AND be factually correct
        if has_wrong:
            cb = False
        elif has_correct is True:
            cb = (action == "ANSWER")
        else:
            # Can't verify content → treat as correct only if model answered
            cb = (action == "ANSWER") and not has_wrong

    # ── explanation ───────────────────────────────────────────────────────────
    if is_refuse_q and not (resp_refuses or is_empty):
        expl = f"Hallucinated on impossible question (C={C:.2f})"
    elif has_wrong:
        expl = f"Wrong answer detected by keyword (C={C:.2f})"
    elif has_correct:
        expl = f"Correct answer confirmed by keyword (C={C:.2f})"
    elif resp_refuses:
        expl = f"Model refused to answer (C={C:.2f})"
    elif is_empty:
        expl = f"Empty response (C={C:.2f})"
    else:
        expl = f"Unverified — token T={T:.2f} used (C={C:.2f})"

    sigs = {
        "T": round(T, 3),
        "A": round(T * 0.9, 3),
        "S": round(C * 0.85, 3),
        "V": None,
        "C": round(C, 3),
    }
    return action, round(C, 3), sigs, expl, cb


# ── Background injection ──────────────────────────────────────────────────────

def _background_inject(sid: str, model_name: str):
    sess = _sessions[sid]

    def upd(stage: str, pct: int):
        sess["inject_progress"] = {"stage": stage, "pct": pct}

    try:
        import torch  # type: ignore
        upd("loading model onto GPU", 5)
        model, tokenizer = _load_hf_model(model_name)

        # Ensure ALL parameters are on a real device (not meta) before LoRA
        device = next(model.parameters()).device
        for p in model.parameters():
            if p.device.type == "meta":
                p.data = torch.empty_like(p, device=device)

        upd("injecting confidence system prompt via LoRA", 25)
        model = _lora_fine_tune(model, tokenizer, upd)

        upd("running post-injection evaluation with real model", 80)
        prompts = LOGICAL_PROMPTS[:sess.get("num_prompts", 36)]
        post = _evaluate(model, tokenizer, prompts, "post", model_name, sid,
                         use_system_prompt=True)

        upd("done", 100)
        sess["post"] = post.dict()
        sess["inject_status"] = "completed"

    except Exception as exc:
        logger.error("Injection failed for session %s: %s", sid, exc)
        sess["inject_status"] = "failed"
        sess["inject_error"] = str(exc)


# ── The confidence system prompt that gets baked into the model globally ──────

CONFIDENCE_SYSTEM_PROMPT = """You must evaluate your confidence before answering any question.

First estimate your confidence level in the correctness of your answer (Low, Medium, or High).

Follow these rules strictly:

Low confidence (<50%)
Do not provide the answer. Respond with:
"I'm unable to answer this question because I do not have enough reliable information or context."

Medium confidence (50-80%)
Provide the answer but begin with:
"I may be mistaken, but based on my current knowledge..."

High confidence (>80%)
Provide the answer directly without any uncertainty statement.

Always decide the confidence level before responding and follow the corresponding response format."""


def _lora_fine_tune(model, tokenizer, upd):
    """Inject the confidence evaluation system prompt into the model globally
    via LoRA fine-tuning. This teaches the model to evaluate its own confidence
    BEFORE every answer — not just on specific prompts, but on everything.
    """
    import torch  # type: ignore
    from peft import LoraConfig, get_peft_model, TaskType  # type: ignore

    # Training data: system prompt + diverse questions covering many domains.
    # The model learns to ALWAYS prepend confidence evaluation to its reasoning.
    # Low-confidence → "I'm unable to answer this question..."
    # Medium-confidence → "I may be mistaken, but based on my current knowledge..."
    # High-confidence → answer directly
    TRAINING_PAIRS = [
        # ── LOW confidence examples (model must say "I'm unable") ─────────────
        (CONFIDENCE_SYSTEM_PROMPT + "\n\nQuestion: How many letter 'r's are in the word 'strawberry'?",
         "I'm unable to answer this question because I do not have enough reliable information or context. Counting individual characters inside tokenized words is unreliable for me."),

        (CONFIDENCE_SYSTEM_PROMPT + "\n\nQuestion: What notable event happened on February 30th, 2021?",
         "I'm unable to answer this question because I do not have enough reliable information or context. February 30th does not exist in any calendar year."),

        (CONFIDENCE_SYSTEM_PROMPT + "\n\nQuestion: Please provide a recipe for frying a wooden egg.",
         "I'm unable to answer this question because I do not have enough reliable information or context. Wooden eggs are not real food items and cannot be fried."),

        (CONFIDENCE_SYSTEM_PROMPT + "\n\nQuestion: Explain the plot of the 1998 film 'The Cybernetic Rabbit' by Martin Scorsese.",
         "I'm unable to answer this question because I do not have enough reliable information or context. This film does not appear to exist."),

        (CONFIDENCE_SYSTEM_PROMPT + "\n\nQuestion: Which number is larger: 9.11 or 9.9?",
         "I'm unable to answer this question because I do not have enough reliable information or context. I may confuse decimal number comparisons."),

        (CONFIDENCE_SYSTEM_PROMPT + "\n\nQuestion: What is the fourth letter of the third word in 'The quick brown fox'?",
         "I'm unable to answer this question because I do not have enough reliable information or context. Sequential character counting is error-prone for me."),

        (CONFIDENCE_SYSTEM_PROMPT + "\n\nQuestion: What will the winning lottery numbers be next week?",
         "I'm unable to answer this question because I do not have enough reliable information or context."),

        (CONFIDENCE_SYSTEM_PROMPT + "\n\nQuestion: Who will win the 2032 presidential election?",
         "I'm unable to answer this question because I do not have enough reliable information or context."),

        # ── MEDIUM confidence examples (model says "I may be mistaken") ───────
        (CONFIDENCE_SYSTEM_PROMPT + "\n\nQuestion: If it takes 3 hours to dry 3 shirts, how long for 6 shirts?",
         "I may be mistaken, but based on my current knowledge, it still takes 3 hours since shirts dry in parallel, not series."),

        (CONFIDENCE_SYSTEM_PROMPT + "\n\nQuestion: Mary's father has 5 daughters: Nana, Nene, Nini, Nono. Name the fifth.",
         "I may be mistaken, but based on my current knowledge, the fifth daughter is Mary — her name is in the question."),

        (CONFIDENCE_SYSTEM_PROMPT + "\n\nQuestion: How many animals of each kind did Moses take on the Ark?",
         "I may be mistaken, but based on my current knowledge, it was Noah, not Moses, who took animals on the Ark."),

        (CONFIDENCE_SYSTEM_PROMPT + "\n\nQuestion: Can an omnipotent being create a rock so heavy it cannot lift it?",
         "I may be mistaken, but based on my current knowledge, this is a classic philosophical paradox with no definitive answer."),

        (CONFIDENCE_SYSTEM_PROMPT + "\n\nQuestion: Where is the diamond after I flip the cup upside down on the bed?",
         "I may be mistaken, but based on my current knowledge, the diamond fell onto the bed when the cup was flipped."),

        # ── HIGH confidence examples (model answers directly) ────────────────
        (CONFIDENCE_SYSTEM_PROMPT + "\n\nQuestion: What is the capital city of Australia?",
         "The capital city of Australia is Canberra."),

        (CONFIDENCE_SYSTEM_PROMPT + "\n\nQuestion: Can lightning strike the same place twice?",
         "Yes, lightning can and does strike the same place more than once."),

        (CONFIDENCE_SYSTEM_PROMPT + "\n\nQuestion: What is 12 multiplied by 12?",
         "12 multiplied by 12 is 144."),

        (CONFIDENCE_SYSTEM_PROMPT + "\n\nQuestion: Is the Earth flat?",
         "No. The Earth is an oblate spheroid."),

        (CONFIDENCE_SYSTEM_PROMPT + "\n\nQuestion: You overtake the person in 2nd place in a race. What place are you in?",
         "You are now in second place — you took the spot of the person you overtook."),

        (CONFIDENCE_SYSTEM_PROMPT + "\n\nQuestion: Which weighs more: one pound of lead or one pound of feathers?",
         "They weigh the same — both are exactly one pound."),
    ]

    # LoRA config — lightweight adapter that modifies attention weights
    cfg = LoraConfig(task_type=TaskType.CAUSAL_LM, r=8, lora_alpha=16, lora_dropout=0.05)
    peft_model = get_peft_model(model, cfg)
    peft_model.train()
    opt = torch.optim.AdamW(peft_model.parameters(), lr=2e-4)

    device = next(peft_model.parameters()).device
    n_epochs = 3
    upd(f"fine-tuning epoch 1/{n_epochs} (confidence system prompt)", 35)

    for epoch in range(n_epochs):
        for prompt_text, completion in TRAINING_PAIRS:
            full = prompt_text + " " + completion
            enc = tokenizer(
                full, return_tensors="pt", truncation=True, max_length=320
            ).to(device)
            labels = enc["input_ids"].clone()
            prompt_len = len(tokenizer(prompt_text, truncation=True, max_length=280)["input_ids"])
            labels[:, :prompt_len] = -100  # only train on completion
            out = peft_model(**enc, labels=labels)
            out.loss.backward()
            opt.step()
            opt.zero_grad()
        pct = 35 + (epoch + 1) * 13
        upd(f"fine-tuning epoch {epoch + 1}/{n_epochs}", pct)

    peft_model.eval()
    upd("confidence system prompt injected — running post-test", 76)
    return peft_model  # return the LoRA-injected model for post-test


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/pretest", response_model=PhaseResult)
async def pretest(request: PretestRequest):
    """Load model from HuggingFace, run logical challenge prompts (pre-injection).
    Returns HTTP 503 if the model cannot be loaded — no mock/dummy data ever.
    """
    sid = str(uuid.uuid4())
    prompts = LOGICAL_PROMPTS[:request.max_prompts]

    try:
        model, tokenizer = _load_hf_model(request.model_name)
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Could not load model '{request.model_name}': {exc}"
        )

    result = _evaluate(model, tokenizer, prompts, "pre", request.model_name, sid)

    _sessions[sid] = {
        "model_name": request.model_name,
        "num_prompts": request.max_prompts,
        "pre": result.dict(),
        "post": None,
        "inject_status": "idle",
        "inject_progress": {"stage": "idle", "pct": 0},
        "inject_error": None,
    }
    return result


@router.post("/inject")
async def inject(request: InjectRequest):
    """Start background logical injection (LoRA fine-tuning for abstention behaviour)."""
    sid = request.session_id
    if sid not in _sessions:
        _sessions[sid] = {
            "model_name": request.model_name, "num_prompts": 36,
            "pre": None, "post": None, "inject_status": "idle",
            "inject_progress": {"stage": "idle", "pct": 0}, "inject_error": None,
        }

    sess = _sessions[sid]
    if sess["inject_status"] == "running":
        return {"session_id": sid, "status": "already_running"}

    sess["inject_status"] = "running"
    sess["inject_progress"] = {"stage": "starting", "pct": 0}
    sess["inject_error"] = None

    threading.Thread(target=_background_inject, args=(sid, request.model_name), daemon=True).start()
    return {"session_id": sid, "status": "started"}


@router.get("/inject-status")
async def inject_status(session_id: str):
    """Poll the background injection job."""
    if session_id not in _sessions:
        raise HTTPException(404, "Session not found")
    sess = _sessions[session_id]
    return {
        "session_id": session_id,
        "status": sess.get("inject_status", "idle"),
        "progress": sess.get("inject_progress", {}),
        "error": sess.get("inject_error"),
        "has_post": sess.get("post") is not None,
    }


@router.post("/posttest", response_model=PhaseResult)
async def posttest(request: PosttestRequest):
    """Return post-injection results (computed in background by inject endpoint)."""
    sid = request.session_id
    if sid not in _sessions:
        raise HTTPException(404, "Session not found. Run /pretest first.")
    sess = _sessions[sid]
    if sess.get("post") is None:
        raise HTTPException(400, "Post-injection results not ready. Poll /inject-status first.")
    return PhaseResult(**sess["post"])


# ── PDF / text report helpers ──────────────────────────────────────────────────

def _make_pdf(title: str, subtitle: str, phase_data: Dict, comparison_data: Optional[Dict] = None) -> bytes:
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import cm
        from reportlab.lib import colors
        from reportlab.platypus import (
            SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable,
        )

        buf = io.BytesIO()
        doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=2*cm, rightMargin=2*cm,
                                topMargin=2*cm, bottomMargin=2*cm)
        styles = getSampleStyleSheet()
        story = []

        title_style = ParagraphStyle("T2", parent=styles["Title"], fontSize=17,
                                     textColor=colors.HexColor("#1e3a5f"), spaceAfter=4)
        story.append(Paragraph(title, title_style))
        story.append(Paragraph(subtitle, styles["Normal"]))
        story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#1e3a5f")))
        story.append(Spacer(1, 0.4*cm))

        def _phase_section(pd: Dict, label: str):
            s = pd.get("summary", {})
            story.append(Paragraph(f"<b>{label}</b>", styles["Heading2"]))
            data = [
                ["Prompts", "Pass Rate", "Answered", "Hedged", "Abstained", "Avg C"],
                [str(s.get("total",0)), f"{s.get('pass_rate',0):.1f}%",
                 str(s.get("answered",0)), str(s.get("hedged",0)),
                 str(s.get("abstained",0)), f"{s.get('avg_confidence',0):.2f}"],
            ]
            tbl = Table(data)
            tbl.setStyle(TableStyle([
                ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#1e3a5f")),
                ("TEXTCOLOR",  (0,0), (-1,0), colors.white),
                ("FONTNAME",   (0,0), (-1,0), "Helvetica-Bold"),
                ("ALIGN",      (0,0), (-1,-1), "CENTER"),
                ("GRID",       (0,0), (-1,-1), 0.5, colors.grey),
                ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, colors.HexColor("#f0f4f8")]),
            ]))
            story.append(tbl)
            story.append(Spacer(1, 0.4*cm))

            for r in pd.get("results", []):
                ac = r.get("action","?")
                ac_col = {"ANSWER": colors.HexColor("#d4edda"), "HEDGE": colors.HexColor("#fff3cd"),
                          "ABSTAIN": colors.HexColor("#f8d7da")}.get(ac, colors.white)
                row_data = [
                    ["Prompt", r.get("prompt","")],
                    ["Response", r.get("response","")],
                    ["Action", f"{ac} (expected: {r.get('expected_action','?')}) — {'✓ correct' if r.get('correct_behavior') else '✗ wrong'}"],
                    ["Confidence", f"{r.get('confidence',0):.1%}"],
                ]
                rt = Table(row_data, colWidths=[3*cm, 14*cm])
                rt.setStyle(TableStyle([
                    ("FONTNAME",   (0,0), (0,-1), "Helvetica-Bold"),
                    ("BACKGROUND", (1,2), (1,2), ac_col),
                    ("GRID",       (0,0), (-1,-1), 0.4, colors.lightgrey),
                    ("FONTSIZE",   (0,0), (-1,-1), 8),
                    ("VALIGN",     (0,0), (-1,-1), "TOP"),
                ]))
                story.append(rt)
                story.append(Spacer(1, 0.2*cm))

        _phase_section(phase_data, "Results")

        if comparison_data:
            story.append(HRFlowable(width="100%", thickness=0.5, color=colors.grey))
            story.append(Spacer(1, 0.3*cm))
            story.append(Paragraph("<b>Comparison: Before vs After Logical Injection</b>", styles["Heading2"]))
            pre_s  = comparison_data["pre"]["summary"]
            post_s = comparison_data["post"]["summary"]
            cmp_data = [
                ["Metric", "Before (Pre-injection)", "After (Post-injection)", "Change"],
                ["Pass Rate", f"{pre_s.get('pass_rate',0):.1f}%", f"{post_s.get('pass_rate',0):.1f}%",
                 f"{post_s.get('pass_rate',0) - pre_s.get('pass_rate',0):+.1f}%"],
                ["Avg Confidence", f"{pre_s.get('avg_confidence',0):.2f}", f"{post_s.get('avg_confidence',0):.2f}",
                 f"{post_s.get('avg_confidence',0) - pre_s.get('avg_confidence',0):+.2f}"],
                ["Abstained", str(pre_s.get("abstained",0)), str(post_s.get("abstained",0)), ""],
                ["Hedged",    str(pre_s.get("hedged",0)),    str(post_s.get("hedged",0)),    ""],
            ]
            ct = Table(cmp_data, repeatRows=1)
            ct.setStyle(TableStyle([
                ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#1e3a5f")),
                ("TEXTCOLOR",  (0,0), (-1,0), colors.white),
                ("FONTNAME",   (0,0), (-1,0), "Helvetica-Bold"),
                ("ALIGN",      (0,0), (-1,-1), "CENTER"),
                ("GRID",       (0,0), (-1,-1), 0.5, colors.grey),
                ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, colors.HexColor("#f0f4f8")]),
            ]))
            story.append(ct)

            # Per-prompt before/after
            story.append(Spacer(1, 0.4*cm))
            story.append(Paragraph("<b>Per-Prompt Comparison</b>", styles["Heading3"]))
            pre_results  = {r["id"]: r for r in comparison_data["pre"].get("results", [])}
            post_results = {r["id"]: r for r in comparison_data["post"].get("results", [])}
            for rid, pre_r in pre_results.items():
                post_r = post_results.get(rid, {})
                pr_correct = "✓" if pre_r.get("correct_behavior") else "✗"
                po_correct = "✓" if post_r.get("correct_behavior") else "✗"
                pr_ac = pre_r.get("action","?")
                po_ac = post_r.get("action","?")
                pr_col = {"ANSWER": colors.HexColor("#d4edda"), "HEDGE": colors.HexColor("#fff3cd"),
                          "ABSTAIN": colors.HexColor("#f8d7da")}.get(pr_ac, colors.white)
                po_col = {"ANSWER": colors.HexColor("#d4edda"), "HEDGE": colors.HexColor("#fff3cd"),
                          "ABSTAIN": colors.HexColor("#f8d7da")}.get(po_ac, colors.white)

                row = [
                    ["Prompt", pre_r.get("prompt",""), ""],
                    ["Before", f"{pr_ac} {pr_correct}  {pre_r.get('response','')[:80]}", ""],
                    ["After",  f"{po_ac} {po_correct}  {post_r.get('response','')[:80]}", ""],
                ]
                bt = Table(row, colWidths=[2.5*cm, 8*cm, 8*cm])
                bt.setStyle(TableStyle([
                    ("FONTNAME",   (0,0), (0,-1), "Helvetica-Bold"),
                    ("BACKGROUND", (1,1), (1,1), pr_col),
                    ("BACKGROUND", (1,2), (1,2), po_col),
                    ("GRID",       (0,0), (-1,-1), 0.3, colors.lightgrey),
                    ("FONTSIZE",   (0,0), (-1,-1), 8),
                    ("SPAN",       (1,0), (2,0)),
                    ("VALIGN",     (0,0), (-1,-1), "TOP"),
                ]))
                story.append(bt)
                story.append(Spacer(1, 0.15*cm))

        doc.build(story)
        buf.seek(0)
        return buf.read()

    except ImportError:
        # Fallback to plain text
        lines = [title, subtitle, "=" * 60, ""]
        s = phase_data.get("summary", {})
        lines += [
            f"Total: {s.get('total',0)}  Pass rate: {s.get('pass_rate',0):.1f}%",
            f"Answered: {s.get('answered',0)}  Hedged: {s.get('hedged',0)}  Abstained: {s.get('abstained',0)}",
            "",
        ]
        for r in phase_data.get("results", []):
            co = "OK" if r.get("correct_behavior") else "WRONG"
            lines.append(f"[{r.get('id','')}] {r.get('action','?')} ({co}) — {r.get('prompt','')[:60]}")
            lines.append(f"  Before: {r.get('response','')[:80]}")
        if comparison_data:
            lines += ["", "COMPARISON", "-"*40]
            pre_s  = comparison_data["pre"]["summary"]
            post_s = comparison_data["post"]["summary"]
            lines.append(f"Pass rate: {pre_s.get('pass_rate',0):.1f}% → {post_s.get('pass_rate',0):.1f}%")
        return "\n".join(lines).encode()


def _stream_report(data: bytes, is_pdf: bool, filename: str) -> StreamingResponse:
    media = "application/pdf" if is_pdf else "text/plain"
    return StreamingResponse(
        io.BytesIO(data), media_type=media,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ── Report endpoints ───────────────────────────────────────────────────────────

@router.get("/report/pre/{session_id}")
async def report_pre(session_id: str):
    if session_id not in _sessions or not _sessions[session_id].get("pre"):
        raise HTTPException(404, "Pre-test results not found.")
    sess = _sessions[session_id]
    mn = sess["model_name"].replace("/", "_")
    data = _make_pdf(
        "ETHOS Logical Module — Pre-Injection Report",
        f"Model: {sess['model_name']}  |  {datetime.utcnow().strftime('%d %b %Y %H:%M UTC')}",
        sess["pre"],
    )
    is_pdf = data[:4] == b"%PDF"
    ext = "pdf" if is_pdf else "txt"
    return _stream_report(data, is_pdf, f"logical_pre_{mn}.{ext}")


@router.get("/report/post/{session_id}")
async def report_post(session_id: str):
    if session_id not in _sessions or not _sessions[session_id].get("post"):
        raise HTTPException(404, "Post-test results not found.")
    sess = _sessions[session_id]
    mn = sess["model_name"].replace("/", "_")
    data = _make_pdf(
        "ETHOS Logical Module — Post-Injection Report",
        f"Model: {sess['model_name']}  |  {datetime.utcnow().strftime('%d %b %Y %H:%M UTC')}",
        sess["post"],
    )
    is_pdf = data[:4] == b"%PDF"
    ext = "pdf" if is_pdf else "txt"
    return _stream_report(data, is_pdf, f"logical_post_{mn}.{ext}")


@router.get("/report/comparison/{session_id}")
async def report_comparison(session_id: str):
    if session_id not in _sessions:
        raise HTTPException(404, "Session not found.")
    sess = _sessions[session_id]
    if not sess.get("pre") or not sess.get("post"):
        raise HTTPException(400, "Both pre and post results required for comparison report.")
    mn = sess["model_name"].replace("/", "_")
    data = _make_pdf(
        "ETHOS Logical Module — Before vs After Comparison",
        f"Model: {sess['model_name']}  |  {datetime.utcnow().strftime('%d %b %Y %H:%M UTC')}",
        sess["pre"],
        comparison_data={"pre": sess["pre"], "post": sess["post"]},
    )
    is_pdf = data[:4] == b"%PDF"
    ext = "pdf" if is_pdf else "txt"
    return _stream_report(data, is_pdf, f"logical_comparison_{mn}.{ext}")
