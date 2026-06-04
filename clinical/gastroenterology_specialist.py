"""
Gastroenterology specialist clinical tools.

Includes:
  - Upper GI Bleed risk (Blatchford / Rockall scoring)
  - Hepatic encephalopathy grading (West Haven)
  - Child-Pugh score (liver cirrhosis severity)
  - Acute pancreatitis severity (Revised Atlanta + BISAP)
  - IBS vs IBD differential
"""

from dataclasses import dataclass, field
from typing import Optional


# ---------------------------------------------------------------------------
# Upper GI Bleed Risk: Blatchford + Rockall
# ---------------------------------------------------------------------------

@dataclass
class BlatchfordResult:
    score: int
    low_risk: bool          # True if score == 0 (safe for outpatient)
    risk_level: str         # low / moderate / high
    interpretation: str
    management: list[str]


def calc_blatchford(
    bun_mmol: float,        # Blood urea nitrogen in mmol/L  (÷ 2.8 to get mg/dL)
    hb_g_dl: float,
    systolic_bp: int,
    heart_rate: int,
    presentation: list[str],  # e.g. ["melena", "syncope", "hepatic_disease", "cardiac_failure"]
    sex: str = "male",        # "male" | "female"
) -> BlatchfordResult:
    """
    Glasgow-Blatchford Bleeding Score (GBS).
    Score 0 → low risk, can consider outpatient management.
    Score ≥ 1 → hospital admission.
    """
    score = 0

    # BUN (mmol/L)
    if bun_mmol >= 25:
        score += 6
    elif bun_mmol >= 10:
        score += 4
    elif bun_mmol >= 8:
        score += 3
    elif bun_mmol >= 6.5:
        score += 2

    # Haemoglobin
    if sex == "male":
        if hb_g_dl < 10:
            score += 6
        elif hb_g_dl < 12:
            score += 3
        elif hb_g_dl < 13:
            score += 1
    else:
        if hb_g_dl < 10:
            score += 6
        elif hb_g_dl < 12:
            score += 1

    # Systolic BP
    if systolic_bp < 90:
        score += 3
    elif systolic_bp < 100:
        score += 2
    elif systolic_bp < 110:
        score += 1

    # Heart rate
    if heart_rate >= 100:
        score += 1

    # Presentation features
    pres = set(p.lower() for p in presentation)
    if "melena" in pres:
        score += 1
    if "syncope" in pres:
        score += 2
    if "hepatic_disease" in pres or "liver_disease" in pres:
        score += 2
    if "cardiac_failure" in pres or "heart_failure" in pres:
        score += 2

    low_risk = score == 0
    if score == 0:
        risk_level = "low"
        interp = "低リスク(GBS=0): 外来管理を検討可"
        mgmt = ["外来での経過観察", "PPI投与", "次回外来での内視鏡予約"]
    elif score <= 2:
        risk_level = "moderate"
        interp = f"中等度リスク(GBS={score}): 早期内視鏡が推奨"
        mgmt = ["入院管理", "PPI持続静注", "24時間以内に上部内視鏡"]
    else:
        risk_level = "high"
        interp = f"高リスク(GBS={score}): 緊急対応が必要"
        mgmt = ["緊急入院・ICU管理", "輸液蘇生", "PPI大量静注", "緊急内視鏡(<12時間)", "輸血準備(Hb<8を目標)"]

    return BlatchfordResult(score=score, low_risk=low_risk, risk_level=risk_level,
                            interpretation=interp, management=mgmt)


@dataclass
class RockallResult:
    pre_endoscopy_score: int
    full_score: Optional[int]   # None if endoscopy data not provided
    rebleed_risk_pct: Optional[float]
    mortality_risk_pct: Optional[float]
    interpretation: str


def calc_rockall(
    age: int,
    shock: str,              # "none" | "tachycardia" | "hypotension"
    comorbidities: list[str],  # e.g. ["ischemic_heart_disease", "renal_failure", "malignancy"]
    endoscopy_diagnosis: Optional[str] = None,   # "mallory_weiss" | "peptic_ulcer" | "malignancy" | "none_found"
    stigmata_recent_hemorrhage: Optional[str] = None,  # "none" | "dark_spots" | "clot_vessel_blood"
) -> RockallResult:
    """
    Rockall Risk Scoring for Upper GI Bleeding.
    Pre-endoscopy score ≤ 2 → low risk.
    """
    score = 0

    # Age
    if age >= 80:
        score += 3
    elif age >= 60:
        score += 2
    elif age >= 0:
        score += 0

    # Shock
    shock_map = {"none": 0, "tachycardia": 1, "hypotension": 2}
    score += shock_map.get(shock.lower(), 0)

    # Comorbidity
    comor = set(c.lower() for c in comorbidities)
    if any(k in comor for k in ["renal_failure", "liver_failure", "disseminated_malignancy"]):
        score += 3
    elif any(k in comor for k in ["ischemic_heart_disease", "heart_failure", "major_comorbidity"]):
        score += 2

    pre_endo = score

    # Endoscopy component (if available)
    if endoscopy_diagnosis is not None:
        diag_map = {
            "mallory_weiss": 0, "none_found": 0,
            "peptic_ulcer": 1, "esophagitis": 1,
            "malignancy": 2, "upper_gi_cancer": 2,
        }
        score += diag_map.get(endoscopy_diagnosis.lower(), 1)

    if stigmata_recent_hemorrhage is not None:
        stig_map = {
            "none": 0, "dark_spots": 1,
            "clot_vessel_blood": 2, "active_bleeding": 2,
        }
        score += stig_map.get(stigmata_recent_hemorrhage.lower(), 0)

    full = score if endoscopy_diagnosis is not None else None

    # Risk estimates (approximate from original Rockall paper)
    rebleed_table = {0: 4.9, 1: 3.4, 2: 5.3, 3: 11.2, 4: 14.1, 5: 24.1, 6: 32.9, 7: 43.8, 8: 41.8}
    mort_table = {0: 0.0, 1: 0.0, 2: 0.2, 3: 2.9, 4: 5.3, 5: 10.8, 6: 17.3, 7: 27.0, 8: 41.1}

    s = full if full is not None else pre_endo
    rebleed = rebleed_table.get(min(s, 8), 41.8)
    mort = mort_table.get(min(s, 8), 41.1)

    if pre_endo <= 2:
        interp = f"低リスク(pre-endo={pre_endo}): 早期退院を検討可"
    elif pre_endo <= 4:
        interp = f"中等度リスク(score={s}): 内視鏡的止血 + 入院管理"
    else:
        interp = f"高リスク(score={s}): 積極的内視鏡治療 + ICU管理"

    return RockallResult(
        pre_endoscopy_score=pre_endo,
        full_score=full,
        rebleed_risk_pct=rebleed,
        mortality_risk_pct=mort,
        interpretation=interp,
    )


# ---------------------------------------------------------------------------
# Hepatic Encephalopathy: West Haven Criteria
# ---------------------------------------------------------------------------

@dataclass
class HEGrading:
    grade: int              # 0-4
    description: str
    symptoms: list[str]
    triggers: list[str]
    management: list[str]


_WH_GRADES = {
    0: ("Grade 0 (Covert HE / MHE)", ["精神測定検査で軽微な変化", "日常生活に支障なし"], []),
    1: ("Grade 1", ["軽度の混乱", "注意力低下", "睡眠覚醒リズム異常", "多幸または不安"], []),
    2: ("Grade 2", ["傾眠・昼夜逆転", "中等度の見当識障害", "羽ばたき振戦(asterixis)", "不適切な行動"], []),
    3: ("Grade 3", ["高度の傾眠・昏迷", "重篤な混乱", "指示に従えるが鎮静様態"], []),
    4: ("Grade 4 (Coma)", ["昏睡", "疼痛刺激にも無反応"], []),
}

_COMMON_TRIGGERS = [
    "消化管出血", "感染症(SBP/肺炎)", "便秘", "脱水・利尿薬過剰",
    "ベンゾジアゼピン系薬剤", "タンパク質過剰摂取", "腎不全",
    "電解質異常(低K/低Na)", "門脈血栓", "シャント手術",
]


def grade_hepatic_encephalopathy(
    confusion: bool = False,
    drowsiness: bool = False,
    stupor: bool = False,
    coma: bool = False,
    asterixis: bool = False,
    disorientation: bool = False,
    sleep_disturbance: bool = False,
    covert_only: bool = False,
    suspected_triggers: Optional[list[str]] = None,
) -> HEGrading:
    """
    West Haven Criteria grading for hepatic encephalopathy.
    Returns grade 0-4 with trigger identification and management.
    """
    if coma:
        grade = 4
    elif stupor:
        grade = 3
    elif drowsiness and (asterixis or disorientation):
        grade = 2
    elif confusion or sleep_disturbance or asterixis:
        grade = 1
    else:
        grade = 0

    desc, symptoms, _ = _WH_GRADES[grade]

    # Identify likely triggers
    detected_triggers = suspected_triggers or []
    if not detected_triggers:
        detected_triggers = ["未同定 — 下記の一般的誘因を評価してください"]

    trigger_list = detected_triggers + [f"一般的誘因: {t}" for t in _COMMON_TRIGGERS[:5]]

    mgmt_map = {
        0: ["MHEの場合ラクツロース/リファキシミン検討", "定期的な神経心理検査"],
        1: ["ラクツロース(排便2-3回/日を目標)", "誘因除去", "タンパク質制限は原則不要"],
        2: ["ラクツロース経口または浣腸", "リファキシミン550mg 1日2回", "誘因の積極的治療"],
        3: ["ICU管理", "気道確保検討", "ラクツロース浣腸", "誘因治療(抗生剤/止血)", "亜鉛補充"],
        4: ["ICU/挿管管理", "頭蓋内圧モニタリング検討", "肝移植評価", "N-アセチルシステイン"],
    }

    return HEGrading(
        grade=grade,
        description=desc,
        symptoms=symptoms,
        triggers=trigger_list,
        management=mgmt_map[grade],
    )


# ---------------------------------------------------------------------------
# Child-Pugh Score
# ---------------------------------------------------------------------------

@dataclass
class ChildPughResult:
    score: int
    child_class: str          # A / B / C
    one_year_survival_pct: float
    two_year_survival_pct: float
    interpretation: str
    recommendations: list[str]


def calc_child_pugh(
    bilirubin_mg_dl: float,
    albumin_g_dl: float,
    inr: float,
    ascites: str,             # "none" | "mild" | "moderate_severe"
    encephalopathy_grade: int,  # 0 / 1-2 / 3-4
) -> ChildPughResult:
    """
    Child-Pugh score for liver cirrhosis severity.
    Class A (5-6): well-compensated, Class B (7-9): significant compromise,
    Class C (10-15): decompensated cirrhosis.
    """
    score = 0

    # Bilirubin
    if bilirubin_mg_dl < 2:
        score += 1
    elif bilirubin_mg_dl <= 3:
        score += 2
    else:
        score += 3

    # Albumin
    if albumin_g_dl > 3.5:
        score += 1
    elif albumin_g_dl >= 2.8:
        score += 2
    else:
        score += 3

    # INR
    if inr < 1.7:
        score += 1
    elif inr <= 2.2:
        score += 2
    else:
        score += 3

    # Ascites
    ascites_map = {"none": 1, "mild": 2, "moderate_severe": 3, "moderate": 2, "severe": 3}
    score += ascites_map.get(ascites.lower(), 2)

    # Encephalopathy
    if encephalopathy_grade == 0:
        score += 1
    elif encephalopathy_grade in (1, 2):
        score += 2
    else:
        score += 3

    if score <= 6:
        child_class = "A"
        surv1, surv2 = 100.0, 85.0
        interp = f"Child-Pugh Class A (score={score}): 代償性肝硬変"
        recs = ["定期的フォロー(6ヶ月毎)", "肝癌スクリーニング(US+AFP 6ヶ月毎)", "塩分制限"]
    elif score <= 9:
        child_class = "B"
        surv1, surv2 = 80.0, 60.0
        interp = f"Child-Pugh Class B (score={score}): 中等度代償不全"
        recs = ["肝移植評価を検討", "腹水管理(利尿薬)", "SBP予防(フルオロキノロン/ST合剤)", "食道静脈瘤スクリーニング"]
    else:
        child_class = "C"
        surv1, surv2 = 45.0, 35.0
        interp = f"Child-Pugh Class C (score={score}): 非代償性肝硬変"
        recs = ["緊急肝移植評価(MELD算出)", "ICU/専門施設転送", "大量腹水管理(アルブミン補充)", "腎機能保護(HRS予防)"]

    return ChildPughResult(
        score=score,
        child_class=child_class,
        one_year_survival_pct=surv1,
        two_year_survival_pct=surv2,
        interpretation=interp,
        recommendations=recs,
    )


# ---------------------------------------------------------------------------
# Acute Pancreatitis Severity: Revised Atlanta + BISAP
# ---------------------------------------------------------------------------

@dataclass
class PancreatitisSeverity:
    bisap_score: int
    bisap_risk: str             # low / moderate / high
    atlanta_severity: str       # mild / moderately_severe / severe
    local_complications: list[str]
    organ_failure: bool
    persistent_organ_failure: bool
    mortality_estimate_pct: float
    management: list[str]


def assess_pancreatitis(
    bun_mg_dl: float,
    mental_status_impaired: bool,
    sirs_criteria_met: int,     # number of SIRS criteria (0-4)
    age: int,
    pleural_effusion: bool,
    # Revised Atlanta local complications
    necrosis: bool = False,
    pseudocyst: bool = False,
    peripancreatic_fluid: bool = False,
    # Organ failure (Marshall score-based)
    respiratory_failure: bool = False,   # PaO2/FiO2 < 300
    renal_failure: bool = False,         # Cr > 1.9 mg/dL
    cardiovascular_failure: bool = False, # SBP < 90 despite resuscitation
    persistent_of_hours: int = 0,        # hours organ failure persisted
) -> PancreatitisSeverity:
    """
    BISAP score + Revised Atlanta Classification for acute pancreatitis.
    BISAP: BUN>25, Impaired mental status, SIRS≥2, Age>60, Pleural effusion.
    Atlanta severity: mild/moderately severe/severe.
    """
    # BISAP
    bisap = 0
    if bun_mg_dl > 25:
        bisap += 1
    if mental_status_impaired:
        bisap += 1
    if sirs_criteria_met >= 2:
        bisap += 1
    if age > 60:
        bisap += 1
    if pleural_effusion:
        bisap += 1

    if bisap <= 1:
        bisap_risk = "low"
        mort_est = 0.1
    elif bisap <= 2:
        bisap_risk = "moderate"
        mort_est = 2.0
    else:
        bisap_risk = "high"
        mort_est = 7.0 + (bisap - 3) * 5.0

    # Revised Atlanta
    organ_failure = respiratory_failure or renal_failure or cardiovascular_failure
    persistent_of = organ_failure and persistent_of_hours >= 48

    local_comps = []
    if necrosis:
        local_comps.append("膵壊死(necrotizing pancreatitis)")
    if pseudocyst:
        local_comps.append("膵仮性嚢胞")
    if peripancreatic_fluid:
        local_comps.append("膵周囲液体貯留")

    if persistent_of:
        atlanta = "severe"
        mgmt = ["ICU管理", "早期経腸栄養(48時間以内)", "感染性壊死の場合のみ抗生剤",
                "経皮的または内視鏡的ドレナージ検討", "外科コンサルト", "臓器不全サポート"]
    elif organ_failure or local_comps:
        atlanta = "moderately_severe"
        mgmt = ["入院管理(一般病棟〜準ICU)", "十分な輸液(初期はRinger乳酸液150-250mL/h)",
                "疼痛管理", "経腸栄養早期開始", "局所合併症の経過観察"]
    else:
        atlanta = "mild"
        mgmt = ["入院管理", "輸液補正", "絶食→経口再開は症状改善後", "疼痛管理(NSAIDs/オピオイド)"]

    return PancreatitisSeverity(
        bisap_score=bisap,
        bisap_risk=bisap_risk,
        atlanta_severity=atlanta,
        local_complications=local_comps,
        organ_failure=organ_failure,
        persistent_organ_failure=persistent_of,
        mortality_estimate_pct=mort_est,
        management=mgmt,
    )


# ---------------------------------------------------------------------------
# IBS vs IBD Differential
# ---------------------------------------------------------------------------

@dataclass
class IBSDifferential:
    ibs_likelihood: str         # low / moderate / high
    ibd_likelihood: str         # low / moderate / high
    ibs_lr: float               # likelihood ratio approximation
    ibd_lr: float
    key_features_for_ibs: list[str]
    key_features_for_ibd: list[str]
    recommended_workup: list[str]
    interpretation: str


def differentiate_ibs_ibd(
    age: int,
    blood_in_stool: bool,
    nocturnal_symptoms: bool,
    unintentional_weight_loss: bool,
    crp_elevated: bool,          # CRP > 0.5 mg/dL
    fecal_calprotectin_elevated: bool = False,  # > 50 µg/g
    family_history_ibd: bool = False,
    symptom_duration_weeks: int = 0,
    symptom_relieved_by_defecation: bool = False,
    bloating: bool = False,
    altered_stool_form: bool = False,  # Bristol 1-2 or 6-7
) -> IBSDifferential:
    """
    Differential between IBS (Rome IV) and IBD using clinical features.
    Returns likelihood ratios and recommended workup.
    """
    ibs_score = 0
    ibd_score = 0
    ibs_features = []
    ibd_features = []

    # Features favouring IBS
    if symptom_relieved_by_defecation:
        ibs_score += 2
        ibs_features.append("排便による症状改善(Rome IV基準)")
    if bloating:
        ibs_score += 1
        ibs_features.append("腹部膨満感")
    if altered_stool_form:
        ibs_score += 1
        ibs_features.append("便形状の変化(Bristol 1-2 or 6-7)")
    if not blood_in_stool and not nocturnal_symptoms:
        ibs_score += 2
        ibs_features.append("血便・夜間症状なし")
    if not crp_elevated and not fecal_calprotectin_elevated:
        ibs_score += 2
        ibs_features.append("炎症マーカー正常(CRP/便中カルプロテクチン)")
    if symptom_duration_weeks > 12:
        ibs_score += 1
        ibs_features.append("慢性経過(>12週間)")
    if age < 45 and not family_history_ibd:
        ibs_score += 1
        ibs_features.append("若年かつ家族歴なし")

    # Features favouring IBD
    if blood_in_stool:
        ibd_score += 4
        ibd_features.append("血便(感度82%: IBD)")
    if nocturnal_symptoms:
        ibd_score += 3
        ibd_features.append("夜間症状(IBDで有意)")
    if unintentional_weight_loss:
        ibd_score += 3
        ibd_features.append("体重減少")
    if crp_elevated:
        ibd_score += 3
        ibd_features.append("CRP上昇")
    if fecal_calprotectin_elevated:
        ibd_score += 4
        ibd_features.append("便中カルプロテクチン上昇(IBD感度80-90%)")
    if family_history_ibd:
        ibd_score += 2
        ibd_features.append("IBD家族歴")
    if age >= 45 and blood_in_stool:
        ibd_score += 1
        ibd_features.append("45歳以上 + 血便 → 大腸癌も除外要")

    total = ibs_score + ibd_score + 1
    ibs_lr = round((ibs_score + 1) / (ibd_score + 1), 2)
    ibd_lr = round((ibd_score + 1) / (ibs_score + 1), 2)

    if ibs_score > ibd_score * 2:
        ibs_like, ibd_like = "high", "low"
        interp = "IBS可能性が高い。Rome IV基準充足の場合、侵襲的検査より先に生活習慣指導・低FODMAP食を検討。"
    elif ibd_score > ibs_score * 2:
        ibs_like, ibd_like = "low", "high"
        interp = "IBD可能性が高い。大腸内視鏡 + 生検および血液炎症マーカー精査を優先。"
    else:
        ibs_like = ibd_like = "moderate"
        interp = "IBS/IBDの鑑別が困難。便中カルプロテクチン測定 + 大腸内視鏡を検討。"

    red_flag_workup = ["便中カルプロテクチン", "CRP/ESR", "CBC(貧血評価)", "大腸内視鏡 + 生検"]
    ibs_workup = ["Rome IV基準評価", "低FODMAP食試行", "腹部エコー(除外目的)"]
    workup = red_flag_workup if ibd_score >= ibs_score else ibs_workup

    return IBSDifferential(
        ibs_likelihood=ibs_like,
        ibd_likelihood=ibd_like,
        ibs_lr=ibs_lr,
        ibd_lr=ibd_lr,
        key_features_for_ibs=ibs_features,
        key_features_for_ibd=ibd_features,
        recommended_workup=workup,
        interpretation=interp,
    )


# ---------------------------------------------------------------------------
# __main__ demo
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("=" * 60)
    print("Blatchford Score Demo")
    print("=" * 60)
    bf = calc_blatchford(
        bun_mmol=12.0, hb_g_dl=9.5, systolic_bp=95, heart_rate=110,
        presentation=["melena", "syncope"], sex="male"
    )
    print(f"Score: {bf.score}, Low risk: {bf.low_risk}")
    print(f"Risk: {bf.risk_level}")
    print(f"Interpretation: {bf.interpretation}")
    print(f"Management: {bf.management}")

    print("\n" + "=" * 60)
    print("Rockall Score Demo")
    print("=" * 60)
    rk = calc_rockall(
        age=72, shock="tachycardia",
        comorbidities=["ischemic_heart_disease"],
        endoscopy_diagnosis="peptic_ulcer",
        stigmata_recent_hemorrhage="clot_vessel_blood",
    )
    print(f"Pre-endo: {rk.pre_endoscopy_score}, Full: {rk.full_score}")
    print(f"Rebleed risk: {rk.rebleed_risk_pct}%, Mortality: {rk.mortality_risk_pct}%")
    print(f"Interpretation: {rk.interpretation}")

    print("\n" + "=" * 60)
    print("Hepatic Encephalopathy Grading Demo")
    print("=" * 60)
    he = grade_hepatic_encephalopathy(
        drowsiness=True, asterixis=True, disorientation=True,
        suspected_triggers=["消化管出血", "利尿薬過剰投与"]
    )
    print(f"Grade: {he.grade} — {he.description}")
    print(f"Symptoms: {he.symptoms}")
    print(f"Triggers: {he.triggers[:3]}")
    print(f"Management: {he.management}")

    print("\n" + "=" * 60)
    print("Child-Pugh Score Demo")
    print("=" * 60)
    cp = calc_child_pugh(
        bilirubin_mg_dl=3.5, albumin_g_dl=2.6, inr=2.0,
        ascites="moderate_severe", encephalopathy_grade=2
    )
    print(f"Score: {cp.score}, Class: {cp.child_class}")
    print(f"1yr survival: {cp.one_year_survival_pct}%, 2yr: {cp.two_year_survival_pct}%")
    print(f"Interpretation: {cp.interpretation}")
    print(f"Recommendations: {cp.recommendations}")

    print("\n" + "=" * 60)
    print("Acute Pancreatitis Severity Demo")
    print("=" * 60)
    ap = assess_pancreatitis(
        bun_mg_dl=30, mental_status_impaired=False, sirs_criteria_met=3,
        age=65, pleural_effusion=True,
        necrosis=True, respiratory_failure=True, persistent_of_hours=60
    )
    print(f"BISAP: {ap.bisap_score} ({ap.bisap_risk})")
    print(f"Atlanta: {ap.atlanta_severity}")
    print(f"Local complications: {ap.local_complications}")
    print(f"Mortality estimate: {ap.mortality_estimate_pct}%")
    print(f"Management: {ap.management[:3]}")

    print("\n" + "=" * 60)
    print("IBS vs IBD Differential Demo")
    print("=" * 60)
    diff = differentiate_ibs_ibd(
        age=32, blood_in_stool=False, nocturnal_symptoms=False,
        unintentional_weight_loss=False, crp_elevated=False,
        fecal_calprotectin_elevated=False,
        symptom_relieved_by_defecation=True, bloating=True,
        altered_stool_form=True, symptom_duration_weeks=20,
    )
    print(f"IBS likelihood: {diff.ibs_likelihood} (LR={diff.ibs_lr})")
    print(f"IBD likelihood: {diff.ibd_likelihood} (LR={diff.ibd_lr})")
    print(f"Key IBS features: {diff.key_features_for_ibs}")
    print(f"Workup: {diff.recommended_workup}")
    print(f"Interpretation: {diff.interpretation}")
