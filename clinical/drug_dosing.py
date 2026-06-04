"""
clinical/drug_dosing.py — Drug Dosing Calculator

成人薬用量計算機（腎機能・肝機能調整対応）。

実装薬剤 (30+):
  抗菌薬: セフトリアキソン・メロペネム・バンコマイシン・
          ピペラシリン-タゾバクタム・アジスロマイシン・クリンダマイシン
  循環器: フロセミド・ニトログリセリン・ドパミン・アミオダロン・
          アルテプラーゼ (PE/STEMI)
  神経:   ロラゼパム・フェニトイン・レベチラセタム・マンニトール
  鎮痛/鎮静: モルヒネ・フェンタニル・ケタミン・プロポフォール
  その他多数
"""

from __future__ import annotations

import difflib
from dataclasses import dataclass, field
from typing import Callable


# ===========================================================================
# データモデル
# ===========================================================================

@dataclass
class DoseCalculation:
    drug: str
    indication: str
    dose_text: str         # "500mg IV q8h"
    total_daily: str       # "1500mg/day"
    route: str
    duration: str
    adjustment_notes: list[str]   # 腎機能・肝機能調整メモ
    monitoring: list[str]
    max_dose: str | None = None
    contraindications: list[str] = field(default_factory=list)
    mechanism: str = ""


# ===========================================================================
# 薬剤計算関数型
# ===========================================================================

# signature: (indication, weight_kg, crcl, hepatic_impairment) -> DoseCalculation
_DoseFn = Callable[[str, float, float, bool], DoseCalculation]


# ===========================================================================
# 腎機能調整ユーティリティ
# ===========================================================================

def _renal_stage(crcl: float) -> str:
    if crcl >= 90:
        return "normal"
    elif crcl >= 60:
        return "mild"
    elif crcl >= 30:
        return "moderate"
    elif crcl >= 15:
        return "severe"
    else:
        return "esrd"  # End-Stage Renal Disease / ESRD


# ===========================================================================
# 薬剤実装 — 抗菌薬
# ===========================================================================

def _ceftriaxone(indication: str, weight_kg: float, crcl: float, hepatic: bool) -> DoseCalculation:
    ind = indication.lower()
    if "meningitis" in ind or "髄膜炎" in ind:
        dose = "2g IV q12h"
        total = "4g/day"
        dur = "14-21 日（起因菌・経過で調整）"
    elif "severe" in ind or "重症" in ind:
        dose = "2g IV q24h"
        total = "2g/day"
        dur = "5-14 日"
    else:
        dose = "1-2g IV q12-24h"
        total = "1-4g/day"
        dur = "5-10 日"

    adj: list[str] = []
    if crcl < 10 and hepatic:
        adj.append("重度腎・肝機能障害の併存 → 用量調整・モニタリング強化")
    elif crcl >= 10:
        adj.append("腎機能調整は通常不要（主に胆汁排泄）")

    if hepatic:
        adj.append("重篤な肝障害: 最大 2g/日を超えない")

    return DoseCalculation(
        drug="セフトリアキソン (Ceftriaxone)",
        indication=indication or "細菌感染症",
        dose_text=dose,
        total_daily=total,
        route="IV（30 分以上）/ IM",
        duration=dur,
        adjustment_notes=adj,
        monitoring=["腎機能（長期使用）", "胆嚢エコー（胆泥形成）", "アレルギー反応"],
        max_dose="4g/日（髄膜炎）",
        mechanism="第三世代セフェム：細胞壁合成阻害",
    )


def _meropenem(indication: str, weight_kg: float, crcl: float, hepatic: bool) -> DoseCalculation:
    ind = indication.lower()
    stage = _renal_stage(crcl)

    if "meningitis" in ind or "髄膜炎" in ind:
        base_dose = 2.0
        base_freq = "q8h"
        base_total = 6.0
    elif "severe" in ind or "esbl" in ind or "重症" in ind:
        base_dose = 2.0
        base_freq = "q8h"
        base_total = 6.0
    else:
        base_dose = 1.0
        base_freq = "q8h"
        base_total = 3.0

    adj: list[str] = []
    if stage == "normal":
        dose_text = f"{base_dose:.0f}g IV {base_freq}"
        total = f"{base_total:.0f}g/day"
        adj.append("腎機能正常 — 通常用量")
    elif stage == "mild":
        dose_text = f"{base_dose:.0f}g IV {base_freq}"
        total = f"{base_total:.0f}g/day"
        adj.append(f"軽度腎障害 (CrCl {crcl:.0f}) — 用量変更不要")
    elif stage == "moderate":
        new_dose = base_dose
        dose_text = f"{new_dose:.0f}g IV q12h"
        total = f"{new_dose*2:.0f}g/day"
        adj.append(f"中等度腎障害 (CrCl {crcl:.0f}) — 投与間隔を q12h に延長")
    elif stage == "severe":
        new_dose = base_dose * 0.5
        dose_text = f"{new_dose:.1f}g IV q12h"
        total = f"{new_dose*2:.1f}g/day"
        adj.append(f"重度腎障害 (CrCl {crcl:.0f}) — 用量 50% 減量、q12h")
    else:  # ESRD
        dose_text = f"{base_dose*0.5:.1f}g IV q24h"
        total = f"{base_dose*0.5:.1f}g/day"
        adj.append(f"ESRD (CrCl {crcl:.0f}) — 用量・頻度大幅調整。透析患者は透析後投与")

    if hepatic:
        adj.append("肝機能障害: 一般に調整不要（腎排泄が主）")

    return DoseCalculation(
        drug="メロペネム (Meropenem)",
        indication=indication or "重症細菌感染症/ESBL 産生菌",
        dose_text=dose_text,
        total_daily=total,
        route="IV（30 分以上、延長投与 3-4 時間も有効）",
        duration="5-14 日（臨床反応で決定）",
        adjustment_notes=adj,
        monitoring=["腎機能 2 日ごと", "痙攣（高用量・腎障害）", "Clostridioides difficile リスク"],
        max_dose="6g/日（髄膜炎）",
        mechanism="カルバペネム系：細胞壁合成阻害、広域スペクトル",
    )


def _vancomycin(indication: str, weight_kg: float, crcl: float, hepatic: bool) -> DoseCalculation:
    stage = _renal_stage(crcl)
    initial_dose_mg = max(15 * weight_kg, 500)
    initial_dose_mg = min(initial_dose_mg, 3000)

    adj: list[str] = []
    if stage == "normal":
        dose_text = f"{initial_dose_mg:.0f}mg IV q8-12h"
        total = f"{initial_dose_mg*2:.0f}-{initial_dose_mg*3:.0f}mg/day"
        adj.append("AUC/MIC 目標 400-600（TDM 必須）")
    elif stage == "mild":
        dose_text = f"{initial_dose_mg:.0f}mg IV q12h"
        total = f"{initial_dose_mg*2:.0f}mg/day"
        adj.append(f"軽度腎障害 (CrCl {crcl:.0f}) — 間隔を q12h に。TDM 必須")
    elif stage == "moderate":
        dose_text = f"{initial_dose_mg:.0f}mg IV q24h"
        total = f"{initial_dose_mg:.0f}mg/day"
        adj.append(f"中等度腎障害 (CrCl {crcl:.0f}) — q24h、TDM で用量調整")
    elif stage == "severe":
        dose_text = f"{initial_dose_mg:.0f}mg IV q48-72h（TDM 後調整）"
        total = "TDM で決定"
        adj.append(f"重度腎障害 (CrCl {crcl:.0f}) — 初回投与後は TDM で次回用量を決定")
    else:
        dose_text = f"{initial_dose_mg:.0f}mg IV（TDM で厳密管理）"
        total = "TDM で決定"
        adj.append("ESRD — 透析除去あり。透析後に必要量を再投与。TDM 厳重管理")

    return DoseCalculation(
        drug="バンコマイシン (Vancomycin)",
        indication=indication or "MRSA・グラム陽性菌重症感染",
        dose_text=dose_text,
        total_daily=total,
        route="IV（60 分以上かけて緩徐投与、速く投与するとレッドマン症候群）",
        duration="7-14 日（MRSA 菌血症は ≥2 週間）",
        adjustment_notes=adj,
        monitoring=[
            "AUC/MIC 目標 400-600（トラフ法なら 15-20 μg/mL）",
            "腎機能 2 日ごと",
            "レッドマン症候群（顔面・頸部の紅潮）",
            "耳毒性（高用量・長期使用）",
        ],
        max_dose="3000mg/回（体重・腎機能に応じて）",
        mechanism="グリコペプチド系：細胞壁合成阻害（D-Ala-D-Ala に結合）",
    )


def _pip_tazo(indication: str, weight_kg: float, crcl: float, hepatic: bool) -> DoseCalculation:
    stage = _renal_stage(crcl)
    adj: list[str] = []

    if stage in ("normal", "mild"):
        dose_text = "4.5g IV q6h（または延長投与 q8h 4 時間かけて）"
        total = "18g/day"
        adj.append("延長投与（4 時間）は PD パラメータ優位でβ-ラクタマーゼ産生菌に有効")
    elif stage == "moderate":
        dose_text = "4.5g IV q8h"
        total = "13.5g/day"
        adj.append(f"中等度腎障害 (CrCl {crcl:.0f}) — q6h → q8h に変更")
    elif stage == "severe":
        dose_text = "4.5g IV q12h"
        total = "9g/day"
        adj.append(f"重度腎障害 (CrCl {crcl:.0f}) — q12h")
    else:
        dose_text = "2.25g IV q12h"
        total = "4.5g/day"
        adj.append("ESRD (透析) — 2.25g q12h、追加投与はTDM後。透析で一部除去")

    return DoseCalculation(
        drug="ピペラシリン-タゾバクタム (Pip-Tazo)",
        indication=indication or "院内感染・腹腔内感染・医療関連肺炎",
        dose_text=dose_text,
        total_daily=total,
        route="IV（30 分以上）",
        duration="5-14 日",
        adjustment_notes=adj,
        monitoring=["腎機能", "電解質（高ナトリウム血症）", "好中球減少（長期使用）"],
        max_dose="18g ピペラシリン/日",
        mechanism="広域ペニシリン + β-ラクタマーゼ阻害薬",
    )


def _azithromycin(indication: str, weight_kg: float, crcl: float, hepatic: bool) -> DoseCalculation:
    adj: list[str] = []
    if hepatic:
        adj.append("重篤な肝障害（Child-Pugh C）: 禁忌または厳重注意")
    else:
        adj.append("腎機能調整: 不要（主に肝代謝・胆汁排泄）")

    return DoseCalculation(
        drug="アジスロマイシン (Azithromycin)",
        indication=indication or "非定型肺炎・咽頭炎・性感染症",
        dose_text="500mg PO/IV q24h",
        total_daily="500mg/day",
        route="PO または IV（1 時間以上）",
        duration="3-5 日（肺炎: 5 日、淋菌: 1-2g 単回）",
        adjustment_notes=adj,
        monitoring=["QTc 延長（他 QT 延長薬との併用注意）", "肝機能（長期使用）"],
        max_dose="500mg/日（一般）; 2g 単回（性感染症）",
        mechanism="マクロライド系：50S リボソームサブユニット阻害",
    )


def _clindamycin(indication: str, weight_kg: float, crcl: float, hepatic: bool) -> DoseCalculation:
    ind = indication.lower()
    if "severe" in ind or "重症" in ind:
        dose_text = "900mg IV q8h"
        total = "2700mg/day"
    else:
        dose_text = "600-900mg IV q8h"
        total = "1800-2700mg/day"

    adj: list[str] = []
    adj.append("腎機能調整: 不要（肝代謝）")
    if hepatic:
        adj.append("重篤な肝障害: 用量の 50% 減量。頻回モニタリング")

    return DoseCalculation(
        drug="クリンダマイシン (Clindamycin)",
        indication=indication or "嫌気性菌感染・MRSA 軟部組織感染",
        dose_text=dose_text,
        total_daily=total,
        route="IV（ゆっくり投与: 300mg を 10 分以上）/ PO",
        duration="5-14 日",
        adjustment_notes=adj,
        monitoring=["Clostridioides difficile 下痢（CDAD リスク高）", "肝機能"],
        max_dose="4800mg/日（例外的重症例）",
        mechanism="リンコサミド系：50S リボソーム阻害",
        contraindications=["既知の C. difficile 感染"],
    )


# ===========================================================================
# 薬剤実装 — 循環器
# ===========================================================================

def _furosemide(indication: str, weight_kg: float, crcl: float, hepatic: bool) -> DoseCalculation:
    stage = _renal_stage(crcl)
    adj: list[str] = []

    if stage in ("normal", "mild"):
        dose_text = "20-80mg IV ボーラス"
        total = "最大 600mg/日"
        adj.append("効果不十分（1 時間後に尿量 ≥150 mL なし）→ 2 倍量で再投与")
    elif stage == "moderate":
        dose_text = "40-120mg IV（高用量が必要）"
        total = "最大 600mg/日"
        adj.append(f"中等度腎障害 (CrCl {crcl:.0f}) — より高用量が必要な場合多い")
    else:
        dose_text = "80-200mg IV（ループ利尿薬抵抗性）"
        total = "最大 1000mg/日"
        adj.append(f"重度腎障害 (CrCl {crcl:.0f}) — 抵抗性が高い。持続投与 5-10mg/h を考慮")

    if hepatic:
        adj.append("肝硬変: アルドステロン拮抗薬との併用でより有効。低カリウム血症に注意")

    return DoseCalculation(
        drug="フロセミド (Furosemide)",
        indication=indication or "急性心不全・浮腫・高血圧",
        dose_text=dose_text,
        total_daily=total,
        route="IV ボーラス または 5-10mg/h 持続 IV（急性心不全重症）",
        duration="臨床反応で決定",
        adjustment_notes=adj,
        monitoring=["尿量（≥0.5 mL/kg/h 目標）", "電解質 (K・Mg・Na)", "BUN/Cr（AKI）", "BP（過剰利尿）"],
        max_dose="持続 IV: 10mg/h（反応性に応じて増量可）",
        mechanism="ループ利尿薬：ヘンレ係蹄上行脚 Na-K-2Cl 共輸送体阻害",
    )


def _nitroglycerin(indication: str, weight_kg: float, crcl: float, hepatic: bool) -> DoseCalculation:
    ind = indication.lower()
    if "acs" in ind or "angina" in ind or "狭心症" in ind or "acs" in ind:
        dose_text = "5-10 μg/min から開始、5 μg/min ずつ増量"
        total = "最大 400 μg/min"
    elif "heart failure" in ind or "心不全" in ind:
        dose_text = "5-20 μg/min から開始、10-20 μg/min ずつ増量"
        total = "最大 200 μg/min"
    else:
        dose_text = "5-200 μg/min IV（滴定）"
        total = "最大 400 μg/min"

    return DoseCalculation(
        drug="ニトログリセリン (Nitroglycerin)",
        indication=indication or "ACS・急性心不全・高血圧緊急症",
        dose_text=dose_text,
        total_daily=total,
        route="IV 持続（専用ルート: PVC チューブに吸着するためポリエチレン製チューブを使用）",
        duration="病態安定まで",
        adjustment_notes=["腎・肝機能調整: 不要", "耐性形成: 24 時間ごとに無投薬時間（8-12 時間）を設ける"],
        monitoring=["SBP（90 mmHg 以上を維持）", "頭痛（最も多い副作用）", "反射性頻脈"],
        max_dose="400 μg/min（実際は反応性で決定）",
        contraindications=["PDE5 阻害薬（シルデナフィル等）内服中 — 致死的低血圧"],
        mechanism="NO 放出 → グアニル酸シクラーゼ活性化 → 血管平滑筋弛緩（静脈 > 動脈）",
    )


def _dopamine(indication: str, weight_kg: float, crcl: float, hepatic: bool) -> DoseCalculation:
    ind = indication.lower()
    if "renal" in ind or "低用量" in ind or "low" in ind:
        dose_text = f"2-5 μg/kg/min（{weight_kg*2:.0f}-{weight_kg*5:.0f} μg/min）"
        total = "腎保護目的（エビデンス限定的）"
        effect = "腎血流増加・利尿（DA 受容体）"
    elif "cardiac" in ind or "inotrope" in ind or "心収縮" in ind:
        dose_text = f"5-10 μg/kg/min（{weight_kg*5:.0f}-{weight_kg*10:.0f} μg/min）"
        total = "心拍出量増加"
        effect = "β1 受容体作動（陽性変力）"
    else:
        dose_text = f"10-20 μg/kg/min（{weight_kg*10:.0f}-{weight_kg*20:.0f} μg/min）"
        total = "昇圧目的"
        effect = "α1 受容体作動（血管収縮・昇圧）"

    return DoseCalculation(
        drug="ドパミン (Dopamine)",
        indication=indication or f"ショック・心不全 — {effect}",
        dose_text=dose_text,
        total_daily="用量依存性に調整",
        route="IV 持続（中心静脈カテーテル推奨）",
        duration="臨床安定まで",
        adjustment_notes=["腎機能調整: 不要", "肝機能調整: 一般に不要"],
        monitoring=["BP・HR 連続（動脈ライン推奨）", "尿量", "不整脈（高用量）", "組織壊死リスク（末梢漏出）"],
        max_dose="20 μg/kg/min（より高用量は通常ノルエピネフリンに切替）",
        mechanism="用量依存的に DA1/DA2→β1→α1 受容体を順次刺激",
    )


def _amiodarone(indication: str, weight_kg: float, crcl: float, hepatic: bool) -> DoseCalculation:
    ind = indication.lower()
    if "vf" in ind or "vt" in ind or "cardiac arrest" in ind or "心停止" in ind:
        dose_text = "300mg IV ボーラス (3-5 分で)。反応なし → 150mg 追加"
        total = "心停止: 計 450mg まで"
        dur = "蘇生中"
    elif "af" in ind or "心房細動" in ind:
        dose_text = "150mg IV ボーラス (10 分) → 1mg/min × 6h → 0.5mg/min × 18h"
        total = "初日最大 2.2g/日"
        dur = "安定後に経口移行（200-400mg/日）"
    else:
        dose_text = "150mg IV ボーラス → 1mg/min × 6h → 0.5mg/min × 18h"
        total = "初日 2.2g 以内"
        dur = "安定後 経口 200mg/日"

    adj: list[str] = []
    adj.append("腎機能調整: 不要（主に肝代謝）")
    if hepatic:
        adj.append("重篤な肝障害: 禁忌または極めて慎重に（肝毒性リスク）")

    return DoseCalculation(
        drug="アミオダロン (Amiodarone)",
        indication=indication or "心室性頻脈・心房細動",
        dose_text=dose_text,
        total_daily=total,
        route="IV（中心静脈推奨; 末梢は血栓性静脈炎リスク）",
        duration=dur,
        adjustment_notes=adj,
        monitoring=[
            "QTc 延長（>500ms → 減量/中止）",
            "甲状腺機能（アミオダロンはヨード 37% 含有）",
            "肺毒性（間質性肺炎 — 慢性使用）",
            "肝機能（肝毒性）",
            "角膜沈着（長期使用 — 通常無症状）",
        ],
        max_dose="2.2g/日（初日）",
        contraindications=["洞不全症候群（ペースメーカーなし）", "高度 AV block（ペースメーカーなし）"],
        mechanism="Class III 抗不整脈薬：K+ チャネル遮断・Na+・Ca2+・β遮断作用も有する",
    )


def _alteplase(indication: str, weight_kg: float, crcl: float, hepatic: bool) -> DoseCalculation:
    ind = indication.lower()
    if "pe" in ind or "pulmonary embolism" in ind or "肺塞栓" in ind:
        dose_text = "100mg IV 2 時間かけて（大量 PE 緊急: 50mg ボーラス → 残り 50mg を 60 分）"
        total = "100mg"
        dur = "単回投与"
        max_dose = "100mg"
    elif "stemi" in ind or "心筋梗塞" in ind:
        dose_text = ("15mg IV ボーラス → 0.75mg/kg（最大 50mg）30 分で → "
                     "0.5mg/kg（最大 35mg）60 分で（総量 ≤100mg）")
        total = "最大 100mg"
        dur = "単回投与（PCI 施設不到達の場合の fibrinolysis）"
        max_dose = "100mg"
    else:  # 脳卒中
        dose_text = "0.9mg/kg（最大 90mg）: 10% を 1 分ボーラス → 残り 90% を 60 分で"
        total = f"{min(0.9 * weight_kg, 90):.0f}mg（体重依存、最大 90mg）"
        dur = "単回投与（虚血性脳卒中 4.5h 以内）"
        max_dose = "90mg"

    return DoseCalculation(
        drug="アルテプラーゼ tPA (Alteplase)",
        indication=indication or "大量肺塞栓症・虚血性脳卒中・STEMI（PCI 不可時）",
        dose_text=dose_text,
        total_daily=total,
        route="IV",
        duration=dur,
        adjustment_notes=["腎機能調整: 不要", "出血リスク厳格評価が必須"],
        monitoring=[
            "出血合併症（頭蓋内出血・消化管出血）",
            "神経学的変化（脳卒中）",
            "BP（SBP <180 mmHg 維持）",
            "投与後 24 時間は抗凝固・抗血小板薬禁止（脳卒中）",
        ],
        max_dose=max_dose,
        contraindications=[
            "活動性出血",
            "3 ヶ月以内の頭蓋内手術/外傷/脳卒中",
            "頭蓋内腫瘍/AVM",
            "SBP >185 mmHg（脳卒中: 投与前に降圧）",
        ],
        mechanism="組織型プラスミノーゲン活性化因子 → プラスミン → フィブリン溶解",
    )


# ===========================================================================
# 薬剤実装 — 神経
# ===========================================================================

def _lorazepam(indication: str, weight_kg: float, crcl: float, hepatic: bool) -> DoseCalculation:
    ind = indication.lower()
    if "seizure" in ind or "se" in ind or "痙攣" in ind:
        dose_mg = min(0.1 * weight_kg, 4.0)
        dose_text = f"0.1mg/kg IV（計 {dose_mg:.1f}mg）、2 分かけて投与"
        freq = "5-10 分後に効果不十分なら繰り返し（最大 2 回）"
    else:
        dose_text = "0.5-1mg PO/IV（不安・鎮静）"
        freq = "q6-8h PRN"

    adj: list[str] = []
    if hepatic:
        adj.append("重篤な肝障害: 低用量から開始。蓄積リスク（活性代謝物なし → 比較的安全）")
    adj.append("腎機能調整: 一般に不要（グルクロン酸抱合で代謝）")

    return DoseCalculation(
        drug="ロラゼパム (Lorazepam)",
        indication=indication or "痙攣重積・急性不安・アルコール離脱",
        dose_text=dose_text,
        total_daily="痙攣重積: 最大 8mg（2 回投与）",
        route="IV（緩徐）/ IM / PO",
        duration=freq,
        adjustment_notes=adj,
        monitoring=["呼吸抑制（SpO2・RR）", "鎮静レベル（RASS）", "低血圧"],
        max_dose="4mg/回（SE）、8mg（計 2 回）",
        contraindications=["重篤な呼吸不全（補助換気なしの場合）", "急性閉塞隅角緑内障"],
        mechanism="GABA-A 受容体へのベンゾジアゼピン結合部位で Cl- チャネル開口増強",
    )


def _phenytoin(indication: str, weight_kg: float, crcl: float, hepatic: bool) -> DoseCalculation:
    load_mg = min(20 * weight_kg, 1500)
    fos_pe = load_mg  # フォスフェニトインは PE 単位（1 mg PE ≒ 1 mg フェニトイン）

    adj: list[str] = []
    adj.append("腎機能調整: 用量調整不要（ただし低アルブミン血症 → 遊離型増加に注意）")
    if hepatic:
        adj.append("重篤な肝障害: 半減期延長。用量減量・TDM 必須")

    return DoseCalculation(
        drug="フェニトイン (Phenytoin) / フォスフェニトイン",
        indication=indication or "痙攣重積・てんかん発作",
        dose_text=f"フォスフェニトイン {fos_pe:.0f} mg PE IV（≤150 mg PE/min）心電図モニター下で投与",
        total_daily="維持: 5mg/kg/日 分 2-3",
        route="IV（フォスフェニトイン推奨: 末梢静脈でも安全）",
        duration="長期維持療法（神経科指導下）",
        adjustment_notes=adj,
        monitoring=[
            "心電図モニター（不整脈・PR 延長・QRS 幅）",
            "BP（低血圧）",
            "血中濃度（目標 10-20 μg/mL; 遊離型 1-2 μg/mL）",
            "注射部位（フェニトイン原液は組織壊死リスク）",
        ],
        max_dose="1500mg 負荷投与",
        contraindications=["洞不全症候群", "第 2・3 度 AV block"],
        mechanism="Na+ チャネル不活性化状態を延長（Class Ib 型）",
    )


def _levetiracetam(indication: str, weight_kg: float, crcl: float, hepatic: bool) -> DoseCalculation:
    stage = _renal_stage(crcl)
    load_mg = min(60 * weight_kg, 4500)

    adj: list[str] = []
    if stage == "normal":
        dose_text = f"60mg/kg IV 15 分で（計 {load_mg:.0f}mg）"
        adj.append("腎機能正常 — 通常用量")
    elif stage == "mild":
        adj.append(f"軽度腎障害 (CrCl {crcl:.0f}) — 維持量を 75% に")
        dose_text = f"{load_mg:.0f}mg 負荷"
    elif stage == "moderate":
        adj.append(f"中等度腎障害 (CrCl {crcl:.0f}) — 維持量を 50% に")
        dose_text = f"{load_mg:.0f}mg 負荷（維持量を 50% 減）"
    else:
        adj.append(f"重度腎障害/ESRD (CrCl {crcl:.0f}) — 維持量を 25-50% に。透析後に補充用量")
        dose_text = f"{load_mg:.0f}mg 負荷（維持量大幅調整）"

    return DoseCalculation(
        drug="レベチラセタム (Levetiracetam)",
        indication=indication or "痙攣重積（第二選択）・てんかん",
        dose_text=dose_text,
        total_daily="維持: 1000-3000mg/日 分 2",
        route="IV（15 分以上）/ PO",
        duration="長期維持（神経科指導下）",
        adjustment_notes=adj,
        monitoring=["腎機能（主要排泄経路）", "行動変容・易刺激性（副作用）", "てんかん発作頻度"],
        max_dose="4500mg 負荷、維持 3000mg/日",
        mechanism="SV2A（シナプス小胞糖タンパク質）に結合し神経終末の興奮性伝達を抑制",
    )


def _mannitol(indication: str, weight_kg: float, crcl: float, hepatic: bool) -> DoseCalculation:
    dose_lo = 0.5 * weight_kg
    dose_hi = min(1.0 * weight_kg, 100)
    dose_max = min(1.5 * weight_kg, 150)

    return DoseCalculation(
        drug="マンニトール (Mannitol) 20%",
        indication=indication or "頭蓋内圧亢進・脳ヘルニア",
        dose_text=f"{dose_lo:.0f}-{dose_hi:.0f}g IV 20-30 分かけて（1g/kg）",
        total_daily="反復投与: 0.25-0.5g/kg q4-6h",
        route="IV（フィルター付きで投与）",
        duration="頭蓋内圧正常化まで（通常数日）",
        adjustment_notes=[
            "腎機能低下（CrCl <30）: 蓄積リスク → 血漿浸透圧差 <20 mOsm/kg で中止考慮",
            f"腎障害時 (CrCl {crcl:.0f}): 使用を制限し生食による血管内容量管理と Hypertonic saline を代替考慮",
        ],
        monitoring=[
            "血漿浸透圧・浸透圧差（目標 310-320 mOsm/kg; <320 を超えないよう）",
            "電解質（低 Na・高 Na）",
            "尿量・体液バランス",
            "ICP モニター（可能であれば）",
            "BUN/Cr（腎機能）",
        ],
        max_dose=f"{dose_max:.0f}g（1.5mg/kg、単回最大値）",
        contraindications=["無尿性腎不全", "活動性頭蓋内出血（相対的禁忌）", "重篤な肺水腫"],
        mechanism="高浸透圧物質として脳実質から血管内への水分移動を促進（脳浮腫軽減）",
    )


# ===========================================================================
# 薬剤実装 — 鎮痛・鎮静
# ===========================================================================

def _morphine(indication: str, weight_kg: float, crcl: float, hepatic: bool) -> DoseCalculation:
    stage = _renal_stage(crcl)
    adj: list[str] = []

    if stage in ("normal", "mild"):
        dose_text = "2-4mg IV ボーラス、15 分ごとに滴定"
    elif stage == "moderate":
        dose_text = "1-2mg IV ボーラス（用量 50% 減）"
        adj.append(f"中等度腎障害 (CrCl {crcl:.0f}): 活性代謝物 M6G 蓄積 → 呼吸抑制リスク")
    else:
        dose_text = "0.5-1mg IV（最小用量から）"
        adj.append(f"重度腎障害/ESRD (CrCl {crcl:.0f}): M6G 蓄積著明 → フェンタニルへの変更を検討")

    if hepatic:
        adj.append("重篤な肝障害: 代謝低下・半減期延長。用量 50% 減")

    return DoseCalculation(
        drug="モルヒネ (Morphine)",
        indication=indication or "重篤な疼痛・急性心不全（補助）",
        dose_text=dose_text,
        total_daily="滴定によって決定",
        route="IV（緩徐）/ SC / 経口",
        duration="必要期間",
        adjustment_notes=adj if adj else ["通常の腎肝機能: 標準用量で開始"],
        monitoring=["SpO2・RR（呼吸抑制）", "RASS（鎮静レベル）", "腸蠕動（便秘）", "嘔気"],
        max_dose="滴定依存（有効な鎮痛が得られる最小量）",
        contraindications=["重篤な呼吸抑制（補助換気なし）"],
        mechanism="μ（ミュー）オピオイド受容体作動薬",
    )


def _fentanyl(indication: str, weight_kg: float, crcl: float, hepatic: bool) -> DoseCalculation:
    adj: list[str] = []
    adj.append("腎機能調整: 通常不要（非活性代謝物 → 腎障害患者でもモルヒネより安全）")
    if hepatic:
        adj.append("重篤な肝障害: CYP3A4 代謝低下 → 半減期延長。用量調整・モニタリング")

    return DoseCalculation(
        drug="フェンタニル (Fentanyl)",
        indication=indication or "急性疼痛・処置前鎮痛・ICU 鎮痛",
        dose_text="25-100μg IV ゆっくり投与（30 秒以上）; 追加: 25-50μg q15-30min",
        total_daily="ICU 持続: 25-100μg/h（滴定）",
        route="IV ボーラス / IV 持続 / 経皮（慢性痛）",
        duration="急性期: 必要期間; ICU: 鎮痛鎮静プロトコルに従う",
        adjustment_notes=adj,
        monitoring=["SpO2・RR（呼吸抑制）", "筋肉硬直（高速ボーラス時）", "RASS"],
        max_dose="滴定依存",
        contraindications=["重篤な呼吸抑制（補助換気なし）", "MAO 阻害薬使用中（セロトニン症候群）"],
        mechanism="μ・κ・δ オピオイド受容体作動薬（主に μ）。高い脂溶性で血脳関門を迅速透過",
    )


def _ketamine(indication: str, weight_kg: float, crcl: float, hepatic: bool) -> DoseCalculation:
    ind = indication.lower()
    if "dissoc" in ind or "induction" in ind or "全身麻酔" in ind:
        dose_text = f"1-2mg/kg IV（体重 {weight_kg:.0f}kg: {weight_kg:.0f}-{weight_kg*2:.0f}mg）"
        note = "気管挿管誘導（RSI）に使用"
    elif "analg" in ind or "鎮痛" in ind:
        dose_text = f"0.1-0.3mg/kg IV（体重 {weight_kg:.0f}kg: {weight_kg*0.1:.0f}-{weight_kg*0.3:.0f}mg）"
        note = "低用量鎮痛（オピオイド節約効果）"
    else:
        dose_text = f"0.5-2mg/kg IV（体重 {weight_kg:.0f}kg: {weight_kg*0.5:.0f}-{weight_kg*2:.0f}mg）"
        note = "解離性麻酔"

    adj: list[str] = []
    adj.append("腎機能調整: 一般に不要")
    if hepatic:
        adj.append("重篤な肝障害: CYP3A4/2B6 代謝低下 → 半減期延長")

    return DoseCalculation(
        drug="ケタミン (Ketamine)",
        indication=indication or note,
        dose_text=dose_text,
        total_daily="用途により異なる",
        route="IV / IM（筋注: 4-6mg/kg）",
        duration="単回または短時間手技",
        adjustment_notes=adj,
        monitoring=["血圧・HR（交感神経刺激により上昇）", "気道分泌物（増加 → アトロピン前投与を検討）", "幻覚・悪夢（回復時）"],
        max_dose="2mg/kg（解離性麻酔）",
        mechanism="NMDA 受容体拮抗薬。気管支拡張作用あり（喘息緊急時に有用）",
    )


def _propofol(indication: str, weight_kg: float, crcl: float, hepatic: bool) -> DoseCalculation:
    adj: list[str] = []
    adj.append("腎機能調整: 不要（肝代謝・肺代謝）")
    if hepatic:
        adj.append("重篤な肝障害: クリアランス低下 → 低用量から開始")

    dose_lo = 0.5 * weight_kg
    dose_hi = 4.0 * weight_kg

    return DoseCalculation(
        drug="プロポフォール (Propofol)",
        indication=indication or "ICU 鎮静・短時間処置の鎮静",
        dose_text=f"0.5-4mg/kg/h 持続 IV（体重 {weight_kg:.0f}kg: {dose_lo:.0f}-{dose_hi:.0f}mg/h）",
        total_daily="4mg/kg/h 以上・48 時間超は PRIS リスク",
        route="IV 持続（専用ルート）",
        duration="必要期間（PRIS リスク管理に注意）",
        adjustment_notes=adj,
        monitoring=[
            "RASS（鎮静深度）— 目標は適応による（RASS -2 を目標が多い）",
            "トリグリセリド（プロポフォールは脂肪乳剤 1.1 kcal/mL）",
            "PRIS（プロポフォール注入症候群）: 代謝アシドーシス・横紋筋融解 → 高用量長期は禁忌",
            "低血圧（急速投与・高用量）",
        ],
        max_dose="4mg/kg/h（ICU）; 短時間処置では 6mg/kg/h まで",
        contraindications=["大豆・卵アレルギー（乳剤の成分）"],
        mechanism="GABA-A 受容体陽性アロステリック調節薬",
    )


# ===========================================================================
# その他の薬剤（簡略実装）
# ===========================================================================

def _norepinephrine(indication: str, weight_kg: float, crcl: float, hepatic: bool) -> DoseCalculation:
    return DoseCalculation(
        drug="ノルエピネフリン (Norepinephrine)",
        indication=indication or "敗血症性ショック・血管拡張性ショック",
        dose_text=f"0.01-3.0 μg/kg/min（{weight_kg:.0f}kg: {weight_kg*0.01:.1f}-{weight_kg*3:.0f} μg/min）",
        total_daily="滴定依存",
        route="IV 持続（中心静脈カテーテル推奨）",
        duration="MAP ≥65 mmHg 安定まで",
        adjustment_notes=["腎・肝機能調整: 不要", "末梢漏出は組織壊死リスク → 中心静脈ライン使用"],
        monitoring=["動脈ライン推奨（連続 BP）", "四肢末梢循環（虚血）", "HR（反射性徐脈）"],
        max_dose="3 μg/kg/min（一般的上限。超えるなら血管収縮薬追加を考慮）",
        mechanism="強力なα1 作動薬（β1 もやや刺激）→ 末梢血管収縮・BP 上昇",
    )


def _dobutamine(indication: str, weight_kg: float, crcl: float, hepatic: bool) -> DoseCalculation:
    return DoseCalculation(
        drug="ドブタミン (Dobutamine)",
        indication=indication or "急性心不全・心原性ショック（心収縮力低下）",
        dose_text=f"2.5-10 μg/kg/min（{weight_kg:.0f}kg: {weight_kg*2.5:.0f}-{weight_kg*10:.0f} μg/min）",
        total_daily="滴定依存",
        route="IV 持続",
        duration="心不全安定まで",
        adjustment_notes=["腎・肝機能調整: 不要"],
        monitoring=["HR・BP 連続", "心調律（頻脈性不整脈）", "心エコーによる CO/EF 評価"],
        max_dose="20 μg/kg/min（頻脈リスク増大）",
        mechanism="β1 受容体作動 → 陽性変力作用（心拍出量増加）; 軽度 β2 で末梢血管拡張",
    )


def _heparin(indication: str, weight_kg: float, crcl: float, hepatic: bool) -> DoseCalculation:
    ind = indication.lower()
    if "acs" in ind or "stemi" in ind or "pe" in ind or "dvt" in ind:
        bolus = min(80 * weight_kg, 8000)
        infusion = 18 * weight_kg
        dose_text = f"{bolus:.0f} IU IV ボーラス → {infusion:.0f} IU/h 持続（体重調整プロトコル）"
    else:
        dose_text = "60-70 IU/kg IV ボーラス → 12-15 IU/kg/h 持続"
    return DoseCalculation(
        drug="ヘパリン未分画 (UFH)",
        indication=indication or "ACS・PE・DVT・体外循環",
        dose_text=dose_text,
        total_daily="APTT 60-80 秒（1.5-2.5 × 正常値）を目標に調整",
        route="IV 持続",
        duration="橋渡し療法まで または 5-7 日（DVT/PE）",
        adjustment_notes=["腎機能調整: 一般に不要", "肝機能調整: 一般に不要（逆に肝障害で過凝固もある）"],
        monitoring=["APTT 6 時間ごと（安定後 24 時間ごと）", "血小板（HIT: 投与 4-14 日目に低下）", "出血症状"],
        max_dose="APTT で制御（目標値超過なら減量）",
        contraindications=["活動性出血", "HIT 既往", "最近の頭蓋内手術"],
        mechanism="アンチトロンビン III を活性化 → Xa・トロンビンを阻害",
    )


def _metoprolol(indication: str, weight_kg: float, crcl: float, hepatic: bool) -> DoseCalculation:
    return DoseCalculation(
        drug="メトプロロール (Metoprolol)",
        indication=indication or "高血圧・AF・ACS・心不全",
        dose_text="急性: 5mg IV 5 分ごと × 3 回; 慢性: 25-200mg PO BID",
        total_daily="最大 400mg/日（PO）",
        route="IV（急性）/ PO（維持）",
        duration="長期（慢性疾患）",
        adjustment_notes=["腎機能調整: 一般に不要", "重篤な肝障害: 用量半減"],
        monitoring=["HR（目標 <60 bpm）", "BP", "喘息・気管支痙攣"],
        max_dose="15mg IV（急性期）",
        contraindications=["喘息・重症 COPD（相対的）", "高度徐脈・AV block"],
        mechanism="選択的 β1 受容体遮断薬",
    )


# ===========================================================================
# 薬剤レジストリ
# ===========================================================================

_DRUG_REGISTRY: dict[str, _DoseFn] = {
    # 抗菌薬
    "ceftriaxone":           _ceftriaxone,
    "meropenem":             _meropenem,
    "vancomycin":            _vancomycin,
    "piperacillin-tazobactam": _pip_tazo,
    "pip-tazo":              _pip_tazo,
    "piptazo":               _pip_tazo,
    "azithromycin":          _azithromycin,
    "clindamycin":           _clindamycin,
    # 循環器
    "furosemide":            _furosemide,
    "nitroglycerin":         _nitroglycerin,
    "dopamine":              _dopamine,
    "amiodarone":            _amiodarone,
    "alteplase":             _alteplase,
    "tpa":                   _alteplase,
    "norepinephrine":        _norepinephrine,
    "noradrenaline":         _norepinephrine,
    "dobutamine":            _dobutamine,
    "heparin":               _heparin,
    "metoprolol":            _metoprolol,
    # 神経
    "lorazepam":             _lorazepam,
    "phenytoin":             _phenytoin,
    "fosphenytoin":          _phenytoin,
    "levetiracetam":         _levetiracetam,
    "mannitol":              _mannitol,
    # 鎮痛・鎮静
    "morphine":              _morphine,
    "fentanyl":              _fentanyl,
    "ketamine":              _ketamine,
    "propofol":              _propofol,
}

# 日本語 → 英語キーマッピング
_JA_DRUG_MAP: dict[str, str] = {
    "セフトリアキソン": "ceftriaxone",
    "ロセフィン": "ceftriaxone",
    "メロペネム": "meropenem",
    "メロペン": "meropenem",
    "バンコマイシン": "vancomycin",
    "ピペラシリンタゾバクタム": "piperacillin-tazobactam",
    "ゾシン": "piperacillin-tazobactam",
    "アジスロマイシン": "azithromycin",
    "ジスロマック": "azithromycin",
    "クリンダマイシン": "clindamycin",
    "ダラシン": "clindamycin",
    "フロセミド": "furosemide",
    "ラシックス": "furosemide",
    "ニトログリセリン": "nitroglycerin",
    "ミリスロール": "nitroglycerin",
    "ドパミン": "dopamine",
    "アミオダロン": "amiodarone",
    "アンカロン": "amiodarone",
    "アルテプラーゼ": "alteplase",
    "グルトパ": "alteplase",
    "ノルエピネフリン": "norepinephrine",
    "ノルアドレナリン": "norepinephrine",
    "ドブタミン": "dobutamine",
    "ドブトレックス": "dobutamine",
    "ヘパリン": "heparin",
    "メトプロロール": "metoprolol",
    "セロケン": "metoprolol",
    "ロラゼパム": "lorazepam",
    "ワイパックス": "lorazepam",
    "フェニトイン": "phenytoin",
    "アレビアチン": "phenytoin",
    "フォスフェニトイン": "fosphenytoin",
    "レベチラセタム": "levetiracetam",
    "イーケプラ": "levetiracetam",
    "マンニトール": "mannitol",
    "モルヒネ": "morphine",
    "フェンタニル": "fentanyl",
    "ケタミン": "ketamine",
    "ケタラール": "ketamine",
    "プロポフォール": "propofol",
    "ディプリバン": "propofol",
}


def calc_dose(
    drug: str,
    indication: str = "",
    weight_kg: float = 70.0,
    crcl: float = 100.0,
    hepatic_impairment: bool = False,
) -> DoseCalculation:
    """
    薬剤の投与量を計算する（腎・肝機能調整対応）。

    Parameters
    ----------
    drug : str
        薬剤名（英語・日本語対応）
    indication : str
        適応（空欄時はデフォルト適応で計算）
    weight_kg : float
        体重 (kg)。デフォルト 70 kg
    crcl : float
        クレアチニンクリアランス mL/min。デフォルト 100 (正常)
    hepatic_impairment : bool
        肝機能障害の有無

    Returns
    -------
    DoseCalculation

    Raises
    ------
    ValueError
        登録されていない薬剤名の場合
    """
    d = drug.lower().strip().replace(" ", "").replace("　", "")

    # 日本語マッピング
    if drug in _JA_DRUG_MAP:
        d = _JA_DRUG_MAP[drug]
    elif drug.strip() in _JA_DRUG_MAP:
        d = _JA_DRUG_MAP[drug.strip()]

    # 直接マッチ
    if d in _DRUG_REGISTRY:
        return _DRUG_REGISTRY[d](indication, weight_kg, crcl, hepatic_impairment)

    # ハイフン・スペース除去後マッチ
    d_clean = d.replace("-", "").replace("_", "")
    for key, fn in _DRUG_REGISTRY.items():
        if d_clean == key.replace("-", "").replace("_", ""):
            return fn(indication, weight_kg, crcl, hepatic_impairment)

    # ファジーマッチング
    all_keys = list(_DRUG_REGISTRY.keys()) + list(_JA_DRUG_MAP.keys())
    matches = difflib.get_close_matches(drug.lower(), [k.lower() for k in all_keys], n=3, cutoff=0.55)
    if matches:
        candidates = ", ".join(matches)
        raise ValueError(
            f"薬剤 '{drug}' は登録されていません。"
            f"近い薬剤名: {candidates}"
        )

    all_registered = ", ".join(sorted(_DRUG_REGISTRY.keys()))
    raise ValueError(
        f"薬剤 '{drug}' は登録されていません。"
        f"登録薬剤: {all_registered}"
    )


def list_drugs() -> list[str]:
    """登録されている薬剤名の一覧を返す。"""
    return sorted(set(list(_DRUG_REGISTRY.keys()) + list(_JA_DRUG_MAP.keys())))


def format_dose_result(result: DoseCalculation) -> str:
    """DoseCalculation を読みやすいテキストに整形する。"""
    sep = "─" * 60
    lines = [
        sep,
        f"  薬剤: {result.drug}",
        f"  適応: {result.indication}",
        sep,
        f"  用量:      {result.dose_text}",
        f"  1日総量:   {result.total_daily}",
        f"  投与経路:  {result.route}",
        f"  投与期間:  {result.duration}",
    ]
    if result.max_dose:
        lines.append(f"  最大用量:  {result.max_dose}")

    if result.adjustment_notes:
        lines.append("\n  [腎・肝機能調整]")
        for note in result.adjustment_notes:
            lines.append(f"    • {note}")

    if result.monitoring:
        lines.append("\n  [モニタリング]")
        for m in result.monitoring:
            lines.append(f"    • {m}")

    if result.contraindications:
        lines.append("\n  [禁忌]")
        for c in result.contraindications:
            lines.append(f"    ✗ {c}")

    if result.mechanism:
        lines.append(f"\n  [作用機序] {result.mechanism}")

    lines.append(sep)
    return "\n".join(lines)


# ===========================================================================
# デモ
# ===========================================================================

if __name__ == "__main__":
    print("=" * 62)
    print("  Drug Dosing Calculator — デモ")
    print("=" * 62)

    # 登録薬剤一覧
    print("\n--- 登録薬剤 ---")
    drugs = [k for k in sorted(_DRUG_REGISTRY.keys())]
    for i, d in enumerate(drugs):
        end = "\n" if (i + 1) % 5 == 0 else "  "
        print(f"{d}", end=end)
    print()

    # 通常腎機能
    print("\n--- 通常例 (体重 70 kg, CrCl 100) ---")
    tests = [
        ("vancomycin", "MRSA bacteremia"),
        ("meropenem", "ESBL 産生菌肺炎"),
        ("amiodarone", "心室細動"),
        ("alteplase", "大量肺塞栓"),
        ("ketamine", "解離性鎮痛"),
        ("propofol", "ICU sedation"),
    ]
    for drug_name, ind in tests:
        result = calc_dose(drug_name, indication=ind, weight_kg=70, crcl=100)
        print(f"\n  [{result.drug}]")
        print(f"    用量: {result.dose_text}")
        print(f"    経路: {result.route}")
        if result.adjustment_notes:
            print(f"    調整: {result.adjustment_notes[0]}")

    # 腎機能低下例
    print("\n\n--- 腎機能低下 (CrCl 20 mL/min, 体重 60 kg) ---")
    renal_tests = [
        "vancomycin",
        "meropenem",
        "levetiracetam",
        "mannitol",
        "morphine",
    ]
    for drug_name in renal_tests:
        r = calc_dose(drug_name, weight_kg=60, crcl=20)
        print(f"\n  [{r.drug}]")
        print(f"    用量: {r.dose_text}")
        for note in r.adjustment_notes:
            print(f"    調整: {note}")

    # フルフォーマット出力
    print("\n\n--- フルフォーマット: バンコマイシン (腎障害例) ---")
    full = calc_dose("vancomycin", indication="MRSA 菌血症", weight_kg=65, crcl=35)
    print(format_dose_result(full))

    # 日本語薬剤名
    print("\n--- 日本語薬剤名テスト ---")
    ja_tests = ["ノルエピネフリン", "ロラゼパム", "フロセミド", "アミオダロン"]
    for ja_name in ja_tests:
        r = calc_dose(ja_name, weight_kg=70)
        print(f"  {ja_name} → {r.drug}: {r.dose_text}")

    # ファジーマッチングエラー
    print("\n--- ファジーマッチング（未登録薬） ---")
    try:
        calc_dose("vankomisin")
    except ValueError as e:
        print(f"  ValueError: {e}")
