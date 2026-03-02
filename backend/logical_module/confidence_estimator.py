"""
Confidence Estimator — token-level uncertainty estimation.

Computes two complementary token-level uncertainty signals:

  1. Attention-Weighted Surprisal (T)
     Uses last-layer attention to weight how much each token
     "mattered" to the model, then weights token surprisal
     (−log p_i) by that attention mass.  Filler tokens like
     "the" that have low attention but possibly high entropy
     don't pollute the overall score.

  2. Plain NLL Fallback
     Used when attention weights are unavailable (e.g. models
     that don't return attentions, or API-only setups).

Output: T ∈ [0, 1] where 1 = very confident, 0 = very uncertain.

Normalisation:
    T_raw → T via sigmoid: T = σ(−k · (T_raw − μ))
    μ, k are estimated from a running window of recent T_raw values
    so that the module self-calibrates from the first few responses.
"""
from __future__ import annotations

import logging
import math
from collections import deque
from typing import List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)

# Optional heavy imports — fail gracefully
try:
    import torch  # type: ignore
    TORCH_AVAILABLE = True
except ImportError:
    torch = None  # type: ignore
    TORCH_AVAILABLE = False


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _sigmoid(x: float) -> float:
    """Numerically-stable sigmoid."""
    if x >= 0:
        return 1.0 / (1.0 + math.exp(-x))
    e = math.exp(x)
    return e / (1.0 + e)


# ─────────────────────────────────────────────────────────────────────────────
# ConfidenceEstimator
# ─────────────────────────────────────────────────────────────────────────────

class ConfidenceEstimator:
    """
    Computes token-level confidence from a HuggingFace causal-LM.

    Args:
        window_size: Number of recent T_raw observations kept for
                     running normalisation (default 200).
        k:           Steepness of sigmoid normalisation (default 3.0).
    """

    def __init__(self, window_size: int = 200, k: float = 3.0) -> None:
        self._window: deque = deque(maxlen=window_size)
        self._k = k

    # ------------------------------------------------------------------
    # Main API
    # ------------------------------------------------------------------

    def compute_token_confidence(
        self,
        model,
        tokenizer,
        input_ids,
        output_ids,
        model_output=None,
    ) -> Tuple[float, dict]:
        """
        Compute attention-weighted token confidence T ∈ [0, 1].

        Args:
            model:        HuggingFace causal-LM (already on device).
            tokenizer:    Corresponding tokenizer.
            input_ids:    Tensor of shape (1, S) — the prompt tokens.
            output_ids:   Tensor of shape (1, S+N) — full output token ids.
            model_output: Optional: output from model.generate() with
                          return_dict_in_generate=True and output_scores=True
                          and output_attentions=True.  If None, we recompute.

        Returns:
            (T, meta) where meta contains intermediate diagnostics.
        """
        if not TORCH_AVAILABLE:
            return 0.5, {"method": "unavailable"}

        try:
            input_len = input_ids.shape[1]
            new_token_ids = output_ids[:, input_len:]
            n_new = new_token_ids.shape[1]

            if n_new == 0:
                return 0.5, {"method": "empty_output"}

            # ── 1. Get per-token log-probs ──────────────────────────────
            # Forward pass on the full output to get logits
            with torch.no_grad():
                logits_output = model(output_ids, output_attentions=True)

            logits = logits_output.logits  # (1, T, vocab)
            attentions = logits_output.attentions  # Tuple of (1, heads, T, T)

            # Shift: logit at position t predicts token t+1
            shift_logits = logits[:, input_len - 1 : -1, :]  # (1, N, vocab)
            shift_tokens = new_token_ids                       # (1, N)

            log_probs_all = torch.nn.functional.log_softmax(shift_logits, dim=-1)
            selected = log_probs_all.gather(
                -1, shift_tokens.unsqueeze(-1)
            ).squeeze(-1)  # (1, N)

            token_surprisal = -selected[0].float().cpu().numpy()  # (N,)

            # ── 2. Attention weights for new tokens ─────────────────────
            attn_weights = self._extract_attention_weights(
                attentions, input_len, n_new
            )  # (N,)

            # ── 3. Weighted surprisal ───────────────────────────────────
            T_raw = float(
                np.sum(attn_weights * token_surprisal) / (np.sum(attn_weights) + 1e-12)
            )

            T = self._sigmoid_normalize(T_raw)

            meta = {
                "method": "attention_weighted",
                "T_raw": T_raw,
                "T": T,
                "n_tokens": n_new,
                "mean_surprisal": float(np.mean(token_surprisal)),
                "mean_attention": float(np.mean(attn_weights)),
            }
            return T, meta

        except Exception as exc:
            logger.warning("Attention-weighted confidence failed (%s); falling back to NLL.", exc)
            return self._fallback_nll(model, tokenizer, input_ids, output_ids)

    # ------------------------------------------------------------------
    # Fallback — plain NLL
    # ------------------------------------------------------------------

    def _fallback_nll(
        self, model, tokenizer, input_ids, output_ids
    ) -> Tuple[float, dict]:
        """Simple per-token NLL when attention is not available."""
        if not TORCH_AVAILABLE:
            return 0.5, {"method": "unavailable"}
        try:
            input_len = input_ids.shape[1]
            new_token_ids = output_ids[:, input_len:]
            n_new = new_token_ids.shape[1]
            if n_new == 0:
                return 0.5, {"method": "empty_output"}

            with torch.no_grad():
                logits = model(output_ids).logits

            shift_logits = logits[:, input_len - 1 : -1, :]
            log_probs = torch.nn.functional.log_softmax(shift_logits, dim=-1)
            selected = log_probs.gather(-1, new_token_ids.unsqueeze(-1)).squeeze(-1)
            surprisal = -selected[0].float().cpu().numpy()
            T_raw = float(np.mean(surprisal))
            T = self._sigmoid_normalize(T_raw)
            return T, {"method": "nll_fallback", "T_raw": T_raw, "T": T, "n_tokens": n_new}
        except Exception as exc:
            logger.warning("NLL fallback also failed: %s", exc)
            return 0.5, {"method": "error", "error": str(exc)}

    # ------------------------------------------------------------------
    # Compute from raw log-prob list (API-only or external usage)
    # ------------------------------------------------------------------

    def from_logprobs(self, token_logprobs: List[float]) -> Tuple[float, dict]:
        """
        Compute T from a list of per-token log-probs (as returned by
        some API endpoints, e.g., logprobs=-1 in OpenAI format).

        Args:
            token_logprobs:  List of log-probabilities (negative floats).

        Returns:
            (T, meta)
        """
        if not token_logprobs:
            return 0.5, {"method": "empty_logprobs"}
        surprisals = [-lp for lp in token_logprobs if lp is not None]
        T_raw = float(np.mean(surprisals))
        T = self._sigmoid_normalize(T_raw)
        return T, {"method": "logprobs_api", "T_raw": T_raw, "T": T, "n_tokens": len(surprisals)}

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _extract_attention_weights(self, attentions, input_len: int, n_new: int) -> np.ndarray:
        """
        Extract attention received by each new generated token.

        Averages over all heads in the LAST attention layer.
        For each new token i (global position = input_len + i),
        we sum the attention *from* all positions *to* position i.
        This captures "how much did the model look at this token".

        Returns:
            weights — shape (n_new,), normalised to sum to 1.
        """
        if attentions is None or len(attentions) == 0:
            return np.ones(n_new) / n_new

        try:
            # Last layer attention: shape (1, num_heads, seq_len, seq_len)
            last_attn = attentions[-1]  # Tensor
            # Mean over heads → (1, seq_len, seq_len)
            mean_attn = last_attn.mean(dim=1).squeeze(0).float().cpu().numpy()

            # For each new token position, sum attention FROM all tokens TO it
            weights = np.zeros(n_new)
            for i in range(n_new):
                global_pos = input_len + i
                if global_pos < mean_attn.shape[1]:
                    weights[i] = mean_attn[:, global_pos].sum()

            total = weights.sum()
            if total < 1e-10:
                return np.ones(n_new) / n_new
            return weights / total

        except Exception as exc:
            logger.debug("Attention extraction failed: %s", exc)
            return np.ones(n_new) / n_new

    def _sigmoid_normalize(self, T_raw: float) -> float:
        """
        Map T_raw (surprisal space, positive reals) to [0,1].

        Uses a running estimate of μ (mean T_raw) and maps via:
            T = σ(−k · (T_raw − μ))
        So T_raw < μ → T > 0.5 (confident),
           T_raw > μ → T < 0.5 (uncertain).

        Falls back to a fixed μ=1.5 if not enough data have been seen.
        """
        self._window.append(T_raw)
        mu = float(np.median(self._window)) if len(self._window) >= 5 else 1.5
        return float(np.clip(_sigmoid(-self._k * (T_raw - mu)), 1e-6, 1.0 - 1e-6))
