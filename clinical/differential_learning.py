"""
clinical/differential_learning.py — Adaptive Differential Diagnosis
─────────────────────────────────────────────────────────────────────
Learn from clinician feedback which differentials are correct / incorrect.
Over time the system re-weights rule-based probabilities toward disease
categories where its predictions are reliable and away from ones where it
frequently misses.

Key class: AdaptiveDDSystem
  predict(case) → DiagnosisResult
  feedback(case_id, true_diagnosis, was_correct) → None
  get_performance_stats() → dict
  adjust_weights() → None
"""

from __future__ import annotations

import os
import sys
import uuid
from dataclasses import dataclass, field
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from model.dd_engine import DiagnosisResult, diagnose
from model.dd_rules_extended import EXTENDED_DD_RULES


# ─────────────────────────────────────────────────────────────────────────────
#  Disease category mapping
# ─────────────────────────────────────────────────────────────────────────────

# Map rule-set ID → broad disease group
_RULE_CATEGORY: dict[str, str] = {
    "ACS":       "cardiovascular",
    "AHF":       "cardiovascular",
    "AORTA":     "cardiovascular",
    "SAH":       "neurological",
    "STROKE":    "neurological",
    "MENINGITIS":"neurological",
    "SEPSIS":    "infectious",
    "PNA":       "infectious",
    "UTI":       "infectious",
    "APPX":      "surgical",
    "BOWEL":     "surgical",
    "PE":        "pulmonary",
    "COPD":      "pulmonary",
    "ANAPHYLAX": "allergic",
    "DKA":       "metabolic",
    "HHS":       "metabolic",
}


def _get_category(disease_name: str, rule_id: Optional[str] = None) -> str:
    """Return disease group for a given disease name or rule id."""
    if rule_id and rule_id.upper() in _RULE_CATEGORY:
        return _RULE_CATEGORY[rule_id.upper()]
    # Fallback: keyword matching on disease name
    name_lower = disease_name.lower()
    if any(k in name_lower for k in ("心", "大動脈", "冠", "cardiac", "aorta", "heart")):
        return "cardiovascular"
    if any(k in name_lower for k in ("神経", "脳", "髄膜", "neuro", "stroke", "sah")):
        return "neurological"
    if any(k in name_lower for k in ("炎症", "菌", "感染", "肺炎", "敗血", "infect", "sepsis", "pneumonia")):
        return "infectious"
    if any(k in name_lower for k in ("外科", "虫垂", "腸閉塞", "appendi", "bowel")):
        return "surgical"
    if any(k in name_lower for k in ("糖尿", "ketoacid", "metaboli", "dka")):
        return "metabolic"
    if any(k in name_lower for k in ("肺", "気道", "copd", "pulmon", "塞栓")):
        return "pulmonary"
    return "other"


# ─────────────────────────────────────────────────────────────────────────────
#  Prediction record
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class PredictionRecord:
    case_id: str
    predicted: str        # primary diagnosis name predicted
    actual: Optional[str] = None
    was_correct: Optional[bool] = None
    category: str = "other"


# ─────────────────────────────────────────────────────────────────────────────
#  AdaptiveDDSystem
# ─────────────────────────────────────────────────────────────────────────────

class AdaptiveDDSystem:
    """
    Rule-based differential diagnosis with feedback-driven weight adaptation.

    Weight adjustment
    ─────────────────
    For each disease category we maintain a multiplier (initial=1.0).
    After each adjust_weights() call:
      - Categories with accuracy > 0.75 → multiplier += 0.05 (up to 2.0)
      - Categories with accuracy < 0.40 → multiplier -= 0.05 (down to 0.3)
      - Categories with < 3 feedback samples → multiplier unchanged

    The multiplier is applied to base_prob values when building the ranked
    differential list.
    """

    def __init__(self):
        # category → {"correct": int, "total": int}
        self._stats: dict[str, dict[str, int]] = {}
        # case_id → PredictionRecord
        self._history: dict[str, PredictionRecord] = {}
        # category → weight multiplier
        self._weights: dict[str, float] = {}

    # ── Prediction ───────────────────────────────────────────────────────────

    def predict(self, case: dict) -> DiagnosisResult:
        """
        Produce a DiagnosisResult for the given case, applying learned weights.

        Parameters
        ----------
        case : dict with at least "text" key (free-text description) and
               optionally "vitals", "labs", "age", "sex" keys.

        Returns
        -------
        DiagnosisResult with a "case_id" injected into case dict for
        later feedback correlation.
        """
        # Assign a unique case_id
        case_id = case.get("case_id") or str(uuid.uuid4())[:8]
        case = {**case, "case_id": case_id}

        # Run base rule engine
        result = diagnose(case)

        # Re-rank differentials using learned weights
        # dd_engine uses "disease" key; fall back gracefully
        weighted_diffs = []
        for diff in result.differentials:
            diff_name = diff.get("name") or diff.get("disease", "")
            cat = _get_category(diff_name, diff.get("rule_id"))
            w   = self._weights.get(cat, 1.0)
            weighted_diffs.append({
                **diff,
                "name": diff_name,
                "probability": min(diff.get("probability", 0.0) * w, 1.0),
                "category": cat,
            })
        weighted_diffs.sort(key=lambda d: -d["probability"])

        # Apply weight to primary too
        primary_raw_name = (
            (result.primary or {}).get("name")
            or (result.primary or {}).get("disease", "")
        )
        primary_cat = _get_category(
            primary_raw_name,
            (result.primary or {}).get("rule_id"),
        )
        weighted_primary = {
            **(result.primary or {}),
            "name": primary_raw_name,         # normalise key for callers
            "probability": min(
                (result.primary or {}).get("probability", 0.0)
                * self._weights.get(primary_cat, 1.0),
                1.0,
            ),
            "category": primary_cat,
        }

        # dd_engine uses "disease" key; normalize to "name" for internal use
        primary_name = (
            (result.primary or {}).get("name")
            or (result.primary or {}).get("disease", "unknown")
        )

        # Record prediction
        self._history[case_id] = PredictionRecord(
            case_id=case_id,
            predicted=primary_name,
            category=primary_cat,
        )

        # Build adapted result
        adapted = DiagnosisResult(
            case=result.case,
            primary=weighted_primary,
            differentials=weighted_diffs,
            red_flags=result.red_flags,
            next_steps=result.next_steps,
            urgency=result.urgency,
            vital_assessment=result.vital_assessment,
            risk_scores=result.risk_scores,
            lab_flags=result.lab_flags,
            icd10=result.icd10,
            scoring_hints=result.scoring_hints,
        )
        return adapted

    # ── Feedback ─────────────────────────────────────────────────────────────

    def feedback(
        self,
        case_id: str,
        true_diagnosis: str,
        was_correct: bool,
    ) -> None:
        """
        Register feedback for a previously predicted case.

        Parameters
        ----------
        case_id       : case identifier (returned in case["case_id"])
        true_diagnosis: the clinician-confirmed diagnosis name
        was_correct   : whether the primary prediction matched
        """
        rec = self._history.get(case_id)
        if rec is None:
            # If case_id not found, create a stub record
            rec = PredictionRecord(
                case_id=case_id,
                predicted="unknown",
                category=_get_category(true_diagnosis),
            )
            self._history[case_id] = rec

        rec.actual      = true_diagnosis
        rec.was_correct = was_correct

        # Update stats for the predicted category
        cat = rec.category
        if cat not in self._stats:
            self._stats[cat] = {"correct": 0, "total": 0}
        self._stats[cat]["total"]   += 1
        if was_correct:
            self._stats[cat]["correct"] += 1

    # ── Statistics ───────────────────────────────────────────────────────────

    def get_performance_stats(self) -> dict:
        """
        Compute accuracy per disease category and overall.

        Returns
        -------
        dict with:
          overall: {"accuracy": float, "correct": int, "total": int}
          by_category: {category: {"accuracy", "correct", "total", "weight"}}
        """
        by_cat: dict[str, dict] = {}
        overall_correct = overall_total = 0

        for cat, counts in self._stats.items():
            correct = counts["correct"]
            total   = counts["total"]
            acc     = correct / total if total > 0 else 0.0
            by_cat[cat] = {
                "accuracy": acc,
                "correct":  correct,
                "total":    total,
                "weight":   self._weights.get(cat, 1.0),
            }
            overall_correct += correct
            overall_total   += total

        return {
            "overall": {
                "accuracy": overall_correct / overall_total if overall_total > 0 else 0.0,
                "correct":  overall_correct,
                "total":    overall_total,
            },
            "by_category": by_cat,
        }

    # ── Weight adjustment ─────────────────────────────────────────────────────

    def adjust_weights(self) -> None:
        """
        Re-weight disease categories based on accumulated feedback.

        Rules:
          - Accuracy > 0.75 AND ≥ 3 samples → boost multiplier by 0.05
          - Accuracy < 0.40 AND ≥ 3 samples → reduce multiplier by 0.05
          - Multiplier clamped to [0.3, 2.0]
        """
        BOOST_THRESHOLD  = 0.75
        REDUCE_THRESHOLD = 0.40
        DELTA            = 0.05
        MIN_SAMPLES      = 3
        WEIGHT_MIN       = 0.3
        WEIGHT_MAX       = 2.0

        for cat, counts in self._stats.items():
            total   = counts["total"]
            if total < MIN_SAMPLES:
                continue
            acc = counts["correct"] / total
            current = self._weights.get(cat, 1.0)
            if acc > BOOST_THRESHOLD:
                self._weights[cat] = min(current + DELTA, WEIGHT_MAX)
            elif acc < REDUCE_THRESHOLD:
                self._weights[cat] = max(current - DELTA, WEIGHT_MIN)
            else:
                self._weights[cat] = current  # no change


# ─────────────────────────────────────────────────────────────────────────────
#  Demo: 20 synthetic feedback examples
# ─────────────────────────────────────────────────────────────────────────────

def _case(chief: str, symptoms: list, vitals: str, history: str = "") -> dict:
    """Helper to build a dd_engine-compatible case dict."""
    return {
        "chief_complaint": chief,
        "symptoms": symptoms,
        "vitals": vitals,
        "history": history,
    }


_SYNTHETIC_CASES = [
    # cardiovascular (ACS-like) — matches ACS rule keywords
    _case("前胸部圧迫感",   ["胸痛", "ST上昇", "冷汗", "放散痛"],        "BP 100/60, HR 100, SpO2 97%", "糖尿病"),
    _case("急性の胸痛",     ["放散痛", "TnI陽性", "絞扼感", "ST上昇"],   "BP 115/72, HR 95"),
    _case("胸部絞扼感",     ["胸痛", "圧迫感", "ST上昇"],                 "BP 160/95, HR 88", "高血圧 喫煙歴"),
    # cardiovascular (aorta)
    _case("急性の背部痛",   ["大動脈", "引き裂く", "血圧左右差", "解離"], "BP 170/100, HR 110"),
    # neurological (SAH)
    _case("雷鳴頭痛",       ["突然の激頭痛", "羞明", "嘔吐", "項部硬直"], "BP 185/110, HR 68"),
    _case("突然の激頭痛",   ["雷鳴頭痛", "項部硬直", "thunderclap"],       "BP 150/90, HR 90"),
    # infectious (sepsis)
    _case("発熱・低血圧",   ["発熱", "意識障害", "敗血症", "ショック"],    "BP 85/50, HR 130, SpO2 93%, RR 28, 体温 39.5℃"),
    _case("高熱",           ["発熱", "敗血症", "腹痛", "ショック"],        "BP 95/60, HR 118, SpO2 94%"),
    _case("咳嗽・発熱",     ["発熱", "呼吸困難", "腹痛"],                  "BP 120/75, HR 100, SpO2 92%, 体温 38.9℃"),
    # infectious (UTI)
    _case("発熱・側腹部痛", ["発熱", "腹痛"],                               "BP 118/70, HR 92, 体温 38.4℃"),
    # surgical (appendicitis)
    _case("右下腹部痛",     ["腹痛", "発熱"],                               "BP 125/78, HR 85, 体温 38.0℃"),
    _case("腹痛悪化",       ["腹痛", "発熱"],                               "BP 122/75, HR 90"),
    # pulmonary (PE)
    _case("突然の呼吸困難", ["呼吸困難", "胸痛", "下肢浮腫"],              "BP 110/70, HR 115, SpO2 89%, RR 26"),
    _case("胸膜性胸痛",     ["呼吸困難", "胸痛"],                           "BP 105/65, HR 108, SpO2 91%"),
    # metabolic (DKA) — closest rule is via diabetes keywords
    _case("クスマウル呼吸", ["嘔吐", "意識障害", "頭痛"],                   "BP 100/60, HR 110, RR 28"),
    _case("口渇・多尿",     ["意識障害", "頭痛", "嘔吐"],                   "BP 95/55, HR 120"),
    # cardiovascular (HF)
    _case("起座呼吸",       ["起座呼吸", "両下腿浮腫", "BNP", "浮腫"],     "BP 90/60, HR 105, SpO2 88%"),
    # neurological (stroke)
    _case("突然の片麻痺",   ["麻痺", "構音障害", "頭痛"],                   "BP 175/100, HR 78"),
    # allergic
    _case("蕁麻疹・低血圧", ["ショック", "浮腫", "呼吸困難"],               "BP 70/40, HR 135, SpO2 90%"),
    # infectious (meningitis)
    _case("頭痛・発熱",     ["発熱", "頭痛", "項部硬直"],                   "BP 130/80, HR 95, 体温 39.2℃"),
]

# True diagnoses (ground truth for each case)
_TRUE_DIAGNOSES = [
    "急性冠症候群（ACS）",
    "急性冠症候群（ACS）",
    "急性冠症候群（ACS）",
    "急性大動脈解離",
    "くも膜下出血（SAH）",
    "細菌性髄膜炎",
    "敗血症性ショック",
    "敗血症",
    "市中肺炎",
    "急性腎盂腎炎",
    "急性虫垂炎",
    "急性虫垂炎",
    "肺塞栓症",
    "肺塞栓症",
    "糖尿病性ケトアシドーシス（DKA）",
    "糖尿病性ケトアシドーシス（DKA）",
    "急性心不全（代償不全）",
    "急性脳梗塞",
    "アナフィラキシー",
    "細菌性髄膜炎",
]


if __name__ == "__main__":
    print("=" * 65)
    print("AdaptiveDDSystem — Feedback Learning Demo")
    print("=" * 65)

    system = AdaptiveDDSystem()

    print(f"\nRunning {len(_SYNTHETIC_CASES)} predictions + feedback examples …\n")

    # ── Round 1: predict + feedback ──────────────────────────────────────────
    case_ids = []
    for i, (case, true_dx) in enumerate(zip(_SYNTHETIC_CASES, _TRUE_DIAGNOSES)):
        result = system.predict(case)
        cid = result.case.get("case_id") or str(i)
        case_ids.append(cid)
        prim      = result.primary or {}
        predicted = prim.get("name") or prim.get("disease", "unknown")
        correct   = true_dx.lower() in predicted.lower() or predicted.lower() in true_dx.lower()
        system.feedback(cid, true_dx, correct)

        status = "✓" if correct else "✗"
        print(f"  [{i+1:02d}] {status} Predicted: {predicted[:40]:40s} | True: {true_dx[:35]}")

    # ── Weight adjustment ────────────────────────────────────────────────────
    print("\n--- Adjusting weights based on feedback ---")
    system.adjust_weights()

    # ── Stats report ─────────────────────────────────────────────────────────
    stats = system.get_performance_stats()
    print(f"\nOverall: {stats['overall']['correct']}/{stats['overall']['total']} "
          f"({stats['overall']['accuracy']*100:.1f}%)")
    print("\nBy category:")
    for cat, s in sorted(stats["by_category"].items()):
        bar = "█" * int(s["accuracy"] * 20) + "░" * (20 - int(s["accuracy"] * 20))
        print(
            f"  {cat:15s}  {s['correct']:2d}/{s['total']:2d}  "
            f"{s['accuracy']*100:5.1f}%  [{bar}]  weight={s['weight']:.2f}"
        )

    # ── Round 2: show weight effect ──────────────────────────────────────────
    print("\n--- Effect of weight adjustment on a new ACS case ---")
    test_case = _case("前胸部圧迫感", ["胸痛", "ST上昇", "TnI", "冷汗"], "BP 90/60, HR 110")
    r_before = system.predict(test_case)
    prim = r_before.primary or {}
    prim_name = prim.get("name") or prim.get("disease", "?")
    print(f"  Primary: {prim_name}  prob={prim.get('probability', 0):.3f}  "
          f"category={prim.get('category', '?')}  weight={system._weights.get(prim.get('category','other'), 1.0):.2f}")

    print("\n--- Final learned weights ---")
    for cat, w in sorted(system._weights.items()):
        direction = "↑" if w > 1.0 else ("↓" if w < 1.0 else "─")
        print(f"  {cat:15s}  {w:.2f}  {direction}")

    print("\nDone.")
