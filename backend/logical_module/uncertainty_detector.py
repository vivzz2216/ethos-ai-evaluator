"""
Uncertainty Detector — multi-sample self-consistency via hierarchical clustering.

Computes two orthogonal agreement signals from M sampled answers:

  A — Cluster Agreement
      Uses HDBSCAN to group semantically similar answers,
      then measures distribution entropy over clusters.
      This handles paraphrases correctly (unlike exact-match).

  S — Semantic Coherence Density
      Mean pairwise cosine similarity among embeddings,
      penalised by the fraction the HDBSCAN marked as noise.

Both signals are in [0, 1] where 1 = high agreement / confident.

Falls back gracefully if:
  - sentence-transformers unavailable → TF-IDF vectors
  - hdbscan unavailable → exact-match + cosine similarity
  - everything unavailable → random 0.5 placebos (logged as warning)
"""
from __future__ import annotations

import logging
import math
import re
from typing import List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)

# ── Optional imports ──────────────────────────────────────────────────────────

try:
    from sentence_transformers import SentenceTransformer  # type: ignore
    ST_AVAILABLE = True
except ImportError:
    SentenceTransformer = None  # type: ignore
    ST_AVAILABLE = False

try:
    import hdbscan  # type: ignore
    HDBSCAN_AVAILABLE = True
except ImportError:
    hdbscan = None  # type: ignore
    HDBSCAN_AVAILABLE = False

try:
    import torch  # type: ignore
    TORCH_AVAILABLE = True
except ImportError:
    torch = None  # type: ignore
    TORCH_AVAILABLE = False

# ─────────────────────────────────────────────────────────────────────────────
# Utilities
# ─────────────────────────────────────────────────────────────────────────────

def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Cosine similarity between two 1-D vectors."""
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a < 1e-10 or norm_b < 1e-10:
        return 0.0
    return float(np.dot(a, b) / (norm_a * norm_b))


def _pairwise_cosine_mean(embeddings: np.ndarray) -> float:
    """Upper-triangle mean of pairwise cosine similarity matrix."""
    n = len(embeddings)
    if n < 2:
        return 1.0
    total, count = 0.0, 0
    for i in range(n):
        for j in range(i + 1, n):
            total += _cosine_similarity(embeddings[i], embeddings[j])
            count += 1
    return total / count if count else 1.0


def _normalize_text(text: str) -> str:
    """Light normalisation for exact-match comparison."""
    text = text.lower().strip()
    text = re.sub(r"[^\w\s]", "", text)
    text = re.sub(r"\s+", " ", text)
    return text


def _shannon_entropy(counts: List[int]) -> float:
    """Shannon entropy over a list of cluster size counts."""
    total = sum(counts)
    if total == 0:
        return 0.0
    nonzero = [c for c in counts if c > 0]
    if len(nonzero) == 1:
        return 0.0  # All mass in one cluster — exact zero, no floating-point residual
    return float(-sum((c / total) * math.log(c / total) for c in nonzero))


# ─────────────────────────────────────────────────────────────────────────────
# UncertaintyDetector
# ─────────────────────────────────────────────────────────────────────────────

class UncertaintyDetector:
    """
    Generates M samples, embeds them, clusters, and computes consistency scores.

    Args:
        embedding_model:  Name of sentence-transformers model.
                          Default: "all-MiniLM-L6-v2" (small, fast, good).
        min_cluster_size: HDBSCAN minimum cluster size (default 2).
    """

    def __init__(
        self,
        embedding_model: str = "all-MiniLM-L6-v2",
        min_cluster_size: int = 2,
    ) -> None:
        self._embed_model_name = embedding_model
        self._embed_model: Optional[SentenceTransformer] = None
        self._min_cluster_size = min_cluster_size
        self._loaded = False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def compute_consistency(
        self,
        model,
        tokenizer,
        prompt: str,
        M: int = 7,
        temperature: float = 0.8,
        max_new_tokens: int = 200,
    ) -> Tuple[float, float, dict]:
        """
        Sample M answers, compute cluster agreement (A) and semantic coherence (S).

        Args:
            model:          HuggingFace causal-LM.
            tokenizer:      Corresponding tokenizer.
            prompt:         The prompt string.
            M:              Number of samples (5–12 recommended).
            temperature:    Sampling temperature.
            max_new_tokens: Max tokens per sample.

        Returns:
            (A, S, meta) — both in [0, 1].
        """
        answers = self._generate_samples(model, tokenizer, prompt, M, temperature, max_new_tokens)
        return self.compute_consistency_from_answers(answers)

    def compute_consistency_from_answers(
        self, answers: List[str]
    ) -> Tuple[float, float, dict]:
        """
        Compute (A, S) from a pre-generated list of answer strings.
        Useful when samples are generated externally.
        """
        if not answers:
            return 0.5, 0.5, {"method": "empty"}

        embeddings = self._embed_answers(answers)
        A, S, cluster_meta = self._cluster_and_score(answers, embeddings)

        meta = {
            "n_samples": len(answers),
            "A": A,
            "S": S,
            **cluster_meta,
        }
        return A, S, meta

    # ------------------------------------------------------------------
    # Sampling
    # ------------------------------------------------------------------

    def _generate_samples(
        self, model, tokenizer, prompt: str, M: int,
        temperature: float, max_new_tokens: int,
    ) -> List[str]:
        """Generate M stochastic samples from the model."""
        if not TORCH_AVAILABLE:
            logger.warning("torch not available; returning empty sample list.")
            return []

        answers: List[str] = []
        try:
            inputs = tokenizer(
                prompt, return_tensors="pt", truncation=True, max_length=512
            )
            input_len = inputs["input_ids"].shape[1]

            # Move to same device as model
            device = next(model.parameters()).device
            inputs = {k: v.to(device) for k, v in inputs.items()}

            for _ in range(M):
                with torch.no_grad():
                    out = model.generate(
                        **inputs,
                        max_new_tokens=max_new_tokens,
                        do_sample=True,
                        temperature=temperature,
                        top_p=0.92,
                        top_k=50,
                        pad_token_id=tokenizer.pad_token_id or tokenizer.eos_token_id,
                        eos_token_id=tokenizer.eos_token_id,
                    )
                new_ids = out[0][input_len:]
                text = tokenizer.decode(new_ids, skip_special_tokens=True).strip()
                if text:
                    answers.append(text)

        except Exception as exc:
            logger.warning("Sample generation failed: %s", exc)

        return answers

    # ------------------------------------------------------------------
    # Embedding
    # ------------------------------------------------------------------

    def _load_embedder(self) -> None:
        """Lazy-load sentence-transformers model."""
        if self._loaded:
            return
        if ST_AVAILABLE and SentenceTransformer:
            try:
                self._embed_model = SentenceTransformer(self._embed_model_name)
                self._loaded = True
                logger.info("SentenceTransformer '%s' loaded.", self._embed_model_name)
            except Exception as exc:
                logger.warning("SentenceTransformer load failed (%s); using TF-IDF.", exc)
        else:
            logger.warning("sentence-transformers not available; using TF-IDF fallback.")
        self._loaded = True

    def _embed_answers(self, answers: List[str]) -> np.ndarray:
        """Return (N, D) embedding matrix for provided answers."""
        self._load_embedder()

        if self._embed_model is not None:
            try:
                return self._embed_model.encode(answers, show_progress_bar=False)
            except Exception as exc:
                logger.warning("Sentence embedding failed (%s); falling back to TF-IDF.", exc)

        # TF-IDF fallback
        return self._tfidf_embed(answers)

    def _tfidf_embed(self, answers: List[str]) -> np.ndarray:
        """Extremely simple TF-IDF character bag-of-ngrams as fallback."""
        try:
            from sklearn.feature_extraction.text import TfidfVectorizer  # type: ignore
            vec = TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 4), max_features=256)
            X = vec.fit_transform(answers).toarray().astype(float)
            return X
        except Exception:
            # Absolute fallback: one-hot word presence over all vocabulary
            vocab = sorted({w for ans in answers for w in ans.lower().split()})
            w2i = {w: i for i, w in enumerate(vocab)}
            X = np.zeros((len(answers), max(1, len(vocab))), dtype=float)
            for j, ans in enumerate(answers):
                for w in ans.lower().split():
                    if w in w2i:
                        X[j, w2i[w]] = 1.0
            return X

    # ------------------------------------------------------------------
    # Clustering & Scoring
    # ------------------------------------------------------------------

    def _cluster_and_score(
        self, answers: List[str], embeddings: np.ndarray
    ) -> Tuple[float, float, dict]:
        """
        Run HDBSCAN (or fallback) and compute A and S.

        Returns:
            (A, S, meta_dict)
        """
        n = len(answers)
        noise_count = 0
        cluster_sizes: List[int] = []

        if HDBSCAN_AVAILABLE and hdbscan and n >= 3:
            labels, noise_count, cluster_sizes = self._run_hdbscan(embeddings)
        else:
            labels, cluster_sizes = self._exact_match_cluster(answers)

        # ── Cluster Agreement (A) ──────────────────────────────────────
        H = _shannon_entropy(cluster_sizes)
        H_max = math.log(max(len(cluster_sizes), 2))
        A = 1.0 - (H / H_max) if H_max > 0 else 1.0
        A = float(np.clip(A, 0.0, 1.0))

        # ── Semantic Coherence (S) ─────────────────────────────────────
        noise_frac = noise_count / max(n, 1)
        S_raw = _pairwise_cosine_mean(embeddings)
        S = float(np.clip(S_raw * (1.0 - noise_frac), 0.0, 1.0))

        # Bonus: largest cluster fraction (secondary signal)
        lcf = max(cluster_sizes, default=0) / max(n, 1)

        meta = {
            "method": "hdbscan" if (HDBSCAN_AVAILABLE and hdbscan and n >= 3) else "exact_match",
            "n_clusters": len(cluster_sizes),
            "noise_count": noise_count,
            "noise_fraction": noise_frac,
            "cluster_sizes": cluster_sizes,
            "cluster_entropy": H,
            "largest_cluster_fraction": lcf,
            "S_raw": S_raw,
        }
        return A, S, meta

    def _run_hdbscan(
        self, embeddings: np.ndarray
    ) -> Tuple[np.ndarray, int, List[int]]:
        """HDBSCAN clustering. Returns (labels, noise_count, cluster_sizes)."""
        try:
            clusterer = hdbscan.HDBSCAN(
                min_cluster_size=self._min_cluster_size,
                min_samples=1,
                metric="euclidean",
            )
            labels = clusterer.fit_predict(embeddings)
        except Exception as exc:
            logger.warning("HDBSCAN failed (%s); falling back to exact match.", exc)
            labels_list, sizes = self._exact_match_cluster(
                [""] * len(embeddings)  # just to get sizes for uniform clusters
            )
            return np.array(labels_list), 0, sizes

        noise_mask = labels == -1
        noise_count = int(noise_mask.sum())
        unique_labels = set(labels[labels >= 0])
        cluster_sizes = [int((labels == lbl).sum()) for lbl in unique_labels]
        return labels, noise_count, cluster_sizes

    def _exact_match_cluster(
        self, answers: List[str]
    ) -> Tuple[List[int], List[int]]:
        """Fallback: group answers by normalised exact text."""
        groups: dict = {}
        labels = []
        for ans in answers:
            key = _normalize_text(ans)
            if key not in groups:
                groups[key] = len(groups)
            labels.append(groups[key])

        cluster_sizes = [0] * len(groups)
        for lbl in labels:
            cluster_sizes[lbl] += 1
        return labels, cluster_sizes
