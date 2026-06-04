"""
clinical — Clinical Decision Support Components

提供モジュール:
  vitals        バイタルサイン解析・異常検知
  risk_scores   臨床リスクスコア (CURB-65, qSOFA, HEART, SOFA, PSI/PORT)
  lab_interpreter 検査値インタープリター
  icd10         ICD-10 コードマッパー
"""

from .vitals import VitalSigns, parse_vitals, assess_vitals
from .risk_scores import (
    ScoreResult,
    calc_curb65,
    calc_qsofa,
    calc_heart_score,
    calc_sofa,
    calc_psi_port,
    HeartHistory,
    HeartECG,
    HeartAge,
    HeartRiskFactors,
    HeartTroponin,
)
from .lab_interpreter import LabFlag, LabResult, interpret_labs, parse_lab_string
from .icd10 import get_icd10, suggest_icd10, list_icd10_by_chapter

__all__ = [
    # vitals
    "VitalSigns",
    "parse_vitals",
    "assess_vitals",
    # risk_scores
    "ScoreResult",
    "calc_curb65",
    "calc_qsofa",
    "calc_heart_score",
    "calc_sofa",
    "calc_psi_port",
    "HeartHistory",
    "HeartECG",
    "HeartAge",
    "HeartRiskFactors",
    "HeartTroponin",
    # lab_interpreter
    "LabFlag",
    "LabResult",
    "interpret_labs",
    "parse_lab_string",
    # icd10
    "get_icd10",
    "suggest_icd10",
    "list_icd10_by_chapter",
]
