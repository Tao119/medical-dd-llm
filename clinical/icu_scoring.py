"""
clinical/icu_scoring.py — ICU Scoring Systems

Implements 5 major ICU scoring systems:
  1. APACHE II — Acute Physiology and Chronic Health Evaluation II
  2. SOFA      — Sequential Organ Failure Assessment (full)
  3. NEWS2     — National Early Warning Score 2
  4. GRACE     — Global Registry of Acute Coronary Events (ACS risk)
  5. MELD/MELD-Na — Model for End-Stage Liver Disease

Each score exposes: calc_{score}(params) -> dict
  with keys: score, interpretation, mortality_pct (where applicable), recommendations
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional


# ===========================================================================
# Common helpers
# ===========================================================================

def _clamp(val: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, float(val)))


def _score_table(val: float, thresholds: list[tuple[float, float, int]]) -> int:
    """Generic scoring from a list of (low, high, score) intervals.
    Interval is inclusive: low <= val <= high → score.
    """
    for lo, hi, pts in thresholds:
        if lo <= val <= hi:
            return pts
    return 0


# ===========================================================================
# 1. APACHE II
# ===========================================================================

@dataclass
class ApacheIIResult:
    score: int
    aps_score: int          # Acute Physiology Score (12 params)
    age_score: int
    chronic_health_score: int
    predicted_mortality_pct: float
    interpretation: str
    recommendations: list[str]
    component_scores: dict[str, int]


def calc_apache_ii(
    *,
    # Vital signs / physiology
    temperature_c: float = 37.0,       # rectal/core °C
    map_mmhg: float = 80.0,            # mean arterial pressure
    hr: float = 75.0,                  # heart rate /min
    rr: float = 16.0,                  # respiratory rate /min
    # Oxygenation — use EITHER fio2+pao2 OR aa_gradient
    fio2: float = 0.21,                # fraction inspired O2 (0.21-1.0)
    pao2_mmhg: float = 90.0,           # arterial PaO2 mmHg
    aa_gradient: Optional[float] = None,  # A-a gradient if FiO2 ≥ 0.5
    # Blood chemistry
    ph: float = 7.40,
    na_meq: float = 140.0,             # serum sodium mEq/L
    k_meq: float = 4.0,               # serum potassium mEq/L
    cr_mg_dl: float = 1.0,            # serum creatinine mg/dL
    hct_pct: float = 42.0,            # haematocrit %
    wbc_k: float = 8.0,               # WBC × 10³/μL
    gcs: int = 15,                     # Glasgow Coma Scale 3-15
    # Renal failure flag (doubles Cr points)
    acute_renal_failure: bool = False,
    # Age
    age: int = 50,
    # Chronic health (choose one)
    elective_postop: bool = False,      # elective post-op: 2 pts
    nonoperative_emergency_postop: bool = False,  # non-op/emergency post-op: 5 pts
    severe_organ_insufficiency: bool = False,  # liver/CV/respiratory/renal/immune: 5 pts
) -> ApacheIIResult:
    """APACHE II スコア計算.

    Knaus WA et al. APACHE II: a severity of disease classification system.
    Crit Care Med. 1985;13(10):818-29.

    Parameters cover all 12 APS variables + age + chronic health.
    Returns APACHE II total, predicted mortality %, and recommendations.
    """
    comp: dict[str, int] = {}

    # -- 1. Temperature --
    comp["temperature"] = _score_table(temperature_c, [
        (41.0, 999, 4), (39.0, 40.9, 3), (38.5, 38.9, 1),
        (36.0, 38.4, 0), (34.0, 35.9, 1), (32.0, 33.9, 2),
        (30.0, 31.9, 3), (-999, 29.9, 4),
    ])

    # -- 2. MAP --
    comp["map"] = _score_table(map_mmhg, [
        (160, 999, 4), (130, 159, 3), (110, 129, 2),
        (70, 109, 0), (50, 69, 2), (-999, 49, 4),
    ])

    # -- 3. HR --
    comp["hr"] = _score_table(hr, [
        (180, 999, 4), (140, 179, 3), (110, 139, 2),
        (70, 109, 0), (55, 69, 2), (40, 54, 3), (-999, 39, 4),
    ])

    # -- 4. RR --
    comp["rr"] = _score_table(rr, [
        (50, 999, 4), (35, 49, 3), (25, 34, 1),
        (12, 24, 0), (10, 11, 1), (6, 9, 2), (-999, 5, 4),
    ])

    # -- 5. Oxygenation --
    if fio2 >= 0.5:
        # Use A-a gradient
        grad = aa_gradient if aa_gradient is not None else _calc_aa_gradient(fio2, pao2_mmhg)
        comp["oxygenation"] = _score_table(grad, [
            (500, 999, 4), (350, 499, 3), (200, 349, 2),
            (-999, 199, 0),
        ])
    else:
        # Use PaO2
        comp["oxygenation"] = _score_table(pao2_mmhg, [
            (70, 999, 0), (61, 70, 1), (55, 60, 3), (-999, 54, 4),
        ])

    # -- 6. pH --
    comp["ph"] = _score_table(ph, [
        (7.7, 999, 4), (7.6, 7.69, 3), (7.5, 7.59, 1),
        (7.33, 7.49, 0), (7.25, 7.32, 2), (7.15, 7.24, 3),
        (-999, 7.14, 4),
    ])

    # -- 7. Serum Sodium --
    comp["sodium"] = _score_table(na_meq, [
        (180, 999, 4), (160, 179, 3), (155, 159, 2), (150, 154, 1),
        (130, 149, 0), (120, 129, 2), (111, 119, 3), (-999, 110, 4),
    ])

    # -- 8. Serum Potassium --
    comp["potassium"] = _score_table(k_meq, [
        (7.0, 999, 4), (6.0, 6.9, 3), (5.5, 5.9, 1),
        (3.5, 5.4, 0), (3.0, 3.4, 1), (2.5, 2.9, 2), (-999, 2.4, 4),
    ])

    # -- 9. Creatinine --
    cr_pts = _score_table(cr_mg_dl, [
        (3.5, 999, 4), (2.0, 3.4, 3), (1.5, 1.9, 2),
        (0.6, 1.4, 0), (-999, 0.59, 2),
    ])
    if acute_renal_failure:
        cr_pts = min(cr_pts * 2, 8)
    comp["creatinine"] = cr_pts

    # -- 10. Haematocrit --
    comp["hct"] = _score_table(hct_pct, [
        (60, 999, 4), (50, 59.9, 2), (46, 49.9, 1),
        (30, 45.9, 0), (20, 29.9, 2), (-999, 19.9, 4),
    ])

    # -- 11. WBC --
    comp["wbc"] = _score_table(wbc_k, [
        (40, 999, 4), (20, 39.9, 2), (15, 19.9, 1),
        (3, 14.9, 0), (1, 2.9, 2), (-999, 0.99, 4),
    ])

    # -- 12. GCS contribution = 15 - GCS --
    gcs_clamped = int(_clamp(gcs, 3, 15))
    comp["gcs"] = 15 - gcs_clamped

    aps = sum(comp.values())

    # Age points
    age_pts = _score_table(float(age), [
        (75, 999, 6), (65, 74, 5), (55, 64, 3),
        (45, 54, 2), (-999, 44, 0),
    ])

    # Chronic health points
    if nonoperative_emergency_postop or severe_organ_insufficiency:
        ch_pts = 5
    elif elective_postop:
        ch_pts = 2
    else:
        ch_pts = 0

    total = aps + age_pts + ch_pts

    # Predicted mortality (logistic regression from Knaus 1991)
    # ln(odds) = -3.517 + (APACHE_II × 0.146) + (diagnosis_weight ≈ 0)
    log_odds = -3.517 + total * 0.146
    mortality_pct = round(100.0 / (1.0 + math.exp(-log_odds)), 1)

    # Interpretation
    if total < 10:
        interp = "低リスク（予測死亡率 <15%）"
    elif total < 20:
        interp = "中等度リスク（予測死亡率 15-40%）"
    elif total < 30:
        interp = "高リスク（予測死亡率 40-70%）"
    else:
        interp = "超高リスク（予測死亡率 >70%）"

    recs: list[str] = [
        "ICU入室・継続的モニタリング（HR/BP/SpO2/尿量）",
        "異常値の積極的補正（電解質/pH/体温）",
    ]
    if total >= 20:
        recs += ["集中治療専門医へのコンサルト", "家族との目標設定(GOC)面談"]
    if acute_renal_failure:
        recs.append("腎臓内科コンサルト — RRT(腎代替療法)適応評価")

    comp["age_pts"] = age_pts
    comp["chronic_health_pts"] = ch_pts

    return ApacheIIResult(
        score=total,
        aps_score=aps,
        age_score=age_pts,
        chronic_health_score=ch_pts,
        predicted_mortality_pct=mortality_pct,
        interpretation=interp,
        recommendations=recs,
        component_scores=comp,
    )


def _calc_aa_gradient(fio2: float, pao2: float, paco2: float = 40.0,
                       barometric: float = 760.0) -> float:
    """Alveolar-arterial (A-a) gradient."""
    pao2_alv = (barometric - 47) * fio2 - paco2 / 0.8
    return round(pao2_alv - pao2, 1)


# ===========================================================================
# 2. SOFA (full version)
# ===========================================================================

@dataclass
class SOFAResult:
    score: int
    organ_scores: dict[str, int]
    interpretation: str
    mortality_estimate: str
    recommendations: list[str]


def calc_sofa(
    *,
    # Respiratory
    pao2_fio2: float = 400.0,          # PaO2/FiO2 ratio
    on_respiratory_support: bool = False,
    # Coagulation
    platelets_k: float = 200.0,        # ×10³/μL
    # Liver
    bilirubin_mg_dl: float = 0.8,
    # Cardiovascular
    map_mmhg: float = 75.0,
    vasopressor: str = "none",         # none / dopa_low / dopa_mid / epi / norepi
    # CNS
    gcs: int = 15,
    # Renal
    cr_mg_dl: float = 0.9,
    urine_output_ml_day: Optional[float] = None,  # mL/24h; if given, may override Cr score
) -> SOFAResult:
    """SOFA (Sequential Organ Failure Assessment) score.

    Vincent JL et al. The SOFA (Sepsis-related Organ Failure Assessment) score.
    Intensive Care Med. 1996;22:707-10.

    Score range: 0-24. Each organ system scored 0-4.
    Total >11 associated with >90% mortality in some cohorts.
    """
    organs: dict[str, int] = {}

    # -- Respiratory: PaO2/FiO2 ratio --
    pf = pao2_fio2
    if pf >= 400:
        organs["respiratory"] = 0
    elif pf >= 300:
        organs["respiratory"] = 1
    elif pf >= 200:
        organs["respiratory"] = 2
    elif pf >= 100 and on_respiratory_support:
        organs["respiratory"] = 3
    elif pf < 100 and on_respiratory_support:
        organs["respiratory"] = 4
    else:
        organs["respiratory"] = 3  # <200 without support → score 3

    # -- Coagulation: Platelets ×10³/μL --
    plt = platelets_k
    if plt >= 150:
        organs["coagulation"] = 0
    elif plt >= 100:
        organs["coagulation"] = 1
    elif plt >= 50:
        organs["coagulation"] = 2
    elif plt >= 20:
        organs["coagulation"] = 3
    else:
        organs["coagulation"] = 4

    # -- Liver: Bilirubin mg/dL --
    bili = bilirubin_mg_dl
    if bili < 1.2:
        organs["liver"] = 0
    elif bili < 2.0:
        organs["liver"] = 1
    elif bili < 6.0:
        organs["liver"] = 2
    elif bili < 12.0:
        organs["liver"] = 3
    else:
        organs["liver"] = 4

    # -- Cardiovascular: vasopressor or MAP --
    vaso_map = {
        "none": 0,
        "map_low": 1,       # MAP < 70
        "dopa_low": 2,      # dopamine ≤5 μg/kg/min
        "dopa_mid": 3,      # dopamine 5-15 OR epi/norepi ≤0.1
        "epi": 4,           # epi/norepi >0.1 OR dopa >15
        "norepi": 4,
    }
    if vasopressor == "none":
        organs["cardiovascular"] = 0 if map_mmhg >= 70 else 1
    else:
        organs["cardiovascular"] = vaso_map.get(vasopressor, 0)

    # -- CNS: GCS --
    gcs_c = int(_clamp(gcs, 3, 15))
    if gcs_c == 15:
        organs["cns"] = 0
    elif gcs_c >= 13:
        organs["cns"] = 1
    elif gcs_c >= 10:
        organs["cns"] = 2
    elif gcs_c >= 6:
        organs["cns"] = 3
    else:
        organs["cns"] = 4

    # -- Renal: Creatinine or urine output --
    cr_score: int
    if cr_mg_dl < 1.2:
        cr_score = 0
    elif cr_mg_dl < 2.0:
        cr_score = 1
    elif cr_mg_dl < 3.5:
        cr_score = 2
    elif cr_mg_dl < 5.0:
        cr_score = 3
    else:
        cr_score = 4

    # Urine output can upgrade renal score
    uo_score = 0
    if urine_output_ml_day is not None:
        if urine_output_ml_day < 200:
            uo_score = 4
        elif urine_output_ml_day < 500:
            uo_score = 3
        else:
            uo_score = 0

    organs["renal"] = max(cr_score, uo_score)

    total = sum(organs.values())

    # Interpretation
    if total <= 1:
        interp = "臓器障害なし〜最小限"
        mort = "<10%"
    elif total <= 6:
        interp = "軽度〜中等度の多臓器障害"
        mort = "10-20%"
    elif total <= 11:
        interp = "重篤な多臓器不全"
        mort = "40-50%"
    else:
        interp = "非常に重篤な多臓器不全 — 蘇生の限界評価が必要"
        mort = ">90%"

    recs: list[str] = ["全臓器機能の経時的モニタリング（6-12時間毎のSOFA再評価）"]
    if organs["respiratory"] >= 3:
        recs.append("呼吸: 肺保護換気戦略(VT 6mL/kg, Pplat≤30), PEEP最適化")
    if organs["cardiovascular"] >= 3:
        recs.append("循環: 十分な輸液蘇生後も低血圧 → ノルエピネフリン第一選択")
    if organs["renal"] >= 3:
        recs.append("腎: 持続的腎代替療法(CRRT)適応評価")
    if organs["liver"] >= 3:
        recs.append("肝: 急性肝不全プロトコル・N-アセチルシステイン検討")
    if organs["coagulation"] >= 3:
        recs.append("凝固: FFP/血小板輸血、DIC評価(フィブリノゲン/Dダイマー)")
    if total >= 11:
        recs.append("集中治療専門医・緩和ケアチームとの目標設定協議")

    return SOFAResult(
        score=total,
        organ_scores=organs,
        interpretation=interp,
        mortality_estimate=mort,
        recommendations=recs,
    )


# ===========================================================================
# 3. NEWS2
# ===========================================================================

@dataclass
class NEWS2Result:
    score: int
    risk_category: str    # low / medium / high / clinical_emergency
    component_scores: dict[str, int]
    escalation_required: bool
    recommended_response: str
    monitoring_frequency: str


def calc_news2(
    *,
    rr: float = 16.0,           # /min
    spo2_pct: float = 97.0,     # SpO2 %
    on_supplemental_o2: bool = False,
    sbp_mmhg: float = 120.0,
    hr: float = 75.0,
    consciousness: str = "A",   # A=Alert, C=Confused, V=Voice, P=Pain, U=Unresponsive
    temperature_c: float = 36.5,
    # COPD / hypercapnic respiratory failure flag
    hypercapnic_respiratory_failure: bool = False,
) -> NEWS2Result:
    """NEWS2 (National Early Warning Score 2) calculation.

    Royal College of Physicians. National Early Warning Score (NEWS) 2. 2017.

    SpO2 scale 1 for normal patients, scale 2 for confirmed/risk hypercapnic RF.
    Total 0-20; ≥5 overall or ≥3 in single parameter triggers escalation.
    """
    comp: dict[str, int] = {}

    # -- RR --
    comp["rr"] = _score_table(rr, [
        (25, 999, 3), (21, 24, 2), (18, 20, 0), (15, 17, 1),
        (12, 14, 0), (9, 11, 1), (-999, 8, 3),
    ])

    # -- SpO2 (scale 1 default; scale 2 for hypercapnic RF) --
    if hypercapnic_respiratory_failure:
        # Scale 2: target 88-92%
        spo2 = spo2_pct
        if spo2 >= 97:
            comp["spo2"] = 3  # too high → possible O2 toxicity risk
        elif spo2 >= 95:
            comp["spo2"] = 2
        elif spo2 >= 93:
            comp["spo2"] = 1
        elif spo2 >= 88:
            comp["spo2"] = 0
        elif spo2 >= 86:
            comp["spo2"] = 1
        elif spo2 >= 84:
            comp["spo2"] = 2
        else:
            comp["spo2"] = 3
    else:
        # Scale 1: normal
        spo2 = spo2_pct
        comp["spo2"] = _score_table(spo2, [
            (96, 999, 0), (94, 95, 1), (92, 93, 2), (-999, 91, 3),
        ])

    # -- Supplemental O2 --
    comp["supplemental_o2"] = 2 if on_supplemental_o2 else 0

    # -- Systolic BP --
    comp["sbp"] = _score_table(sbp_mmhg, [
        (220, 999, 3), (111, 219, 0), (101, 110, 1),
        (91, 100, 2), (-999, 90, 3),
    ])

    # -- HR --
    comp["hr"] = _score_table(hr, [
        (131, 999, 3), (111, 130, 2), (91, 110, 1), (51, 90, 0),
        (41, 50, 1), (-999, 40, 3),
    ])

    # -- Level of consciousness (ACVPU) --
    avpu_score = {"A": 0, "C": 3, "V": 3, "P": 3, "U": 3}
    comp["avpu"] = avpu_score.get(consciousness.upper(), 3)

    # -- Temperature --
    comp["temperature"] = _score_table(temperature_c, [
        (39.1, 999, 2), (38.1, 39.0, 1), (36.1, 38.0, 0),
        (35.1, 36.0, 1), (-999, 35.0, 3),
    ])

    total = sum(comp.values())
    max_single = max(comp.values())

    # Risk category and escalation
    if total >= 7 or (max_single >= 3 and total >= 5):
        risk = "clinical_emergency"
        escalate = True
        response = "即時: 院内緊急チーム(RRT/MET)召集 — 持続モニタリング"
        freq = "継続モニタリング（持続）"
    elif total >= 5 or max_single == 3:
        risk = "high"
        escalate = True
        response = "緊急: 担当医・上級医への即時報告 — 30分以内評価"
        freq = "30分毎"
    elif total >= 1:
        risk = "medium"
        escalate = False
        response = "観察強化: 看護師による頻回観察・医師への連絡検討"
        freq = "1時間毎"
    else:
        risk = "low"
        escalate = False
        response = "通常ケア継続"
        freq = "4-6時間毎"

    # Override for single parameter ≥3
    if max_single >= 3 and risk == "medium":
        risk = "high"
        escalate = True
        response = "単一パラメータ3点: 担当医への即時連絡"
        freq = "30分毎"

    return NEWS2Result(
        score=total,
        risk_category=risk,
        component_scores=comp,
        escalation_required=escalate,
        recommended_response=response,
        monitoring_frequency=freq,
    )


# ===========================================================================
# 4. GRACE Score (ACS Risk)
# ===========================================================================

@dataclass
class GRACEResult:
    score: int
    in_hospital_mortality_pct: float
    sixmonth_mortality_pct: float
    risk_category: str    # low / intermediate / high
    component_scores: dict[str, int]
    recommendations: list[str]


def calc_grace(
    *,
    age: int = 60,
    hr: float = 80.0,
    sbp_mmhg: float = 130.0,
    cr_mg_dl: float = 1.0,
    cardiac_arrest_at_admission: bool = False,
    st_deviation: bool = False,
    elevated_cardiac_enzymes: bool = False,
    killip_class: int = 1,      # 1-4
) -> GRACEResult:
    """GRACE score for ACS in-hospital and 6-month MACE risk.

    Fox KAA et al. Prediction of risk of death and myocardial infarction in the
    six months after presentation with ACS. BMJ 2006;333:1091.

    Simplified GRACE 2.0 approximation using published lookup tables.
    """
    comp: dict[str, int] = {}

    # Age
    comp["age"] = _score_table(float(age), [
        (-999, 29, 0), (30, 39, 8), (40, 49, 25), (50, 59, 41),
        (60, 69, 58), (70, 79, 75), (80, 89, 91), (90, 999, 100),
    ])

    # HR (bpm)
    comp["hr"] = _score_table(hr, [
        (-999, 49, 0), (50, 69, 3), (70, 89, 9), (90, 109, 15),
        (110, 149, 24), (150, 199, 38), (200, 999, 46),
    ])

    # SBP (mmHg)
    comp["sbp"] = _score_table(sbp_mmhg, [
        (-999, 79, 58), (80, 99, 53), (100, 119, 43), (120, 139, 34),
        (140, 159, 24), (160, 199, 10), (200, 999, 0),
    ])

    # Creatinine
    comp["cr"] = _score_table(cr_mg_dl, [
        (-999, 0.39, 1), (0.40, 0.79, 4), (0.80, 1.19, 7),
        (1.20, 1.59, 10), (1.60, 1.99, 13), (2.00, 3.99, 21),
        (4.00, 999, 28),
    ])

    # Killip class
    killip_pts = {1: 0, 2: 20, 3: 39, 4: 59}
    comp["killip"] = killip_pts.get(int(_clamp(killip_class, 1, 4)), 0)

    # Other binary variables
    comp["cardiac_arrest"] = 39 if cardiac_arrest_at_admission else 0
    comp["st_deviation"] = 28 if st_deviation else 0
    comp["cardiac_enzymes"] = 14 if elevated_cardiac_enzymes else 0

    total = sum(comp.values())

    # In-hospital mortality (from GRACE lookup table approximation)
    # Logistic: P = 1/(1+exp(-(-7.43 + 0.028*score)))  (approximation)
    log_odds_inh = -7.43 + 0.028 * total
    ih_mort = round(100.0 / (1.0 + math.exp(-log_odds_inh)), 1)

    # 6-month mortality approximation (higher)
    log_odds_6m = -6.5 + 0.025 * total
    sixm_mort = round(100.0 / (1.0 + math.exp(-log_odds_6m)), 1)

    # Risk categories (GRACE 2.0)
    if total < 109:
        risk = "low"
    elif total <= 140:
        risk = "intermediate"
    else:
        risk = "high"

    recs: list[str] = [
        "12誘導心電図・連続モニタリング",
        "Tn(I or T)初回・3時間・6時間後測定",
        "アスピリン + P2Y12阻害薬(DAPT)開始",
    ]
    if risk == "high" or st_deviation:
        recs += [
            "早期侵襲的戦略: 24時間以内に冠動脈造影(PCI/CABG検討)",
            "抗凝固療法: UFH / エノキサパリン / ビバリルジン",
        ]
    if risk == "intermediate":
        recs.append("72時間以内に侵襲的評価検討")
    if killip_class >= 3:
        recs.append("心原性ショック対応: 大動脈内バルーンパンピング(IABP)評価")

    return GRACEResult(
        score=total,
        in_hospital_mortality_pct=ih_mort,
        sixmonth_mortality_pct=sixm_mort,
        risk_category=risk,
        component_scores=comp,
        recommendations=recs,
    )


# ===========================================================================
# 5. MELD / MELD-Na Score
# ===========================================================================

@dataclass
class MELDResult:
    meld_score: int
    meld_na_score: int
    three_month_mortality_pct: float
    priority_category: str    # UNOS listing priority
    recommendations: list[str]


def calc_meld(
    *,
    cr_mg_dl: float = 1.0,
    bilirubin_mg_dl: float = 1.0,
    inr: float = 1.0,
    sodium_meq: float = 140.0,     # for MELD-Na
    on_dialysis: bool = False,     # if dialysis twice/week → Cr = 4.0
) -> MELDResult:
    """MELD and MELD-Na score calculation for liver transplant listing.

    MELD    = 10 × (0.957×ln(Cr) + 0.378×ln(Bili) + 1.12×ln(INR)) + 0.643
    MELD-Na = MELD - Na - (0.025×MELD×(140-Na)) + 140

    Kamath PS et al. A model to predict survival in patients with end-stage
    liver disease. Hepatology 2001;33(2):464-70.
    """
    # Dialysis → Cr set to 4.0
    cr = 4.0 if on_dialysis else cr_mg_dl

    # Floor all values at 1.0 (per UNOS policy)
    cr_val = max(1.0, min(cr, 4.0))
    bili_val = max(1.0, bilirubin_mg_dl)
    inr_val = max(1.0, inr)

    raw_meld = (
        10 * (0.957 * math.log(cr_val)
              + 0.378 * math.log(bili_val)
              + 1.12 * math.log(inr_val))
        + 0.643
    )
    meld = round(raw_meld)

    # MELD-Na correction
    # Na bounded 125-137
    na = max(125.0, min(137.0, sodium_meq))
    meld_na = round(meld - na - (0.025 * meld * (140 - na)) + 140)

    # 3-month mortality estimate (Kim WR, 2008 approximation)
    if meld < 9:
        mort3m = 1.9
        priority = "UNOS status 1B (stable)"
    elif meld < 15:
        mort3m = 6.0
        priority = "UNOS status 1B (待機リスト)"
    elif meld < 20:
        mort3m = 19.6
        priority = "UNOS status 1A (優先待機)"
    elif meld < 30:
        mort3m = 52.6
        priority = "UNOS 上位優先 — 緊急肝移植評価"
    else:
        mort3m = 71.3
        priority = "UNOS 最高優先 — ICU管理・肝移植緊急検討"

    recs: list[str] = ["3-6ヶ月毎のMELD再計算 — 待機順位更新"]
    if meld >= 15:
        recs += [
            "肝移植センターへの紹介",
            "肝腎症候群・自発性細菌性腹膜炎予防（ノルフロキサシン）",
        ]
    if meld >= 25:
        recs += [
            "ICU入室 — 肝性脳症管理(リファキシミン/ラクツロース)",
            "TIPS(経頸静脈的肝内門脈短絡術)適応評価",
        ]
    if sodium_meq < 130:
        recs.append(f"低Na血症({sodium_meq:.0f} mEq/L): 水制限・トルバプタン検討")
    if on_dialysis:
        recs.append("透析中: 腎移植同時施行の検討(SLKT)")

    return MELDResult(
        meld_score=meld,
        meld_na_score=meld_na,
        three_month_mortality_pct=mort3m,
        priority_category=priority,
        recommendations=recs,
    )


# ===========================================================================
# __main__ — smoke tests
# ===========================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("1. APACHE II")
    print("=" * 60)
    ap = calc_apache_ii(
        temperature_c=38.5, map_mmhg=65.0, hr=120, rr=28,
        fio2=0.5, pao2_mmhg=70, ph=7.32, na_meq=148, k_meq=5.8,
        cr_mg_dl=2.1, hct_pct=28, wbc_k=18, gcs=12,
        age=68, nonoperative_emergency_postop=True,
    )
    print(f"APACHE II score    : {ap.score}")
    print(f"APS / Age / Chronic: {ap.aps_score} / {ap.age_score} / {ap.chronic_health_score}")
    print(f"Predicted mortality: {ap.predicted_mortality_pct}%")
    print(f"Interpretation     : {ap.interpretation}")

    print("\n" + "=" * 60)
    print("2. SOFA")
    print("=" * 60)
    sf = calc_sofa(
        pao2_fio2=180, on_respiratory_support=True,
        platelets_k=80, bilirubin_mg_dl=3.5,
        map_mmhg=60, vasopressor="dopa_mid",
        gcs=10, cr_mg_dl=3.2,
    )
    print(f"SOFA total : {sf.score}")
    print(f"Organs     : {sf.organ_scores}")
    print(f"Mortality  : {sf.mortality_estimate}")
    print(f"Interpretation: {sf.interpretation}")

    print("\n" + "=" * 60)
    print("3. NEWS2")
    print("=" * 60)
    nw = calc_news2(
        rr=26, spo2_pct=92, on_supplemental_o2=True,
        sbp_mmhg=95, hr=115, consciousness="C", temperature_c=38.9,
    )
    print(f"NEWS2 score    : {nw.score}")
    print(f"Risk category  : {nw.risk_category}")
    print(f"Escalation     : {nw.escalation_required}")
    print(f"Response       : {nw.recommended_response}")
    print(f"Components     : {nw.component_scores}")

    print("\n" + "=" * 60)
    print("4. GRACE")
    print("=" * 60)
    gr = calc_grace(
        age=72, hr=105, sbp_mmhg=95, cr_mg_dl=1.8,
        cardiac_arrest_at_admission=False, st_deviation=True,
        elevated_cardiac_enzymes=True, killip_class=2,
    )
    print(f"GRACE score       : {gr.score}")
    print(f"In-hospital mort  : {gr.in_hospital_mortality_pct}%")
    print(f"6-month mort      : {gr.sixmonth_mortality_pct}%")
    print(f"Risk              : {gr.risk_category}")

    print("\n" + "=" * 60)
    print("5. MELD / MELD-Na")
    print("=" * 60)
    ml = calc_meld(cr_mg_dl=2.8, bilirubin_mg_dl=5.2, inr=2.1, sodium_meq=128)
    print(f"MELD    : {ml.meld_score}")
    print(f"MELD-Na : {ml.meld_na_score}")
    print(f"3-month mortality: {ml.three_month_mortality_pct}%")
    print(f"Priority: {ml.priority_category}")
    print(f"Recs: {ml.recommendations}")
