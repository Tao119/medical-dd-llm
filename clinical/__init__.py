"""
clinical — Clinical Decision Support Components

提供モジュール:
  vitals              バイタルサイン解析・異常検知
  risk_scores         臨床リスクスコア (CURB-65, qSOFA, HEART, SOFA, PSI/PORT)
  lab_interpreter     検査値インタープリター
  icd10               ICD-10 コードマッパー
  pediatric           小児科モード（年齢別バイタル・PEWS・薬用量・輸液計算）
  treatment_protocols エビデンスベース治療プロトコル（12 疾患）
  triage              Manchester Triage System（5 レベル MTS）
  drug_dosing         成人薬用量計算機（腎・肝機能調整、30+ 薬剤）
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
from .pediatric import (
    AgeGroup,
    PediatricVitals,
    PediatricVitalAssessmentResult,
    PEWSInput,
    PEWSResult,
    PedsDose,
    FluidCalculation,
    classify_age,
    estimate_weight_kg,
    assess_pediatric_vitals,
    calc_pews,
    pediatric_drug_dose,
    holliday_segar,
    pediatric_dd_adjustments,
)
from .treatment_protocols import (
    TreatmentStep,
    TreatmentProtocol,
    get_protocol,
    list_protocols,
    format_protocol_text,
)
from .triage import (
    TriageResult,
    triage,
    triage_chest_pain,
    triage_dyspnea,
    format_triage_result,
)
from .drug_dosing import (
    DoseCalculation,
    calc_dose,
    list_drugs,
    format_dose_result,
)

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
    # pediatric
    "AgeGroup",
    "PediatricVitals",
    "PediatricVitalAssessmentResult",
    "PEWSInput",
    "PEWSResult",
    "PedsDose",
    "FluidCalculation",
    "classify_age",
    "estimate_weight_kg",
    "assess_pediatric_vitals",
    "calc_pews",
    "pediatric_drug_dose",
    "holliday_segar",
    "pediatric_dd_adjustments",
    # treatment_protocols
    "TreatmentStep",
    "TreatmentProtocol",
    "get_protocol",
    "list_protocols",
    "format_protocol_text",
    # triage
    "TriageResult",
    "triage",
    "triage_chest_pain",
    "triage_dyspnea",
    "format_triage_result",
    # drug_dosing
    "DoseCalculation",
    "calc_dose",
    "list_drugs",
    "format_dose_result",
]
