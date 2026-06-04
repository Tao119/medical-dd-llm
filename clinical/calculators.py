"""
clinical/calculators.py — General-Purpose Clinical Calculators

Implements 18 clinical calculators covering pharmacokinetics, renal function,
metabolic assessment, trauma scoring, and specialty risk tools.

Each calculator returns a CalcResult dataclass with:
  value         — numeric result
  unit          — unit string
  category      — risk/severity category label
  interpretation — plain-language interpretation
  recommendation — clinical action recommendation
  formula        — formula used (for reference / transparency)
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional


# ================================================================== #
# Common result type
# ================================================================== #

@dataclass
class CalcResult:
    value: float
    unit: str
    category: str
    interpretation: str
    recommendation: str
    formula: str = ""


# ================================================================== #
# Internal helpers
# ================================================================== #

def _clamp(val: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, float(val)))


def _ibw(height_cm: float, sex: str) -> float:
    """Ideal Body Weight (Devine formula), kg."""
    ht_in = height_cm / 2.54
    if sex.lower() in ("m", "male", "男性", "男"):
        return 50.0 + 2.3 * max(ht_in - 60, 0)
    else:
        return 45.5 + 2.3 * max(ht_in - 60, 0)


# ================================================================== #
# 1. Body Surface Area (Mosteller)
# ================================================================== #

def calc_bsa(height_cm: float, weight_kg: float) -> CalcResult:
    """Body Surface Area using the Mosteller formula.

    BSA = sqrt(height_cm × weight_kg / 3600)   [m²]

    Mosteller RD. Simplified calculation of body-surface area.
    N Engl J Med. 1987;317(17):1098.
    """
    if height_cm <= 0 or weight_kg <= 0:
        raise ValueError("身長・体重は正の値である必要があります")
    bsa = math.sqrt(height_cm * weight_kg / 3600.0)
    bsa = round(bsa, 3)

    if bsa < 1.5:
        category = "小柄"
    elif bsa <= 1.9:
        category = "標準"
    else:
        category = "大柄"

    return CalcResult(
        value=bsa,
        unit="m²",
        category=category,
        interpretation=f"体表面積 {bsa:.3f} m²（{category}）",
        recommendation="化学療法・薬剤投与量の調整に使用。"
                       "BSAベース投与設計は薬剤添付文書を参照。",
        formula="sqrt(height_cm × weight_kg / 3600)",
    )


# ================================================================== #
# 2. BMI + WHO / Asia-Pacific classification
# ================================================================== #

def calc_bmi(weight_kg: float, height_cm: float) -> CalcResult:
    """BMI with WHO global and Asia-Pacific thresholds.

    BMI = weight_kg / (height_m)²

    WHO 2000 / WHO WPR 2004 Asia-Pacific classification.
    """
    if height_cm <= 0 or weight_kg <= 0:
        raise ValueError("身長・体重は正の値である必要があります")
    height_m = height_cm / 100.0
    bmi = round(weight_kg / (height_m ** 2), 1)

    # WHO global categories
    if bmi < 18.5:
        who_cat = "低体重 (Underweight)"
        who_risk = "栄養管理・低体重関連疾患リスク評価"
    elif bmi < 25.0:
        who_cat = "標準体重 (Normal)"
        who_risk = "現状維持・定期健診"
    elif bmi < 30.0:
        who_cat = "過体重 (Overweight)"
        who_risk = "心血管リスク管理・生活習慣改善"
    elif bmi < 35.0:
        who_cat = "肥満I度 (Obese I)"
        who_risk = "代謝疾患精査・減量介入"
    elif bmi < 40.0:
        who_cat = "肥満II度 (Obese II)"
        who_risk = "積極的減量・薬物療法検討"
    else:
        who_cat = "肥満III度 / 高度肥満 (Obese III)"
        who_risk = "肥満外科・集中的介入"

    # Asia-Pacific thresholds (lower cutoffs)
    if bmi < 18.5:
        ap_cat = "低体重"
    elif bmi < 23.0:
        ap_cat = "標準体重"
    elif bmi < 27.5:
        ap_cat = "過体重（アジア太平洋）"
    else:
        ap_cat = "肥満（アジア太平洋）"

    interp = (
        f"BMI {bmi} kg/m² — WHO分類: {who_cat} / アジア太平洋分類: {ap_cat}"
    )

    return CalcResult(
        value=bmi,
        unit="kg/m²",
        category=who_cat,
        interpretation=interp,
        recommendation=who_risk,
        formula="weight_kg / (height_m)²",
    )


# ================================================================== #
# 3. eGFR — CKD-EPI 2021 (race-free)
# ================================================================== #

def calc_egfr_ckdepi(creatinine: float, age: int, sex: str) -> CalcResult:
    """eGFR using CKD-EPI 2021 race-free equation.

    Inker LA et al. New Creatinine- and Cystatin C-Based Equations to
    Estimate GFR without Race. N Engl J Med. 2021;385(19):1737-1749.

    Parameters
    ----------
    creatinine : float  — serum Cr (mg/dL)
    age        : int    — age in years
    sex        : str    — 'M'/'F' or '男性'/'女性'
    """
    if creatinine <= 0:
        raise ValueError("クレアチニンは正の値である必要があります")
    cr = float(creatinine)
    is_female = sex.lower() in ("f", "female", "女性", "女")

    if is_female:
        kappa, alpha = 0.7, -0.241
        sex_factor = 1.012
    else:
        kappa, alpha = 0.9, -0.302
        sex_factor = 1.0

    cr_kappa = cr / kappa
    egfr = (
        142
        * (min(cr_kappa, 1.0) ** alpha)
        * (max(cr_kappa, 1.0) ** -1.200)
        * (0.9938 ** age)
        * sex_factor
    )
    egfr = round(egfr, 1)

    # CKD staging (KDIGO 2012)
    if egfr >= 90:
        stage = "G1（正常または高い）"
        rec = "腎保護・危険因子管理。必要に応じて尿検査で蛋白尿評価。"
    elif egfr >= 60:
        stage = "G2（軽度低下）"
        rec = "腎機能モニタリング・腎毒性薬剤に注意。"
    elif egfr >= 45:
        stage = "G3a（軽度〜中等度低下）"
        rec = "腎臓内科コンサルト検討。貧血・骨ミネラル代謝評価。"
    elif egfr >= 30:
        stage = "G3b（中等度〜高度低下）"
        rec = "腎臓内科コンサルト。透析準備教育開始。"
    elif egfr >= 15:
        stage = "G4（高度低下）"
        rec = "透析・腎移植準備。腎代替療法カウンセリング。"
    else:
        stage = "G5（腎不全）"
        rec = "腎代替療法（透析または腎移植）の開始/検討。"

    return CalcResult(
        value=egfr,
        unit="mL/min/1.73m²",
        category=f"CKD {stage}",
        interpretation=f"eGFR (CKD-EPI 2021) = {egfr} mL/min/1.73m² — CKD {stage}",
        recommendation=rec,
        formula=(
            "142 × (Cr/κ)^α × (max(Cr/κ,1))^-1.200 × 0.9938^age × sex_factor"
        ),
    )


# ================================================================== #
# 4. Creatinine Clearance — Cockcroft-Gault (IBW-capped)
# ================================================================== #

def calc_crcl_cockroft_gault(
    creatinine: float,
    age: int,
    weight_kg: float,
    sex: str,
    height_cm: Optional[float] = None,
) -> CalcResult:
    """Creatinine clearance by Cockcroft-Gault formula.

    CrCl = ((140 - age) × weight_kg) / (72 × Cr_mg/dL) × [0.85 if female]

    If height_cm is provided and weight > IBW, IBW is used (prevents
    overestimation in obese patients). ABW is NOT used here — clinical
    teams may choose to use AdjBW for drug dosing.

    Cockcroft DW, Gault MH. Nephron. 1976;16(1):31-41.
    """
    if creatinine <= 0 or weight_kg <= 0 or age <= 0:
        raise ValueError("入力値は正の値である必要があります")
    is_female = sex.lower() in ("f", "female", "女性", "女")
    sex_factor = 0.85 if is_female else 1.0

    actual_wt = weight_kg
    wt_note = "実測体重使用"
    if height_cm is not None and height_cm > 0:
        ibw = _ibw(height_cm, sex)
        if weight_kg > ibw:
            actual_wt = ibw
            wt_note = f"IBW {ibw:.1f}kg 使用（実測体重{weight_kg}kg > IBW）"

    cr_safe = max(creatinine, 0.6)  # avoid unrealistically low Cr
    crcl = ((140.0 - age) * actual_wt) / (72.0 * cr_safe) * sex_factor
    crcl = round(max(crcl, 0.0), 1)

    if crcl >= 90:
        cat = "正常"
        rec = "腎機能は正常範囲。標準用量で投与可。"
    elif crcl >= 60:
        cat = "軽度低下"
        rec = "腎排泄薬剤の用量調整は原則不要。定期的モニタリング。"
    elif crcl >= 30:
        cat = "中等度低下"
        rec = "腎排泄薬剤（抗菌薬・DOAC等）は用量減量・間隔延長を検討。"
    elif crcl >= 15:
        cat = "高度低下"
        rec = "多くの薬剤で禁忌または大幅減量が必要。添付文書必参照。"
    else:
        cat = "末期腎不全"
        rec = "腎代替療法（透析）患者に準じた用量調整。"

    return CalcResult(
        value=crcl,
        unit="mL/min",
        category=cat,
        interpretation=f"CrCl (CG法) = {crcl} mL/min — {cat}。{wt_note}。",
        recommendation=rec,
        formula="(140 - age) × weight / (72 × Cr) × [0.85 if female]",
    )


# ================================================================== #
# 5. Corrected Calcium (albumin correction)
# ================================================================== #

def calc_corrected_calcium(calcium: float, albumin: float) -> CalcResult:
    """Corrected calcium for hypoalbuminemia.

    Ca_corrected = Ca + 0.8 × (4.0 - albumin)

    Payne RB et al. Br Med J. 1973;4(5893):643-646.

    Parameters
    ----------
    calcium : float  — total serum calcium (mg/dL)
    albumin : float  — serum albumin (g/dL)
    """
    correction = 0.8 * (4.0 - albumin)
    ca_corr = round(calcium + correction, 2)

    if ca_corr < 8.5:
        cat = "低カルシウム血症"
        interp = f"補正Ca {ca_corr} mg/dL — 低Ca血症。テタニー・QT延長リスク。"
        rec = "Ca補充（経口または点滴）。ビタミンD評価。副甲状腺機能評価。"
    elif ca_corr <= 10.5:
        cat = "正常"
        interp = f"補正Ca {ca_corr} mg/dL — 正常範囲。"
        rec = "経過観察。"
    elif ca_corr <= 12.0:
        cat = "軽度高カルシウム血症"
        interp = f"補正Ca {ca_corr} mg/dL — 軽度高Ca血症。"
        rec = "原因検索（副甲状腺機能亢進症・悪性腫瘍）。水分補給。"
    elif ca_corr <= 14.0:
        cat = "中等度高カルシウム血症"
        interp = f"補正Ca {ca_corr} mg/dL — 中等度高Ca血症。症状あれば入院。"
        rec = "生食輸液・ビスフォスフォネート投与。原因治療。"
    else:
        cat = "重篤な高カルシウム血症"
        interp = f"補正Ca {ca_corr} mg/dL — 重篤な高Ca血症（Ca>14）。緊急治療。"
        rec = "緊急入院・大量生食輸液・フロセミド・ビスフォスフォネート・カルシトニン。"

    return CalcResult(
        value=ca_corr,
        unit="mg/dL",
        category=cat,
        interpretation=interp,
        recommendation=rec,
        formula="Ca + 0.8 × (4.0 − albumin)",
    )


# ================================================================== #
# 6. Anion Gap (with albumin correction)
# ================================================================== #

def calc_anion_gap(
    na: float, cl: float, hco3: float, albumin: float = 4.0
) -> CalcResult:
    """Serum anion gap with albumin correction.

    AG       = Na − (Cl + HCO3)
    AG_corr  = AG + 2.5 × (4.0 − albumin)   [Figge correction]

    Normal AG = 8-12 mEq/L (or 3-11 with newer assays).
    Corrected normal ≈ 12 mEq/L.

    Figge J et al. Crit Care Med. 1998;26(11):1807-16.
    """
    ag = na - (cl + hco3)
    ag_corr = ag + 2.5 * (4.0 - albumin)
    ag = round(ag, 1)
    ag_corr = round(ag_corr, 1)

    normal_upper = 12.0
    if ag_corr > normal_upper:
        cat = "高AGアシドーシス"
        interp = (
            f"AG = {ag} / 補正AG = {ag_corr} mEq/L — 高AG代謝性アシドーシス。"
            " MUDPILES（Methanol/Uremia/DKA/Paraldehyde/Isoniazid/"
            "Lactic acidosis/Ethanol/Salicylate）を検索。"
        )
        rec = "δ/δ比（delta-delta ratio）を計算し混合性酸塩基障害を評価。"
    elif ag < 3:
        cat = "低AGアシドーシス"
        interp = f"AG = {ag} mEq/L — 低AG。低Mg・低蛋白血症・多発性骨髄腫を検討。"
        rec = "血清タンパク・免疫電気泳動を確認。"
    else:
        cat = "正常AG"
        interp = f"AG = {ag} / 補正AG = {ag_corr} mEq/L — 正常AG。"
        rec = "正常AG代謝性アシドーシスの場合はurine AG・NH4+測定。"

    return CalcResult(
        value=ag_corr,
        unit="mEq/L",
        category=cat,
        interpretation=interp,
        recommendation=rec,
        formula="Na − (Cl + HCO3); corrected: AG + 2.5×(4.0−albumin)",
    )


# ================================================================== #
# 7. Osmolal Gap
# ================================================================== #

def calc_osmolal_gap(
    na: float,
    glucose: float,
    bun: float,
    measured_osm: float,
) -> CalcResult:
    """Serum osmolal gap calculation.

    Calculated osmolality = 2×Na + glucose/18 + BUN/2.8
    Osmolal gap = measured − calculated

    Normal osmolal gap ≤ 10 mOsm/kg H2O.
    Elevated gap (>10) suggests toxic alcohols or unmeasured osmoles.

    Parameters
    ----------
    na           : serum sodium (mEq/L)
    glucose      : serum glucose (mg/dL)
    bun          : BUN (mg/dL)
    measured_osm : measured serum osmolality (mOsm/kg)
    """
    calc_osm = 2.0 * na + glucose / 18.0 + bun / 2.8
    og = measured_osm - calc_osm
    calc_osm = round(calc_osm, 1)
    og = round(og, 1)

    if og <= 10:
        cat = "正常"
        interp = f"浸透圧ギャップ = {og} mOsm/kg（正常 ≤10）。"
        rec = "中毒性アルコール（メタノール・エタノール・エチレングリコール）は現時点で低リスク。"
    elif og <= 20:
        cat = "軽度上昇"
        interp = f"浸透圧ギャップ = {og} mOsm/kg — 軽度上昇。臨床的文脈で評価。"
        rec = "中毒性アルコール摂取疑い。血中アルコール測定・毒物スクリーニングを検討。"
    else:
        cat = "高度上昇（中毒疑い）"
        interp = f"浸透圧ギャップ = {og} mOsm/kg — 高度上昇。中毒性物質を強く疑う。"
        rec = (
            "緊急対応: メタノール・エチレングリコール中毒除外。"
            "ホメピゾール投与・透析を検討。毒物専門家/中毒センターへ相談。"
        )

    return CalcResult(
        value=og,
        unit="mOsm/kg",
        category=cat,
        interpretation=interp,
        recommendation=rec,
        formula="measured_osm − (2×Na + glucose/18 + BUN/2.8)",
    )


# ================================================================== #
# 8. FENa — Fractional Excretion of Sodium
# ================================================================== #

def calc_fena(
    urine_na: float,
    serum_cr: float,
    serum_na: float,
    urine_cr: float,
) -> CalcResult:
    """Fractional Excretion of Sodium (FENa).

    FENa = (UNa × SCr) / (SNa × UCr) × 100 [%]

    Interpretation:
      FENa < 1%: Pre-renal AKI (or early obstruction)
      FENa > 2%: Intrinsic renal (ATN, etc.)
      Note: unreliable with diuretic use → use FEUrea instead.

    Parameters
    ----------
    urine_na : urine sodium (mEq/L)
    serum_cr : serum creatinine (mg/dL)
    serum_na : serum sodium (mEq/L)
    urine_cr : urine creatinine (mg/dL)
    """
    if serum_na <= 0 or urine_cr <= 0:
        raise ValueError("血清Na・尿中Crは正の値である必要があります")
    fena = (urine_na * serum_cr) / (serum_na * urine_cr) * 100.0
    fena = round(fena, 2)

    if fena < 1.0:
        cat = "腎前性 AKI"
        interp = f"FENa = {fena}% (<1%) — 腎前性AKIを示唆。"
        rec = (
            "循環血液量の評価（脱水・出血・心不全）。"
            "輸液負荷試験を検討。利尿薬使用中はFEUreaを参照。"
        )
    elif fena > 2.0:
        cat = "腎性 AKI（ATN疑い）"
        interp = f"FENa = {fena}% (>2%) — 急性尿細管壊死（ATN）を示唆。"
        rec = "腎毒性薬剤中止・造影剤回避・輸液量適正化・腎臓内科コンサルト。"
    else:
        cat = "境界値（1-2%）"
        interp = f"FENa = {fena}% (1-2%) — 判断困難。臨床的文脈で統合的評価が必要。"
        rec = "尿沈渣・尿比重・臨床状況を総合判断。腎臓内科コンサルト検討。"

    return CalcResult(
        value=fena,
        unit="%",
        category=cat,
        interpretation=interp,
        recommendation=rec,
        formula="(UNa × SCr) / (SNa × UCr) × 100",
    )


# ================================================================== #
# 9. QTc — Corrected QT interval
# ================================================================== #

def calc_qtc(
    qt_ms: float,
    rr_ms: float,
    method: str = "bazett",
) -> CalcResult:
    """QTc calculation using Bazett, Fredericia, or Framingham formula.

    Bazett    : QTc = QT / sqrt(RR)         — most common, overcorrects at high HR
    Fredericia: QTc = QT / RR^(1/3)         — preferred at high HR
    Framingham: QTc = QT + 0.154 × (1 - RR) — linear correction

    RR in seconds.
    Normal QTc ≤440 ms (men) / ≤460 ms (women).

    Parameters
    ----------
    qt_ms  : measured QT interval (ms)
    rr_ms  : R-R interval (ms)
    method : 'bazett' | 'fredericia' | 'framingham'
    """
    if qt_ms <= 0 or rr_ms <= 0:
        raise ValueError("QT・RRは正の値である必要があります")
    rr_sec = rr_ms / 1000.0

    method = method.lower()
    if method == "bazett":
        qtc = qt_ms / math.sqrt(rr_sec)
        formula = "QT / sqrt(RR_sec)"
    elif method in ("fredericia", "fridericia"):
        qtc = qt_ms / (rr_sec ** (1.0 / 3.0))
        formula = "QT / RR_sec^(1/3)"
    elif method == "framingham":
        qtc = qt_ms + 0.154 * (1.0 - rr_sec) * 1000
        formula = "QT + 154 × (1 - RR_sec) [ms]"
    else:
        raise ValueError(f"method は 'bazett' / 'fredericia' / 'framingham' のいずれかを指定してください。受け取り: {method}")

    qtc = round(qtc, 1)
    hr_bpm = round(60000 / rr_ms, 0)

    if qtc > 500:
        cat = "危険域 QTc延長"
        interp = f"QTc ({method}) = {qtc} ms — QTc>500 ms: Torsades de Pointes 高リスク。"
        rec = "QT延長誘発薬剤の中止確認。電解質補正（K・Mg）。循環器科緊急コンサルト。"
    elif qtc > 460:
        cat = "QTc延長"
        interp = f"QTc ({method}) = {qtc} ms — QTc延長（460-500 ms）。"
        rec = "QT延長薬剤確認。低K血症・低Mg血症補正。連続心電図モニタリング。"
    elif qtc >= 440:
        cat = "境界値"
        interp = f"QTc ({method}) = {qtc} ms — 境界域（440-460 ms）。"
        rec = "連続モニタリング・誘因薬剤確認。"
    else:
        cat = "正常"
        interp = f"QTc ({method}) = {qtc} ms — 正常範囲（<440 ms）。"
        rec = "現時点で経過観察。"

    return CalcResult(
        value=qtc,
        unit="ms",
        category=cat,
        interpretation=interp + f" HR={hr_bpm:.0f} bpm。",
        recommendation=rec,
        formula=formula,
    )


# ================================================================== #
# 10. Predicted Body Weight (ventilator tidal volume dosing)
# ================================================================== #

def calc_predicted_body_weight(height_cm: float, sex: str) -> CalcResult:
    """Predicted Body Weight for ventilator tidal volume dosing.

    PBW male   = 50  + 2.3 × (height_in − 60)
    PBW female = 45.5 + 2.3 × (height_in − 60)

    ARDSNet / NIH ARDS Network. NEJM 2000;342(18):1301-1308.
    Tidal volume target: 6 mL/kg PBW (lung-protective ventilation).
    """
    if height_cm <= 0:
        raise ValueError("身長は正の値である必要があります")
    ht_in = height_cm / 2.54
    pbw = _ibw(height_cm, sex)
    pbw = round(pbw, 1)

    is_female = sex.lower() in ("f", "female", "女性", "女")
    sex_label = "女性" if is_female else "男性"

    tv_low  = round(pbw * 6, 0)
    tv_high = round(pbw * 8, 0)
    tv_lung_protect = round(pbw * 6, 0)

    interp = f"PBW = {pbw} kg ({sex_label}, {height_cm} cm)"
    rec = (
        f"肺保護換気: TV目標 {tv_lung_protect} mL/回（6 mL/kg PBW）。"
        f"通常換気: {tv_low}〜{tv_high} mL（6〜8 mL/kg PBW）。"
        " Pplat ≤30 cmH2O を維持。"
    )

    return CalcResult(
        value=pbw,
        unit="kg",
        category="換気設定目標体重",
        interpretation=interp,
        recommendation=rec,
        formula=(
            "男性: 50 + 2.3×(Ht_in − 60) / 女性: 45.5 + 2.3×(Ht_in − 60)"
        ),
    )


# ================================================================== #
# 11. Alvarado Score (Appendicitis)
# ================================================================== #

def calc_alvarado(
    migrating_pain: bool,
    anorexia: bool,
    nausea_vomiting: bool,
    rb_tenderness: bool,
    rebound_tenderness: bool,
    elevated_temp: bool,
    leukocytosis: bool,
    left_shift: bool,
) -> CalcResult:
    """Alvarado score for acute appendicitis risk stratification.

    MANTRELS scoring system. Score range 0-10.
    ≥7: High probability — surgical consultation.
    4-6: Equivocal — observation / imaging.
    ≤3: Low probability — likely not appendicitis.

    Alvarado A. Ann Emerg Med. 1986;15(5):557-564.
    """
    # Symptoms (max 3 pts)
    s1 = 1 if migrating_pain else 0       # Migration of pain to RLQ
    s2 = 1 if anorexia else 0             # Anorexia
    s3 = 1 if nausea_vomiting else 0      # Nausea / vomiting

    # Signs (max 4 pts)
    s4 = 2 if rb_tenderness else 0        # Tenderness in RLQ (2 pts)
    s5 = 1 if rebound_tenderness else 0   # Rebound tenderness
    s6 = 1 if elevated_temp else 0        # Elevated temperature

    # Lab (max 3 pts)
    s7 = 2 if leukocytosis else 0         # Leukocytosis (2 pts)
    s8 = 1 if left_shift else 0           # Left shift

    score = s1 + s2 + s3 + s4 + s5 + s6 + s7 + s8

    if score >= 7:
        cat = "高確率虫垂炎"
        interp = f"Alvarado score = {score}/10 — 急性虫垂炎の可能性が高い。"
        rec = "外科コンサルト・手術検討。CTまたは超音波で確認後に手術計画。"
    elif score >= 4:
        cat = "中等度リスク"
        interp = f"Alvarado score = {score}/10 — 中等度リスク。精査が必要。"
        rec = "入院・経過観察。CT/超音波施行。連続的腹部所見評価。"
    else:
        cat = "低確率虫垂炎"
        interp = f"Alvarado score = {score}/10 — 虫垂炎の可能性は低い。"
        rec = "外来経過観察可。症状増悪時は再受診指示。他の診断を検索。"

    return CalcResult(
        value=float(score),
        unit="点",
        category=cat,
        interpretation=interp,
        recommendation=rec,
        formula=(
            "移動痛(1)+食欲不振(1)+嘔気(1)+RLQ圧痛(2)+反跳痛(1)"
            "+発熱(1)+白血球増多(2)+核左方移動(1)"
        ),
    )


# ================================================================== #
# 12. LRINEC Score (Necrotizing Fasciitis)
# ================================================================== #

def calc_lrinec(
    crp: float,
    wbc: float,
    hb: float,
    na: float,
    cr: float,
    glucose: float,
) -> CalcResult:
    """LRINEC (Laboratory Risk Indicator for Necrotizing Fasciitis) score.

    Differentiates necrotizing fasciitis from other severe soft tissue infections.
    Score ≥6: High risk — surgical exploration warranted.

    Wong CH et al. Crit Care Med. 2004;32(7):1535-1541.

    Parameters
    ----------
    crp     : CRP (mg/L)
    wbc     : WBC (×10³/μL)
    hb      : hemoglobin (g/dL)
    na      : serum sodium (mEq/L)
    cr      : serum creatinine (mg/dL)
    glucose : serum glucose (mg/dL)
    """
    score = 0

    # CRP (mg/L)
    if crp >= 150:
        score += 4
    # WBC
    if wbc > 25:
        score += 2
    elif wbc >= 15:
        score += 1
    # Hb
    if hb < 11:
        score += 2
    elif hb <= 13.5:
        score += 1
    # Na
    if na < 135:
        score += 2
    # Creatinine
    if cr > 1.6:
        score += 2
    # Glucose
    if glucose > 180:
        score += 1

    if score >= 8:
        cat = "壊死性筋膜炎 高リスク（緊急手術）"
        interp = f"LRINEC score = {score}/13 — 壊死性筋膜炎の可能性が非常に高い。"
        rec = "外科医緊急コール。即座の手術的探索（デブリードマン）が必要。遅延は死命を制す。"
    elif score >= 6:
        cat = "壊死性筋膜炎 中〜高リスク"
        interp = f"LRINEC score = {score}/13 — 壊死性筋膜炎を強く疑う。"
        rec = "外科コンサルト・緊急画像検査（CT）。手術準備。"
    else:
        cat = "低リスク（≤5点）"
        interp = f"LRINEC score = {score}/13 — 低リスクだが臨床所見と総合判断が必須。"
        rec = (
            "スコアが低くても臨床上壊死性筋膜炎を疑う所見（急速進行・捻髪音・皮膚変色）"
            "があれば外科コンサルト。"
        )

    return CalcResult(
        value=float(score),
        unit="点",
        category=cat,
        interpretation=interp,
        recommendation=rec,
        formula=(
            "CRP≥150→4, WBC>25→2/15-25→1, Hb<11→2/11-13.5→1, "
            "Na<135→2, Cr>1.6→2, Glucose>180→1"
        ),
    )


# ================================================================== #
# 13. SCORTEN (Stevens-Johnson / TEN mortality)
# ================================================================== #

def calc_scorten(
    age: int,
    hr: int,
    malignancy: bool,
    bsa_pct: float,
    bun: float,
    bicarb: float,
    glucose: float,
) -> CalcResult:
    """SCORTEN severity score for Stevens-Johnson Syndrome / TEN.

    Each criterion = 1 point (0-7). Mortality increases with score.

    Bastuji-Garin S et al. J Invest Dermatol. 2000;115(2):149-153.

    Parameters
    ----------
    age      : age in years (≥40 = 1 pt)
    hr       : heart rate bpm (≥120 = 1 pt)
    malignancy : active malignancy (True = 1 pt)
    bsa_pct  : percentage of body surface area detached (≥10% = 1 pt)
    bun      : BUN mg/dL (≥28 = 1 pt)
    bicarb   : serum bicarbonate mEq/L (<20 = 1 pt)
    glucose  : serum glucose mg/dL (>252 = 1 pt)
    """
    score = 0
    if age >= 40:
        score += 1
    if hr >= 120:
        score += 1
    if malignancy:
        score += 1
    if bsa_pct >= 10:
        score += 1
    if bun >= 28:
        score += 1
    if bicarb < 20:
        score += 1
    if glucose > 252:
        score += 1

    # Published mortality estimates from Bastuji-Garin 2000
    mortality_table = {0: 3.2, 1: 3.2, 2: 12.1, 3: 35.3, 4: 58.3, 5: 90.0, 6: 90.0, 7: 90.0}
    mortality = mortality_table.get(score, 90.0)

    if score <= 1:
        cat = "低リスク"
    elif score <= 2:
        cat = "中リスク"
    elif score <= 4:
        cat = "高リスク"
    else:
        cat = "最重症"

    interp = f"SCORTEN = {score}/7 — 推定死亡率 {mortality}%。"
    rec = (
        "皮膚科・集中治療科共同管理。原因薬剤即時中止。"
        "熱傷ユニット準じた管理（水分・電解質・体温管理・感染予防）。"
        "眼科・婦人科・泌尿器科合同評価。IVIG・シクロスポリン検討。"
    )

    return CalcResult(
        value=float(score),
        unit="点",
        category=cat,
        interpretation=interp,
        recommendation=rec,
        formula=(
            "年齢≥40(1)+HR≥120(1)+悪性腫瘍(1)+BSA剥離≥10%(1)"
            "+BUN≥28(1)+HCO3<20(1)+血糖>252(1)"
        ),
    )


# ================================================================== #
# 14. Revised Trauma Score (RTS)
# ================================================================== #

def calc_rts(sbp: float, rr: float, gcs: int) -> CalcResult:
    """Revised Trauma Score for trauma triage.

    RTS = 0.9368×GCS_coded + 0.7326×SBP_coded + 0.2908×RR_coded
    Range: 0 (worst) – 7.8408 (best survival).
    RTS <4: suggests major injury, activate trauma team.

    Champion HR et al. J Trauma. 1989;29(5):623-629.
    """
    # SBP coding
    if sbp > 89:
        sbp_code = 4
    elif sbp >= 76:
        sbp_code = 3
    elif sbp >= 50:
        sbp_code = 2
    elif sbp >= 1:
        sbp_code = 1
    else:
        sbp_code = 0

    # RR coding
    if 10 <= rr <= 29:
        rr_code = 4
    elif rr >= 30:
        rr_code = 3
    elif rr >= 6:
        rr_code = 2
    elif rr >= 1:
        rr_code = 1
    else:
        rr_code = 0

    # GCS coding
    gcs_c = int(_clamp(gcs, 3, 15))
    if gcs_c == 15:
        gcs_code = 4
    elif gcs_c >= 12:
        gcs_code = 3
    elif gcs_c >= 9:
        gcs_code = 2
    elif gcs_c >= 6:
        gcs_code = 1
    else:
        gcs_code = 0

    rts = round(0.9368 * gcs_code + 0.7326 * sbp_code + 0.2908 * rr_code, 4)

    # Survival probability (approximate)
    survival_pct = round(100 / (1 + math.exp(-(-3.5718 + 0.9368 * gcs_code
                                                + 0.7326 * sbp_code
                                                + 0.2908 * rr_code))), 1)

    if rts >= 6:
        cat = "軽傷（Minor）"
        rec = "通常評価継続。バイタル経過観察。"
    elif rts >= 4:
        cat = "中等症（Moderate）"
        rec = "入院加療。外傷チームによる評価。"
    else:
        cat = "重症（Critical）"
        rec = "外傷チーム活性化。蘇生・外科的介入を優先。ICU搬送。"

    interp = (
        f"RTS = {rts:.4f} / 生存確率 ≈ {survival_pct}%。"
        f" GCS_coded={gcs_code}, SBP_coded={sbp_code}, RR_coded={rr_code}。"
    )

    return CalcResult(
        value=rts,
        unit="点",
        category=cat,
        interpretation=interp,
        recommendation=rec,
        formula=(
            "0.9368×GCS_coded + 0.7326×SBP_coded + 0.2908×RR_coded"
        ),
    )


# ================================================================== #
# 15. Wells DVT Score
# ================================================================== #

def calc_wells_dvt(
    active_cancer: bool,
    paralysis: bool,
    bedridden: bool,
    local_tenderness: bool,
    leg_swelling: bool,
    pitting_edema: bool,
    collateral_veins: bool,
    previous_dvt: bool,
    alternative_dx: bool,
) -> CalcResult:
    """Wells score for DVT pre-test probability.

    Score ≥2: High probability — LDUS and/or anticoagulation.
    Score 1: Moderate — LDUS + D-dimer.
    Score ≤0: Low — D-dimer only; if negative, DVT excluded.

    Wells PS et al. Lancet. 1997;350(9094):1795-1798.

    Parameters
    ----------
    alternative_dx : alternative diagnosis is at least as likely (−2 pts)
    """
    score = 0
    if active_cancer:
        score += 1
    if paralysis:
        score += 1
    if bedridden:
        score += 1
    if local_tenderness:
        score += 1
    if leg_swelling:
        score += 1
    if pitting_edema:
        score += 1
    if collateral_veins:
        score += 1
    if previous_dvt:
        score += 1
    if alternative_dx:
        score -= 2  # Makes DVT less likely

    if score >= 2:
        cat = "高確率（>50%）"
        interp = f"Wells DVT score = {score} — 高確率。DVTリスク >50%。"
        rec = "下肢静脈超音波（LDUS）実施。陰性でも再検（7日後）。抗凝固療法開始検討。"
    elif score == 1:
        cat = "中確率（17%）"
        interp = f"Wells DVT score = {score} — 中確率。"
        rec = "D-dimer測定 + LDUS。D-dimer陽性ならLDUS実施。"
    else:
        cat = "低確率（<5%）"
        interp = f"Wells DVT score = {score} — 低確率。"
        rec = "D-dimer測定。陰性であればDVT除外可能。陽性の場合はLDUS施行。"

    return CalcResult(
        value=float(score),
        unit="点",
        category=cat,
        interpretation=interp,
        recommendation=rec,
        formula=(
            "活動性癌(1)+麻痺(1)+臥床(1)+圧痛(1)+下肢腫脹(1)"
            "+圧痕性浮腫(1)+側副静脈(1)+DVT既往(1)+代替診断(-2)"
        ),
    )


# ================================================================== #
# 16. TIMI Risk Score for NSTEMI/UA
# ================================================================== #

def calc_timi_nstemi(
    age65: bool,
    cad_markers: int,
    st_deviation: bool,
    severe_angina: bool,
    aspirin: bool,
    elevated_markers: bool,
    risk_factors: int,
) -> CalcResult:
    """TIMI Risk Score for NSTEMI / Unstable Angina.

    Score 0-7 points. Higher score → higher 14-day MACE rate.
    Score 0-1: 5%; 2: 8%; 3: 13%; 4: 20%; 5: 26%; 6-7: 41%.

    Antman EM et al. JAMA. 2000;284(7):835-842.

    Parameters
    ----------
    age65      : age ≥65 years
    cad_markers: number of CAD risk factors (≥3 = 1 pt)
    st_deviation: ST deviation ≥0.5 mm
    severe_angina: ≥2 anginal events in 24h
    aspirin    : aspirin use in past 7 days
    elevated_markers: elevated cardiac markers (TnI/CK-MB)
    risk_factors: number of traditional CAD risk factors (0/1-2/≥3)
    """
    score = 0
    if age65:
        score += 1
    if cad_markers >= 3 or risk_factors >= 3:
        score += 1
    if st_deviation:
        score += 1
    if severe_angina:
        score += 1
    if aspirin:
        score += 1
    if elevated_markers:
        score += 1
    # Known CAD (stenosis ≥50%)
    # Note: cad_markers as a proxy here
    if cad_markers >= 1:
        score += 1

    score = min(score, 7)

    mace_rate_table = {0: 4.7, 1: 4.7, 2: 8.3, 3: 13.2, 4: 19.9, 5: 26.2, 6: 40.9, 7: 40.9}
    mace = mace_rate_table.get(score, 40.9)

    if score <= 2:
        cat = "低リスク"
        rec = "保存的管理を検討。12-24時間内のTn再検・心電図確認。"
    elif score <= 4:
        cat = "中リスク"
        rec = "入院・連続TnI/心電図モニタリング。72時間以内の侵襲的戦略検討。"
    else:
        cat = "高リスク"
        rec = "早期侵襲的戦略（24時間以内の冠動脈造影）。DAPT・抗凝固療法開始。"

    interp = f"TIMI NSTEMI score = {score}/7 — 14日間MACE率 ≈ {mace}%。"

    return CalcResult(
        value=float(score),
        unit="点",
        category=cat,
        interpretation=interp,
        recommendation=rec,
        formula=(
            "年齢≥65(1)+CAD危険因子≥3(1)+ST偏位(1)+重篤な狭心症(1)"
            "+アスピリン使用(1)+心筋マーカー上昇(1)+既知CAD(1)"
        ),
    )


# ================================================================== #
# 17. GRACE Score for ACS
# ================================================================== #

def calc_grace_acs(
    age: int,
    hr: int,
    sbp: int,
    creatinine: float,
    cardiac_arrest: bool,
    st_deviation: bool,
    elevated_enzymes: bool,
    killip_class: int,
) -> CalcResult:
    """GRACE score for ACS in-hospital and 6-month mortality.

    Fox KAA et al. BMJ. 2006;333(7578):1091.

    Simplified lookup-table approximation.
    """
    comp_score = 0

    # Age
    age_pts = {
        (0,   29): 0,  (30, 39): 8,  (40, 49): 25, (50, 59): 41,
        (60, 69): 58, (70, 79): 75, (80, 89): 91, (90, 999): 100,
    }
    for (lo, hi), pts in age_pts.items():
        if lo <= age <= hi:
            comp_score += pts
            break

    # HR
    hr_pts = {
        (0, 49): 0, (50, 69): 3, (70, 89): 9, (90, 109): 15,
        (110, 149): 24, (150, 199): 38, (200, 999): 46,
    }
    for (lo, hi), pts in hr_pts.items():
        if lo <= hr <= hi:
            comp_score += pts
            break

    # SBP
    sbp_pts = {
        (0, 79): 58, (80, 99): 53, (100, 119): 43, (120, 139): 34,
        (140, 159): 24, (160, 199): 10, (200, 999): 0,
    }
    for (lo, hi), pts in sbp_pts.items():
        if lo <= sbp <= hi:
            comp_score += pts
            break

    # Creatinine
    cr_pts = {
        (0.0, 0.39): 1,  (0.40, 0.79): 4,  (0.80, 1.19): 7,
        (1.20, 1.59): 10, (1.60, 1.99): 13, (2.00, 3.99): 21,
        (4.00, 99.0): 28,
    }
    for (lo, hi), pts in cr_pts.items():
        if lo <= creatinine <= hi:
            comp_score += pts
            break

    # Killip class
    killip_pts = {1: 0, 2: 20, 3: 39, 4: 59}
    comp_score += killip_pts.get(max(1, min(killip_class, 4)), 0)

    # Binary variables
    if cardiac_arrest:
        comp_score += 39
    if st_deviation:
        comp_score += 28
    if elevated_enzymes:
        comp_score += 14

    total = comp_score

    # In-hospital mortality (logistic approximation)
    log_odds_ih = -7.43 + 0.028 * total
    ih_mort = round(100.0 / (1.0 + math.exp(-log_odds_ih)), 1)

    # 6-month mortality approximation
    log_odds_6m = -6.50 + 0.025 * total
    sm_mort = round(100.0 / (1.0 + math.exp(-log_odds_6m)), 1)

    if total < 109:
        cat = "低リスク"
        rec = "保存的管理。Tn再検・連続心電図モニタリング。"
    elif total <= 140:
        cat = "中リスク"
        rec = "72時間以内の侵襲的戦略検討。DAPT開始。"
    else:
        cat = "高リスク"
        rec = "早期侵襲的戦略（24時間以内の冠動脈造影）。抗凝固・DAPT開始。"

    interp = (
        f"GRACE score = {total} — 院内死亡率 ≈ {ih_mort}% / 6ヶ月死亡率 ≈ {sm_mort}%。"
    )

    return CalcResult(
        value=float(total),
        unit="点",
        category=cat,
        interpretation=interp,
        recommendation=rec,
        formula=(
            "年齢+HR+SBP+Cr+Killip+心停止(39)+STD(28)+酵素上昇(14)"
        ),
    )


# ================================================================== #
# 18. HAS-BLED Score (Bleeding risk in AF)
# ================================================================== #

def calc_has_bled(
    hypertension: bool,
    renal_liver_disease: int,
    stroke: bool,
    bleeding: bool,
    labile_inr: bool,
    elderly: bool,
    drugs_alcohol: int,
) -> CalcResult:
    """HAS-BLED score for bleeding risk in patients on anticoagulation (AF).

    Pisters R et al. Chest. 2010;138(5):1093-1100.

    Score ≥3: High bleeding risk — close monitoring or consider alternatives.
    Does NOT contraindicate anticoagulation alone.

    Parameters
    ----------
    hypertension       : uncontrolled hypertension (SBP >160 mmHg) [1 pt]
    renal_liver_disease: 0=none / 1=one / 2=both [1 pt each, max 2]
    stroke             : stroke history [1 pt]
    bleeding           : prior bleeding history or predisposition [1 pt]
    labile_inr         : labile INR (TTR <60%) [1 pt]
    elderly            : age ≥65 years [1 pt]
    drugs_alcohol      : concomitant antiplatelet/NSAID (1 pt) + alcohol (1 pt) [max 2]
    """
    score = 0
    if hypertension:
        score += 1
    score += min(int(renal_liver_disease), 2)
    if stroke:
        score += 1
    if bleeding:
        score += 1
    if labile_inr:
        score += 1
    if elderly:
        score += 1
    score += min(int(drugs_alcohol), 2)

    # Bleeding rate per 100 patient-years (Pisters 2010)
    bleed_table = {0: 1.13, 1: 1.02, 2: 1.88, 3: 3.74, 4: 8.70, 5: 12.50, 6: 0.0, 7: 0.0, 8: 0.0, 9: 0.0}
    bleed_rate = bleed_table.get(score, 12.50)

    if score >= 3:
        cat = "高出血リスク"
        interp = (
            f"HAS-BLED = {score} — 年間大出血率 ≈ {bleed_rate} 件/100患者年。"
            " 高出血リスク。"
        )
        rec = (
            "抗凝固療法を禁忌とはしない（血栓リスクが通常優位）。"
            "修正可能因子（血圧コントロール・INR安定化・抗血小板薬見直し）を積極的に改善。"
            "月1回の出血モニタリング。"
        )
    elif score >= 1:
        cat = "中出血リスク"
        interp = (
            f"HAS-BLED = {score} — 年間大出血率 ≈ {bleed_rate} 件/100患者年。"
        )
        rec = "抗凝固療法継続。修正可能因子の改善と定期モニタリング。"
    else:
        cat = "低出血リスク"
        interp = f"HAS-BLED = {score} — 年間大出血率 ≈ {bleed_rate} 件/100患者年。低リスク。"
        rec = "抗凝固療法安全に使用可能。定期フォローアップ継続。"

    return CalcResult(
        value=float(score),
        unit="点",
        category=cat,
        interpretation=interp,
        recommendation=rec,
        formula=(
            "高血圧(1)+腎・肝障害(各1)+脳卒中(1)+出血既往(1)"
            "+不安定INR(1)+高齢≥65(1)+薬剤/アルコール(各1)"
        ),
    )


# ================================================================== #
# __main__ — demonstration block
# ================================================================== #

if __name__ == "__main__":
    SEP = "=" * 62

    def show(title: str, result: CalcResult) -> None:
        print(f"\n{SEP}")
        print(f"  {title}")
        print(SEP)
        print(f"  値    : {result.value} {result.unit}")
        print(f"  分類  : {result.category}")
        print(f"  解釈  : {result.interpretation}")
        print(f"  推奨  : {result.recommendation}")
        print(f"  式    : {result.formula}")

    # 1. BSA
    show("1. 体表面積 (Mosteller BSA)", calc_bsa(170, 70))

    # 2. BMI
    show("2. BMI (WHO + アジア太平洋)", calc_bmi(80, 170))

    # 3. eGFR CKD-EPI 2021
    show("3. eGFR (CKD-EPI 2021)", calc_egfr_ckdepi(1.5, 65, "M"))

    # 4. CrCl Cockcroft-Gault
    show("4. CrCl (Cockcroft-Gault)", calc_crcl_cockroft_gault(1.5, 65, 70, "M", 170))

    # 5. Corrected Calcium
    show("5. 補正Ca (アルブミン補正)", calc_corrected_calcium(7.8, 2.5))

    # 6. Anion Gap
    show("6. アニオンギャップ", calc_anion_gap(140, 100, 10, 3.2))

    # 7. Osmolal Gap
    show("7. 浸透圧ギャップ", calc_osmolal_gap(142, 90, 20, 310))

    # 8. FENa
    show("8. FENa (腎前性/腎性判定)", calc_fena(15, 1.8, 140, 80))

    # 9. QTc
    show("9. QTc (Bazett)", calc_qtc(480, 720, "bazett"))
    show("9b. QTc (Fredericia)", calc_qtc(480, 720, "fredericia"))

    # 10. PBW
    show("10. 予測体重 (人工呼吸器設定)", calc_predicted_body_weight(175, "M"))

    # 11. Alvarado (Appendicitis)
    show(
        "11. Alvarado (虫垂炎スコア)",
        calc_alvarado(
            migrating_pain=True, anorexia=True, nausea_vomiting=True,
            rb_tenderness=True, rebound_tenderness=True, elevated_temp=True,
            leukocytosis=True, left_shift=False,
        ),
    )

    # 12. LRINEC (Necrotizing Fasciitis)
    show(
        "12. LRINEC (壊死性筋膜炎)",
        calc_lrinec(crp=200, wbc=28, hb=10, na=132, cr=1.8, glucose=200),
    )

    # 13. SCORTEN (SJS/TEN)
    show(
        "13. SCORTEN (SJS/TEN 予後)",
        calc_scorten(age=68, hr=125, malignancy=True, bsa_pct=25,
                     bun=35, bicarb=17, glucose=280),
    )

    # 14. Revised Trauma Score
    show("14. 外傷修正スコア (RTS)", calc_rts(sbp=85, rr=28, gcs=10))

    # 15. Wells DVT
    show(
        "15. Wells DVT スコア",
        calc_wells_dvt(
            active_cancer=True, paralysis=False, bedridden=True,
            local_tenderness=True, leg_swelling=True, pitting_edema=True,
            collateral_veins=False, previous_dvt=False, alternative_dx=False,
        ),
    )

    # 16. TIMI NSTEMI
    show(
        "16. TIMI NSTEMI/UA スコア",
        calc_timi_nstemi(
            age65=True, cad_markers=2, st_deviation=True,
            severe_angina=True, aspirin=True, elevated_markers=True,
            risk_factors=3,
        ),
    )

    # 17. GRACE ACS
    show(
        "17. GRACE ACS スコア",
        calc_grace_acs(
            age=72, hr=105, sbp=95, creatinine=1.8,
            cardiac_arrest=False, st_deviation=True,
            elevated_enzymes=True, killip_class=2,
        ),
    )

    # 18. HAS-BLED
    show(
        "18. HAS-BLED 出血リスク",
        calc_has_bled(
            hypertension=True, renal_liver_disease=1, stroke=True,
            bleeding=False, labile_inr=True, elderly=True,
            drugs_alcohol=1,
        ),
    )

    print(f"\n{SEP}")
    print("  全 18 計算機のデモ完了。")
    print(SEP)
