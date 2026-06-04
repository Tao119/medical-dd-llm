"""
clinical/triage.py — Manchester Triage System (MTS)

マンチェスター・トリアージ・システム（5 レベル）の実装。

レベル定義:
  1: Immediate (赤)   — 生命の危機
  2: Very Urgent (橙) — 重篤な症状・重度疼痛
  3: Urgent (黄)      — 急性疼痛・軽度バイタル異常
  4: Standard (緑)    — 非急性
  5: Non-Urgent (青)  — 軽微

MTS ディスクリミネーター実装:
  - 気道・呼吸・循環の緊急評価
  - GCS・意識障害
  - 疼痛スコア（NRS 0-10）
  - バイタルサイン異常度
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import NamedTuple

from .vitals import VitalSigns, parse_vitals


# ===========================================================================
# データモデル
# ===========================================================================

@dataclass
class TriageResult:
    level: int               # 1-5 (1=Immediate)
    color: str               # "red" | "orange" | "yellow" | "green" | "blue"
    name_en: str
    name_ja: str
    max_wait_minutes: int    # 最大待機時間（分）
    reasoning: list[str]     # 判定根拠
    vital_contribution: list[str]  # バイタルサインの寄与
    recommended_action: str


# トリアージレベル定義
class _Level(NamedTuple):
    level: int
    color: str
    name_en: str
    name_ja: str
    max_wait_minutes: int
    recommended_action: str


_LEVELS: dict[int, _Level] = {
    1: _Level(1, "red",    "Immediate",   "蘇生 (即時)",    0,   "直ちに蘇生室へ。蘇生チームを招集。"),
    2: _Level(2, "orange", "Very Urgent", "最優先 (10分)",  10,  "10 分以内に医師評価。モニタリング開始。"),
    3: _Level(3, "yellow", "Urgent",      "優先 (30分)",    30,  "30 分以内に医師評価。定期バイタルモニタリング。"),
    4: _Level(4, "green",  "Standard",    "通常 (60-90分)", 90,  "90 分以内に評価。"),
    5: _Level(5, "blue",   "Non-Urgent",  "低優先 (120分)", 120, "120 分以内に評価。必要なら一次医療機関への誘導を考慮。"),
}


# ===========================================================================
# バイタルサイン異常度評価
# ===========================================================================

def _assess_vitals_severity(vs: VitalSigns) -> tuple[int, list[str]]:
    """
    バイタルサインから最大トリアージレベルの悪化度を算出する。

    Returns
    -------
    (severity_level: int, contributions: list[str])
      severity_level: 1(最重症)-5(正常)
    """
    level = 5
    contributions: list[str] = []

    # SpO2
    if vs.spo2 is not None:
        if vs.spo2 < 90:
            level = min(level, 1)
            contributions.append(f"SpO2 {vs.spo2}% — 重篤な低酸素血症 (Level 1)")
        elif vs.spo2 < 94:
            level = min(level, 2)
            contributions.append(f"SpO2 {vs.spo2}% — 低酸素血症 (Level 2)")
        elif vs.spo2 < 96:
            level = min(level, 3)
            contributions.append(f"SpO2 {vs.spo2}% — 軽度低酸素血症 (Level 3)")

    # 呼吸数
    if vs.rr is not None:
        if vs.rr > 30 or vs.rr < 8:
            level = min(level, 1)
            tag = "頻呼吸" if vs.rr > 30 else "徐呼吸"
            contributions.append(f"RR {vs.rr}/min — {tag} (Level 1)")
        elif vs.rr > 25 or vs.rr < 10:
            level = min(level, 2)
            contributions.append(f"RR {vs.rr}/min — 異常呼吸数 (Level 2)")
        elif vs.rr > 20:
            level = min(level, 3)
            contributions.append(f"RR {vs.rr}/min — 軽度頻呼吸 (Level 3)")

    # 収縮期血圧
    if vs.sbp is not None:
        if vs.sbp < 80:
            level = min(level, 1)
            contributions.append(f"SBP {vs.sbp} mmHg — 重篤な低血圧/ショック (Level 1)")
        elif vs.sbp < 90:
            level = min(level, 2)
            contributions.append(f"SBP {vs.sbp} mmHg — 低血圧 (Level 2)")
        elif vs.sbp < 100:
            level = min(level, 3)
            contributions.append(f"SBP {vs.sbp} mmHg — 境界低血圧 (Level 3)")
        elif vs.sbp > 220:
            level = min(level, 2)
            contributions.append(f"SBP {vs.sbp} mmHg — 高血圧緊急症疑い (Level 2)")
        elif vs.sbp > 180:
            level = min(level, 3)
            contributions.append(f"SBP {vs.sbp} mmHg — 重度高血圧 (Level 3)")

    # 心拍数
    if vs.hr is not None:
        if vs.hr > 150 or vs.hr < 40:
            level = min(level, 1)
            tag = "頻脈" if vs.hr > 150 else "重篤な徐脈"
            contributions.append(f"HR {vs.hr}/min — {tag} (Level 1)")
        elif vs.hr > 130 or vs.hr < 50:
            level = min(level, 2)
            contributions.append(f"HR {vs.hr}/min — 重篤な不整脈/頻脈 (Level 2)")
        elif vs.hr > 110 or vs.hr < 55:
            level = min(level, 3)
            contributions.append(f"HR {vs.hr}/min — 軽度脈拍異常 (Level 3)")

    # GCS
    if vs.gcs is not None:
        if vs.gcs <= 8:
            level = min(level, 1)
            contributions.append(f"GCS {vs.gcs} — 重篤な意識障害 (Level 1)")
        elif vs.gcs <= 11:
            level = min(level, 2)
            contributions.append(f"GCS {vs.gcs} — 中等度意識障害 (Level 2)")
        elif vs.gcs <= 13:
            level = min(level, 3)
            contributions.append(f"GCS {vs.gcs} — 軽度意識障害 (Level 3)")

    # 体温
    if vs.temp is not None:
        if vs.temp >= 41.0 or vs.temp < 35.0:
            level = min(level, 2)
            tag = "高体温" if vs.temp >= 41.0 else "低体温"
            contributions.append(f"体温 {vs.temp}℃ — 重篤な{tag} (Level 2)")
        elif vs.temp >= 39.5:
            level = min(level, 3)
            contributions.append(f"体温 {vs.temp}℃ — 高熱 (Level 3)")

    return level, contributions


# ===========================================================================
# 症状・テキストからの緊急サイン検出
# ===========================================================================

# (pattern, level, description)
_CRITICAL_PATTERNS: list[tuple[re.Pattern, int, str]] = [
    # Level 1 — Immediate
    (re.compile(r"airway|気道閉塞|窒息|chok", re.I),         1, "気道閉塞"),
    (re.compile(r"cardiac arrest|心停止|VF|VT|pulseless", re.I), 1, "心停止/致死的不整脈"),
    (re.compile(r"apnea|無呼吸|apnoea", re.I),               1, "無呼吸"),
    (re.compile(r"unresponsive|意識なし|昏睡|coma", re.I),   1, "意識消失/昏睡"),
    (re.compile(r"major haemorrhage|大量出血|exsanguination", re.I), 1, "大量出血"),
    (re.compile(r"eclampsia|子癇|seizure.*pregnant|妊娠.*痙攣", re.I), 1, "子癇"),
    (re.compile(r"tension pneumo|緊張性気胸", re.I),          1, "緊張性気胸"),
    (re.compile(r"anaphylaxis|アナフィラキシー|anaphylactic", re.I), 1, "アナフィラキシー"),
    # Level 2 — Very Urgent
    (re.compile(r"stroke|CVA|脳卒中|hemiplegia|片麻痺|顔面麻痺", re.I), 2, "急性神経症状（脳卒中疑い）"),
    (re.compile(r"chest pain.*diaphor|chest pain.*radiat|心筋梗塞疑い|STEMI", re.I), 2, "ACS 疑い（放散痛・冷汗）"),
    (re.compile(r"severe chest pain|激しい胸痛|tearing|引き裂く", re.I), 2, "重篤な胸痛（解離疑い）"),
    (re.compile(r"status epilepticus|痙攣重積|convulsion.*prolonged", re.I), 2, "痙攣重積"),
    (re.compile(r"sepsis|敗血症|meningitis|髄膜炎|petechiae.*fever|発熱.*点状出血", re.I), 2, "敗血症/髄膜炎疑い"),
    (re.compile(r"testicular torsion|精巣捻転|limb ischaemia|四肢虚血", re.I), 2, "外科的緊急症（虚血）"),
    (re.compile(r"ectopic preg|異所性妊娠|子宮外妊娠", re.I), 2, "子宮外妊娠疑い"),
    (re.compile(r"diabetic ketoacidosis|DKA|ケトアシドーシス", re.I), 2, "DKA 疑い"),
    # Level 3 — Urgent
    (re.compile(r"moderate.*chest pain|中等度.*胸痛|pleuritic", re.I), 3, "中等度胸痛"),
    (re.compile(r"abdominal pain.*vomit|腹痛.*嘔吐|acute abdomen|急性腹症", re.I), 3, "急性腹症疑い"),
    (re.compile(r"fracture|骨折|dislocation|脱臼", re.I), 3, "骨折/脱臼"),
    (re.compile(r"head injury|頭部外傷|concussion|脳震盪", re.I), 3, "頭部外傷"),
    (re.compile(r"epistaxis.*severe|重篤な鼻出血|haemoptysis|喀血", re.I), 3, "重篤な出血"),
]


def _detect_critical_symptoms(case_text: str) -> list[tuple[int, str]]:
    """
    テキストから緊急サインを検出して (level, description) のリストを返す。
    """
    findings: list[tuple[int, str]] = []
    for pattern, level, desc in _CRITICAL_PATTERNS:
        if pattern.search(case_text):
            findings.append((level, desc))
    return findings


# ===========================================================================
# 疼痛スコアによるレベル調整
# ===========================================================================

def _pain_level(pain_score: int) -> tuple[int, str]:
    """
    NRS 疼痛スコア（0-10）をトリアージレベルに変換する。
    """
    if pain_score >= 10:
        return 2, f"最大疼痛 NRS {pain_score}/10 (Level 2)"
    elif pain_score >= 7:
        return 2, f"重篤な疼痛 NRS {pain_score}/10 (Level 2)"
    elif pain_score >= 4:
        return 3, f"中等度疼痛 NRS {pain_score}/10 (Level 3)"
    elif pain_score >= 1:
        return 4, f"軽度疼痛 NRS {pain_score}/10 (Level 4)"
    return 5, "疼痛なし"


# ===========================================================================
# メイントリアージ関数
# ===========================================================================

def triage(
    case: dict,
    vitals_str: str = "",
    pain_score: int = 0,
) -> TriageResult:
    """
    Manchester Triage System でトリアージを実行する。

    Parameters
    ----------
    case : dict
        症例情報。キー例:
          "chief_complaint": str — 主訴
          "symptoms": str        — 症状記述（自由文）
          "age": int             — 年齢
          "mechanism": str       — 受傷機転 (外傷)
          "history": str         — 既往歴
          "pregnant": bool       — 妊娠の有無
    vitals_str : str
        バイタルサイン文字列（parse_vitals で解析）
    pain_score : int
        NRS 疼痛スコア 0-10

    Returns
    -------
    TriageResult
    """
    reasoning: list[str] = []
    vital_contribution: list[str] = []
    candidate_levels: list[int] = [5]  # デフォルト Non-Urgent から開始

    # --- 1. バイタルサイン評価 ---
    vs = VitalSigns()
    if vitals_str:
        vs = parse_vitals(vitals_str)
        vital_level, vital_contribs = _assess_vitals_severity(vs)
        vital_contribution.extend(vital_contribs)
        candidate_levels.append(vital_level)

    # --- 2. 症状テキスト評価 ---
    combined_text = " ".join([
        case.get("chief_complaint", ""),
        str(case.get("symptoms", "")),   # ensure string
        case.get("mechanism", ""),
        case.get("history", ""),
    ])

    critical_findings = _detect_critical_symptoms(combined_text)
    for level, desc in critical_findings:
        candidate_levels.append(level)
        reasoning.append(f"症状検出: {desc}")

    # --- 3. 疼痛スコア評価 ---
    if pain_score > 0:
        pain_lv, pain_desc = _pain_level(pain_score)
        candidate_levels.append(pain_lv)
        reasoning.append(pain_desc)

    # --- 4. 特殊ケース評価 ---

    # 妊娠
    if case.get("pregnant"):
        reasoning.append("妊娠中 — 最低 Level 3 以上に優先度設定")
        candidate_levels.append(3)

    # 小児（<3ヶ月）
    age_months = case.get("age_months")
    age_years = case.get("age")
    if age_months is not None and age_months < 3:
        reasoning.append(f"3 ヶ月未満乳児 ({age_months} ヶ月) — Level 2 以上に設定")
        candidate_levels.append(2)
    elif age_years is not None and age_years < 1:
        reasoning.append(f"1 歳未満乳児 — Level 2 以上に設定")
        candidate_levels.append(2)

    # 免疫不全 + 発熱
    history_text = case.get("history", "").lower()
    if any(term in history_text for term in ["immunocompromised", "hiv", "化学療法", "neutropenic", "好中球減少"]):
        if vs.temp is not None and vs.temp >= 38.0:
            reasoning.append("免疫不全 + 発熱 — Level 2 (好中球減少性発熱疑い)")
            candidate_levels.append(2)

    # 急性片麻痺・顔面麻痺 + 発症時間
    if re.search(r"片麻痺|顔面.*麻痺|构音障碍|dysarthria|sudden.*weakness|sudden.*slurred", combined_text, re.I):
        reasoning.append("急性神経症状 — 脳卒中ファストトラック (Level 2)")
        candidate_levels.append(2)

    # 刺創・銃創
    if re.search(r"stab|刺創|gunshot|銃創|penetrating", combined_text, re.I):
        reasoning.append("穿通性外傷 — Level 2 以上")
        candidate_levels.append(2)

    # --- 5. 最終レベル決定（最悪の指標を採用）---
    final_level = min(candidate_levels)
    lv = _LEVELS[final_level]

    # 根拠がない場合のデフォルト
    if not reasoning and not vital_contribution:
        reasoning.append("バイタルサイン安定・重篤な症状なし → 通常トリアージ")

    return TriageResult(
        level=lv.level,
        color=lv.color,
        name_en=lv.name_en,
        name_ja=lv.name_ja,
        max_wait_minutes=lv.max_wait_minutes,
        reasoning=reasoning,
        vital_contribution=vital_contribution,
        recommended_action=lv.recommended_action,
    )


# ===========================================================================
# MTS 疼痛フロー（主訴別ショートカット）
# ===========================================================================

def triage_chest_pain(
    pain_score: int,
    sbp: float | None = None,
    hr: float | None = None,
    diaphoresis: bool = False,
    radiation: bool = False,
    onset_sudden: bool = False,
) -> TriageResult:
    """
    胸痛症例の特化型トリアージ。

    Parameters
    ----------
    pain_score : int
        NRS 0-10
    sbp : float | None
        収縮期血圧
    hr : float | None
        心拍数
    diaphoresis : bool
        冷汗・発汗あり
    radiation : bool
        左腕・顎への放散痛あり
    onset_sudden : bool
        突然発症（解離・PE を示唆）
    """
    symptoms = "chest pain"
    if diaphoresis:
        symptoms += " with diaphoresis"
    if radiation:
        symptoms += " with radiation to arm"
    if onset_sudden:
        symptoms += " sudden tearing"

    vitals_parts = []
    if sbp is not None:
        vitals_parts.append(f"BP {sbp}/70")
    if hr is not None:
        vitals_parts.append(f"HR {hr}")
    vitals_str = ", ".join(vitals_parts)

    return triage(
        case={"chief_complaint": "chest pain", "symptoms": symptoms},
        vitals_str=vitals_str,
        pain_score=pain_score,
    )


def triage_dyspnea(
    spo2: float | None = None,
    rr: float | None = None,
    stridor: bool = False,
    wheeze: bool = False,
) -> TriageResult:
    """
    呼吸困難症例の特化型トリアージ。
    """
    symptoms = "dyspnea"
    if stridor:
        symptoms += " stridor airway compromise"
    if wheeze:
        symptoms += " wheeze"

    vitals_parts = []
    if spo2 is not None:
        vitals_parts.append(f"SpO2 {spo2}%")
    if rr is not None:
        vitals_parts.append(f"RR {rr}")
    vitals_str = ", ".join(vitals_parts)

    return triage(
        case={"chief_complaint": "dyspnea", "symptoms": symptoms},
        vitals_str=vitals_str,
    )


def format_triage_result(result: TriageResult) -> str:
    """トリアージ結果を見やすい文字列に整形する。"""
    sep = "─" * 55
    lines = [
        sep,
        f"  トリアージレベル: {result.level} — {result.name_ja}  [{result.color.upper()}]",
        f"  最大待機時間: {result.max_wait_minutes} 分",
        f"  推奨対応: {result.recommended_action}",
        sep,
    ]

    if result.vital_contribution:
        lines.append("  バイタルサイン寄与:")
        for v in result.vital_contribution:
            lines.append(f"    • {v}")

    if result.reasoning:
        lines.append("  判定根拠:")
        for r in result.reasoning:
            lines.append(f"    • {r}")

    lines.append(sep)
    return "\n".join(lines)


# ===========================================================================
# デモ
# ===========================================================================

if __name__ == "__main__":
    print("=" * 58)
    print("  Manchester Triage System — デモ")
    print("=" * 58)

    test_cases = [
        {
            "name": "Case 1: 心肺停止疑い",
            "case": {"chief_complaint": "cardiac arrest", "symptoms": "unresponsive pulseless"},
            "vitals": "HR 0, RR 0, SpO2 70%",
            "pain": 0,
        },
        {
            "name": "Case 2: STEMI 疑い（放散痛・冷汗）",
            "case": {"chief_complaint": "chest pain", "symptoms": "chest pain with diaphoresis radiation to arm"},
            "vitals": "BP 95/60, HR 110, SpO2 96%, RR 22",
            "pain": 8,
        },
        {
            "name": "Case 3: 急性脳卒中疑い",
            "case": {"chief_complaint": "stroke", "symptoms": "sudden weakness hemiplegia facial droop dysarthria"},
            "vitals": "BP 175/100, HR 88, SpO2 97%",
            "pain": 3,
        },
        {
            "name": "Case 4: アナフィラキシー",
            "case": {"chief_complaint": "anaphylaxis", "symptoms": "anaphylactic reaction urticaria hypotension"},
            "vitals": "BP 75/40, HR 135, SpO2 88%, RR 28",
            "pain": 5,
        },
        {
            "name": "Case 5: 急性喘息発作（中等度）",
            "case": {"chief_complaint": "dyspnea", "symptoms": "wheeze difficulty breathing"},
            "vitals": "SpO2 91%, RR 26, HR 115",
            "pain": 4,
        },
        {
            "name": "Case 6: 骨折（大腿骨）",
            "case": {"chief_complaint": "leg pain", "symptoms": "fracture femur trauma"},
            "vitals": "BP 120/80, HR 90, SpO2 98%",
            "pain": 7,
        },
        {
            "name": "Case 7: 軽微な切り傷",
            "case": {"chief_complaint": "minor laceration", "symptoms": "small cut finger"},
            "vitals": "BP 120/78, HR 72, SpO2 99%",
            "pain": 2,
        },
        {
            "name": "Case 8: 免疫不全 + 発熱",
            "case": {"chief_complaint": "fever", "symptoms": "fever cough", "history": "化学療法中 好中球減少"},
            "vitals": "体温 38.9, HR 105, BP 108/65, RR 22",
            "pain": 2,
        },
        {
            "name": "Case 9: DKA 疑い",
            "case": {"chief_complaint": "vomiting", "symptoms": "diabetic ketoacidosis nausea vomiting altered consciousness"},
            "vitals": "BP 100/65, HR 120, RR 28, SpO2 97%",
            "pain": 5,
        },
        {
            "name": "Case 10: 3 ヶ月未満乳児の発熱",
            "case": {"chief_complaint": "fever infant", "symptoms": "febrile seizure infant", "age_months": 2},
            "vitals": "体温 38.5, HR 160, RR 50",
            "pain": 0,
        },
    ]

    for tc in test_cases:
        print(f"\n{tc['name']}")
        result = triage(tc["case"], vitals_str=tc["vitals"], pain_score=tc["pain"])
        print(format_triage_result(result))

    # 特化型トリアージのデモ
    print("\n--- 胸痛特化型トリアージ ---")
    ct = triage_chest_pain(pain_score=9, sbp=90, hr=120, diaphoresis=True, radiation=True)
    print(format_triage_result(ct))

    print("\n--- 呼吸困難特化型トリアージ (喘鳴 + 低 SpO2) ---")
    dt = triage_dyspnea(spo2=88, rr=32, stridor=False, wheeze=True)
    print(format_triage_result(dt))
