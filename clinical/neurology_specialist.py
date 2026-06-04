"""
clinical/neurology_specialist.py — Neurology Decision Support

Implements:
  1. Stroke severity (NIHSS) + mRS outcome prediction
  2. tPA eligibility checklist (AHA 2023)
  3. Seizure classification (ILAE 2017)
  4. Headache RED FLAGS (SNOOP checklist)
  5. Dementia vs Delirium differential (CAM scoring)
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional


# ===========================================================================
# 1. NIHSS / mRS Stroke Severity
# ===========================================================================

@dataclass
class NIHSSResult:
    total_score: int
    severity: str
    mrs_predicted: int
    mrs_interpretation: str
    component_scores: dict[str, int]
    recommendations: list[str]


def calc_nihss(
    *,
    consciousness: int = 0,     # 1a: 0-3
    orientation: int = 0,       # 1b: 0-2
    commands: int = 0,          # 1c: 0-2
    gaze: int = 0,              # 2:  0-2
    visual: int = 0,            # 3:  0-3
    facial: int = 0,            # 4:  0-3
    motor_arm_left: int = 0,    # 5a: 0-4
    motor_arm_right: int = 0,   # 5b: 0-4
    motor_leg_left: int = 0,    # 6a: 0-4
    motor_leg_right: int = 0,   # 6b: 0-4
    ataxia: int = 0,            # 7:  0-2
    sensory: int = 0,           # 8:  0-2
    language: int = 0,          # 9:  0-3 (失語)
    dysarthria: int = 0,        # 10: 0-2
    extinction: int = 0,        # 11: 0-2
) -> NIHSSResult:
    """NIHSS (NIH Stroke Scale) を計算する.

    Parameters (各スコアの範囲と意味):
      consciousness  : 意識レベル 0=正常 1=傾眠 2=昏迷 3=昏睡
      orientation    : 見当識(2問) 0=2問正解 1=1問 2=0問
      commands       : 従命(2命令) 0=2命令可 1=1命令 2=不可
      gaze           : 眼球運動 0=正常 1=部分麻痺 2=完全偏視
      visual         : 視野 0=正常 1=部分欠損 2=完全半盲 3=両側盲
      facial         : 顔面麻痺 0=正常 1=軽度 2=部分 3=完全
      motor_arm_*    : 上肢運動 0=10s保持 1=drift 2=重力不能 3=動きのみ 4=無動
      motor_leg_*    : 下肢運動 0=5s保持 1=drift 2=重力不能 3=動きのみ 4=無動
      ataxia         : 協調運動 0=なし 1=1肢 2=2肢以上
      sensory        : 感覚 0=正常 1=軽度低下 2=重度低下/無感覚
      language       : 言語 0=正常 1=軽度失語 2=重度失語 3=無言/全失語
      dysarthria     : 構音 0=正常 1=軽度 2=重度/無言
      extinction     : 無視/消去 0=なし 1=1感覚 2=重度

    Returns NIHSSResult with score, severity, predicted mRS, recommendations.
    """
    components = {
        "1a_consciousness": _clamp(consciousness, 0, 3),
        "1b_orientation": _clamp(orientation, 0, 2),
        "1c_commands": _clamp(commands, 0, 2),
        "2_gaze": _clamp(gaze, 0, 2),
        "3_visual": _clamp(visual, 0, 3),
        "4_facial": _clamp(facial, 0, 3),
        "5a_arm_left": _clamp(motor_arm_left, 0, 4),
        "5b_arm_right": _clamp(motor_arm_right, 0, 4),
        "6a_leg_left": _clamp(motor_leg_left, 0, 4),
        "6b_leg_right": _clamp(motor_leg_right, 0, 4),
        "7_ataxia": _clamp(ataxia, 0, 2),
        "8_sensory": _clamp(sensory, 0, 2),
        "9_language": _clamp(language, 0, 3),
        "10_dysarthria": _clamp(dysarthria, 0, 2),
        "11_extinction": _clamp(extinction, 0, 2),
    }
    total = sum(components.values())

    # Severity classification
    if total == 0:
        severity = "正常 (No stroke symptoms)"
    elif total <= 4:
        severity = "軽微 (Minor stroke)"
    elif total <= 15:
        severity = "中等度 (Moderate stroke)"
    elif total <= 20:
        severity = "中等度重症 (Moderate-severe stroke)"
    else:
        severity = "重症 (Severe stroke)"

    # mRS prediction at 90 days (simplified Rankin)
    # Based on NIHSS: rough linear mapping with floor/ceiling
    if total <= 1:
        mrs = 0
        mrs_interp = "0: 症状なし — 完全回復見込み"
    elif total <= 4:
        mrs = 1
        mrs_interp = "1: 軽微な症状 — 日常生活ほぼ支障なし"
    elif total <= 9:
        mrs = 2
        mrs_interp = "2: 軽度障害 — 介助なしで日常生活可"
    elif total <= 14:
        mrs = 3
        mrs_interp = "3: 中等度障害 — 一部介助必要"
    elif total <= 19:
        mrs = 4
        mrs_interp = "4: 中等度重症障害 — 常時介助・自立歩行不可"
    elif total <= 24:
        mrs = 5
        mrs_interp = "5: 重症障害 — 完全介助・意識障害"
    else:
        mrs = 5
        mrs_interp = "5: 重症 — 全介護"

    recs: list[str] = [
        "脳卒中ユニット（SCU）または集中治療室への収容",
        "12誘導心電図、連続心電図モニタリング",
        "CT/MRI(DWI)の緊急施行",
        "血圧・血糖・体温管理",
    ]
    if total >= 4:
        recs.append("血栓溶解療法（tPA）適応評価")
    if total >= 10:
        recs.append("機械的血栓回収療法（EVT）適応評価（大血管閉塞疑い）")
    if total >= 16:
        recs.append("ICUモニタリング・脳浮腫対策（過換気・グリセロール）")

    return NIHSSResult(
        total_score=total,
        severity=severity,
        mrs_predicted=mrs,
        mrs_interpretation=mrs_interp,
        component_scores=components,
        recommendations=recs,
    )


def _clamp(val: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, int(val)))


# ===========================================================================
# 2. tPA Eligibility (AHA 2023)
# ===========================================================================

@dataclass
class TpaEligibility:
    eligible: bool
    dose_mg: float          # 0.9 mg/kg (max 90 mg) if eligible
    absolute_exclusions: list[str]
    relative_exclusions: list[str]
    notes: list[str]


def check_tpa_eligibility(
    *,
    ischemic_stroke: bool = True,
    nihss: int = 0,
    onset_hours: float = 0.0,
    age: int = 18,
    weight_kg: float = 70.0,
    hemorrhage_on_ct: bool = False,
    inr: float = 1.0,
    platelets_k: float = 200.0,     # 千/μL
    recent_major_surgery_days: int = 9999,   # days since last surgery
    recent_intracranial_surgery: bool = False,
    sbp: float = 140.0,
    dbp: float = 80.0,
    glucose: float = 100.0,         # mg/dL
    on_anticoagulant: bool = False,
    on_doac: bool = False,
    severe_stroke_nihss: int = 0,   # NIHSSが25超 → 相対禁忌
    prior_stroke_diabetes: bool = False,  # 相対禁忌
) -> TpaEligibility:
    """tPA適応判定 (AHA/ASA 2023ガイドライン準拠).

    Returns TpaEligibility with eligible flag and detailed exclusion list.
    """
    abs_excl: list[str] = []
    rel_excl: list[str] = []
    notes: list[str] = []

    # --- Absolute inclusions check ---
    if not ischemic_stroke:
        abs_excl.append("虚血性脳卒中ではない（出血性・その他）")
    if nihss < 4:
        notes.append(f"NIHSS {nihss} — 軽症(4未満)は個別判断（症状障害的であれば投与可）")
    if nihss > 25:
        abs_excl.append(f"NIHSS {nihss} > 25 — 重症すぎて転帰改善の見込み薄（絶対禁忌）")
    if onset_hours > 4.5:
        abs_excl.append(f"発症から{onset_hours:.1f}時間経過 — 4.5時間超は適応外")
    if age < 18:
        abs_excl.append(f"年齢{age}歳 — 18歳未満は適応外")

    # --- Absolute exclusions ---
    if hemorrhage_on_ct:
        abs_excl.append("CT上の頭蓋内出血 — 絶対禁忌")
    if inr > 1.7:
        abs_excl.append(f"INR {inr:.2f} > 1.7 — 経口抗凝固薬による凝固障害")
    if platelets_k < 100:
        abs_excl.append(f"血小板 {platelets_k:.0f}千/μL < 100千 — 血小板低下")
    if recent_intracranial_surgery:
        abs_excl.append("3ヶ月以内の頭蓋内手術・重篤な頭部外傷")
    if recent_major_surgery_days <= 14:
        abs_excl.append(f"{recent_major_surgery_days}日前の大手術（14日以内）")
    if on_doac:
        abs_excl.append("DOAC（直接経口抗凝固薬）服用中 — 最終服用48h以内は禁忌")

    # --- Relative exclusions ---
    if sbp > 185 or dbp > 110:
        rel_excl.append(f"血圧 {sbp:.0f}/{dbp:.0f} mmHg > 185/110 — 降圧後に再評価")
    if glucose < 50:
        rel_excl.append(f"血糖 {glucose:.0f} mg/dL < 50 — 低血糖補正後に再評価")
    if glucose > 400:
        rel_excl.append(f"血糖 {glucose:.0f} mg/dL > 400 — 高血糖は転帰不良と関連")
    if on_anticoagulant:
        rel_excl.append("ヘパリン/ワルファリン服用中（PTT/PT確認必要）")
    if prior_stroke_diabetes:
        rel_excl.append("脳卒中既往＋糖尿病合併 — 相対禁忌（個別判断）")
    if nihss > 22:
        rel_excl.append(f"NIHSS {nihss} > 22 — 重症（出血性変換リスク）")

    eligible = len(abs_excl) == 0

    # Dose calculation: 0.9 mg/kg max 90 mg
    if eligible:
        dose = round(min(0.9 * weight_kg, 90.0), 1)
        notes.append(f"推奨用量: {dose} mg (0.9 mg/kg, 最大90 mg)")
        notes.append("投与法: 10%をボーラス静注(1分)、残90%を60分で持続静注")
        notes.append("投与後24時間は抗血栓薬投与禁止")
    else:
        dose = 0.0

    return TpaEligibility(
        eligible=eligible,
        dose_mg=dose,
        absolute_exclusions=abs_excl,
        relative_exclusions=rel_excl,
        notes=notes,
    )


# ===========================================================================
# 3. Seizure Classification (ILAE 2017)
# ===========================================================================

@dataclass
class SeizureClassification:
    onset_type: str           # focal / generalized / unknown
    awareness: str            # preserved / impaired / unknown / n/a
    motor_features: list[str]
    non_motor_features: list[str]
    classification: str       # full ILAE label
    recommended_aed: list[str]
    notes: list[str]


def classify_seizure(
    *,
    focal: bool = False,
    generalized: bool = False,
    awareness_preserved: bool = True,
    # Motor features
    tonic_clonic: bool = False,
    tonic: bool = False,
    clonic: bool = False,
    myoclonic: bool = False,
    atonic: bool = False,
    epileptic_spasms: bool = False,
    automatisms: bool = False,
    # Non-motor features
    absence: bool = False,
    sensory: bool = False,
    autonomic: bool = False,
    cognitive: bool = False,
    emotional: bool = False,
    age_years: int = 30,
    prior_aed_failure: list[str] | None = None,
) -> SeizureClassification:
    """ILAE 2017分類に基づく発作分類と抗てんかん薬（AED）推奨.

    Parameters:
      focal / generalized : 発症様式(どちらか一方をTrueに)
      awareness_preserved : 焦点発作での意識保持(focal=Trueのとき有効)
      各種運動/非運動特徴 : 該当するものをTrueに
      age_years : 患者年齢
      prior_aed_failure : 過去に無効だったAEDリスト

    Returns SeizureClassification with ILAE label + AED recommendations.
    """
    prior_aed_failure = prior_aed_failure or []

    # Determine onset
    if focal and not generalized:
        onset = "focal"
    elif generalized and not focal:
        onset = "generalized"
    elif focal and generalized:
        onset = "focal_to_bilateral_tonic_clonic"
    else:
        onset = "unknown"

    # Build motor/non-motor feature lists
    motor: list[str] = []
    non_motor: list[str] = []
    if tonic_clonic:
        motor.append("強直間代")
    if tonic:
        motor.append("強直")
    if clonic:
        motor.append("間代")
    if myoclonic:
        motor.append("ミオクロニー")
    if atonic:
        motor.append("脱力（無緊張）")
    if epileptic_spasms:
        motor.append("てんかんスパズム")
    if automatisms:
        motor.append("自動症")
    if absence:
        non_motor.append("欠神")
    if sensory:
        non_motor.append("感覚")
    if autonomic:
        non_motor.append("自律神経")
    if cognitive:
        non_motor.append("認知")
    if emotional:
        non_motor.append("情動")

    # ILAE classification label
    if onset == "focal":
        awareness_label = "意識保持" if awareness_preserved else "意識障害"
        if motor:
            feat = motor[0]
            label = f"焦点発作 {awareness_label}型 運動症状（{feat}）"
        elif non_motor:
            feat = non_motor[0]
            label = f"焦点発作 {awareness_label}型 非運動症状（{feat}）"
        elif not motor and not non_motor:
            label = f"焦点発作 {awareness_label}型（分類不能）"
        else:
            label = f"焦点発作 {awareness_label}型"
    elif onset == "generalized":
        if tonic_clonic:
            label = "全般強直間代発作（GTCS）"
        elif absence:
            label = "欠神発作（小発作）"
        elif myoclonic:
            label = "ミオクロニー発作"
        elif atonic:
            label = "脱力発作（無緊張発作）"
        elif tonic:
            label = "強直発作"
        elif clonic:
            label = "間代発作"
        elif epileptic_spasms:
            label = "てんかんスパズム"
        else:
            label = "全般発作（詳細不明）"
    elif onset == "focal_to_bilateral_tonic_clonic":
        label = "焦点起始両側強直間代発作（旧: 二次性全般化）"
    else:
        label = "分類不能発作"

    # AED recommendations
    aed = _recommend_aed(
        onset=onset,
        tonic_clonic=tonic_clonic,
        absence=absence,
        myoclonic=myoclonic,
        age_years=age_years,
        prior_failure=prior_aed_failure,
    )

    notes: list[str] = []
    if onset in ("focal", "focal_to_bilateral_tonic_clonic"):
        notes.append("MRI（海馬含む）・EEG（長時間）を施行し、焦点原因を検索")
    if onset == "generalized":
        notes.append("EEGで全般性棘徐波複合を確認。光過敏性検索も")
    if onset == "unknown":
        notes.append("発作目撃者証言・長時間ビデオEEGで発症様式の確定を")

    awareness_out = ("preserved" if awareness_preserved else "impaired") if focal else "n/a"

    return SeizureClassification(
        onset_type=onset,
        awareness=awareness_out,
        motor_features=motor,
        non_motor_features=non_motor,
        classification=label,
        recommended_aed=aed,
        notes=notes,
    )


def _recommend_aed(
    onset: str, tonic_clonic: bool, absence: bool, myoclonic: bool,
    age_years: int, prior_failure: list[str],
) -> list[str]:
    """First/second-line AED recommendation based on seizure type."""
    base: list[str] = []
    if onset in ("focal", "focal_to_bilateral_tonic_clonic"):
        base = ["レベチラセタム(LEV)", "ラモトリギン(LTG)", "カルバマゼピン(CBZ)"]
    elif absence:
        base = ["バルプロ酸(VPA)", "エトスクシミド(ESM)", "ラモトリギン(LTG)"]
    elif myoclonic:
        base = ["バルプロ酸(VPA)", "レベチラセタム(LEV)", "クロナゼパム(CZP)"]
    elif tonic_clonic:
        base = ["バルプロ酸(VPA)", "レベチラセタム(LEV)", "ラモトリギン(LTG)"]
    else:
        base = ["レベチラセタム(LEV)", "バルプロ酸(VPA)"]

    # Remove prior failures
    filtered = [a for a in base if not any(f.upper() in a.upper() for f in prior_failure)]
    if not filtered:
        filtered = ["専門医（てんかん専門医）へ紹介 — 難治性てんかん評価"]
    return filtered


# ===========================================================================
# 4. Headache RED FLAGS (SNOOP Checklist)
# ===========================================================================

@dataclass
class HeadacheRedFlagResult:
    red_flags: list[str]
    snoop_items: dict[str, bool]
    urgency: str          # "immediate" / "urgent" / "routine"
    workup: list[str]
    notes: list[str]


def screen_headache_red_flags(
    *,
    # S — Systemic
    fever: bool = False,
    weight_loss: bool = False,
    hiv_cancer: bool = False,
    # N — Neurologic
    neuro_signs: bool = False,     # focal deficits, papilledema
    confusion: bool = False,
    # O — Onset sudden
    thunderclap: bool = False,     # worst headache of life / <1min to peak
    # O2 — Older onset
    age_over_50_new: bool = False,  # new headache after age 50
    # P — Progressive / postural / positional / prior similar
    progressive: bool = False,
    postural: bool = False,        # worse when lying down (ICP)
    # P2 — Prior pattern change
    prior_pattern_change: bool = False,
    # Exertion / Valsalva
    exertional: bool = False,
    # Additional
    trauma: bool = False,
    pregnancy_postpartum: bool = False,
    immunosuppressed: bool = False,
) -> HeadacheRedFlagResult:
    """SNOOP/SNOOP4 頭痛危険徴候スクリーニング.

    Returns red flags list, urgency level, and recommended workup.
    """
    snoop = {
        "S_全身症状(発熱/体重減少)": fever or weight_loss,
        "S_HIV/悪性腫瘍既往": hiv_cancer,
        "N_神経学的徴候": neuro_signs,
        "N_意識障害・混乱": confusion,
        "O_突然発症(雷鳴頭痛)": thunderclap,
        "O_50歳以上の新規頭痛": age_over_50_new,
        "P_進行性増悪": progressive,
        "P_起立性(頭蓋内圧亢進疑い)": postural,
        "P_従来パターン変化": prior_pattern_change,
        "P_労作時・バルサルバ誘発": exertional,
        "外傷後頭痛": trauma,
        "妊娠・産褥期": pregnancy_postpartum,
        "免疫抑制状態": immunosuppressed,
    }

    flags = [k for k, v in snoop.items() if v]

    # Workup recommendations
    workup: list[str] = []
    if thunderclap or neuro_signs or confusion:
        workup += ["頭部CT(非造影) — くも膜下出血除外", "腰椎穿刺(CT陰性でも疑う場合)"]
    if fever or hiv_cancer or immunosuppressed:
        workup += ["頭部MRI+造影", "腰椎穿刺(髄液検査) — 髄膜炎/脳炎"]
    if age_over_50_new or progressive:
        workup += ["頭部MRI+造影 — 脳腫瘍/硬膜下血腫除外", "側頭動脈生検(巨細胞性動脈炎疑い)"]
    if exertional or postural:
        workup += ["頭部MRI(FLAIR/DWI)", "脊髄MRI — 低髄液圧症候群除外"]
    if pregnancy_postpartum:
        workup += ["頭部MRI+MRV — 脳静脈洞血栓症除外", "血圧管理・子癇前症評価"]
    if trauma:
        workup += ["頭部CT — 硬膜外/硬膜下血腫除外"]

    # Remove duplicates preserving order
    seen: set[str] = set()
    workup = [w for w in workup if not (w in seen or seen.add(w))]  # type: ignore[func-returns-value]

    # Urgency
    immediate_flags = {thunderclap, neuro_signs, confusion, fever and (hiv_cancer or immunosuppressed)}
    if any(immediate_flags) or (fever and neuro_signs):
        urgency = "immediate"     # 即時対応（救急）
    elif flags:
        urgency = "urgent"        # 当日〜翌日対応
    else:
        urgency = "routine"       # 外来フォロー可

    notes: list[str] = []
    if not flags:
        notes.append("SNOOP危険徴候なし — 片頭痛・緊張型頭痛を考慮。IHS基準で診断")
    if thunderclap:
        notes.append("雷鳴頭痛: くも膜下出血の除外が最優先。CT陰性でも6時間以内は腰椎穿刺")
    if age_over_50_new:
        notes.append("50歳以降の新規頭痛: 巨細胞性動脈炎(CRP/ESR)・脳腫瘍のスクリーニング")

    return HeadacheRedFlagResult(
        red_flags=flags,
        snoop_items=snoop,
        urgency=urgency,
        workup=workup,
        notes=notes,
    )


# ===========================================================================
# 5. Dementia vs Delirium Differential (CAM scoring)
# ===========================================================================

@dataclass
class DeliriumAssessment:
    cam_positive: bool
    cam_components: dict[str, bool]
    likely_diagnosis: str     # "delirium" / "dementia" / "both" / "neither"
    key_differentiators: dict[str, str]
    immediate_actions: list[str]
    reversible_causes: list[str]


def assess_delirium_dementia(
    *,
    # CAM (Confusion Assessment Method) components
    acute_onset: bool = False,          # 1. 急性発症かつ変動する経過
    fluctuating_course: bool = False,   # (1とセット)
    inattention: bool = False,          # 2. 注意障害（必須）
    disorganized_thinking: bool = False, # 3. 支離滅裂な思考
    altered_consciousness: bool = False,  # 4. 意識レベル変容
    # Dementia features
    gradual_onset: bool = False,        # 緩徐発症
    memory_predominant: bool = False,   # 記憶障害が主体
    progressive_months: bool = False,   # 数ヶ月〜年単位の進行
    # Additional context
    age: int = 70,
    hospitalized: bool = False,
    known_dementia: bool = False,
    # Potential delirium precipitants
    recent_infection: bool = False,
    new_medication: bool = False,
    metabolic_abnormality: bool = False,
    urinary_retention: bool = False,
    pain_uncontrolled: bool = False,
    sleep_deprivation: bool = False,
) -> DeliriumAssessment:
    """CAMスコアリングと認知症/せん妄の鑑別診断.

    CAM陽性条件: 1(急性・変動) + 2(注意障害) + (3 or 4)
    """
    cam_components = {
        "1_急性発症・変動する経過": acute_onset and fluctuating_course,
        "2_注意障害（必須）": inattention,
        "3_支離滅裂な思考": disorganized_thinking,
        "4_意識レベル変容": altered_consciousness,
    }

    # CAM algorithm
    cam_positive = (
        cam_components["1_急性発症・変動する経過"]
        and cam_components["2_注意障害（必須）"]
        and (cam_components["3_支離滅裂な思考"] or cam_components["4_意識レベル変容"])
    )

    dementia_features = gradual_onset and (memory_predominant or progressive_months)

    if cam_positive and known_dementia:
        diagnosis = "both"   # 認知症に重畳したせん妄（最も見落とされるケース）
    elif cam_positive:
        diagnosis = "delirium"
    elif dementia_features:
        diagnosis = "dementia"
    else:
        diagnosis = "neither"

    # Key differentiators table
    differentiators = {
        "発症様式": "急性(時間〜日)" if cam_positive else "緩徐(月〜年)",
        "注意障害": "高度・変動する" if inattention else "比較的軽度",
        "意識レベル": "変容あり" if altered_consciousness else "清明（初期）",
        "日内変動": "著明(特に夜間悪化)" if fluctuating_course else "乏しい",
        "可逆性": "可逆的（原因除去で改善）" if cam_positive else "非可逆的（進行性）",
        "記憶障害": "短期・長期ともに" if memory_predominant else "エピソード記憶優位（認知症）",
    }

    # Immediate actions
    actions: list[str] = []
    if cam_positive:
        actions += [
            "ABCDE評価（安全確認・転倒リスク管理）",
            "原因検索: CBC/CMP/BUN/Cr/電解質/CRP/血培",
            "投薬確認（抗コリン薬・ベンゾ・オピオイドの見直し）",
            "非薬物療法: 昼間光暴露、睡眠リズム、早期離床、補聴器/眼鏡の使用",
        ]
        if age >= 65:
            actions.append("高齢者せん妄: ハロペリドール低用量または非定型抗精神病薬（ただし転倒・死亡リスク注意）")
    if dementia_features or known_dementia:
        actions += [
            "認知機能評価: MMSE / MoCA施行",
            "MRI(海馬萎縮・白質病変)",
            "甲状腺機能・B12/葉酸・梅毒・HIV（可逆性認知症の除外）",
        ]

    # Precipitant checklist
    reversible: list[str] = []
    if recent_infection:
        reversible.append("感染症（肺炎・尿路感染）")
    if new_medication:
        reversible.append("薬剤性（抗コリン、ベンゾ、オピオイド、ステロイド）")
    if metabolic_abnormality:
        reversible.append("代謝異常（低Na/高Ca/肝性/尿毒症/低血糖）")
    if urinary_retention:
        reversible.append("尿閉・便秘（不快感による過活動型せん妄）")
    if pain_uncontrolled:
        reversible.append("疼痛コントロール不良")
    if sleep_deprivation:
        reversible.append("睡眠剥奪（ICU環境・夜間処置）")

    return DeliriumAssessment(
        cam_positive=cam_positive,
        cam_components=cam_components,
        likely_diagnosis=diagnosis,
        key_differentiators=differentiators,
        immediate_actions=actions,
        reversible_causes=reversible,
    )


# ===========================================================================
# __main__ — smoke tests
# ===========================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("1. NIHSS Calculation")
    print("=" * 60)
    result = calc_nihss(
        consciousness=1, gaze=1, visual=1, facial=1,
        motor_arm_left=2, motor_leg_left=1, language=1, dysarthria=1,
    )
    print(f"Total NIHSS: {result.total_score}")
    print(f"Severity   : {result.severity}")
    print(f"Predicted mRS: {result.mrs_predicted} — {result.mrs_interpretation}")
    print(f"Recommendations: {result.recommendations}")

    print("\n" + "=" * 60)
    print("2. tPA Eligibility")
    print("=" * 60)
    tpa = check_tpa_eligibility(
        nihss=10, onset_hours=2.5, age=68, weight_kg=65.0,
        sbp=175, dbp=95, glucose=130,
    )
    print(f"Eligible: {tpa.eligible}")
    print(f"Dose    : {tpa.dose_mg} mg")
    print(f"Relative exclusions: {tpa.relative_exclusions}")
    print(f"Notes: {tpa.notes}")

    # Not eligible
    tpa2 = check_tpa_eligibility(
        nihss=8, onset_hours=5.0, hemorrhage_on_ct=False,
        inr=2.1, platelets_k=80, weight_kg=70,
    )
    print(f"\nCase 2 Eligible: {tpa2.eligible}")
    print(f"Absolute exclusions: {tpa2.absolute_exclusions}")

    print("\n" + "=" * 60)
    print("3. Seizure Classification")
    print("=" * 60)
    sz = classify_seizure(
        focal=True, awareness_preserved=False,
        automatisms=True, cognitive=True, age_years=25,
    )
    print(f"Classification: {sz.classification}")
    print(f"Awareness: {sz.awareness}")
    print(f"Recommended AEDs: {sz.recommended_aed}")

    print("\n" + "=" * 60)
    print("4. Headache Red Flags")
    print("=" * 60)
    hd = screen_headache_red_flags(
        thunderclap=True, neuro_signs=True, age_over_50_new=True,
    )
    print(f"Red flags   : {hd.red_flags}")
    print(f"Urgency     : {hd.urgency}")
    print(f"Workup      : {hd.workup}")

    print("\n" + "=" * 60)
    print("5. Delirium vs Dementia (CAM)")
    print("=" * 60)
    cam = assess_delirium_dementia(
        acute_onset=True, fluctuating_course=True, inattention=True,
        disorganized_thinking=True, altered_consciousness=True,
        recent_infection=True, new_medication=True, age=78,
    )
    print(f"CAM positive     : {cam.cam_positive}")
    print(f"Likely diagnosis : {cam.likely_diagnosis}")
    print(f"Reversible causes: {cam.reversible_causes}")
    print(f"Key differentiators: {cam.key_differentiators}")
