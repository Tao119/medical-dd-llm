"""
clinical/pediatric.py — Pediatric Clinical Decision Support

小児科モード:
  - 年齢別バイタルサイン正常値（日本小児科学会 2023 準拠）
  - PEWS（Pediatric Early Warning Score）
  - 体重推定（Holliday-Segar 法）
  - 小児薬用量計算（体重ベース）
  - 小児維持輸液計算
  - 年齢別鑑別診断確率調整
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import NamedTuple


# ===========================================================================
# 年齢グループ定義
# ===========================================================================

class AgeGroup(str, Enum):
    NEONATE   = "neonate"    # <28日
    INFANT    = "infant"     # 1-12ヶ月
    TODDLER   = "toddler"    # 1-3歳
    PRESCHOOL = "preschool"  # 3-6歳
    SCHOOL    = "school"     # 6-12歳
    ADOLESCENT = "adolescent" # 12-18歳


def classify_age(age_months: int) -> AgeGroup:
    """月齢から年齢グループを返す。"""
    if age_months < 1:
        return AgeGroup.NEONATE
    elif age_months < 12:
        return AgeGroup.INFANT
    elif age_months < 36:
        return AgeGroup.TODDLER
    elif age_months < 72:
        return AgeGroup.PRESCHOOL
    elif age_months < 144:
        return AgeGroup.SCHOOL
    else:
        return AgeGroup.ADOLESCENT


# ===========================================================================
# 正常範囲テーブル（日本小児科学会 2023）
# ===========================================================================

class _VRange(NamedTuple):
    lo: float
    hi: float


_HR_NORMS: dict[AgeGroup, _VRange] = {
    AgeGroup.NEONATE:    _VRange(120, 160),
    AgeGroup.INFANT:     _VRange(100, 150),
    AgeGroup.TODDLER:    _VRange(90,  140),
    AgeGroup.PRESCHOOL:  _VRange(80,  130),
    AgeGroup.SCHOOL:     _VRange(70,  120),
    AgeGroup.ADOLESCENT: _VRange(60,  100),
}

_RR_NORMS: dict[AgeGroup, _VRange] = {
    AgeGroup.NEONATE:    _VRange(40, 60),
    AgeGroup.INFANT:     _VRange(30, 40),
    AgeGroup.TODDLER:    _VRange(25, 35),
    AgeGroup.PRESCHOOL:  _VRange(22, 34),
    AgeGroup.SCHOOL:     _VRange(18, 25),
    AgeGroup.ADOLESCENT: _VRange(12, 20),
}

_SBP_NORMS: dict[AgeGroup, _VRange] = {
    AgeGroup.NEONATE:    _VRange(60,  90),
    AgeGroup.INFANT:     _VRange(70,  100),
    AgeGroup.TODDLER:    _VRange(80,  110),
    AgeGroup.PRESCHOOL:  _VRange(80,  112),
    AgeGroup.SCHOOL:     _VRange(90,  120),
    AgeGroup.ADOLESCENT: _VRange(100, 130),
}

_SPO2_NORMAL = _VRange(95, 100)  # 全年齢共通
_TEMP_NORMAL = _VRange(36.0, 37.5)


# ===========================================================================
# データモデル
# ===========================================================================

@dataclass
class PediatricVitals:
    age_months: int
    weight_kg: float | None = None
    sbp: float | None = None
    hr: float | None = None
    rr: float | None = None
    spo2: float | None = None
    temp: float | None = None


@dataclass
class VitalAssessment:
    parameter: str
    value: float
    normal_range: str
    status: str         # "normal" | "mildly_abnormal" | "abnormal" | "critical"
    note: str


@dataclass
class PediatricVitalAssessmentResult:
    age_group: str
    age_months: int
    estimated_weight_kg: float | None
    assessments: list[VitalAssessment]
    alerts: list[str]
    pews_hint: str


def estimate_weight_kg(age_months: int) -> float | None:
    """
    体重推定:
      - 1-12ヶ月: (月齢/2) + 4 kg (近似値)
      - 1-12歳: 2×(年齢+4) kg
      - 12歳超: 50-70 kg (思春期個人差大のため None)
    """
    if age_months < 1:
        return 3.5      # 新生児平均
    if age_months <= 12:
        return round(age_months / 2 + 4, 1)
    age_years = age_months / 12
    if age_years <= 12:
        return round(2 * (age_years + 4), 1)
    return None


def _classify_vital(
    value: float,
    norm: _VRange,
    critical_lo_factor: float = 0.8,
    critical_hi_factor: float = 1.3,
) -> str:
    """バイタルの逸脱度を分類する。"""
    if value < norm.lo * critical_lo_factor or value > norm.hi * critical_hi_factor:
        return "critical"
    if value < norm.lo or value > norm.hi:
        return "abnormal"
    return "normal"


def assess_pediatric_vitals(pv: PediatricVitals) -> dict:
    """
    小児バイタルサインを年齢別正常値で評価する。

    Returns
    -------
    dict with keys:
        age_group, assessments, alerts, estimated_weight_kg,
        normal_ranges, overall_status
    """
    group = classify_age(pv.age_months)
    est_weight = pv.weight_kg if pv.weight_kg else estimate_weight_kg(pv.age_months)

    assessments: list[VitalAssessment] = []
    alerts: list[str] = []

    # --- 心拍数 ---
    if pv.hr is not None:
        hr_norm = _HR_NORMS[group]
        status = _classify_vital(pv.hr, hr_norm, 0.75, 1.35)
        note = ""
        if status == "critical" and pv.hr > hr_norm.hi * 1.35:
            note = "重篤な頻脈 — 敗血症・脱水・ショックを除外"
            alerts.append(f"[緊急] 心拍数 {pv.hr}/min — 重篤な頻脈")
        elif status == "critical" and pv.hr < hr_norm.lo * 0.75:
            note = "重篤な徐脈 — 迷走神経反射・低酸素・薬剤の可能性"
            alerts.append(f"[緊急] 心拍数 {pv.hr}/min — 重篤な徐脈")
        elif status == "abnormal":
            note = "正常範囲外 — 発熱・活動・不安でも増加"
        assessments.append(VitalAssessment(
            parameter="HR (心拍数)",
            value=pv.hr,
            normal_range=f"{hr_norm.lo}-{hr_norm.hi}/min",
            status=status,
            note=note,
        ))

    # --- 呼吸数 ---
    if pv.rr is not None:
        rr_norm = _RR_NORMS[group]
        status = _classify_vital(pv.rr, rr_norm, 0.7, 1.4)
        note = ""
        if status == "critical" and pv.rr > rr_norm.hi * 1.4:
            note = "重篤な頻呼吸 — 呼吸不全・肺炎・心不全を疑う"
            alerts.append(f"[緊急] 呼吸数 {pv.rr}/min — 重篤な頻呼吸")
        elif status == "critical" and pv.rr < rr_norm.lo * 0.7:
            note = "徐呼吸 — 中枢神経抑制・薬剤を疑う"
            alerts.append(f"[緊急] 呼吸数 {pv.rr}/min — 徐呼吸")
        elif status == "abnormal":
            note = "正常範囲外 — 発熱・運動・気道疾患で変動"
        assessments.append(VitalAssessment(
            parameter="RR (呼吸数)",
            value=pv.rr,
            normal_range=f"{rr_norm.lo}-{rr_norm.hi}/min",
            status=status,
            note=note,
        ))

    # --- 収縮期血圧 ---
    if pv.sbp is not None:
        sbp_norm = _SBP_NORMS[group]
        status = _classify_vital(pv.sbp, sbp_norm, 0.8, 1.3)
        note = ""
        if status == "critical" and pv.sbp < sbp_norm.lo * 0.8:
            note = "低血圧性ショック — 緊急輸液・昇圧薬を検討"
            alerts.append(f"[緊急] 収縮期血圧 {pv.sbp} mmHg — 低血圧性ショック")
        elif status == "abnormal" and pv.sbp < sbp_norm.lo:
            note = "低血圧 — 脱水・感染・出血を除外"
        elif status in ("abnormal", "critical") and pv.sbp > sbp_norm.hi:
            note = "高血圧 — 腎疾患・疼痛・不安を考慮"
        assessments.append(VitalAssessment(
            parameter="SBP (収縮期血圧)",
            value=pv.sbp,
            normal_range=f"{sbp_norm.lo}-{sbp_norm.hi} mmHg",
            status=status,
            note=note,
        ))

    # --- SpO2 ---
    if pv.spo2 is not None:
        if pv.spo2 < 90:
            status = "critical"
            alerts.append(f"[緊急] SpO2 {pv.spo2}% — 低酸素血症、酸素投与を開始")
            note = "重篤な低酸素血症 — 高流量酸素または補助換気を開始"
        elif pv.spo2 < 95:
            status = "abnormal"
            note = "低酸素血症 — 酸素投与・原因検索"
        else:
            status = "normal"
            note = ""
        assessments.append(VitalAssessment(
            parameter="SpO2",
            value=pv.spo2,
            normal_range="≥95%",
            status=status,
            note=note,
        ))

    # --- 体温 ---
    if pv.temp is not None:
        if pv.temp >= 38.0:
            if pv.temp >= 41.0:
                status = "critical"
                alerts.append(f"[緊急] 体温 {pv.temp}℃ — 重篤な高体温、熱射病/敗血症を疑う")
                note = "重篤な高体温"
            elif pv.temp >= 38.5:
                status = "abnormal"
                note = "発熱 — 感染症・川崎病等を検索"
            else:
                status = "abnormal"
                note = "微熱"
        elif pv.temp < 36.0:
            status = "abnormal" if pv.temp >= 35.0 else "critical"
            if pv.temp < 35.0:
                alerts.append(f"[緊急] 体温 {pv.temp}℃ — 低体温症")
            note = "低体温 — 環境・敗血症・中枢神経疾患を確認"
        else:
            status = "normal"
            note = ""
        assessments.append(VitalAssessment(
            parameter="体温",
            value=pv.temp,
            normal_range="36.0-37.5℃",
            status=status,
            note=note,
        ))

    # Overall status
    statuses = [a.status for a in assessments]
    if "critical" in statuses:
        overall = "critical"
    elif "abnormal" in statuses:
        overall = "abnormal"
    else:
        overall = "normal"

    return {
        "age_group": group.value,
        "age_months": pv.age_months,
        "estimated_weight_kg": est_weight,
        "assessments": assessments,
        "alerts": alerts,
        "overall_status": overall,
        "normal_ranges": {
            "HR": f"{_HR_NORMS[group].lo}-{_HR_NORMS[group].hi}/min",
            "RR": f"{_RR_NORMS[group].lo}-{_RR_NORMS[group].hi}/min",
            "SBP": f"{_SBP_NORMS[group].lo}-{_SBP_NORMS[group].hi} mmHg",
            "SpO2": "≥95%",
            "体温": "36.0-37.5℃",
        },
    }


# ===========================================================================
# PEWS — Pediatric Early Warning Score
# ===========================================================================

@dataclass
class PEWSInput:
    """PEWS 評価入力。各サブスコアは 0-4 の整数。"""
    # Behavior: 0=遊ぶ/正常, 1=眠っているが反応あり, 2=易刺激性, 3=反応低下, 4=無反応
    behavior: int = 0
    # Cardiovascular: 0=正常, 1=蒼白, 2=灰色, 3=灰色+頻脈, 4=灰色+ショック
    cardiovascular: int = 0
    # Respiratory: 0=正常, 1=軽度頻呼吸, 2=中等度, 3=重度/陥凹呼吸, 4=無呼吸
    respiratory: int = 0


@dataclass
class PEWSResult:
    total: int
    behavior: int
    cardiovascular: int
    respiratory: int
    risk_level: str        # "low" | "medium" | "high" | "critical"
    recommendation: str
    escalation_triggers: list[str]


_PEWS_BEHAVIOR_DESC = {
    0: "遊ぶ/正常",
    1: "眠っているが覚醒可能",
    2: "易刺激性",
    3: "反応低下",
    4: "無反応/昏睡",
}
_PEWS_CARDIO_DESC = {
    0: "皮膚色正常、毛細血管再充填時間 <2秒",
    1: "蒼白、毛細血管再充填時間 2-3秒",
    2: "灰色、毛細血管再充填時間 3-4秒",
    3: "灰色 + 年齢上限比 20% 超の頻脈",
    4: "灰色 + ショック（毛細血管再充填時間 >5秒）",
}
_PEWS_RESP_DESC = {
    0: "正常、補助筋使用なし",
    1: "軽度頻呼吸、補助筋使用なし",
    2: "中等度頻呼吸、一部補助筋使用",
    3: "重度頻呼吸、陥凹呼吸、鼻翼呼吸",
    4: "無呼吸、努力呼吸の減少",
}


def calc_pews(pews: PEWSInput) -> PEWSResult:
    """
    PEWS スコアを算出し、臨床的推奨を返す。

    スコア 0-1: Low risk — 定期モニタリング継続
    スコア 2-3: Medium risk — 担当医へ報告、評価頻度を上げる
    スコア 4-5: High risk — 上級医・PICU チームへ連絡
    スコア ≥6: Critical — 即時対応・蘇生チーム招集
    """
    # バリデーション
    for name, val in [("behavior", pews.behavior), ("cardiovascular", pews.cardiovascular),
                      ("respiratory", pews.respiratory)]:
        if not 0 <= val <= 4:
            raise ValueError(f"PEWS {name} must be 0-4, got {val}")

    total = pews.behavior + pews.cardiovascular + pews.respiratory

    if total <= 1:
        risk = "low"
        recommendation = "定期モニタリングを継続（4-8時間ごと）。異変時は再評価。"
    elif total <= 3:
        risk = "medium"
        recommendation = "担当医への報告。モニタリング頻度を上げる（1-2時間ごと）。IV アクセス確保を考慮。"
    elif total <= 5:
        risk = "high"
        recommendation = "上級医・PICU チームへ即時連絡。継続的モニタリング。バイタル 30 分ごと。"
    else:
        risk = "critical"
        recommendation = "[緊急] 蘇生チームを招集。PICU トリアージを実施。ABC 評価を直ちに開始。"

    escalation_triggers = []
    if pews.behavior >= 3:
        escalation_triggers.append(f"意識レベル低下: {_PEWS_BEHAVIOR_DESC[pews.behavior]}")
    if pews.cardiovascular >= 3:
        escalation_triggers.append(f"循環不全: {_PEWS_CARDIO_DESC[pews.cardiovascular]}")
    if pews.respiratory >= 3:
        escalation_triggers.append(f"呼吸不全: {_PEWS_RESP_DESC[pews.respiratory]}")
    if any(v == 4 for v in [pews.behavior, pews.cardiovascular, pews.respiratory]):
        escalation_triggers.insert(0, "サブスコア 4 は単独で蘇生チーム招集の適応")

    return PEWSResult(
        total=total,
        behavior=pews.behavior,
        cardiovascular=pews.cardiovascular,
        respiratory=pews.respiratory,
        risk_level=risk,
        recommendation=recommendation,
        escalation_triggers=escalation_triggers,
    )


# ===========================================================================
# 小児薬用量計算
# ===========================================================================

@dataclass
class PedsDose:
    drug: str
    indication: str
    dose_per_kg: str
    calculated_dose: str
    max_dose: str
    route: str
    frequency: str
    notes: list[str] = field(default_factory=list)
    age_restriction: str = ""


def pediatric_drug_dose(
    drug: str,
    weight_kg: float,
    age_months: int,
) -> PedsDose | None:
    """
    小児薬用量を体重あたりで計算する。

    Parameters
    ----------
    drug : str
        薬剤名（英語・日本語対応、大文字小文字不問）
    weight_kg : float
        体重 (kg)
    age_months : int
        月齢

    Returns
    -------
    PedsDose | None
        計算結果。未登録薬剤は None。
    """
    d = drug.lower().replace("-", "").replace(" ", "")

    # パラセタモール / アセトアミノフェン
    if d in ("paracetamol", "acetaminophen", "アセトアミノフェン", "カロナール"):
        dose_mg = min(15 * weight_kg, 1000)
        return PedsDose(
            drug="パラセタモール (アセトアミノフェン)",
            indication="解熱・鎮痛",
            dose_per_kg="15 mg/kg/回",
            calculated_dose=f"{dose_mg:.0f} mg/回",
            max_dose="1000 mg/回",
            route="経口/坐剤/IV",
            frequency="4-6 時間ごと（最大 5 回/日）",
            notes=["1 日最大 75 mg/kg または 4000 mg のいずれか少ない方"],
        )

    # イブプロフェン
    if d in ("ibuprofen", "イブプロフェン", "ブルフェン"):
        if age_months < 6:
            return PedsDose(
                drug="イブプロフェン",
                indication="（使用不可）",
                dose_per_kg="禁忌",
                calculated_dose="禁忌",
                max_dose="—",
                route="—",
                frequency="—",
                age_restriction="6 ヶ月未満は禁忌",
                notes=["6 ヶ月未満の乳児には使用しない"],
            )
        dose_lo = min(5 * weight_kg, 400)
        dose_hi = min(10 * weight_kg, 400)
        return PedsDose(
            drug="イブプロフェン",
            indication="解熱・鎮痛・抗炎症",
            dose_per_kg="5-10 mg/kg/回",
            calculated_dose=f"{dose_lo:.0f}-{dose_hi:.0f} mg/回",
            max_dose="400 mg/回",
            route="経口",
            frequency="6-8 時間ごと（食後）",
            age_restriction="6 ヶ月以上",
            notes=["食事と一緒に服用", "GI 出血リスクがある場合は回避"],
        )

    # アモキシシリン
    if d in ("amoxicillin", "アモキシシリン", "サワシリン", "パセトシン"):
        dose_lo = min(40 * weight_kg / 3, weight_kg * 30)  # /day ÷ 3
        dose_hi = min(90 * weight_kg / 3, weight_kg * 30)
        return PedsDose(
            drug="アモキシシリン",
            indication="細菌感染症（中耳炎・咽頭炎・肺炎等）",
            dose_per_kg="40-90 mg/kg/日（分 3）",
            calculated_dose=f"{dose_lo:.0f}-{dose_hi:.0f} mg/回（分 3）",
            max_dose="3000 mg/日（重症）",
            route="経口",
            frequency="8 時間ごと",
            notes=["軽症: 40 mg/kg/日、中耳炎・重症: 90 mg/kg/日"],
        )

    # アモキシシリン-クラブラン酸
    if d in ("amoxicillinclavulanate", "amoxiclavulanate", "augmentin",
             "アモキシシリンクラブラン酸", "オーグメンチン"):
        dose_lo = min(40 * weight_kg / 3, 500)
        dose_hi = min(90 * weight_kg / 3, 875)
        return PedsDose(
            drug="アモキシシリン-クラブラン酸",
            indication="β-ラクタマーゼ産生菌感染症（AOM・副鼻腔炎・皮膚軟部組織）",
            dose_per_kg="40-90 mg/kg/日（アモキシシリン成分）分 3",
            calculated_dose=f"{dose_lo:.0f}-{dose_hi:.0f} mg/回",
            max_dose="875/125 mg/回（成人量）",
            route="経口",
            frequency="8 時間ごと（12 時間ごと製剤もあり）",
            notes=["クラブラン酸による GI 副作用（下痢）に注意"],
        )

    # セフトリアキソン
    if d in ("ceftriaxone", "セフトリアキソン", "ロセフィン"):
        dose_lo = min(50 * weight_kg, 2000)
        dose_hi = min(100 * weight_kg, 4000)
        meningitis_dose = min(100 * weight_kg, 4000)
        return PedsDose(
            drug="セフトリアキソン",
            indication="重症細菌感染症・髄膜炎",
            dose_per_kg="50-100 mg/kg/日",
            calculated_dose=f"{dose_lo:.0f}-{dose_hi:.0f} mg/日（髄膜炎: {meningitis_dose:.0f} mg/日）",
            max_dose="4000 mg/日",
            route="IV/IM",
            frequency="24 時間ごと（髄膜炎は 12 時間ごと）",
            notes=["カルシウム含有製剤との混合禁忌（新生児）", "胆泥形成の可能性"],
        )

    # バンコマイシン
    if d in ("vancomycin", "バンコマイシン"):
        dose = 15 * weight_kg
        return PedsDose(
            drug="バンコマイシン",
            indication="MRSA・重症グラム陽性菌感染症",
            dose_per_kg="15 mg/kg/回",
            calculated_dose=f"{dose:.0f} mg/回",
            max_dose="最大 2500 mg/回（AUC/MIC で調整）",
            route="IV（60 分以上かけて緩徐投与）",
            frequency="6 時間ごと（腎機能に応じて調整）",
            notes=[
                "レッドマン症候群予防のため速度 10 mg/min 以下",
                "AUC/MIC 目標 400-600（TDM 必須）",
                "腎機能モニタリング必須",
            ],
        )

    # メチルプレドニゾロン
    if d in ("methylprednisolone", "メチルプレドニゾロン", "ソル・メドロール"):
        dose_lo = min(1 * weight_kg, 60)
        dose_hi = min(2 * weight_kg, 60)
        return PedsDose(
            drug="メチルプレドニゾロン",
            indication="急性喘息・炎症・クループ等",
            dose_per_kg="1-2 mg/kg/日",
            calculated_dose=f"{dose_lo:.0f}-{dose_hi:.0f} mg/日（分 1-2）",
            max_dose="60 mg/日",
            route="IV/経口",
            frequency="12-24 時間ごと",
            notes=["短期使用（3-5 日）では漸減不要のことが多い", "高血糖・感染リスクに注意"],
        )

    # サルブタモール MDI (急性喘息)
    if d in ("salbutamol", "albuterol", "サルブタモール", "アルブテロール", "ベネトリン"):
        return PedsDose(
            drug="サルブタモール (SABA)",
            indication="急性喘息発作",
            dose_per_kg="4-8 puff/回（体重非依存）",
            calculated_dose="4-8 puff/回（スペーサー使用）",
            max_dose="8 puff/回",
            route="吸入（MDI + スペーサー）",
            frequency="20 分ごと × 3 回 → 効果判定",
            notes=[
                "スペーサー必須（<6 歳は マスク付き）",
                "重症の場合はネブライザー 2.5-5 mg",
                "3 回後も改善なければ IV マグネシウムまたは ICU を考慮",
            ],
        )

    # エピネフリン (アナフィラキシー)
    if d in ("epinephrine", "adrenaline", "エピネフリン", "アドレナリン"):
        dose_mg = min(0.01 * weight_kg, 0.5)
        dose_mcg = dose_mg * 1000
        return PedsDose(
            drug="エピネフリン (アドレナリン)",
            indication="アナフィラキシー",
            dose_per_kg="0.01 mg/kg IM",
            calculated_dose=f"{dose_mg:.3f} mg ({dose_mcg:.0f} μg) IM",
            max_dose="0.5 mg/回",
            route="IM（大腿外側、中間広筋）",
            frequency="5-15 分後に効果不十分であれば繰り返し可",
            notes=[
                "エピペン 0.15 mg (15 kg 未満) または 0.3 mg (15 kg 以上)",
                "仰臥位または下肢挙上位",
                "IV ルート確保・補液を並行",
            ],
        )

    # ロラゼパム (痙攣)
    if d in ("lorazepam", "ロラゼパム", "ワイパックス"):
        dose_lo = min(0.05 * weight_kg, 4.0)
        dose_hi = min(0.1 * weight_kg, 4.0)
        return PedsDose(
            drug="ロラゼパム",
            indication="痙攣重積・急性痙攣",
            dose_per_kg="0.05-0.1 mg/kg IV",
            calculated_dose=f"{dose_lo:.2f}-{dose_hi:.2f} mg IV",
            max_dose="4 mg/回",
            route="IV（2 分かけて緩徐投与）",
            frequency="5-10 分後に反応なければ繰り返し（最大 2 回）",
            notes=[
                "IV なければジアゼパム直腸内投与 0.5 mg/kg を代替",
                "呼吸抑制モニタリング必須",
                "2 回投与後も効果なければ第二選択薬（レベチラセタム等）を考慮",
            ],
        )

    # ブドウ糖 (低血糖)
    if d in ("dextrose", "glucose", "dextrosew", "ブドウ糖", "グルコース", "d10w", "d10"):
        vol_lo = 2 * weight_kg
        vol_hi = 4 * weight_kg
        return PedsDose(
            drug="ブドウ糖 (D10W)",
            indication="症候性低血糖（血糖 <45 mg/dL）",
            dose_per_kg="2-4 mL/kg の D10W（グルコース 0.2-0.4 g/kg）",
            calculated_dose=f"{vol_lo:.0f}-{vol_hi:.0f} mL の D10W IV",
            max_dose="体重依存（上限なし、血糖値で評価）",
            route="IV（緩徐投与 1-5 分）",
            frequency="投与 15 分後に血糖再測定、必要に応じて繰り返し",
            notes=[
                "新生児は D10W で開始（高濃度ブドウ糖は血管刺激）",
                "血糖 >60 mg/dL を目標",
                "原因の検索（インスリン腫・先天性代謝異常等）",
            ],
        )

    return None


# ===========================================================================
# Holliday-Segar 維持輸液計算
# ===========================================================================

@dataclass
class FluidCalculation:
    weight_kg: float
    daily_ml: float
    hourly_rate_ml_h: float
    calculation_detail: str
    notes: list[str]


def holliday_segar(weight_kg: float) -> FluidCalculation:
    """
    Holliday-Segar 法で小児の維持輸液量を計算する。

    100 mL/kg for first 10 kg
     50 mL/kg for 10-20 kg
     20 mL/kg for >20 kg

    Maintenance rate (mL/h):
     4 mL/kg/h for first 10 kg
     2 mL/kg/h for 10-20 kg
     1 mL/kg/h for >20 kg
    """
    if weight_kg <= 0:
        raise ValueError("weight_kg must be positive")

    # 1日量
    if weight_kg <= 10:
        daily = 100 * weight_kg
        detail = f"100 × {weight_kg:.1f} = {daily:.0f} mL/日"
    elif weight_kg <= 20:
        daily = 1000 + 50 * (weight_kg - 10)
        detail = f"1000 + 50 × {weight_kg-10:.1f} = {daily:.0f} mL/日"
    else:
        daily = 1500 + 20 * (weight_kg - 20)
        detail = f"1500 + 20 × {weight_kg-20:.1f} = {daily:.0f} mL/日"

    # 時間レート
    if weight_kg <= 10:
        hourly = 4 * weight_kg
    elif weight_kg <= 20:
        hourly = 40 + 2 * (weight_kg - 10)
    else:
        hourly = 60 + 1 * (weight_kg - 20)

    return FluidCalculation(
        weight_kg=weight_kg,
        daily_ml=round(daily, 1),
        hourly_rate_ml_h=round(hourly, 1),
        calculation_detail=detail,
        notes=[
            "維持輸液量は開始点。臨床的に deficit/ongoing loss を追加評価すること",
            "脱水補正: 軽度 (5%) = +50 mL/kg、中等度 (10%) = +100 mL/kg を最初の 8 時間で半量投与",
            "敗血症・熱傷・腎不全等では個別調整必須",
            "電解質: 通常 0.45% NaCl + 5% ブドウ糖 ± KCl 20 mEq/L",
        ],
    )


# ===========================================================================
# 年齢別鑑別診断確率調整
# ===========================================================================

_DD_AGE_WEIGHTS: dict[str, dict] = {
    "kawasaki": {
        "peak_months": (6, 24),
        "high_months": (2, 60),
        "display": "川崎病",
        "notes": "5 日以上の発熱 + 4/5 主要症状で診断。6-24 ヶ月でピーク。",
    },
    "intussusception": {
        "peak_months": (6, 36),
        "high_months": (3, 60),
        "display": "腸重積",
        "notes": "間欠的腹痛・嘔吐・粘血便のトライアド。6-36 ヶ月でピーク。",
    },
    "croup": {
        "peak_months": (6, 60),
        "high_months": (3, 84),
        "display": "クループ（急性喉頭気管支炎）",
        "notes": "犬吠様咳嗽・吸気性喘鳴。6 ヶ月-5 歳。パラインフルエンザウイルスが主因。",
    },
    "rsv bronchiolitis": {
        "peak_months": (0, 24),
        "high_months": (0, 36),
        "display": "RSV 細気管支炎",
        "notes": "2 歳未満の喘鳴・呼吸困難。冬季流行。重症化リスク: 早産・先天性心疾患。",
    },
    "meningococcemia": {
        "peak_months": (0, 60),
        "high_months": (0, 120),
        "display": "髄膜炎菌血症",
        "notes": "発熱 + 点状出血/紫斑。5 歳未満でピーク。緊急ペニシリン G 投与。",
    },
    "legg calve perthes": {
        "peak_months": (48, 120),
        "high_months": (36, 156),
        "display": "ペルテス病（大腿骨頭壊死）",
        "notes": "4-10 歳の男児に多い跛行・股関節痛。X 線・MRI で診断。",
    },
    "appendicitis": {
        "peak_months": (60, 216),
        "high_months": (48, 216),
        "display": "虫垂炎",
        "notes": "5 歳以上で増加。2 歳未満は非典型的で穿孔率高い。Pediatric Appendicitis Score を使用。",
    },
    "febrile seizure": {
        "peak_months": (6, 60),
        "high_months": (6, 72),
        "display": "熱性痙攣",
        "notes": "6 ヶ月-5 歳。熱の上昇期に多い。単純型は予後良好。",
    },
    "pyloric stenosis": {
        "peak_months": (1, 12),
        "high_months": (0, 18),
        "display": "肥厚性幽門狭窄症",
        "notes": "2-8 週齢の男児に多い噴水様嘔吐。超音波で診断。手術適応。",
    },
    "hip dysplasia": {
        "peak_months": (0, 12),
        "high_months": (0, 24),
        "display": "発育性股関節脱臼 (DDH)",
        "notes": "新生児健診・Ortolani/Barlow テスト。超音波スクリーニング推奨。",
    },
}


def pediatric_dd_adjustments(diagnosis: str, age_months: int) -> dict:
    """
    鑑別診断に対して年齢に基づく確率修正係数を返す。

    Parameters
    ----------
    diagnosis : str
        疾患名（英語・日本語対応）
    age_months : int
        月齢

    Returns
    -------
    dict
        probability_modifier: float (0.0-2.0)
        age_group: str
        peak_age: str
        clinical_note: str
        recommendation: str
    """
    d = diagnosis.lower().strip()

    # キーのマッチング
    matched_key: str | None = None
    for key in _DD_AGE_WEIGHTS:
        if key in d or d in key:
            matched_key = key
            break

    # 日本語マッピング
    ja_map = {
        "川崎病": "kawasaki",
        "腸重積": "intussusception",
        "クループ": "croup",
        "rsv": "rsv bronchiolitis",
        "細気管支炎": "rsv bronchiolitis",
        "髄膜炎菌": "meningococcemia",
        "ペルテス": "legg calve perthes",
        "虫垂炎": "appendicitis",
        "熱性痙攣": "febrile seizure",
        "幽門狭窄": "pyloric stenosis",
        "股関節脱臼": "hip dysplasia",
        "ddh": "hip dysplasia",
    }
    if matched_key is None:
        for ja_key, en_key in ja_map.items():
            if ja_key in d:
                matched_key = en_key
                break

    if matched_key is None:
        return {
            "probability_modifier": 1.0,
            "age_group": classify_age(age_months).value,
            "peak_age": "不明",
            "clinical_note": "登録外疾患。年齢に基づく調整なし。",
            "recommendation": "標準的な評価を行う。",
            "matched": False,
        }

    info = _DD_AGE_WEIGHTS[matched_key]
    peak_lo, peak_hi = info["peak_months"]
    high_lo, high_hi = info["high_months"]

    # 修正係数の計算
    if peak_lo <= age_months <= peak_hi:
        modifier = 2.0   # ピーク年齢: 確率 2 倍
        likelihood = "高い（ピーク年齢）"
    elif high_lo <= age_months <= high_hi:
        modifier = 1.3   # 発症範囲内: 1.3 倍
        likelihood = "やや高い（発症好発年齢内）"
    else:
        modifier = 0.3   # 発症範囲外: 大幅に下げる
        likelihood = "低い（通常の発症年齢外）"

    def _fmt_months(m: int) -> str:
        if m < 12:
            return f"{m} ヶ月"
        return f"{m // 12} 歳 {m % 12} ヶ月" if m % 12 else f"{m // 12} 歳"

    return {
        "probability_modifier": modifier,
        "age_group": classify_age(age_months).value,
        "peak_age": f"{_fmt_months(peak_lo)} - {_fmt_months(peak_hi)}",
        "high_risk_age": f"{_fmt_months(high_lo)} - {_fmt_months(high_hi)}",
        "likelihood": likelihood,
        "clinical_note": info["notes"],
        "display_name": info["display"],
        "matched": True,
    }


# ===========================================================================
# デモ
# ===========================================================================

if __name__ == "__main__":
    print("=" * 65)
    print("  Pediatric Clinical Decision Support — デモ")
    print("=" * 65)

    # 1. バイタルサイン評価
    print("\n--- 1. 小児バイタルサイン評価 ---")
    pv = PediatricVitals(
        age_months=18,   # 1歳6ヶ月
        weight_kg=11.0,
        sbp=75,
        hr=160,
        rr=42,
        spo2=93,
        temp=38.8,
    )
    result = assess_pediatric_vitals(pv)
    print(f"年齢: 18 ヶ月 ({result['age_group']})")
    print(f"推定体重: {result['estimated_weight_kg']} kg")
    print(f"総合ステータス: {result['overall_status']}")
    print("\n各バイタル:")
    for a in result["assessments"]:
        print(f"  {a.parameter}: {a.value} (正常: {a.normal_range}) → [{a.status}] {a.note}")
    if result["alerts"]:
        print("\nアラート:")
        for alert in result["alerts"]:
            print(f"  {alert}")

    # 2. PEWS
    print("\n--- 2. PEWS 計算 ---")
    pews_input = PEWSInput(behavior=2, cardiovascular=2, respiratory=3)
    pews_result = calc_pews(pews_input)
    print(f"PEWS 合計: {pews_result.total} / 12")
    print(f"リスク: {pews_result.risk_level}")
    print(f"推奨: {pews_result.recommendation}")
    if pews_result.escalation_triggers:
        print("エスカレーション要因:")
        for t in pews_result.escalation_triggers:
            print(f"  - {t}")

    # 3. 薬用量計算
    print("\n--- 3. 小児薬用量計算 (体重 15 kg, 月齢 36) ---")
    for drug_name in ["paracetamol", "ibuprofen", "ceftriaxone", "epinephrine", "lorazepam", "dextrose"]:
        dose = pediatric_drug_dose(drug_name, weight_kg=15.0, age_months=36)
        if dose:
            print(f"\n  [{dose.drug}]")
            print(f"    用量: {dose.calculated_dose}")
            print(f"    最大: {dose.max_dose}")
            print(f"    投与: {dose.route} / {dose.frequency}")
            if dose.notes:
                print(f"    注記: {dose.notes[0]}")

    # 4. 維持輸液
    print("\n--- 4. Holliday-Segar 維持輸液計算 ---")
    for wt in [5.0, 12.0, 25.0]:
        fc = holliday_segar(wt)
        print(f"  体重 {wt} kg → {fc.daily_ml:.0f} mL/日 ({fc.hourly_rate_ml_h:.1f} mL/h)")
        print(f"    計算式: {fc.calculation_detail}")

    # 5. 年齢別DD調整
    print("\n--- 5. 年齢別鑑別診断調整 ---")
    test_cases = [
        ("川崎病", 18),
        ("川崎病", 84),
        ("虫垂炎", 36),
        ("虫垂炎", 96),
        ("腸重積", 12),
        ("RSV細気管支炎", 10),
    ]
    for dx, age_m in test_cases:
        r = pediatric_dd_adjustments(dx, age_m)
        age_y = age_m / 12
        print(f"\n  {dx} / {age_m} ヶ月 ({age_y:.1f} 歳)")
        print(f"    確率修正係数: {r['probability_modifier']}×")
        print(f"    評価: {r.get('likelihood', '—')}")
        print(f"    ピーク年齢: {r.get('peak_age', '—')}")
