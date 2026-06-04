"""
clinical/uncertainty.py — Uncertainty Estimation for Differential Diagnoses

Provides:
  UncertaintyEstimator
    .monte_carlo_dropout(case, n_samples)  — MC-dropout simulation via keyword noise
    .ensemble_uncertainty(case, n_models)  — bootstrap rule-config ensemble
    .calibration_curve(cases, true_labels) — ECE + reliability diagram data
    .conformal_prediction(case, alpha)     — conformal prediction set

Usage::

    from clinical.uncertainty import UncertaintyEstimator
    ue = UncertaintyEstimator(n_samples=20)
    result = ue.monte_carlo_dropout(case, n_samples=20)
    pred_set = ue.conformal_prediction(case, alpha=0.1)
"""

from __future__ import annotations

import os
import random
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Optional

# ── resolve project root so imports work from any cwd ──────────────────────
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from model.dd_engine import diagnose, DiagnosisResult
from model.dd_rules_extended import EXTENDED_DD_RULES


# ===========================================================================
# Internal helpers
# ===========================================================================

def _all_disease_names() -> list[str]:
    """Collect unique disease names across all rules."""
    names = []
    seen: set[str] = set()
    for rule in EXTENDED_DD_RULES:
        for d in rule["diagnoses"]:
            if d["disease"] not in seen:
                names.append(d["disease"])
                seen.add(d["disease"])
    return names


def _drop_keywords(case: dict, drop_rate: float, rng: random.Random) -> dict:
    """Return a copy of *case* where each symptom keyword is independently
    dropped with probability *drop_rate* (simulating MC dropout noise)."""
    import copy
    noisy = copy.deepcopy(case)

    # Drop individual symptoms
    symptoms = noisy.get("symptoms", [])
    noisy["symptoms"] = [s for s in symptoms if rng.random() > drop_rate]

    # Randomly blank out words in free-text fields
    for field_name in ("chief_complaint", "history"):
        text = noisy.get(field_name, "")
        if text:
            words = text.split()
            noisy[field_name] = " ".join(
                w if rng.random() > drop_rate else "" for w in words
            ).strip()

    return noisy


def _result_to_prob_dict(result: DiagnosisResult) -> dict[str, float]:
    """Flatten a DiagnosisResult into {disease: probability} dict."""
    probs: dict[str, float] = {}
    probs[result.primary["disease"]] = result.primary.get("probability", 0.0)
    for d in result.differentials:
        probs[d["disease"]] = d.get("probability", 0.0)
    return probs


def _shannon_entropy(probs: dict[str, float]) -> float:
    import math
    total = sum(probs.values())
    if total == 0:
        return 0.0
    ent = 0.0
    for p in probs.values():
        p_norm = p / total
        if p_norm > 0:
            ent -= p_norm * math.log(p_norm + 1e-12)
    return ent


# ===========================================================================
# UncertaintyEstimator
# ===========================================================================

class UncertaintyEstimator:
    """Uncertainty quantification for the rule-based DD system.

    Parameters
    ----------
    n_samples:
        Default number of stochastic samples for MC-dropout and ensemble.
    """

    def __init__(self, n_samples: int = 20) -> None:
        self.n_samples = n_samples

    # ------------------------------------------------------------------
    # 1. Monte Carlo Dropout (simulated via keyword noise)
    # ------------------------------------------------------------------

    def monte_carlo_dropout(
        self,
        case: dict,
        n_samples: int | None = None,
        drop_rate: float = 0.15,
        seed: int = 42,
    ) -> dict:
        """Estimate uncertainty by running the diagnose engine *n_samples* times,
        each time randomly dropping 10-20% of keyword matches from the case.

        Parameters
        ----------
        case:
            Patient case dict (chief_complaint, symptoms, history, vitals …).
        n_samples:
            Number of stochastic forward passes (overrides ``self.n_samples``).
        drop_rate:
            Fraction of symptom tokens dropped per sample.
        seed:
            RNG seed for reproducibility.

        Returns
        -------
        dict::

            {
              "mean_probs":         {disease: mean_probability, ...},
              "std_probs":          {disease: std_probability,  ...},
              "entropy":            float,          # mean Shannon entropy
              "confidence_interval":{disease: [lower_95, upper_95], ...},
              "top_disease":        str,
              "top_confidence":     float,
              "n_samples":          int,
            }
        """
        n = n_samples or self.n_samples
        rng = random.Random(seed)

        all_probs: list[dict[str, float]] = []
        for _ in range(n):
            noisy_case = _drop_keywords(case, drop_rate, rng)
            try:
                result = diagnose(noisy_case)
                all_probs.append(_result_to_prob_dict(result))
            except Exception:
                pass

        if not all_probs:
            return {"error": "All samples failed", "n_samples": 0}

        # Aggregate
        all_diseases = sorted(
            {d for probs in all_probs for d in probs}
        )
        mean_probs: dict[str, float] = {}
        std_probs: dict[str, float] = {}
        ci: dict[str, list[float]] = {}

        for disease in all_diseases:
            vals = [p.get(disease, 0.0) for p in all_probs]
            mu = sum(vals) / len(vals)
            sigma = (sum((v - mu) ** 2 for v in vals) / len(vals)) ** 0.5
            mean_probs[disease] = round(mu, 4)
            std_probs[disease] = round(sigma, 4)
            # Normal-approximation 95% CI
            z95 = 1.96
            ci[disease] = [
                round(max(0.0, mu - z95 * sigma), 4),
                round(min(1.0, mu + z95 * sigma), 4),
            ]

        # Mean entropy across samples
        entropies = [_shannon_entropy(p) for p in all_probs]
        mean_entropy = sum(entropies) / len(entropies)

        top = max(mean_probs, key=mean_probs.get)  # type: ignore[arg-type]

        return {
            "mean_probs": dict(
                sorted(mean_probs.items(), key=lambda x: -x[1])
            ),
            "std_probs": std_probs,
            "entropy": round(mean_entropy, 4),
            "confidence_interval": ci,
            "top_disease": top,
            "top_confidence": mean_probs[top],
            "n_samples": len(all_probs),
        }

    # ------------------------------------------------------------------
    # 2. Ensemble Uncertainty (bootstrap rule configurations)
    # ------------------------------------------------------------------

    def ensemble_uncertainty(
        self,
        case: dict,
        n_models: int | None = None,
        perturbation_scale: float = 0.05,
        seed: int = 99,
    ) -> dict:
        """Bootstrap multiple slightly-perturbed rule configurations and measure
        the variance of diagnosis probabilities across the ensemble.

        Each "model" is created by adding uniform noise (±perturbation_scale)
        to the ``base_prob`` values in EXTENDED_DD_RULES, then running diagnose().

        Parameters
        ----------
        case:
            Patient case dict.
        n_models:
            Ensemble size (overrides ``self.n_samples``).
        perturbation_scale:
            Magnitude of random perturbation added to base_prob.
        seed:
            RNG seed.

        Returns
        -------
        dict::

            {
              "mean_probs":  {disease: float, ...},
              "std_probs":   {disease: float, ...},
              "entropy":     float,
              "ensemble_size": int,
              "agreement":   float,   # fraction of ensemble agreeing on top-1
            }
        """
        import copy

        n = n_models or self.n_samples
        rng = random.Random(seed)

        all_probs: list[dict[str, float]] = []
        top_votes: list[str] = []

        for _ in range(n):
            # Perturb rule probabilities
            perturbed_rules = copy.deepcopy(EXTENDED_DD_RULES)
            for rule in perturbed_rules:
                for d in rule["diagnoses"]:
                    noise = rng.uniform(-perturbation_scale, perturbation_scale)
                    d["base_prob"] = max(0.01, d["base_prob"] + noise)

            # Monkey-patch rules, run diagnose, restore
            import model.dd_rules_extended as _ext_module
            import model.dd_engine as _engine_module

            original_rules = _ext_module.EXTENDED_DD_RULES
            _ext_module.EXTENDED_DD_RULES = perturbed_rules

            # Also reload engine's reference
            original_engine_rules = getattr(_engine_module, "_RULES_CACHE", None)
            _engine_module.EXTENDED_DD_RULES = perturbed_rules  # type: ignore[attr-defined]

            try:
                result = diagnose(case)
                probs = _result_to_prob_dict(result)
                all_probs.append(probs)
                top_votes.append(result.primary["disease"])
            except Exception:
                pass
            finally:
                _ext_module.EXTENDED_DD_RULES = original_rules
                _engine_module.EXTENDED_DD_RULES = original_rules  # type: ignore[attr-defined]

        if not all_probs:
            return {"error": "All ensemble members failed", "ensemble_size": 0}

        all_diseases = sorted({d for p in all_probs for d in p})
        mean_probs: dict[str, float] = {}
        std_probs: dict[str, float] = {}

        for disease in all_diseases:
            vals = [p.get(disease, 0.0) for p in all_probs]
            mu = sum(vals) / len(vals)
            sigma = (sum((v - mu) ** 2 for v in vals) / len(vals)) ** 0.5
            mean_probs[disease] = round(mu, 4)
            std_probs[disease] = round(sigma, 4)

        # Agreement = fraction voting for the most common top-1
        top_counts: dict[str, int] = defaultdict(int)
        for t in top_votes:
            top_counts[t] += 1
        majority = max(top_counts.values()) if top_counts else 0
        agreement = majority / len(top_votes) if top_votes else 0.0

        mean_entropy = sum(_shannon_entropy(p) for p in all_probs) / len(all_probs)

        return {
            "mean_probs": dict(sorted(mean_probs.items(), key=lambda x: -x[1])),
            "std_probs": std_probs,
            "entropy": round(mean_entropy, 4),
            "ensemble_size": len(all_probs),
            "agreement": round(agreement, 4),
        }

    # ------------------------------------------------------------------
    # 3. Calibration Curve
    # ------------------------------------------------------------------

    def calibration_curve(
        self,
        cases: list[dict],
        true_labels: list[str],
        n_bins: int = 10,
    ) -> dict:
        """Compute Expected Calibration Error (ECE) and reliability diagram data.

        For each case the predicted probability of the *true label* is extracted.
        Cases are binned by predicted confidence; within each bin the empirical
        accuracy and mean confidence are compared.

        Parameters
        ----------
        cases:
            list of patient case dicts.
        true_labels:
            list of ground-truth primary disease names (one per case).
        n_bins:
            Number of equal-width confidence bins.

        Returns
        -------
        dict::

            {
              "ece":         float,       # Expected Calibration Error
              "mce":         float,       # Maximum Calibration Error
              "bins": [
                {
                  "bin":          str,    # e.g. "[0.1, 0.2)"
                  "count":        int,
                  "mean_conf":    float,
                  "accuracy":     float,
                  "gap":          float,  # |accuracy - mean_conf|
                },
                ...
              ],
              "n_cases": int,
            }
        """
        results = []
        for case, true_label in zip(cases, true_labels):
            try:
                result = diagnose(case)
                probs = _result_to_prob_dict(result)
                # Confidence = probability assigned to the true label
                conf = probs.get(true_label, 0.0)
                # Correct if true label is the primary diagnosis
                correct = int(result.primary["disease"] == true_label)
                results.append((conf, correct))
            except Exception:
                pass

        if not results:
            return {"error": "No valid cases", "n_cases": 0}

        # Build bins
        bin_width = 1.0 / n_bins
        bins_data = []
        ece = 0.0
        mce = 0.0
        n_total = len(results)

        for b in range(n_bins):
            lo = b * bin_width
            hi = lo + bin_width
            in_bin = [(c, a) for c, a in results if lo <= c < hi]
            if not in_bin:
                continue
            mean_conf = sum(c for c, _ in in_bin) / len(in_bin)
            accuracy = sum(a for _, a in in_bin) / len(in_bin)
            gap = abs(accuracy - mean_conf)
            weight = len(in_bin) / n_total
            ece += weight * gap
            mce = max(mce, gap)
            bins_data.append({
                "bin": f"[{lo:.1f}, {hi:.1f})",
                "count": len(in_bin),
                "mean_conf": round(mean_conf, 4),
                "accuracy": round(accuracy, 4),
                "gap": round(gap, 4),
            })

        return {
            "ece": round(ece, 4),
            "mce": round(mce, 4),
            "bins": bins_data,
            "n_cases": n_total,
        }

    # ------------------------------------------------------------------
    # 4. Conformal Prediction
    # ------------------------------------------------------------------

    def conformal_prediction(
        self,
        case: dict,
        alpha: float = 0.1,
        calibration_scores: list[float] | None = None,
    ) -> list[str]:
        """Return a prediction set guaranteed to contain the true diagnosis
        with probability ≥ 1 - alpha under the exchangeability assumption.

        Uses split-conformal prediction with non-conformity score
        s_i = 1 - p(true_label_i | case_i).

        When *calibration_scores* is not supplied the method falls back to a
        conservative heuristic: include all diseases whose cumulative
        probability (sorted descending) reaches (1 - alpha).

        Parameters
        ----------
        case:
            Patient case dict.
        alpha:
            Miscoverage level (0.1 = 90% coverage guarantee).
        calibration_scores:
            Pre-computed non-conformity scores from a held-out calibration set.
            If provided, the conformal threshold is set at the
            ⌈(n+1)(1-alpha)⌉/n quantile.

        Returns
        -------
        list[str]:
            Ordered list of disease names forming the prediction set.
        """
        result = diagnose(case)
        probs = _result_to_prob_dict(result)
        sorted_diseases = sorted(probs, key=probs.get, reverse=True)  # type: ignore[arg-type]

        if calibration_scores:
            import math
            n = len(calibration_scores)
            q_level = math.ceil((n + 1) * (1 - alpha)) / n
            q_level = min(q_level, 1.0)
            sorted_cal = sorted(calibration_scores)
            q_idx = min(int(q_level * n), n - 1)
            threshold = 1.0 - sorted_cal[q_idx]  # convert score to prob threshold
            pred_set = [d for d in sorted_diseases if probs.get(d, 0.0) >= threshold]
        else:
            # Conservative fallback: include until cumulative prob ≥ 1 - alpha
            cumulative = 0.0
            pred_set = []
            for disease in sorted_diseases:
                pred_set.append(disease)
                cumulative += probs.get(disease, 0.0)
                if cumulative >= 1.0 - alpha:
                    break

        return pred_set if pred_set else sorted_diseases[:1]


# ===========================================================================
# Demo
# ===========================================================================

_DEMO_CASES = [
    {
        "chief_complaint": "前胸部圧迫感",
        "symptoms": ["冷汗", "放散痛", "悪心"],
        "history": "高血圧 糖尿病 喫煙歴あり",
        "demographics": "62歳 男性",
        "vitals": "BP 90/60, HR 110, SpO2 96%, RR 22",
        "_true_label": "急性冠症候群（ACS）",
    },
    {
        "chief_complaint": "急な激しい頭痛",
        "symptoms": ["雷鳴頭痛", "嘔吐", "項部硬直"],
        "history": "突然発症",
        "demographics": "45歳 女性",
        "vitals": "BP 180/100, HR 88, SpO2 98%",
        "_true_label": "くも膜下出血（SAH）",
    },
    {
        "chief_complaint": "呼吸困難",
        "symptoms": ["起座呼吸", "両下腿浮腫", "体重増加"],
        "history": "心筋梗塞既往 BNP高値",
        "demographics": "70歳 男性",
        "vitals": "BP 160/90, HR 100, SpO2 90%, RR 28",
        "_true_label": "急性心不全（代償不全）",
    },
    {
        "chief_complaint": "発熱と咳",
        "symptoms": ["発熱", "湿性咳嗽", "膿性痰"],
        "history": "3日前から発症",
        "demographics": "55歳 男性",
        "vitals": "BP 120/80, HR 92, SpO2 95%, RR 20, 体温 38.8",
        "_true_label": "市中肺炎（CAP）",
    },
    {
        "chief_complaint": "腹痛",
        "symptoms": ["右下腹部痛", "発熱", "悪心"],
        "history": "昨日から増悪",
        "demographics": "25歳 女性",
        "vitals": "BP 110/70, HR 98, SpO2 99%, 体温 37.9",
        "_true_label": "虫垂炎",
    },
    {
        "chief_complaint": "意識障害",
        "symptoms": ["意識消失", "高血糖", "Kussmaul呼吸", "クスマウル"],
        "history": "1型糖尿病 インスリン中断",
        "demographics": "28歳 女性",
        "vitals": "BP 100/65, HR 118, SpO2 98%, RR 28",
        "_true_label": "糖尿病性ケトアシドーシス（DKA）",
    },
    {
        "chief_complaint": "下肢の腫れ",
        "symptoms": ["片側下腿浮腫", "圧痛", "発赤"],
        "history": "2週間前に長距離フライト",
        "demographics": "38歳 男性",
        "vitals": "BP 125/80, HR 82, SpO2 98%",
        "_true_label": "深部静脈血栓症（DVT）",
    },
    {
        "chief_complaint": "胸痛と呼吸困難",
        "symptoms": ["突然発症", "胸膜性胸痛", "下肢浮腫"],
        "history": "術後 Wells高値 D-dimer上昇",
        "demographics": "55歳 女性",
        "vitals": "BP 95/60, HR 122, SpO2 92%, RR 26",
        "_true_label": "肺塞栓症",
    },
    {
        "chief_complaint": "背部痛",
        "symptoms": ["引き裂く", "血圧左右差", "突然発症"],
        "history": "高血圧 マルファン症候群",
        "demographics": "50歳 男性",
        "vitals": "BP 200/110, HR 95, SpO2 97%",
        "_true_label": "急性大動脈解離",
    },
    {
        "chief_complaint": "痙攣",
        "symptoms": ["全身痙攣", "意識障害", "舌咬傷"],
        "history": "てんかん 服薬中断",
        "demographics": "33歳 男性",
        "vitals": "BP 140/90, HR 105, SpO2 97%",
        "_true_label": "てんかん発作",
    },
]


def _run_demo() -> None:
    print("=" * 70)
    print("Uncertainty Estimation Demo")
    print("=" * 70)

    ue = UncertaintyEstimator(n_samples=20)

    for i, case in enumerate(_DEMO_CASES[:10], 1):
        true_label = case.pop("_true_label", "unknown")
        print(f"\n[Case {i}] {case['chief_complaint']}  (true: {true_label})")
        print("-" * 60)

        # MC Dropout
        mc = ue.monte_carlo_dropout(case, n_samples=20)
        print(f"  MC Dropout:")
        print(f"    Top-1: {mc['top_disease']} ({mc['top_confidence']:.3f})")
        print(f"    Entropy: {mc['entropy']:.4f}")
        top3 = list(mc["mean_probs"].items())[:3]
        for disease, prob in top3:
            std = mc["std_probs"].get(disease, 0.0)
            ci = mc["confidence_interval"].get(disease, [0.0, 0.0])
            print(f"    {disease}: {prob:.3f} ± {std:.3f}  95%CI [{ci[0]:.3f}, {ci[1]:.3f}]")

        # Conformal prediction set
        pred_set = ue.conformal_prediction(case, alpha=0.1)
        print(f"  Conformal Prediction Set (α=0.1): {pred_set}")

        case["_true_label"] = true_label  # restore

    # Calibration curve
    print("\n" + "=" * 70)
    print("Calibration Curve (ECE)")
    print("=" * 70)
    cases_clean = []
    true_labels = []
    for c in _DEMO_CASES:
        cc = dict(c)
        true_labels.append(cc.pop("_true_label", "unknown"))
        cases_clean.append(cc)

    cal = ue.calibration_curve(cases_clean, true_labels, n_bins=5)
    print(f"  ECE: {cal['ece']:.4f}")
    print(f"  MCE: {cal['mce']:.4f}")
    print(f"  N cases: {cal['n_cases']}")
    for b in cal.get("bins", []):
        print(f"    Bin {b['bin']}: n={b['count']}  conf={b['mean_conf']:.3f}  acc={b['accuracy']:.3f}  gap={b['gap']:.3f}")


if __name__ == "__main__":
    _run_demo()
