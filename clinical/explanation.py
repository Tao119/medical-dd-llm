"""
clinical/explanation.py — Feature Attribution for Differential Diagnoses

Explains *why* a diagnosis was made by attributing contributions to
individual symptoms, vitals, and lab values.

Public API
----------
  explain_diagnosis(case, result)         -> dict   (structured attribution)
  explain_in_plain_language(result)       -> str    (patient-friendly)
  explain_for_provider(result)            -> str    (clinical reasoning)

Usage::

    from model.dd_engine import diagnose
    from clinical.explanation import explain_diagnosis, explain_in_plain_language

    result = diagnose(case)
    expl   = explain_diagnosis(case, result)
    text   = explain_in_plain_language(result)
"""

from __future__ import annotations

import os
import re
import sys
from dataclasses import dataclass, field
from typing import Optional

# ── path setup ─────────────────────────────────────────────────────────────
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from model.dd_engine import DiagnosisResult, diagnose, _match_rule
from model.dd_rules_extended import EXTENDED_DD_RULES
from clinical.vitals import parse_vitals, assess_vitals


# ===========================================================================
# Data structures
# ===========================================================================

@dataclass
class SymptomContribution:
    symptom: str
    weight: float          # 0–1, higher = stronger contribution
    matched_rule: str      # ID of the rule this symptom triggered


@dataclass
class VitalContribution:
    vital: str             # human-readable vital description
    flag: str              # e.g. "critical_low", "warning_high", "normal"
    contribution: str      # qualitative effect on urgency/diagnosis


@dataclass
class LabContribution:
    name: str
    value: str             # raw value as string
    contribution: str      # e.g. "ACS prob +0.12"


@dataclass
class ExplanationResult:
    primary_disease: str
    key_symptoms: list[SymptomContribution] = field(default_factory=list)
    key_vitals: list[VitalContribution] = field(default_factory=list)
    key_labs: list[LabContribution] = field(default_factory=list)
    counterfactual: str = ""
    evidence_strength: str = "weak"   # "strong" | "moderate" | "weak"

    def to_dict(self) -> dict:
        return {
            "primary_disease": self.primary_disease,
            "key_symptoms": [
                {"symptom": s.symptom, "weight": s.weight, "matched_rule": s.matched_rule}
                for s in self.key_symptoms
            ],
            "key_vitals": [
                {"vital": v.vital, "flag": v.flag, "contribution": v.contribution}
                for v in self.key_vitals
            ],
            "key_labs": [
                {"name": l.name, "value": l.value, "contribution": l.contribution}
                for l in self.key_labs
            ],
            "counterfactual": self.counterfactual,
            "evidence_strength": self.evidence_strength,
        }


# ===========================================================================
# Internal helpers
# ===========================================================================

# Lab keywords and their disease associations
_LAB_PATTERNS = [
    (r"TnI\s*([\d.]+)", "TnI", "ACS"),
    (r"CK-?MB\s*([\d.]+)", "CK-MB", "ACS"),
    (r"BNP\s*([\d.]+)", "BNP", "AHF"),
    (r"D-?dimer\s*([\d.]+)", "D-dimer", "PE"),
    (r"Cr(?:eatinine)?\s*([\d.]+)", "Creatinine", "AKI"),
    (r"WBC\s*([\d.]+)", "WBC", "感染症"),
    (r"CRP\s*([\d.]+)", "CRP", "感染症"),
    (r"PLT\s*([\d.]+)", "PLT", "血液疾患"),
    (r"Hb\s*([\d.]+)", "Hb", "貧血"),
    (r"Na\s*([\d.]+)", "Na", "電解質異常"),
    (r"K\s*([\d.]+)", "K", "電解質異常"),
    (r"Glucose\s*([\d.]+)", "Glucose", "DKA"),
    (r"pH\s*([\d.]+)", "pH", "DKA"),
    (r"HbA1c\s*([\d.]+)", "HbA1c", "糖尿病"),
    (r"PT-INR\s*([\d.]+)", "PT-INR", "凝固異常"),
    (r"AST\s*([\d.]+)", "AST", "肝疾患"),
    (r"ALT\s*([\d.]+)", "ALT", "肝疾患"),
    (r"T-Bil\s*([\d.]+)", "T-Bil", "胆道疾患"),
    (r"Lipase\s*([\d.]+)", "Lipase", "急性膵炎"),
]

_VITAL_FLAG_MAP = {
    "sbp_critical_low": ("critical_low", "低血圧ショック → 緊急度: immediate"),
    "sbp_warning_low": ("warning_low", "低血圧 → 循環不全の可能性"),
    "sbp_warning_high": ("warning_high", "高血圧 → 大動脈解離・高血圧脳症リスク"),
    "hr_critical_high": ("critical_high", "頻脈 → 出血・ショック・頻脈性不整脈"),
    "hr_warning_low": ("warning_low", "徐脈 → 房室ブロック・β遮断薬過量"),
    "spo2_critical_low": ("critical_low", "SpO2 低下 → 酸素化不全: 即時対応"),
    "spo2_warning_low": ("warning_low", "SpO2 軽度低下 → 呼吸補助考慮"),
    "rr_warning_high": ("warning_high", "多呼吸 → 代謝性アシドーシス・肺炎・心不全"),
    "temp_warning_high": ("warning_high", "発熱 → 感染症・炎症反応"),
    "temp_critical_high": ("critical_high", "高熱 → 敗血症・熱中症"),
}


def _extract_matched_symptoms(case: dict, rule_id: str) -> list[SymptomContribution]:
    """Find which symptom keywords matched the winning rule and assign weights."""
    # Find the rule
    matched_rule = None
    for rule in EXTENDED_DD_RULES:
        if rule["id"] == rule_id:
            matched_rule = rule
            break
    if not matched_rule:
        return []

    case_text = " ".join([
        case.get("chief_complaint", ""),
        " ".join(case.get("symptoms", [])),
        case.get("history", ""),
    ])

    contributions = []
    total_possible = len(matched_rule["keywords"])
    for kw in matched_rule["keywords"]:
        if kw in case_text:
            # Weight proportional to keyword specificity (longer = more specific)
            weight = round(min(1.0, 0.1 + len(kw) / 30.0), 3)
            contributions.append(SymptomContribution(
                symptom=kw,
                weight=weight,
                matched_rule=rule_id,
            ))

    # Normalise weights so they sum to 1 if we have contributions
    total = sum(c.weight for c in contributions)
    if total > 0:
        for c in contributions:
            c.weight = round(c.weight / total, 3)

    return sorted(contributions, key=lambda x: -x.weight)


def _extract_vital_contributions(case: dict) -> list[VitalContribution]:
    """Parse vitals and identify abnormal readings with clinical impact."""
    vitals_str = case.get("vitals", "")
    if not vitals_str:
        return []

    try:
        vs = parse_vitals(vitals_str)
        av = assess_vitals(vs)
    except Exception:
        return []

    contributions = []
    for flag in av.get("flags", []):
        param = flag.get("parameter", "")
        severity = flag.get("severity", "")
        msg = flag.get("message", "")
        flag_key = f"{param}_{severity}"
        flag_type, contribution = _VITAL_FLAG_MAP.get(
            flag_key, (severity, msg)
        )
        contributions.append(VitalContribution(
            vital=f"{param} {msg}",
            flag=flag_type,
            contribution=contribution,
        ))

    return contributions


def _extract_lab_contributions(
    case: dict,
    result: DiagnosisResult,
) -> list[LabContribution]:
    """Extract lab values from case and estimate probability contribution."""
    labs_text = case.get("labs", case.get("history", ""))
    if not labs_text:
        return []

    primary_disease = result.primary.get("disease", "")
    contributions = []

    for pattern, name, target_disease in _LAB_PATTERNS:
        m = re.search(pattern, labs_text, re.IGNORECASE)
        if not m:
            continue
        value = m.group(1)
        # Only report if this lab is relevant to the primary diagnosis
        if target_disease in primary_disease or primary_disease in target_disease:
            contribution = f"{primary_disease} の診断根拠 (関連マーカー)"
        else:
            contribution = f"{target_disease} との関連 (補助情報)"
        contributions.append(LabContribution(name=name, value=value, contribution=contribution))

    # Also check explicit lab_flags from the result
    for lf in result.lab_flags:
        if lf.get("status") in ("high", "low", "critical"):
            n = lf.get("name", "")
            v = str(lf.get("value", ""))
            s = lf.get("status", "")
            contributions.append(LabContribution(
                name=n,
                value=f"{v} ({s})",
                contribution=lf.get("message", f"{s} → 精査推奨"),
            ))

    # Deduplicate by name
    seen: set[str] = set()
    unique = []
    for c in contributions:
        if c.name not in seen:
            unique.append(c)
            seen.add(c.name)
    return unique


def _build_counterfactual(
    case: dict,
    result: DiagnosisResult,
    key_symptoms: list[SymptomContribution],
) -> str:
    """Generate a simple counterfactual explanation."""
    if not key_symptoms:
        return ""

    top_symptom = key_symptoms[0].symptom
    primary = result.primary.get("disease", "")
    differentials = [d.get("disease", "") for d in result.differentials[:2]]

    if differentials:
        alt = " または ".join(differentials)
        return (
            f"もし「{top_symptom}」が認められなければ、"
            f"診断は「{alt}」になる可能性が高い。"
        )
    return (
        f"「{top_symptom}」は「{primary}」診断の最重要根拠であり、"
        f"この所見なしでは確診が困難となる。"
    )


def _assess_evidence_strength(
    key_symptoms: list[SymptomContribution],
    key_vitals: list[VitalContribution],
    key_labs: list[LabContribution],
    primary_prob: float,
) -> str:
    """Classify evidence strength as strong / moderate / weak."""
    score = 0
    score += min(3, len(key_symptoms))       # up to 3 pts for symptoms
    score += min(2, len(key_vitals))         # up to 2 pts for abnormal vitals
    score += min(2, len(key_labs))           # up to 2 pts for lab findings
    if primary_prob >= 0.60:
        score += 2
    elif primary_prob >= 0.45:
        score += 1

    if score >= 6:
        return "strong"
    if score >= 3:
        return "moderate"
    return "weak"


# ===========================================================================
# Main public functions
# ===========================================================================

def explain_diagnosis(case: dict, result: DiagnosisResult) -> dict:
    """Build a structured feature-attribution explanation for *result*.

    Parameters
    ----------
    case:
        Original patient case dict.
    result:
        :class:`DiagnosisResult` from :func:`diagnose`.

    Returns
    -------
    dict::

        {
          "key_symptoms": [{"symptom": str, "weight": float, "matched_rule": str},...],
          "key_vitals":   [{"vital": str, "flag": str, "contribution": str},...],
          "key_labs":     [{"name": str, "value": str, "contribution": str},...],
          "counterfactual": str,
          "evidence_strength": "strong" | "moderate" | "weak",
        }
    """
    # Recover the matched rule ID from the primary disease (heuristic: scan rules)
    primary_disease = result.primary.get("disease", "")
    rule_id = ""
    for rule in EXTENDED_DD_RULES:
        for d in rule["diagnoses"]:
            if d["disease"] == primary_disease:
                rule_id = rule["id"]
                break
        if rule_id:
            break

    key_symptoms = _extract_matched_symptoms(case, rule_id)
    key_vitals = _extract_vital_contributions(case)
    key_labs = _extract_lab_contributions(case, result)
    counterfactual = _build_counterfactual(case, result, key_symptoms)
    evidence_strength = _assess_evidence_strength(
        key_symptoms, key_vitals, key_labs,
        result.primary.get("probability", 0.0),
    )

    expl = ExplanationResult(
        primary_disease=primary_disease,
        key_symptoms=key_symptoms,
        key_vitals=key_vitals,
        key_labs=key_labs,
        counterfactual=counterfactual,
        evidence_strength=evidence_strength,
    )
    return expl.to_dict()


def explain_in_plain_language(result: DiagnosisResult) -> str:
    """Generate a patient-friendly plain-language explanation.

    Parameters
    ----------
    result:
        :class:`DiagnosisResult` to explain.

    Returns
    -------
    str:
        Plain Japanese text suitable for a patient summary.
    """
    primary = result.primary.get("disease", "不明")
    prob = result.primary.get("probability", 0.0)
    urgency = result.urgency

    urgency_jp = {
        "immediate": "今すぐ",
        "urgent": "できるだけ早く",
        "routine": "通常の診療として",
    }.get(urgency, "適切な時期に")

    lines = [
        f"あなたの症状を総合的に評価した結果、最も可能性が高い診断は「{primary}」です"
        f"（確率 {prob*100:.0f}%）。",
    ]

    if result.differentials:
        diff_names = "、".join(d["disease"] for d in result.differentials[:2])
        lines.append(f"他に「{diff_names}」の可能性も除外する必要があります。")

    if result.red_flags:
        rf = "、".join(result.red_flags[:2])
        lines.append(f"特に重要な確認事項として、{rf} が挙げられます。")

    if result.next_steps:
        ns = "、".join(result.next_steps[:3])
        lines.append(f"次のステップとして、{ns} を行う予定です。")

    lines.append(f"担当医師が{urgency_jp}対応します。ご不安な点は遠慮なくご質問ください。")

    return "\n".join(lines)


def explain_for_provider(result: DiagnosisResult) -> str:
    """Generate a clinical reasoning summary for healthcare providers.

    Parameters
    ----------
    result:
        :class:`DiagnosisResult` to explain.

    Returns
    -------
    str:
        Structured clinical reasoning in Japanese, suitable for a clinical note.
    """
    primary = result.primary.get("disease", "不明")
    prob = result.primary.get("probability", 0.0)
    basis = result.primary.get("basis", "")

    lines = ["【臨床推論サマリー】", ""]
    lines.append(f"主診断: {primary}（事前確率 {prob*100:.0f}%）")
    if basis:
        lines.append(f"根拠: {basis}")

    if result.vital_assessment:
        sev = result.vital_assessment.get("severity", "normal")
        flags = result.vital_assessment.get("flags", [])
        lines.append(f"\nバイタル評価: {sev}")
        for f in flags[:3]:
            lines.append(f"  - {f.get('parameter','')}: {f.get('message','')}")

    if result.risk_scores:
        lines.append("\nリスクスコア:")
        for score_name, score_data in result.risk_scores.items():
            if isinstance(score_data, dict):
                score_val = score_data.get("score", "")
                interp = score_data.get("category", score_data.get("interpretation", ""))
                lines.append(f"  {score_name}: {score_val} — {interp}")

    if result.lab_flags:
        lines.append("\n異常検査値:")
        for lf in result.lab_flags[:5]:
            lines.append(
                f"  - {lf.get('name','')}: {lf.get('value','')} "
                f"[{lf.get('status','')}] {lf.get('message','')}"
            )

    if result.differentials:
        lines.append("\n鑑別診断:")
        for d in result.differentials[:4]:
            df = d.get("distinguishing_features", "")
            lines.append(
                f"  - {d['disease']} ({d.get('probability',0)*100:.0f}%)"
                + (f": {df}" if df else "")
            )

    if result.red_flags:
        lines.append("\n警告サイン (Red Flags):")
        for rf in result.red_flags:
            lines.append(f"  ⚠ {rf}")

    if result.next_steps:
        lines.append("\n推奨ネクストステップ:")
        for ns in result.next_steps:
            lines.append(f"  □ {ns}")

    lines.append(f"\n緊急度: {result.urgency.upper()}")
    if result.icd10:
        icd = result.icd10
        lines.append(f"ICD-10: {icd.get('code','')} — {icd.get('name_ja','')}")

    return "\n".join(lines)


# ===========================================================================
# Demo
# ===========================================================================

_DEMO_CASES_EXPLAIN = [
    {
        "chief_complaint": "前胸部圧迫感",
        "symptoms": ["冷汗", "放散痛", "ST上昇", "悪心"],
        "history": "高血圧 糖尿病 喫煙歴あり TnI 0.8",
        "demographics": "62歳 男性",
        "vitals": "BP 90/60, HR 110, SpO2 96%, RR 22",
        "labs": "TnI 0.8 ng/mL  CK-MB 45 U/L",
    },
    {
        "chief_complaint": "急激な頭痛",
        "symptoms": ["雷鳴頭痛", "嘔吐", "項部硬直", "羞明"],
        "history": "突然発症 既往なし",
        "demographics": "45歳 女性",
        "vitals": "BP 180/100, HR 88, SpO2 98%, 体温 37.2",
    },
    {
        "chief_complaint": "呼吸困難",
        "symptoms": ["起座呼吸", "両下腿浮腫", "体重増加", "BNP"],
        "history": "心筋梗塞既往 BNP 1200 pg/mL",
        "demographics": "70歳 男性",
        "vitals": "BP 160/90, HR 100, SpO2 90%, RR 28",
        "labs": "BNP 1200 pg/mL",
    },
    {
        "chief_complaint": "腹部の激痛",
        "symptoms": ["引き裂く", "血圧左右差", "背部痛", "突然発症"],
        "history": "高血圧 マルファン症候群 突然発症",
        "demographics": "50歳 男性",
        "vitals": "BP 200/110, HR 95, SpO2 97%",
    },
    {
        "chief_complaint": "発熱と倦怠感",
        "symptoms": ["発熱", "湿性咳嗽", "膿性痰", "呼吸困難"],
        "history": "3日前からの発症 WBC 14000 CRP 15",
        "demographics": "55歳 男性",
        "vitals": "BP 120/80, HR 92, SpO2 95%, RR 20, 体温 38.8",
        "labs": "WBC 14000  CRP 15 mg/dL",
    },
]


def _run_demo() -> None:
    print("=" * 70)
    print("Feature Attribution Explanation Demo")
    print("=" * 70)

    for i, case in enumerate(_DEMO_CASES_EXPLAIN, 1):
        print(f"\n{'='*70}")
        print(f"[Case {i}] {case['chief_complaint']}")
        print("-" * 70)

        result = diagnose(case)
        expl = explain_diagnosis(case, result)

        print(f"Primary diagnosis: {expl['primary_disease']}")
        print(f"Evidence strength: {expl['evidence_strength']}")

        if expl["key_symptoms"]:
            print("\nKey symptoms:")
            for s in expl["key_symptoms"][:4]:
                print(f"  [{s['weight']:.3f}] {s['symptom']}  (rule: {s['matched_rule']})")

        if expl["key_vitals"]:
            print("\nKey vitals:")
            for v in expl["key_vitals"][:3]:
                print(f"  [{v['flag']}] {v['vital']} → {v['contribution']}")

        if expl["key_labs"]:
            print("\nKey labs:")
            for l in expl["key_labs"][:3]:
                print(f"  {l['name']}={l['value']} → {l['contribution']}")

        if expl["counterfactual"]:
            print(f"\nCounterfactual: {expl['counterfactual']}")

        print("\n--- Plain Language (Patient) ---")
        print(explain_in_plain_language(result))

        print("\n--- Clinical Summary (Provider) ---")
        print(explain_for_provider(result))


if __name__ == "__main__":
    _run_demo()
