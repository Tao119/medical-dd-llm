"""
clinical/risk_scores.py — Clinical Risk Score Calculators

以下のスコアを実装:
  - CURB-65   (市中肺炎の重症度)
  - qSOFA     (敗血症スクリーニング)
  - HEART     (胸痛患者の MACE リスク)
  - SOFA      (臓器不全スコア、簡易版)
  - PSI/PORT  (肺炎重症度指数、簡易版)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


# ===========================================================================
# 共通データモデル
# ===========================================================================

@dataclass
class ScoreResult:
    score: int
    category: str
    recommendation: str
    interpretation: str
    components: dict = field(default_factory=dict)  # サブスコア内訳


# ===========================================================================
# CURB-65
# ===========================================================================

def calc_curb65(
    *,
    confusion: bool = False,      # C: 意識障害
    bun_mg_dl: float | None = None,  # U: BUN mg/dL (>19 mg/dL = 7 mmol/L)
    bun_mmol_l: float | None = None, # U: BUN mmol/L (>7)
    rr: float | None = None,      # R: 呼吸数 /min (≥30)
    sbp: float | None = None,     # B: 収縮期血圧 mmHg (<90)
    dbp: float | None = None,     # B: 拡張期血圧 mmHg (≤60)
    age: int | None = None,       # 65: 年齢 (≥65)
) -> ScoreResult:
    """CURB-65 スコアを計算する。

    スコア 0-1: 外来治療可
    スコア   2: 入院加療考慮
    スコア 3+: ICU 入院考慮（30日死亡率 14-40%）

    Parameters
    ----------
    confusion : bool
        新規発症の意識変容
    bun_mg_dl : float | None
        BUN (mg/dL); 19 mg/dL = 7 mmol/L
    bun_mmol_l : float | None
        BUN (mmol/L); mg/dL より優先
    rr : float | None
        呼吸数 (/min)
    sbp : float | None
        収縮期血圧 (mmHg)
    dbp : float | None
        拡張期血圧 (mmHg)
    age : int | None
        年齢 (歳)
    """
    components: dict[str, int | None] = {}

    # C
    c = int(confusion)
    components["C (意識障害)"] = c

    # U — どちらかの単位を受け付ける
    if bun_mmol_l is not None:
        u = int(bun_mmol_l > 7.0)
        components["U (BUN>7mmol/L)"] = u
    elif bun_mg_dl is not None:
        u = int(bun_mg_dl > 19.0)
        components["U (BUN>19mg/dL)"] = u
    else:
        u = 0
        components["U (BUN: データなし)"] = None

    # R
    if rr is not None:
        r = int(rr >= 30)
        components["R (RR≥30/min)"] = r
    else:
        r = 0
        components["R (RR: データなし)"] = None

    # B
    b_sbp = sbp is not None and sbp < 90
    b_dbp = dbp is not None and dbp <= 60
    b = int(b_sbp or b_dbp)
    components["B (低血圧)"] = b

    # 65
    if age is not None:
        age65 = int(age >= 65)
        components["65 (年齢≥65歳)"] = age65
    else:
        age65 = 0
        components["65 (年齢: データなし)"] = None

    score = c + u + r + b + age65

    if score <= 1:
        category = "低リスク"
        recommendation = "外来治療を考慮。経口抗菌薬で管理可能。"
        interpretation = "30日死亡率 約1-2%。外来フォローアップで対応可。"
    elif score == 2:
        category = "中等リスク"
        recommendation = "入院加療を考慮。短期入院または密な外来管理。"
        interpretation = "30日死亡率 約9%。入院での経過観察を推奨。"
    elif score == 3:
        category = "高リスク"
        recommendation = "入院加療。重症肺炎として管理。"
        interpretation = "30日死亡率 約14-17%。ICU 転科基準を評価。"
    else:
        category = "最重症"
        recommendation = "ICU 入院を強く考慮。集中治療管理が必要。"
        interpretation = f"30日死亡率 約40%（スコア {score}）。緊急介入を要する。"

    return ScoreResult(
        score=score,
        category=category,
        recommendation=recommendation,
        interpretation=interpretation,
        components=components,
    )


# ===========================================================================
# qSOFA
# ===========================================================================

def calc_qsofa(
    *,
    rr: float | None = None,          # ≥22 /min で1点
    altered_consciousness: bool = False,  # GCS < 15 で1点
    sbp: float | None = None,          # ≤100 mmHg で1点
    gcs: int | None = None,            # GCS 値でも判定可
) -> ScoreResult:
    """qSOFA スコアを計算する。

    ≥2点: 敗血症による臓器障害ハイリスク

    Parameters
    ----------
    rr : float | None
        呼吸数 (/min)
    altered_consciousness : bool
        意識変容あり (GCS < 15)
    sbp : float | None
        収縮期血圧 (mmHg)
    gcs : int | None
        GCS 値 (altered_consciousness より優先)
    """
    components: dict[str, int | None] = {}

    # RR
    if rr is not None:
        rr_pt = int(rr >= 22)
        components[f"呼吸数 {rr}/min (≥22で1点)"] = rr_pt
    else:
        rr_pt = 0
        components["呼吸数 (データなし)"] = None

    # 意識変容
    if gcs is not None:
        ac_pt = int(gcs < 15)
        components[f"GCS {gcs} (<15で1点)"] = ac_pt
    else:
        ac_pt = int(altered_consciousness)
        components[f"意識変容 ({'あり' if altered_consciousness else 'なし'})"] = ac_pt

    # SBP
    if sbp is not None:
        sbp_pt = int(sbp <= 100)
        components[f"SBP {sbp}mmHg (≤100で1点)"] = sbp_pt
    else:
        sbp_pt = 0
        components["収縮期血圧 (データなし)"] = None

    score = rr_pt + ac_pt + sbp_pt

    if score >= 2:
        category = "高リスク"
        recommendation = "敗血症ハイリスク: 血液培養2セット・乳酸値測定・輸液負荷・抗菌薬投与を至急開始。ICU 入室評価。"
        interpretation = "院内死亡リスク 3倍以上。Sepsis-3 基準に基づく臓器障害を疑う。"
    elif score == 1:
        category = "要注意"
        recommendation = "敗血症の可能性あり。バイタルサインの頻回モニタリングと原因検索を継続。"
        interpretation = "低リスクだが感染源の管理と経過観察を怠らないこと。"
    else:
        category = "低リスク"
        recommendation = "現時点で敗血症の緊急徴候なし。定期的なバイタルモニタリングを継続。"
        interpretation = "qSOFA 陰性でも敗血症を除外できない。臨床的判断を優先すること。"

    return ScoreResult(
        score=score,
        category=category,
        recommendation=recommendation,
        interpretation=interpretation,
        components=components,
    )


# ===========================================================================
# HEART スコア
# ===========================================================================

class HeartHistory(int, Enum):
    """既往歴・症状の疑わしさ"""
    SLIGHTLY_SUSPICIOUS = 0   # 軽度疑い（非典型的胸痛）
    MODERATE = 1              # 中等度疑い
    HIGHLY_SUSPICIOUS = 2     # 高度疑い（典型的胸痛）


class HeartECG(int, Enum):
    """心電図所見"""
    NORMAL = 0              # 正常
    NON_SPECIFIC = 1        # 非特異的変化
    SIGNIFICANT = 2         # LBBB/ST低下/T波逆転


class HeartAge(int, Enum):
    """年齢カテゴリー"""
    YOUNG = 0    # <45 歳
    MIDDLE = 1   # 45-64 歳
    ELDERLY = 2  # ≥65 歳


class HeartRiskFactors(int, Enum):
    """冠危険因子の数"""
    NONE = 0           # なし
    ONE_OR_TWO = 1     # 1-2個
    THREE_OR_MORE = 2  # ≥3個または既知の冠動脈疾患


class HeartTroponin(int, Enum):
    """トロポニン値"""
    NORMAL = 0           # ≤ 正常上限
    ONE_TO_THREE = 1     # 1-3倍
    MORE_THAN_THREE = 2  # >3倍


def calc_heart_score(
    *,
    history: HeartHistory | int,
    ecg: HeartECG | int,
    age: HeartAge | int | None = None,
    age_years: int | None = None,
    risk_factors: HeartRiskFactors | int,
    troponin: HeartTroponin | int,
) -> ScoreResult:
    """HEART スコアを計算する。

    MACE (主要心臓有害事象) の 6 週間リスクを推定。

    Parameters
    ----------
    history : HeartHistory | int
        0=軽度疑い, 1=中等度, 2=高度疑い
    ecg : HeartECG | int
        0=正常, 1=非特異的変化, 2=有意な変化
    age : HeartAge | int | None
        0=<45歳, 1=45-64歳, 2=≥65歳
    age_years : int | None
        実年齢 (歳) を直接指定する場合 age より優先
    risk_factors : HeartRiskFactors | int
        0=なし, 1=1-2個, 2=≥3個/既知CAD
    troponin : HeartTroponin | int
        0=正常以下, 1=1-3倍, 2=>3倍
    """
    # 年齢カテゴリーを実年齢から決定
    if age_years is not None:
        if age_years >= 65:
            age_score = 2
        elif age_years >= 45:
            age_score = 1
        else:
            age_score = 0
    elif age is not None:
        age_score = int(age)
    else:
        raise ValueError("age または age_years のどちらかを指定してください")

    h = int(history)
    e = int(ecg)
    r = int(risk_factors)
    t = int(troponin)

    score = h + e + age_score + r + t

    components = {
        f"H (既往歴・疑い度 {h}点)": h,
        f"E (心電図 {e}点)": e,
        f"A (年齢 {age_score}点)": age_score,
        f"R (危険因子 {r}点)": r,
        f"T (トロポニン {t}点)": t,
    }

    if score <= 3:
        category = "低リスク"
        mace_risk = "1.7%"
        recommendation = (
            "6週間 MACE リスク低。早期退院・外来フォローを検討。"
            "2時間後トロポニン再検で陰性なら帰宅可。"
        )
        interpretation = f"HEART スコア {score}/10。MACE 発生率 約{mace_risk}。"
    elif score <= 6:
        category = "中リスク"
        mace_risk = "12%"
        recommendation = (
            "6週間 MACE リスク中等度。入院・心臓専門医コンサルト・連続トロポニン測定を推奨。"
            "負荷試験または冠動脈 CT を考慮。"
        )
        interpretation = f"HEART スコア {score}/10。MACE 発生率 約{mace_risk}。"
    else:
        category = "高リスク"
        mace_risk = "65%"
        recommendation = (
            "6週間 MACE リスク高。早期侵襲的戦略（心臓カテーテル）を強く推奨。"
            "ICU/CCU モニタリング、循環器科緊急コンサルト。"
        )
        interpretation = f"HEART スコア {score}/10。MACE 発生率 約{mace_risk}。"

    return ScoreResult(
        score=score,
        category=category,
        recommendation=recommendation,
        interpretation=interpretation,
        components=components,
    )


# ===========================================================================
# SOFA スコア (簡易版)
# ===========================================================================

def calc_sofa(
    *,
    pao2_fio2: float | None = None,     # 呼吸: PaO2/FiO2 比
    spo2_fio2: float | None = None,     # PaO2 未測定時の SpO2/FiO2 代替
    platelets: float | None = None,     # 凝固: 血小板数 (×10³/μL)
    bilirubin: float | None = None,     # 肝臓: 総ビリルビン (mg/dL)
    map_mmhg: float | None = None,      # 循環: 平均動脈圧 (mmHg)
    on_vasopressors: bool = False,       # 昇圧剤使用中
    dopamine_dose: float | None = None, # ドパミン用量 (μg/kg/min)
    gcs: int | None = None,             # 神経: GCS
    creatinine: float | None = None,    # 腎臓: クレアチニン (mg/dL)
    urine_output_ml_day: float | None = None,  # 尿量 (mL/日)
) -> ScoreResult:
    """SOFA スコア (Sequential Organ Failure Assessment) を計算する。

    各臓器 0-4 点, 合計 0-24 点。
    スコアが高いほど臓器障害が重篤。

    Parameters
    ----------
    pao2_fio2 : float | None
        呼吸: PaO2/FiO2 比 (mmHg)
    spo2_fio2 : float | None
        PaO2 代替: SpO2/FiO2 比 (>315 ≒ PaO2/FiO2 >400)
    platelets : float | None
        凝固: 血小板数 (×10³/μL)
    bilirubin : float | None
        肝機能: 総ビリルビン (mg/dL)
    map_mmhg : float | None
        循環: 平均動脈圧 (mmHg)
    on_vasopressors : bool
        昇圧剤を使用中か
    dopamine_dose : float | None
        ドパミン投与量 (μg/kg/min)
    gcs : int | None
        Glasgow Coma Scale (3-15)
    creatinine : float | None
        血清クレアチニン (mg/dL)
    urine_output_ml_day : float | None
        24 時間尿量 (mL)
    """
    components: dict[str, int | None] = {}

    # --- 呼吸 (PaO2/FiO2 または SpO2/FiO2) ---
    if pao2_fio2 is not None:
        if pao2_fio2 < 100:
            resp = 4
        elif pao2_fio2 < 200:
            resp = 3
        elif pao2_fio2 < 300:
            resp = 2
        elif pao2_fio2 < 400:
            resp = 1
        else:
            resp = 0
        components[f"呼吸 PaO2/FiO2={pao2_fio2:.0f}"] = resp
    elif spo2_fio2 is not None:
        # SpO2/FiO2 → 近似変換 (Pandharipande 2010)
        # >315: SOFA 0,  ≤315: 1,  ≤235: 2,  ≤150: 3,  ≤89: 4
        if spo2_fio2 <= 89:
            resp = 4
        elif spo2_fio2 <= 150:
            resp = 3
        elif spo2_fio2 <= 235:
            resp = 2
        elif spo2_fio2 <= 315:
            resp = 1
        else:
            resp = 0
        components[f"呼吸 SpO2/FiO2={spo2_fio2:.0f}(近似)"] = resp
    else:
        resp = 0
        components["呼吸 (データなし)"] = None

    # --- 凝固 (血小板) ---
    if platelets is not None:
        if platelets < 20:
            coag = 4
        elif platelets < 50:
            coag = 3
        elif platelets < 100:
            coag = 2
        elif platelets < 150:
            coag = 1
        else:
            coag = 0
        components[f"凝固 血小板={platelets:.0f}×10³/μL"] = coag
    else:
        coag = 0
        components["凝固 (データなし)"] = None

    # --- 肝臓 (ビリルビン) ---
    if bilirubin is not None:
        if bilirubin >= 12.0:
            liver = 4
        elif bilirubin >= 6.0:
            liver = 3
        elif bilirubin >= 2.0:
            liver = 2
        elif bilirubin >= 1.2:
            liver = 1
        else:
            liver = 0
        components[f"肝臓 Bil={bilirubin}mg/dL"] = liver
    else:
        liver = 0
        components["肝臓 (データなし)"] = None

    # --- 循環 ---
    if on_vasopressors or dopamine_dose is not None:
        if dopamine_dose is not None and dopamine_dose > 15:
            cardio = 4
        elif dopamine_dose is not None and dopamine_dose > 5:
            cardio = 3
        elif on_vasopressors:
            cardio = 3
        else:
            cardio = 2
        components["循環 (昇圧剤使用中)"] = cardio
    elif map_mmhg is not None and map_mmhg < 70:
        cardio = 1
        components[f"循環 MAP={map_mmhg}mmHg"] = cardio
    else:
        cardio = 0
        label = f"循環 MAP={map_mmhg}mmHg" if map_mmhg is not None else "循環 (データなし)"
        components[label] = cardio if map_mmhg is not None else None

    # --- 神経 (GCS) ---
    if gcs is not None:
        if gcs < 6:
            neuro = 4
        elif gcs < 10:
            neuro = 3
        elif gcs < 13:
            neuro = 2
        elif gcs < 15:
            neuro = 1
        else:
            neuro = 0
        components[f"神経 GCS={gcs}"] = neuro
    else:
        neuro = 0
        components["神経 (データなし)"] = None

    # --- 腎臓 (Cr / 尿量) ---
    if creatinine is not None or urine_output_ml_day is not None:
        cr_score = 0
        if creatinine is not None:
            if creatinine >= 5.0:
                cr_score = 4
            elif creatinine >= 3.5:
                cr_score = 3
            elif creatinine >= 2.0:
                cr_score = 2
            elif creatinine >= 1.2:
                cr_score = 1
        uo_score = 0
        if urine_output_ml_day is not None:
            if urine_output_ml_day < 200:
                uo_score = 4
            elif urine_output_ml_day < 500:
                uo_score = 3
        renal = max(cr_score, uo_score)
        cr_str = f"Cr={creatinine}" if creatinine is not None else ""
        uo_str = f"UO={urine_output_ml_day:.0f}mL/日" if urine_output_ml_day is not None else ""
        components[f"腎臓 {cr_str} {uo_str}".strip()] = renal
    else:
        renal = 0
        components["腎臓 (データなし)"] = None

    score = resp + coag + liver + cardio + neuro + renal

    # 予後推定 (ICU 患者の院内死亡率)
    if score >= 11:
        category = "重篤"
        mortality = ">90%"
        recommendation = "最大限の集中治療管理。家族へのインフォームドコンセントを考慮。"
    elif score >= 9:
        category = "高度臓器障害"
        mortality = "40-50%"
        recommendation = "ICU 入室・多臓器サポート（人工呼吸器・CRRT 等）を検討。"
    elif score >= 6:
        category = "中等度臓器障害"
        mortality = "20-33%"
        recommendation = "高度モニタリング・臓器保護療法を継続。ICU 管理を推奨。"
    elif score >= 3:
        category = "軽度臓器障害"
        mortality = "6-10%"
        recommendation = "入院管理継続。スコア推移を 24 時間ごとに評価。"
    else:
        category = "臓器障害なし〜軽微"
        mortality = "<10%"
        recommendation = "現時点での重篤な臓器障害なし。定期的再評価を継続。"

    return ScoreResult(
        score=score,
        category=category,
        recommendation=recommendation,
        interpretation=f"SOFA スコア {score}/24。推定院内死亡率 {mortality}。",
        components=components,
    )


# ===========================================================================
# PSI/PORT スコア (簡易版)
# ===========================================================================

def calc_psi_port(
    *,
    age: int,
    sex_female: bool = False,
    nursing_home: bool = False,
    # 既往疾患
    neoplasm: bool = False,
    liver_disease: bool = False,
    chf: bool = False,           # うっ血性心不全
    cerebrovascular: bool = False,
    renal_disease: bool = False,
    # バイタルサイン
    altered_mental_status: bool = False,
    rr: float | None = None,     # 呼吸数 /min (≥30 = +20)
    sbp: float | None = None,    # 収縮期血圧 mmHg (<90 = +20)
    temp: float | None = None,   # 体温 ℃ (<35 or ≥40 = +15)
    hr: float | None = None,     # 心拍数 /min (≥125 = +10)
    # 検査値
    ph: float | None = None,     # 動脈血 pH (<7.35 = +30)
    bun_mg_dl: float | None = None,  # BUN (≥30 = +20)
    na: float | None = None,     # Na mEq/L (<130 = +20)
    glucose: float | None = None,    # 血糖 mg/dL (≥250 = +10)
    hematocrit: float | None = None, # Ht % (<30 = +10)
    pao2: float | None = None,   # PaO2 mmHg (<60 = +10) または
    spo2: float | None = None,   # SpO2 % (<90 = +10)
    pleural_effusion: bool = False,  # 胸水あり (+10)
) -> ScoreResult:
    """PSI/PORT スコア (Pneumonia Severity Index) を計算する。

    クラス I: 低リスク (外来)
    クラス II (≤70点): 低リスク (外来)
    クラス III (71-90): 低〜中リスク (短期入院)
    クラス IV (91-130): 中〜高リスク (入院)
    クラス V (>130): 高リスク (ICU)
    """
    score = 0
    components: dict[str, int] = {}

    # 年齢
    age_pts = age - (10 if sex_female else 0)
    score += age_pts
    components[f"年齢 {age}歳{'(女性 -10)' if sex_female else ''}"] = age_pts

    if nursing_home:
        score += 10
        components["施設入居 (+10)"] = 10

    # 既往疾患
    if neoplasm:
        score += 30
        components["悪性腫瘍 (+30)"] = 30
    if liver_disease:
        score += 20
        components["肝疾患 (+20)"] = 20
    if chf:
        score += 10
        components["うっ血性心不全 (+10)"] = 10
    if cerebrovascular:
        score += 10
        components["脳血管疾患 (+10)"] = 10
    if renal_disease:
        score += 10
        components["腎疾患 (+10)"] = 10

    # バイタル
    if altered_mental_status:
        score += 20
        components["意識障害 (+20)"] = 20
    if rr is not None and rr >= 30:
        score += 20
        components[f"RR {rr}/min≥30 (+20)"] = 20
    if sbp is not None and sbp < 90:
        score += 20
        components[f"SBP {sbp}mmHg<90 (+20)"] = 20
    if temp is not None and (temp < 35.0 or temp >= 40.0):
        score += 15
        components[f"体温 {temp}℃ 異常 (+15)"] = 15
    if hr is not None and hr >= 125:
        score += 10
        components[f"HR {hr}/min≥125 (+10)"] = 10

    # 検査値
    if ph is not None and ph < 7.35:
        score += 30
        components[f"pH {ph}<7.35 (+30)"] = 30
    if bun_mg_dl is not None and bun_mg_dl >= 30:
        score += 20
        components[f"BUN {bun_mg_dl}mg/dL≥30 (+20)"] = 20
    if na is not None and na < 130:
        score += 20
        components[f"Na {na}mEq/L<130 (+20)"] = 20
    if glucose is not None and glucose >= 250:
        score += 10
        components[f"Glu {glucose}mg/dL≥250 (+10)"] = 10
    if hematocrit is not None and hematocrit < 30:
        score += 10
        components[f"Ht {hematocrit}%<30 (+10)"] = 10
    # PaO2 or SpO2
    hypoxia = (pao2 is not None and pao2 < 60) or (spo2 is not None and spo2 < 90)
    if hypoxia:
        score += 10
        components["低酸素 PaO2<60 or SpO2<90 (+10)"] = 10
    if pleural_effusion:
        score += 10
        components["胸水 (+10)"] = 10

    if score <= 70:
        psi_class = "II"
        category = "低リスク"
        mortality = "<1%"
        recommendation = "外来治療。経口抗菌薬 5-7 日。外来フォローアップを手配。"
    elif score <= 90:
        psi_class = "III"
        category = "低〜中リスク"
        mortality = "2.8%"
        recommendation = "短期入院または 24 時間観察入院を検討。"
    elif score <= 130:
        psi_class = "IV"
        category = "中〜高リスク"
        mortality = "8.2%"
        recommendation = "入院加療。静注抗菌薬・酸素療法・全身管理。"
    else:
        psi_class = "V"
        category = "高リスク"
        mortality = "29.2%"
        recommendation = "ICU 入院を強く推奨。集中治療管理、早期挿管を考慮。"

    return ScoreResult(
        score=score,
        category=f"クラス {psi_class} ({category})",
        recommendation=recommendation,
        interpretation=f"PSI/PORT スコア {score}。推定 30 日死亡率 {mortality}。",
        components=components,
    )


# ===========================================================================
# デモ
# ===========================================================================

if __name__ == "__main__":
    def print_result(name: str, result: ScoreResult) -> None:
        print(f"\n{'=' * 60}")
        print(f"スコア名: {name}")
        print(f"スコア : {result.score}")
        print(f"カテゴリ: {result.category}")
        print(f"推奨   : {result.recommendation}")
        print(f"解釈   : {result.interpretation}")
        if result.components:
            print("内訳:")
            for k, v in result.components.items():
                print(f"  {k}: {v}")

    # CURB-65: 80歳, 呼吸数32, 低血圧あり, BUN 25mg/dL
    curb = calc_curb65(
        confusion=False,
        bun_mg_dl=25.0,
        rr=32,
        sbp=85,
        age=80,
    )
    print_result("CURB-65", curb)

    # qSOFA: RR 24, SBP 95, GCS 14
    qsofa = calc_qsofa(rr=24, sbp=95, gcs=14)
    print_result("qSOFA", qsofa)

    # HEART: 典型的胸痛, 有意な心電図変化, 68歳男性, 高血圧+糖尿病, トロポニン2倍
    heart = calc_heart_score(
        history=HeartHistory.HIGHLY_SUSPICIOUS,
        ecg=HeartECG.SIGNIFICANT,
        age_years=68,
        risk_factors=HeartRiskFactors.ONE_OR_TWO,
        troponin=HeartTroponin.ONE_TO_THREE,
    )
    print_result("HEART スコア", heart)

    # SOFA: PaO2/FiO2=180, 血小板80, Bil=3.5, MAP=62, GCS=12, Cr=2.5
    sofa = calc_sofa(
        pao2_fio2=180,
        platelets=80,
        bilirubin=3.5,
        map_mmhg=62,
        gcs=12,
        creatinine=2.5,
    )
    print_result("SOFA スコア", sofa)

    # PSI/PORT: 72歳女性, 施設入居, 糖尿病なし, 呼吸数28, BUN 32, SpO2 88%
    psi = calc_psi_port(
        age=72,
        sex_female=True,
        nursing_home=True,
        rr=28,
        bun_mg_dl=32,
        spo2=88,
    )
    print_result("PSI/PORT スコア", psi)
