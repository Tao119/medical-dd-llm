import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
from dataclasses import dataclass, field
from typing import Optional

from clinical.vitals import parse_vitals, assess_vitals, VitalSigns
from clinical.risk_scores import calc_curb65, calc_qsofa, calc_heart_score
from clinical.lab_interpreter import interpret_labs
from clinical.icd10 import get_icd10
from model.dd_rules_extended import EXTENDED_DD_RULES
from model.keyword_patch import apply_patches as _apply_patches
from model.red_flag_patch import apply_red_flag_patches as _apply_rf_patches
EXTENDED_DD_RULES = _apply_patches(EXTENDED_DD_RULES)
EXTENDED_DD_RULES = _apply_rf_patches(EXTENDED_DD_RULES)


@dataclass
class DiagnosisResult:
    case: dict
    primary: dict
    differentials: list
    red_flags: list
    next_steps: list
    urgency: str
    vital_assessment: Optional[dict] = None
    risk_scores: dict = field(default_factory=dict)
    lab_flags: list = field(default_factory=list)
    icd10: Optional[dict] = None
    scoring_hints: list = field(default_factory=list)
    rag_sources: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "primary": self.primary,
            "differentials": self.differentials,
            "red_flags": self.red_flags,
            "next_steps": self.next_steps,
            "urgency": self.urgency,
            "vital_assessment": self.vital_assessment,
            "risk_scores": self.risk_scores,
            "lab_flags": self.lab_flags,
            "icd10": self.icd10,
            "scoring_hints": self.scoring_hints,
            "rag_sources": self.rag_sources,
        }


def _infer_urgency(case_text: str, vitals: VitalSigns, rule_override: Optional[str]) -> str:
    if rule_override:
        return rule_override
    if vitals:
        av = assess_vitals(vitals)
        if av["severity"] == "critical":
            return "immediate"
        if av["severity"] == "warning":
            return "urgent"
    IMMEDIATE_KW = ["ショック", "意識消失", "心停止", "大動脈解離", "クスマウル",
                    "麻痺", "頸部硬直", "点状出血", "雷鳴頭痛", "子癇"]
    if any(kw in case_text for kw in IMMEDIATE_KW):
        return "immediate"
    URGENT_KW = ["発熱", "呼吸困難", "腹痛", "頭痛", "胸痛", "嘔吐", "黄疸"]
    if any(kw in case_text for kw in URGENT_KW):
        return "urgent"
    return "routine"


def _match_rule(case_text: str) -> Optional[dict]:
    best_rule = None
    best_score = 0
    for rule in EXTENDED_DD_RULES:
        # キーワードスコア（部分一致も含む）
        score = 0
        for kw in rule["keywords"]:
            if kw in case_text:
                score += 1
            # 否定形チェック（「頸部硬直なし」などを除外）
        # 特異度が高い単一キーワードルール (min_match=1 フラグ)
        min_match = rule.get("min_match", 2)
        if score > best_score and score >= min_match:
            best_score = score
            best_rule = rule
    return best_rule


def _normalize(diagnoses: list) -> list:
    total = sum(d["base_prob"] for d in diagnoses)
    result = []
    for d in diagnoses:
        result.append({
            "disease": d["disease"],
            "probability": round(d["base_prob"] / total, 3),
            "icd10": d.get("icd10", ""),
            "distinguishing_features": d.get("distinguishing_features", ""),
        })
    return result


def _calc_risk_scores(case: dict, vitals: Optional[VitalSigns], labs_text: str, rule_id: str) -> dict:
    scores = {}
    age = None
    demo = case.get("demographics", "")
    import re
    m = re.search(r"(\d+)歳", demo)
    if m:
        age = int(m.group(1))

    if rule_id == "CAP" and vitals:
        try:
            c65 = calc_curb65(
                rr=vitals.rr, sbp=vitals.sbp, dbp=vitals.dbp,
                age=age, altered_consciousness="意識障害" in str(case)
            )
            scores["CURB-65"] = {"score": c65.score, "category": c65.category,
                                  "recommendation": c65.recommendation}
        except Exception:
            pass

    if vitals:
        try:
            qs = calc_qsofa(rr=vitals.rr, sbp=vitals.sbp,
                            altered_consciousness="意識障害" in str(case))
            scores["qSOFA"] = {"score": qs.score, "interpretation": qs.interpretation}
        except Exception:
            pass

    if rule_id == "ACS" and age:
        try:
            hs = calc_heart_score(age=age)
            scores["HEART"] = {"score": hs.score, "category": hs.category,
                                "mace_risk": hs.mace_risk_percent}
        except Exception:
            pass

    return scores


def diagnose(
    case: dict,
    retrieved_docs: list = None,
    labs_text: str = "",
) -> DiagnosisResult:
    chief = case.get("chief_complaint", "")
    symptoms = " ".join(case.get("symptoms", []))
    history = case.get("history", "")
    demographics = case.get("demographics", "")
    vitals_str = case.get("vitals", "")

    case_text = f"{chief} {symptoms} {history} {demographics}"

    # バイタル解析
    vitals = None
    vital_assessment = None
    if vitals_str:
        try:
            vitals = parse_vitals(vitals_str)
            av = assess_vitals(vitals)
            vital_assessment = {
                "severity": av["severity"],
                "flags": [
                    {"param": f["parameter"], "message": f["message"]}
                    for f in av["flags"]
                ],
            }
        except Exception:
            pass

    # 検査値解析
    lab_flags = []
    if labs_text:
        try:
            result = interpret_labs(labs_text)
            lab_flags = [
                {"name": f.name, "value": f.value, "status": f.status,
                 "unit": f.unit, "message": f.message}
                for f in result.flags if f.status != "normal"
            ]
        except Exception:
            pass

    # ルールマッチ
    rule = _match_rule(case_text)
    if rule is None:
        return DiagnosisResult(
            case=case,
            primary={"disease": "精査必要", "probability": 0.50,
                     "basis": "症状パターンが特定できません", "source_refs": []},
            differentials=[],
            red_flags=["専門医への紹介を検討", "バイタル安定化優先"],
            next_steps=["詳細な病歴聴取", "バイタル監視"],
            urgency=_infer_urgency(case_text, vitals, None),
            vital_assessment=vital_assessment,
            risk_scores={},
            lab_flags=lab_flags,
        )

    diagnoses = [dict(d) for d in rule["diagnoses"]]
    for d in diagnoses:
        boost = sum(1 for kw in d.get("boost_kw", []) if kw in case_text)
        d["base_prob"] = d["base_prob"] + boost * 0.025

    normalized = _normalize(diagnoses)
    primary_diag = normalized[0]
    primary_diag["basis"] = f"{chief} + {', '.join(case.get('symptoms', [])[:3])}"
    primary_diag["source_refs"] = [d["source"] for d in (retrieved_docs or [])]

    # ICD-10: ルール内のコードを優先し、なければ辞書引き
    rule_icd = rule["diagnoses"][0].get("icd10", "")
    if rule_icd:
        icd_info = {"code": rule_icd, "name_ja": primary_diag["disease"], "name_en": ""}
    else:
        icd_info = get_icd10(primary_diag["disease"])

    risk_scores = _calc_risk_scores(case, vitals, labs_text, rule.get("id", ""))

    urgency = _infer_urgency(case_text, vitals, rule.get("urgency_override"))

    return DiagnosisResult(
        case=case,
        primary=primary_diag,
        differentials=normalized[1:],
        red_flags=rule["red_flags"],
        next_steps=rule["next_steps"],
        urgency=urgency,
        vital_assessment=vital_assessment,
        risk_scores=risk_scores,
        lab_flags=lab_flags,
        icd10=icd_info,
        scoring_hints=rule.get("scoring_hints", []),
        rag_sources=[d["source"] for d in (retrieved_docs or [])],
    )
