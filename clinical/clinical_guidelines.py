"""
clinical/clinical_guidelines.py — Clinical Guideline Database

Structured, evidence-based clinical guidelines for major conditions.
Covers ACS, Heart Failure, Sepsis, Pneumonia, and Stroke.

Usage
-----
    cd medical-dd-llm
    python clinical/clinical_guidelines.py
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional


# ---------------------------------------------------------------------------
# Dataclass
# ---------------------------------------------------------------------------

@dataclass
class Guideline:
    condition: str
    organization: str       # e.g. "AHA/ACC", "ESC", "JCS"
    year: int
    class_of_recommendation: str  # "I", "IIa", "IIb", "III"
    level_of_evidence: str        # "A", "B", "C"
    recommendation: str
    notes: str = ""


# ---------------------------------------------------------------------------
# Guideline database
# ---------------------------------------------------------------------------

GUIDELINES: list[Guideline] = [

    # ── ACS (ESC 2023) ──────────────────────────────────────────────────────
    Guideline(
        condition="ACS",
        organization="ESC",
        year=2023,
        class_of_recommendation="I",
        level_of_evidence="A",
        recommendation="STEMI患者において、症状発症から120分以内にプライマリPCIを施行すること。",
        notes="ファーストメディカルコンタクトから120分以内が目標。",
    ),
    Guideline(
        condition="ACS",
        organization="ESC",
        year=2023,
        class_of_recommendation="I",
        level_of_evidence="A",
        recommendation="抗血小板療法として、アスピリン（162-325mg）とP2Y12阻害薬（プラスグレルまたはチカグレロル）のDAAP療法を推奨する。",
        notes="禁忌がない限り全ACS患者に適用。",
    ),
    Guideline(
        condition="ACS",
        organization="ESC",
        year=2023,
        class_of_recommendation="I",
        level_of_evidence="A",
        recommendation="PCI施行前に抗凝固療法（ヘパリンまたはビバリルジン）を投与すること。",
        notes="UFH 70-100 IU/kg i.v. as bolus.",
    ),
    Guideline(
        condition="ACS",
        organization="ESC",
        year=2023,
        class_of_recommendation="I",
        level_of_evidence="B",
        recommendation="STEMI患者において、βブロッカー（禁忌がない場合）の早期経口投与を推奨する。",
        notes="心不全やショックの徴候がない場合に適用。",
    ),
    Guideline(
        condition="ACS",
        organization="ESC",
        year=2023,
        class_of_recommendation="I",
        level_of_evidence="A",
        recommendation="高用量スタチン療法（アトルバスタチン40-80mgまたはロスバスタチン20-40mg）を入院後早期から開始すること。",
        notes="LDL-C 目標値 55 mg/dL 未満（超高リスク）。",
    ),
    Guideline(
        condition="ACS",
        organization="ESC",
        year=2023,
        class_of_recommendation="IIa",
        level_of_evidence="B",
        recommendation="ACE阻害薬またはARBを、特にEF低下・高血圧・糖尿病合併ACS患者に推奨する。",
        notes="血行動態的に安定している場合に開始。",
    ),
    Guideline(
        condition="ACS",
        organization="AHA/ACC",
        year=2022,
        class_of_recommendation="I",
        level_of_evidence="A",
        recommendation="NSTEMIの高リスク患者において、24時間以内の早期侵襲的戦略（冠動脈造影+PCI）を推奨する。",
        notes="TIMI ≥3、GRACE score > 140など高リスク基準を満たす場合。",
    ),
    Guideline(
        condition="ACS",
        organization="ESC",
        year=2023,
        class_of_recommendation="I",
        level_of_evidence="A",
        recommendation="12誘導心電図を胸痛発症後10分以内に施行すること。",
        notes="STEMIの早期診断と再灌流決定に必須。",
    ),

    # ── Heart Failure (JCS 2021) ─────────────────────────────────────────────
    Guideline(
        condition="Heart Failure",
        organization="JCS",
        year=2021,
        class_of_recommendation="I",
        level_of_evidence="A",
        recommendation="HFrEF（EF < 40%）患者にACE阻害薬またはARBを投与すること。",
        notes="ARNIが使用できない場合の第一選択。",
    ),
    Guideline(
        condition="Heart Failure",
        organization="JCS",
        year=2021,
        class_of_recommendation="I",
        level_of_evidence="A",
        recommendation="HFrEF患者に心不全に適応のあるβブロッカー（カルベジロール、ビソプロロール）を投与すること。",
        notes="低用量から開始し、忍容性に応じて漸増する。",
    ),
    Guideline(
        condition="Heart Failure",
        organization="JCS",
        year=2021,
        class_of_recommendation="I",
        level_of_evidence="A",
        recommendation="HFrEFおよびうっ血の徴候がある患者にループ利尿薬（フロセミド）を投与すること。",
        notes="体液過剰の症状・徴候緩和を目的とする。",
    ),
    Guideline(
        condition="Heart Failure",
        organization="JCS",
        year=2021,
        class_of_recommendation="I",
        level_of_evidence="A",
        recommendation="HFrEF患者にミネラルコルチコイド受容体拮抗薬（スピロノラクトン、エプレレノン）を追加投与すること。",
        notes="eGFR ≥ 30 mL/min/1.73m²、K+ < 5.0 mEq/L の場合に適用。",
    ),
    Guideline(
        condition="Heart Failure",
        organization="ESC",
        year=2021,
        class_of_recommendation="I",
        level_of_evidence="B",
        recommendation="ARNI（サクビトリル/バルサルタン）をACE阻害薬の代替としてHFrEF患者に推奨する。",
        notes="ACE阻害薬から切り替える場合は36時間のウォッシュアウト期間が必要。",
    ),
    Guideline(
        condition="Heart Failure",
        organization="ESC",
        year=2021,
        class_of_recommendation="I",
        level_of_evidence="A",
        recommendation="SGLT2阻害薬（ダパグリフロジン、エンパグリフロジン）をHFrEF患者に推奨する。",
        notes="糖尿病の有無に関わらず心不全による入院・心血管死を減少させる。",
    ),
    Guideline(
        condition="Heart Failure",
        organization="JCS",
        year=2021,
        class_of_recommendation="I",
        level_of_evidence="B",
        recommendation="適格なHFrEF患者（QRS ≥ 150ms, LBBB）に心臓再同期療法（CRT）を施行すること。",
        notes="NYHA II-IV度かつ最大薬物療法下でのEF ≤ 35%が適応基準。",
    ),
    Guideline(
        condition="Heart Failure",
        organization="JCS",
        year=2021,
        class_of_recommendation="IIa",
        level_of_evidence="B",
        recommendation="HFpEF（EF ≥ 50%）患者に対してSGLT2阻害薬を考慮する。",
        notes="症状および心不全入院を減少させるエビデンスが蓄積されている。",
    ),

    # ── Sepsis (SSC 2021) ────────────────────────────────────────────────────
    Guideline(
        condition="Sepsis",
        organization="SSC",
        year=2021,
        class_of_recommendation="I",
        level_of_evidence="A",
        recommendation="敗血症/敗血症性ショックが疑われる場合、認識後1時間以内に抗菌薬投与を開始すること（Hour-1 Bundle）。",
        notes="遅延するごとに死亡率が上昇する。",
    ),
    Guideline(
        condition="Sepsis",
        organization="SSC",
        year=2021,
        class_of_recommendation="I",
        level_of_evidence="A",
        recommendation="抗菌薬投与前に血液培養2セットを採取すること。",
        notes="皮膚消毒後に静脈穿刺で採取する。投与遅延は45分を超えてはならない。",
    ),
    Guideline(
        condition="Sepsis",
        organization="SSC",
        year=2021,
        class_of_recommendation="I",
        level_of_evidence="A",
        recommendation="敗血症性ショックの初期輸液として、晶質液30 mL/kgを3時間以内に投与すること。",
        notes="輸液反応性を評価しながら慎重に実施する。",
    ),
    Guideline(
        condition="Sepsis",
        organization="SSC",
        year=2021,
        class_of_recommendation="I",
        level_of_evidence="A",
        recommendation="適切な輸液後も低血圧が持続する場合、ノルエピネフリンを第一選択昇圧薬として使用すること。",
        notes="目標MAP ≥ 65 mmHg。",
    ),
    Guideline(
        condition="Sepsis",
        organization="SSC",
        year=2021,
        class_of_recommendation="I",
        level_of_evidence="B",
        recommendation="乳酸値が2 mmol/Lを超える場合、乳酸値をモニタリングしながら蘇生を行うこと。",
        notes="乳酸クリアランス ≥ 10%/2時間を目標とする。",
    ),
    Guideline(
        condition="Sepsis",
        organization="SSC",
        year=2021,
        class_of_recommendation="IIa",
        level_of_evidence="B",
        recommendation="敗血症性ショックでノルエピネフリンに反応しない場合、ヒドロコルチゾン200 mg/日を追加投与すること。",
        notes="バソプレシンを追加してもショックが改善しない場合に適用。",
    ),

    # ── Pneumonia (ATS/IDSA 2019) ────────────────────────────────────────────
    Guideline(
        condition="Pneumonia",
        organization="ATS/IDSA",
        year=2019,
        class_of_recommendation="I",
        level_of_evidence="A",
        recommendation="CURB-65スコア0-1の軽症市中肺炎（CAP）の外来治療にアモキシシリンを第一選択とする。",
        notes="βラクタムアレルギーの場合はドキシサイクリンまたはマクロライドを使用。",
    ),
    Guideline(
        condition="Pneumonia",
        organization="ATS/IDSA",
        year=2019,
        class_of_recommendation="I",
        level_of_evidence="A",
        recommendation="入院CAPに対して、βラクタム（アンピシリン/スルバクタムまたはセフトリアキソン）+マクロライドの併用療法を推奨する。",
        notes="もしくはレスピラトリーフルオロキノロン単剤療法。",
    ),
    Guideline(
        condition="Pneumonia",
        organization="ATS/IDSA",
        year=2019,
        class_of_recommendation="I",
        level_of_evidence="A",
        recommendation="CURB-65スコアを用いて入院要否を判断すること（スコア2以上は入院推奨）。",
        notes="PSI/PORTスコアも有用。CURB-65: 尿素窒素>19mg/dL、意識障害、RR≥30、BP<90/60、年齢≥65。",
    ),
    Guideline(
        condition="Pneumonia",
        organization="ATS/IDSA",
        year=2019,
        class_of_recommendation="I",
        level_of_evidence="B",
        recommendation="重症CAPの患者ではICU入室基準（ATS major/minor criteria）を評価すること。",
        notes="Major: 侵襲的人工呼吸器管理または昇圧薬が必要。Minor: RR≥30、PaO2/FiO2≤250など。",
    ),
    Guideline(
        condition="Pneumonia",
        organization="ATS/IDSA",
        year=2019,
        class_of_recommendation="IIb",
        level_of_evidence="B",
        recommendation="軽症CAPへの過度な広域抗菌薬使用を避けること。",
        notes="耐性菌リスクがない場合、狭域抗菌薬を優先する。",
    ),

    # ── Stroke (AHA 2019) ────────────────────────────────────────────────────
    Guideline(
        condition="Stroke",
        organization="AHA",
        year=2019,
        class_of_recommendation="I",
        level_of_evidence="A",
        recommendation="虚血性脳卒中で発症4.5時間以内かつ適応基準を満たす患者にアルテプラーゼ静注血栓溶解療法（IV-tPA）を施行すること。",
        notes="禁忌: 最近の手術・外傷・出血歴、INR > 1.7、血小板 < 100,000/μLなど。",
    ),
    Guideline(
        condition="Stroke",
        organization="AHA",
        year=2019,
        class_of_recommendation="I",
        level_of_evidence="A",
        recommendation="前方循環大血管閉塞（ICAまたはM1/M2）に対して、発症6時間以内に血管内血栓回収術（血栓摘出術）を施行すること。",
        notes="NIHSS ≥ 6、ASPECTS ≥ 6が適応基準の目安。",
    ),
    Guideline(
        condition="Stroke",
        organization="AHA",
        year=2019,
        class_of_recommendation="I",
        level_of_evidence="A",
        recommendation="脳卒中急性期（24時間以内）に抗血小板療法（アスピリン325mg）を開始すること（tPA非適応例）。",
        notes="tPA後24時間は抗血小板療法を開始しない。",
    ),
    Guideline(
        condition="Stroke",
        organization="AHA",
        year=2019,
        class_of_recommendation="I",
        level_of_evidence="A",
        recommendation="IV-tPA前後の血圧管理目標: 収縮期血圧 < 185/110 mmHg（tPA前）、180/105 mmHg未満（tPA後24時間）。",
        notes="降圧薬として labetalol 10 mg i.v. または nicardipine 5 mg/h i.v. が推奨される。",
    ),
    Guideline(
        condition="Stroke",
        organization="AHA",
        year=2019,
        class_of_recommendation="IIa",
        level_of_evidence="B",
        recommendation="DWI-MRIで梗塞巣が確認されていないウェイクアップ脳卒中患者（発症時刻不明）に対し、MRI FLAIR陰性例へのtPAを考慮する。",
        notes="WAKE-UP試験のエビデンスに基づく。",
    ),
    Guideline(
        condition="Stroke",
        organization="AHA",
        year=2019,
        class_of_recommendation="I",
        level_of_evidence="A",
        recommendation="脳卒中疑い患者に対し、病院到着から60分以内にCTまたはMRIを施行すること（Door-to-Imaging ≤ 25分目標）。",
        notes="出血性脳卒中の除外が最優先事項。",
    ),
    Guideline(
        condition="Stroke",
        organization="AHA",
        year=2019,
        class_of_recommendation="I",
        level_of_evidence="B",
        recommendation="心原性脳塞栓症（心房細動合併）には、急性期以降に経口抗凝固薬（DOACまたはワルファリン）を開始すること。",
        notes="開始時期は梗塞巣の大きさや出血リスクにより判断する（1-3-6-12ルール）。",
    ),
]


# ---------------------------------------------------------------------------
# Accessors
# ---------------------------------------------------------------------------

def _normalize_condition(name: str) -> str:
    return name.lower().replace(" ", "").replace("_", "").replace("-", "")


_CONDITION_ALIASES: dict[str, str] = {
    "acs": "ACS",
    "acutecoronarysyndrome": "ACS",
    "急性冠症候群": "ACS",
    "心筋梗塞": "ACS",
    "stemi": "ACS",
    "nstemi": "ACS",
    "heartfailure": "Heart Failure",
    "hf": "Heart Failure",
    "心不全": "Heart Failure",
    "hfref": "Heart Failure",
    "hfpef": "Heart Failure",
    "sepsis": "Sepsis",
    "敗血症": "Sepsis",
    "sepsisshock": "Sepsis",
    "敗血症性ショック": "Sepsis",
    "pneumonia": "Pneumonia",
    "肺炎": "Pneumonia",
    "cap": "Pneumonia",
    "stroke": "Stroke",
    "脳卒中": "Stroke",
    "脳梗塞": "Stroke",
    "cerebralinfarction": "Stroke",
    "ischemicstroke": "Stroke",
}


def get_guidelines(condition: str) -> list[Guideline]:
    """
    Return guidelines for the given condition.

    Supports fuzzy matching via alias lookup and substring matching.

    Parameters
    ----------
    condition : str
        Condition name (English or Japanese, case-insensitive).

    Returns
    -------
    list[Guideline]
    """
    normalized = _normalize_condition(condition)

    # Direct alias lookup
    canonical = _CONDITION_ALIASES.get(normalized)
    if canonical:
        return [g for g in GUIDELINES if g.condition == canonical]

    # Substring match against canonical condition names
    for g in GUIDELINES:
        if _normalize_condition(g.condition) in normalized or normalized in _normalize_condition(g.condition):
            canonical = g.condition
            return [g for g in GUIDELINES if g.condition == canonical]

    # Broad fuzzy: check each word in the query against guideline conditions
    query_words = re.split(r"[\s\-_/]", condition.lower())
    for g in GUIDELINES:
        cond_lower = g.condition.lower()
        if any(w in cond_lower for w in query_words if len(w) >= 3):
            canonical = g.condition
            return [g for g in GUIDELINES if g.condition == canonical]

    return []


def format_guidelines_text(guidelines: list[Guideline]) -> str:
    """
    Format a list of guidelines into a human-readable text block.

    Parameters
    ----------
    guidelines : list[Guideline]

    Returns
    -------
    str
    """
    if not guidelines:
        return "(該当するガイドラインが見つかりません)"

    lines = []
    for i, g in enumerate(guidelines, 1):
        lines.append(
            f"[{i}] {g.condition} — {g.organization} {g.year}\n"
            f"    Class {g.class_of_recommendation} / Level {g.level_of_evidence}\n"
            f"    推奨: {g.recommendation}"
        )
        if g.notes:
            lines.append(f"    備考: {g.notes}")
        lines.append("")
    return "\n".join(lines)


def check_adherence(
    treatment_steps: list[str],
    guidelines: list[Guideline],
) -> dict:
    """
    Check whether a list of treatment steps is adherent to the given guidelines.

    Matching is keyword-based: extracts critical action terms from the
    recommendation text and checks if they appear in any treatment step.

    Parameters
    ----------
    treatment_steps : list[str]
        Free-text list of actions taken (e.g. ["アスピリン投与", "12誘導心電図施行"]).
    guidelines : list[Guideline]
        Guidelines to check against (typically from get_guidelines()).

    Returns
    -------
    dict
        {
            "adherent":  list of recommendation snippets that were addressed,
            "missing":   list of Class I/IIa recommendations not addressed,
            "score":     float (0-1) fraction of Class I guidelines addressed,
        }
    """
    adherent = []
    missing = []

    # Extract representative action phrases (first 20 chars of recommendation)
    class_i_total = 0
    class_i_covered = 0

    combined_steps = " ".join(treatment_steps)

    for g in guidelines:
        # Build keyword set from recommendation text
        rec_words = set(re.split(r"[、。\s（）()「」]", g.recommendation))
        rec_words = {w for w in rec_words if len(w) >= 2}

        # Count how many keywords appear in the combined steps
        matches = sum(1 for w in rec_words if w in combined_steps)
        total_words = max(len(rec_words), 1)
        covered = (matches / total_words) >= 0.15  # at least 15 % of words present

        snippet = g.recommendation[:40] + ("…" if len(g.recommendation) > 40 else "")

        if covered:
            adherent.append(snippet)
        elif g.class_of_recommendation in ("I", "IIa"):
            missing.append(snippet)

        if g.class_of_recommendation == "I":
            class_i_total += 1
            if covered:
                class_i_covered += 1

    score = class_i_covered / max(class_i_total, 1)

    return {
        "adherent": adherent,
        "missing": missing,
        "score": round(score, 3),
    }


# ---------------------------------------------------------------------------
# Demo
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("=" * 70)
    print("Clinical Guideline Database Demo")
    print("=" * 70)

    # --- 1. List guidelines for ACS ---
    print("\n--- ACS Guidelines (ESC 2023 / AHA 2022) ---")
    acs_gl = get_guidelines("ACS")
    print(format_guidelines_text(acs_gl))

    # --- 2. Fuzzy lookup ---
    print("\n--- Fuzzy lookup: '心不全' ---")
    hf_gl = get_guidelines("心不全")
    print(f"Found {len(hf_gl)} guidelines for 心不全 (Heart Failure)")
    print(format_guidelines_text(hf_gl[:3]))

    # --- 3. Adherence check for a sample treatment plan ---
    print("\n--- Adherence Check: ACS Treatment Plan ---")
    treatment = [
        "12誘導心電図施行",
        "アスピリン200mg投与",
        "P2Y12阻害薬（チカグレロル）投与",
        "ヘパリン5000単位静注",
        "緊急冠動脈造影+PCI施行",
        "スタチン療法開始（アトルバスタチン40mg）",
    ]
    adherence = check_adherence(treatment, acs_gl)
    print(f"  Score         : {adherence['score']:.1%}")
    print(f"  Adherent ({len(adherence['adherent'])}): {adherence['adherent'][:3]}")
    print(f"  Missing  ({len(adherence['missing'])}): {adherence['missing'][:3]}")

    # --- 4. Stroke guidelines ---
    print("\n--- Stroke Guidelines ---")
    stroke_gl = get_guidelines("脳卒中")
    print(f"Found {len(stroke_gl)} guidelines")
    print(format_guidelines_text(stroke_gl[:2]))

    # --- 5. Sepsis adherence ---
    print("\n--- Sepsis Adherence Check ---")
    sepsis_treatment = [
        "血液培養2セット採取",
        "セフトリアキソン2g静注（1時間以内）",
        "生理食塩水30mL/kg輸液",
        "ノルエピネフリン開始（MAP 65mmHg目標）",
    ]
    sepsis_gl = get_guidelines("敗血症")
    sep_adherence = check_adherence(sepsis_treatment, sepsis_gl)
    print(f"  Score         : {sep_adherence['score']:.1%}")
    print(f"  Missing  ({len(sep_adherence['missing'])}): {sep_adherence['missing'][:2]}")

    print("\n" + "=" * 70)
    print(f"Total guidelines in database: {len(GUIDELINES)}")
    conditions = sorted({g.condition for g in GUIDELINES})
    print(f"Conditions covered: {conditions}")
    print("Done.")
