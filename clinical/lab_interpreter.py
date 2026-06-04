"""
clinical/lab_interpreter.py — Lab Value Interpreter

検査値文字列または辞書を受け取り、基準値と比較して異常フラグを立てる。

対応入力形式:
  "WBC 14000, CRP 8.5, TnI 0.8, BNP 450, D-dimer 2.5, Cr 2.1"
  {"WBC": 14000, "CRP": 8.5}
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal


# ===========================================================================
# データモデル
# ===========================================================================

@dataclass
class LabFlag:
    name: str
    value: float
    status: Literal["critical_high", "critical_low", "high", "low", "normal"]
    unit: str
    message: str
    ref_range: str = ""


@dataclass
class LabResult:
    flags: list[LabFlag]
    summary: str
    parsed: dict[str, float]   # パースできた項目の生データ


# ===========================================================================
# 基準値定義
# ===========================================================================
# 形式: キー → (表示名, 単位, crit_low, warn_low, warn_high, crit_high, 参考範囲文字列, コメント関数)
# None は「その方向の閾値なし」を意味する。

_REF: dict[str, dict] = {
    # --- 血球系 ---
    "WBC": {
        "name": "白血球数",
        "name_en": "White Blood Cell",
        "unit": "/μL",
        "crit_low": 2000,
        "warn_low": 3500,
        "warn_high": 9700,
        "crit_high": 30000,
        "ref_range": "3500–9700 /μL",
        "high_msg": "白血球増多: 感染・炎症・血液疾患を考慮",
        "low_msg": "白血球減少: 骨髄抑制・ウイルス感染・薬剤性を考慮",
        "crit_high_msg": "著明な白血球増多: 白血病緊急または重症感染を除外",
        "crit_low_msg": "危機的白血球減少: 敗血症リスク高・無菌管理が必要",
    },
    "RBC": {
        "name": "赤血球数",
        "name_en": "Red Blood Cell",
        "unit": "×10⁴/μL",
        "crit_low": 200,
        "warn_low": 380,   # 女性基準で低め設定
        "warn_high": 600,
        "crit_high": None,
        "ref_range": "男性 427–570, 女性 376–500 ×10⁴/μL",
        "high_msg": "赤血球増多",
        "low_msg": "赤血球減少: 貧血",
        "crit_low_msg": "重篤な貧血: 輸血適応を評価",
        "crit_high_msg": None,
    },
    "HGB": {
        "name": "ヘモグロビン",
        "name_en": "Hemoglobin",
        "unit": "g/dL",
        "crit_low": 7.0,
        "warn_low": 12.0,  # 女性下限基準
        "warn_high": 17.5,
        "crit_high": None,
        "ref_range": "男性 13.7–16.8, 女性 11.6–14.8 g/dL",
        "high_msg": "高ヘモグロビン: 脱水・多血症を考慮",
        "low_msg": "貧血: 原因精査を要す",
        "crit_low_msg": "重篤な貧血 (Hgb<7): 輸血・原因検索が急務",
        "crit_high_msg": None,
    },
    "HCT": {
        "name": "ヘマトクリット",
        "name_en": "Hematocrit",
        "unit": "%",
        "crit_low": 20,
        "warn_low": 36,
        "warn_high": 54,
        "crit_high": None,
        "ref_range": "男性 40–52%, 女性 36–47%",
        "high_msg": "高ヘマトクリット: 脱水・多血症",
        "low_msg": "低ヘマトクリット: 貧血",
        "crit_low_msg": "危機的貧血: 緊急輸血評価",
        "crit_high_msg": None,
    },
    "PLT": {
        "name": "血小板数",
        "name_en": "Platelet",
        "unit": "×10³/μL",
        "crit_low": 20,
        "warn_low": 100,
        "warn_high": 400,
        "crit_high": 1000,
        "ref_range": "150–350 ×10³/μL",
        "high_msg": "血小板増多: 反応性または本態性血小板血症",
        "low_msg": "血小板減少: 出血リスク上昇",
        "crit_low_msg": "危機的血小板減少 (<20): 自然出血の危険・緊急輸血を検討",
        "crit_high_msg": "著明な血小板増多: 血栓リスク増大",
    },
    # --- 炎症・感染マーカー ---
    "CRP": {
        "name": "C反応性蛋白",
        "name_en": "C-reactive Protein",
        "unit": "mg/dL",
        "crit_low": None,
        "warn_low": None,
        "warn_high": 0.3,
        "crit_high": 10.0,
        "ref_range": "<0.3 mg/dL",
        "high_msg": "CRP 上昇: 炎症・感染を示唆",
        "low_msg": None,
        "crit_high_msg": "高度 CRP 上昇: 重篤な感染・敗血症・膠原病を疑う",
        "crit_low_msg": None,
    },
    "PCT": {
        "name": "プロカルシトニン",
        "name_en": "Procalcitonin",
        "unit": "ng/mL",
        "crit_low": None,
        "warn_low": None,
        "warn_high": 0.1,
        "crit_high": 10.0,
        "ref_range": "<0.1 ng/mL",
        "high_msg": "PCT 上昇: 細菌感染・敗血症を示唆",
        "low_msg": None,
        "crit_high_msg": "高度 PCT 上昇 (>10): 重症敗血症・敗血症性ショックを強く示唆",
        "crit_low_msg": None,
    },
    # --- 心筋マーカー ---
    "TNI": {
        "name": "トロポニンI",
        "name_en": "Troponin I",
        "unit": "ng/mL",
        "crit_low": None,
        "warn_low": None,
        "warn_high": 0.04,
        "crit_high": 0.4,
        "ref_range": "<0.04 ng/mL",
        "high_msg": "トロポニンI 上昇: 心筋障害・ACS を疑う。連続測定・心電図精査が必要",
        "low_msg": None,
        "crit_high_msg": "著明なトロポニンI 上昇 (>10倍): AMI または大規模心筋障害を示唆。緊急カテーテル評価",
        "crit_low_msg": None,
    },
    "TNT": {
        "name": "トロポニンT",
        "name_en": "Troponin T",
        "unit": "ng/mL",
        "crit_low": None,
        "warn_low": None,
        "warn_high": 0.014,
        "crit_high": 0.1,
        "ref_range": "<0.014 ng/mL",
        "high_msg": "トロポニンT 上昇: 心筋障害を示唆",
        "low_msg": None,
        "crit_high_msg": "著明なトロポニンT 上昇: AMI を強く示唆",
        "crit_low_msg": None,
    },
    "HSCTNT": {
        "name": "高感度トロポニンT",
        "name_en": "hs-cTnT",
        "unit": "pg/mL",
        "crit_low": None,
        "warn_low": None,
        "warn_high": 14.0,
        "crit_high": 53.0,
        "ref_range": "<14 pg/mL",
        "high_msg": "hs-cTnT 上昇: 心筋障害を示唆",
        "low_msg": None,
        "crit_high_msg": "hs-cTnT 著明上昇: AMI に準じた対応を",
        "crit_low_msg": None,
    },
    "BNP": {
        "name": "BNP",
        "name_en": "B-type Natriuretic Peptide",
        "unit": "pg/mL",
        "crit_low": None,
        "warn_low": None,
        "warn_high": 18.4,
        "crit_high": 200.0,
        "ref_range": "<18.4 pg/mL",
        "high_msg": "BNP 上昇: 心負荷増大・心不全を疑う",
        "low_msg": None,
        "crit_high_msg": "高度 BNP 上昇 (>200): 心不全の強い指標。利尿薬・心不全治療の開始を考慮",
        "crit_low_msg": None,
    },
    "NTPROBNP": {
        "name": "NT-proBNP",
        "name_en": "NT-proBNP",
        "unit": "pg/mL",
        "crit_low": None,
        "warn_low": None,
        "warn_high": 125.0,
        "crit_high": 1000.0,
        "ref_range": "<125 pg/mL",
        "high_msg": "NT-proBNP 上昇: 心不全・心負荷増大を示唆",
        "low_msg": None,
        "crit_high_msg": "高度 NT-proBNP 上昇: 重症心不全を疑う",
        "crit_low_msg": None,
    },
    # --- 凝固系 ---
    "DDIMER": {
        "name": "Dダイマー",
        "name_en": "D-dimer",
        "unit": "μg/mL FEU",
        "crit_low": None,
        "warn_low": None,
        "warn_high": 1.0,
        "crit_high": 5.0,
        "ref_range": "<1.0 μg/mL FEU",
        "high_msg": "D ダイマー上昇: 肺塞栓・深部静脈血栓・播種性血管内凝固 (DIC) を考慮",
        "low_msg": None,
        "crit_high_msg": "D ダイマー著明上昇: 大動脈解離・重症 PE・DIC の可能性。緊急精査が必要",
        "crit_low_msg": None,
    },
    "INR": {
        "name": "INR (PT-INR)",
        "name_en": "International Normalized Ratio",
        "unit": "",
        "crit_low": None,
        "warn_low": None,
        "warn_high": 1.1,
        "crit_high": 3.0,
        "ref_range": "0.9–1.1",
        "high_msg": "PT-INR 延長: 肝機能障害・ビタミンK欠乏・抗凝固薬を考慮",
        "low_msg": None,
        "crit_high_msg": "PT-INR 著明延長 (>3): 出血リスク高。ワーファリン過剰・重症肝障害",
        "crit_low_msg": None,
    },
    "FIBRINOGEN": {
        "name": "フィブリノゲン",
        "name_en": "Fibrinogen",
        "unit": "mg/dL",
        "crit_low": 100,
        "warn_low": 200,
        "warn_high": 400,
        "crit_high": None,
        "ref_range": "200–400 mg/dL",
        "high_msg": "フィブリノゲン高値: 炎症・急性期反応",
        "low_msg": "フィブリノゲン低下: 出血リスク",
        "crit_low_msg": "フィブリノゲン危機的低値: DIC を強く疑う",
        "crit_high_msg": None,
    },
    # --- 腎機能 ---
    "CR": {
        "name": "クレアチニン",
        "name_en": "Creatinine",
        "unit": "mg/dL",
        "crit_low": None,
        "warn_low": None,
        "warn_high": 1.07,   # 男性上限 (女性: 0.79)
        "crit_high": 5.0,
        "ref_range": "男性 0.65–1.07, 女性 0.46–0.79 mg/dL",
        "high_msg": "クレアチニン上昇: 腎機能障害 (AKI/CKD) を評価",
        "low_msg": None,
        "crit_high_msg": "重篤なクレアチニン上昇: 重症腎不全。透析適応の評価を",
        "crit_low_msg": None,
    },
    "BUN": {
        "name": "BUN (血中尿素窒素)",
        "name_en": "Blood Urea Nitrogen",
        "unit": "mg/dL",
        "crit_low": None,
        "warn_low": None,
        "warn_high": 20.0,
        "crit_high": 100.0,
        "ref_range": "8–20 mg/dL",
        "high_msg": "BUN 上昇: 腎機能障害・タンパク異化亢進・脱水を考慮",
        "low_msg": None,
        "crit_high_msg": "BUN 著明上昇: 重症腎不全・尿毒症症状に注意",
        "crit_low_msg": None,
    },
    # --- 電解質 ---
    "NA": {
        "name": "ナトリウム",
        "name_en": "Sodium",
        "unit": "mEq/L",
        "crit_low": 125,
        "warn_low": 136,
        "warn_high": 145,
        "crit_high": 155,
        "ref_range": "136–145 mEq/L",
        "high_msg": "高ナトリウム血症: 脱水・過剰 Na 投与",
        "low_msg": "低ナトリウム血症: SIADH・心不全・肝硬変・過剰輸液",
        "crit_high_msg": "危機的高 Na: 中枢神経症状・昏睡リスク",
        "crit_low_msg": "危機的低 Na (<125): 脳浮腫・痙攣リスク。緊急補正を考慮",
    },
    "K": {
        "name": "カリウム",
        "name_en": "Potassium",
        "unit": "mEq/L",
        "crit_low": 2.5,
        "warn_low": 3.5,
        "warn_high": 5.0,
        "crit_high": 6.5,
        "ref_range": "3.5–5.0 mEq/L",
        "high_msg": "高カリウム血症: 腎不全・代謝性アシドーシス・薬剤性",
        "low_msg": "低カリウム血症: 利尿薬・下痢・嘔吐・不整脈リスク",
        "crit_high_msg": "危機的高 K (>6.5): 致死的不整脈リスク。心電図確認・緊急降下処置",
        "crit_low_msg": "危機的低 K (<2.5): 致死的不整脈・横紋筋融解症リスク",
    },
    "CL": {
        "name": "クロール",
        "name_en": "Chloride",
        "unit": "mEq/L",
        "crit_low": 85,
        "warn_low": 98,
        "warn_high": 108,
        "crit_high": 120,
        "ref_range": "98–108 mEq/L",
        "high_msg": "高クロール血症",
        "low_msg": "低クロール血症",
        "crit_high_msg": "危機的高 Cl: 代謝性アシドーシス",
        "crit_low_msg": "危機的低 Cl: 代謝性アルカローシス",
    },
    "CA": {
        "name": "カルシウム",
        "name_en": "Calcium",
        "unit": "mg/dL",
        "crit_low": 7.0,
        "warn_low": 8.4,
        "warn_high": 10.2,
        "crit_high": 13.0,
        "ref_range": "8.4–10.2 mg/dL",
        "high_msg": "高カルシウム血症: 副甲状腺機能亢進・悪性腫瘍",
        "low_msg": "低カルシウム血症: テタニー・痙攣リスク",
        "crit_high_msg": "危機的高 Ca: 意識障害・不整脈・腎機能障害",
        "crit_low_msg": "危機的低 Ca: テタニー・痙攣・QT 延長",
    },
    # --- 血糖・代謝 ---
    "GLU": {
        "name": "血糖",
        "name_en": "Glucose",
        "unit": "mg/dL",
        "crit_low": 50,
        "warn_low": 70,
        "warn_high": 109,
        "crit_high": 400,
        "ref_range": "70–109 mg/dL (空腹時)",
        "high_msg": "血糖高値: 糖尿病・ストレス性高血糖",
        "low_msg": "低血糖: ブドウ糖補充を考慮",
        "crit_high_msg": "危機的高血糖 (>400): DKA・HHS を除外。緊急対応が必要",
        "crit_low_msg": "危機的低血糖 (<50): 意識障害リスク。即時ブドウ糖投与",
    },
    "HBA1C": {
        "name": "HbA1c",
        "name_en": "Hemoglobin A1c",
        "unit": "%",
        "crit_low": None,
        "warn_low": None,
        "warn_high": 5.6,
        "crit_high": 10.0,
        "ref_range": "<5.6% 正常, 5.7–6.4% 前糖尿病, ≥6.5% 糖尿病",
        "high_msg": "HbA1c 上昇: 糖尿病または前糖尿病状態",
        "low_msg": None,
        "crit_high_msg": "HbA1c 著明高値 (>10%): 血糖コントロール不良。合併症リスクが高い",
        "crit_low_msg": None,
    },
    # --- 肝機能 ---
    "AST": {
        "name": "AST (GOT)",
        "name_en": "Aspartate Aminotransferase",
        "unit": "U/L",
        "crit_low": None,
        "warn_low": None,
        "warn_high": 40,
        "crit_high": 1000,
        "ref_range": "<40 U/L",
        "high_msg": "AST 上昇: 肝細胞障害・心筋障害・横紋筋融解症",
        "low_msg": None,
        "crit_high_msg": "AST 著明上昇: 電撃性肝炎・虚血性肝炎・横紋筋融解症を疑う",
        "crit_low_msg": None,
    },
    "ALT": {
        "name": "ALT (GPT)",
        "name_en": "Alanine Aminotransferase",
        "unit": "U/L",
        "crit_low": None,
        "warn_low": None,
        "warn_high": 40,
        "crit_high": 1000,
        "ref_range": "<40 U/L",
        "high_msg": "ALT 上昇: 肝細胞障害 (肝炎・脂肪肝・薬剤性)",
        "low_msg": None,
        "crit_high_msg": "ALT 著明上昇: 急性肝炎・肝壊死・薬剤性肝障害を精査",
        "crit_low_msg": None,
    },
    "GGT": {
        "name": "γ-GTP",
        "name_en": "Gamma-glutamyl Transferase",
        "unit": "U/L",
        "crit_low": None,
        "warn_low": None,
        "warn_high": 50,
        "crit_high": 500,
        "ref_range": "男性 <50, 女性 <30 U/L",
        "high_msg": "γ-GTP 上昇: 胆道系疾患・アルコール性肝障害",
        "low_msg": None,
        "crit_high_msg": "γ-GTP 著明上昇: 閉塞性黄疸・肝硬変",
        "crit_low_msg": None,
    },
    "TBIL": {
        "name": "総ビリルビン",
        "name_en": "Total Bilirubin",
        "unit": "mg/dL",
        "crit_low": None,
        "warn_low": None,
        "warn_high": 1.2,
        "crit_high": 5.0,
        "ref_range": "<1.2 mg/dL",
        "high_msg": "ビリルビン上昇: 黄疸。肝細胞性・閉塞性・溶血性を鑑別",
        "low_msg": None,
        "crit_high_msg": "ビリルビン著明上昇: 重篤な黄疸。肝不全・胆道完全閉塞を疑う",
        "crit_low_msg": None,
    },
    "ALP": {
        "name": "ALP",
        "name_en": "Alkaline Phosphatase",
        "unit": "U/L",
        "crit_low": None,
        "warn_low": None,
        "warn_high": 120,
        "crit_high": 600,
        "ref_range": "38–120 U/L",
        "high_msg": "ALP 上昇: 胆道系疾患・骨疾患",
        "low_msg": None,
        "crit_high_msg": "ALP 著明上昇: 閉塞性黄疸・骨転移・肝疾患",
        "crit_low_msg": None,
    },
    # --- 膵臓 ---
    "AMY": {
        "name": "アミラーゼ",
        "name_en": "Amylase",
        "unit": "U/L",
        "crit_low": None,
        "warn_low": None,
        "warn_high": 132,
        "crit_high": 500,
        "ref_range": "44–132 U/L",
        "high_msg": "アミラーゼ上昇: 急性膵炎・耳下腺疾患を考慮",
        "low_msg": None,
        "crit_high_msg": "アミラーゼ著明上昇: 重症急性膵炎を疑う。造影 CT 検索を",
        "crit_low_msg": None,
    },
    "LIPASE": {
        "name": "リパーゼ",
        "name_en": "Lipase",
        "unit": "U/L",
        "crit_low": None,
        "warn_low": None,
        "warn_high": 55,
        "crit_high": 200,
        "ref_range": "13–55 U/L",
        "high_msg": "リパーゼ上昇: 急性膵炎の強い指標",
        "low_msg": None,
        "crit_high_msg": "リパーゼ著明上昇: 重症急性膵炎。循環管理・ICU 評価を",
        "crit_low_msg": None,
    },
    # --- 血液ガス ---
    "PH": {
        "name": "動脈血pH",
        "name_en": "Arterial pH",
        "unit": "",
        "crit_low": 7.20,
        "warn_low": 7.35,
        "warn_high": 7.45,
        "crit_high": 7.60,
        "ref_range": "7.35–7.45",
        "high_msg": "アルカローシス: 過換気・代謝性アルカローシス",
        "low_msg": "アシドーシス: 代謝性または呼吸性アシドーシス",
        "crit_high_msg": "重篤なアルカローシス: 不整脈・意識障害リスク",
        "crit_low_msg": "重篤なアシドーシス (pH<7.20): 心停止リスク。緊急補正が必要",
    },
    "LACTATE": {
        "name": "乳酸値",
        "name_en": "Lactate",
        "unit": "mmol/L",
        "crit_low": None,
        "warn_low": None,
        "warn_high": 2.0,
        "crit_high": 4.0,
        "ref_range": "<2.0 mmol/L",
        "high_msg": "乳酸上昇: 組織低酸素・敗血症・ショックを考慮",
        "low_msg": None,
        "crit_high_msg": "乳酸著明上昇 (>4): ショック状態を示唆。積極的輸液・昇圧剤投与・ICU 管理",
        "crit_low_msg": None,
    },
    "PCO2": {
        "name": "PaCO2",
        "name_en": "Partial Pressure CO2",
        "unit": "mmHg",
        "crit_low": 20,
        "warn_low": 35,
        "warn_high": 45,
        "crit_high": 70,
        "ref_range": "35–45 mmHg",
        "high_msg": "高炭酸ガス血症: 換気不全・COPD 増悪",
        "low_msg": "低炭酸ガス血症: 過換気・代謝性アシドーシスの代償",
        "crit_high_msg": "重篤な高 CO2: 呼吸性アシドーシス・CO2 ナルコーシス。緊急気道管理",
        "crit_low_msg": "重篤な低 CO2: 重症過換気・脳血流低下リスク",
    },
    "PO2": {
        "name": "PaO2",
        "name_en": "Partial Pressure O2",
        "unit": "mmHg",
        "crit_low": 55,
        "warn_low": 80,
        "warn_high": None,
        "crit_high": None,
        "ref_range": "80–100 mmHg",
        "high_msg": None,
        "low_msg": "低酸素血症: 酸素療法を考慮",
        "crit_high_msg": None,
        "crit_low_msg": "重篤な低酸素血症 (PaO2<55): 緊急酸素療法・人工呼吸を検討",
    },
    # --- 甲状腺 ---
    "TSH": {
        "name": "TSH",
        "name_en": "Thyroid Stimulating Hormone",
        "unit": "μIU/mL",
        "crit_low": 0.01,
        "warn_low": 0.4,
        "warn_high": 4.0,
        "crit_high": 10.0,
        "ref_range": "0.4–4.0 μIU/mL",
        "high_msg": "TSH 上昇: 甲状腺機能低下症を疑う",
        "low_msg": "TSH 低下: 甲状腺機能亢進症・バセドウ病を疑う",
        "crit_high_msg": "TSH 著明上昇: 重症甲状腺機能低下。粘液水腫性昏睡を除外",
        "crit_low_msg": "TSH 危機的低値: 甲状腺クリーゼを除外",
    },
    "FT4": {
        "name": "FT4 (遊離T4)",
        "name_en": "Free Thyroxine",
        "unit": "ng/dL",
        "crit_low": 0.5,
        "warn_low": 0.8,
        "warn_high": 1.8,
        "crit_high": 3.0,
        "ref_range": "0.8–1.8 ng/dL",
        "high_msg": "FT4 上昇: 甲状腺機能亢進症",
        "low_msg": "FT4 低下: 甲状腺機能低下症",
        "crit_high_msg": "FT4 著明上昇: 甲状腺クリーゼを疑う",
        "crit_low_msg": "FT4 著明低下: 粘液水腫性昏睡リスク",
    },
}

# ===========================================================================
# エイリアス (入力文字列 → 正規キー)
# ===========================================================================

_ALIASES: dict[str, str] = {
    # WBC
    "WBC": "WBC", "白血球": "WBC", "白血球数": "WBC",
    # RBC
    "RBC": "RBC", "赤血球": "RBC",
    # HGB
    "HGB": "HGB", "HB": "HGB", "HGB": "HGB", "ヘモグロビン": "HGB", "Hgb": "HGB",
    # HCT
    "HCT": "HCT", "Ht": "HCT", "ヘマトクリット": "HCT",
    # PLT
    "PLT": "PLT", "血小板": "PLT", "Plt": "PLT",
    # CRP
    "CRP": "CRP", "C反応性蛋白": "CRP",
    # PCT
    "PCT": "PCT", "プロカルシトニン": "PCT", "Procalcitonin": "PCT",
    # Troponin
    "TNI": "TNI", "TnI": "TNI", "troponin I": "TNI", "Troponin": "TNI",
    "TNT": "TNT", "TnT": "TNT", "troponin T": "TNT",
    "HSCTNT": "HSCTNT", "hs-TnT": "HSCTNT", "hsTnT": "HSCTNT",
    # BNP
    "BNP": "BNP",
    "NTPROBNP": "NTPROBNP", "NT-proBNP": "NTPROBNP", "NTproBNP": "NTPROBNP",
    # D-dimer
    "DDIMER": "DDIMER", "D-dimer": "DDIMER", "DDimer": "DDIMER",
    "Dダイマー": "DDIMER", "Dダイマー": "DDIMER",
    # INR
    "INR": "INR", "PT-INR": "INR", "PTINR": "INR",
    # Fibrinogen
    "FIBRINOGEN": "FIBRINOGEN", "Fibrinogen": "FIBRINOGEN", "フィブリノゲン": "FIBRINOGEN",
    # Creatinine
    "CR": "CR", "Cr": "CR", "CREA": "CR", "Creatinine": "CR", "クレアチニン": "CR",
    "SCr": "CR",
    # BUN
    "BUN": "BUN", "尿素窒素": "BUN", "UN": "BUN",
    # Electrolytes
    "NA": "NA", "Na": "NA", "ナトリウム": "NA",
    "K": "K", "カリウム": "K",
    "CL": "CL", "Cl": "CL", "クロール": "CL",
    "CA": "CA", "Ca": "CA", "カルシウム": "CA",
    # Glucose
    "GLU": "GLU", "Glu": "GLU", "BS": "GLU", "血糖": "GLU", "Glucose": "GLU",
    "FBS": "GLU", "空腹時血糖": "GLU",
    # HbA1c
    "HBA1C": "HBA1C", "HbA1c": "HBA1C", "A1C": "HBA1C",
    # Liver
    "AST": "AST", "GOT": "AST",
    "ALT": "ALT", "GPT": "ALT",
    "GGT": "GGT", "γGTP": "GGT", "γ-GTP": "GGT", "GGTP": "GGT",
    "TBIL": "TBIL", "T-Bil": "TBIL", "TBil": "TBIL", "総ビリルビン": "TBIL",
    "ALP": "ALP",
    # Pancreas
    "AMY": "AMY", "Amy": "AMY", "Amylase": "AMY", "アミラーゼ": "AMY",
    "LIPASE": "LIPASE", "Lipase": "LIPASE", "リパーゼ": "LIPASE",
    # Blood gas
    "PH": "PH", "pH": "PH",
    "LACTATE": "LACTATE", "Lac": "LACTATE", "Lactate": "LACTATE", "乳酸": "LACTATE",
    "PCO2": "PCO2", "PaCO2": "PCO2",
    "PO2": "PO2", "PaO2": "PO2",
    # Thyroid
    "TSH": "TSH",
    "FT4": "FT4",
}


def _normalize_key(raw: str) -> str | None:
    """入力キーを正規化して _REF のキーに変換する。"""
    upper = raw.strip().upper().replace(" ", "").replace("-", "").replace("_", "")
    # エイリアスを大文字で検索
    for alias, canonical in _ALIASES.items():
        if alias.upper().replace(" ", "").replace("-", "").replace("_", "") == upper:
            return canonical
    return None


# ===========================================================================
# 文字列パーサー
# ===========================================================================

# "BNP 450" / "D-dimer 2.5" / "WBC 14000" / "AST 1200" などにマッチ
# 項目名: 英字・日本語・ハイフン・γ等の特殊文字を含むが、末尾は数字で終わらない
_RE_LAB = re.compile(
    r"""([A-Za-zα-ωΑ-Ωぁ-ん゠-ヿぁ-ん぀-ゟ一-鿿\-]+
         (?:\s*[A-Za-zα-ωΑ-Ω\-]+)*)        # 項目名 (英字/日本語/記号)
        \s*[:：=＝]?\s*                      # 区切り (任意)
        (\d+(?:\.\d+)?)                      # 数値
        \s*(?:[a-zA-Z%μmgdLUIUmol/]*)?      # 単位 (任意、無視)
    """,
    re.VERBOSE,
)


def parse_lab_string(text: str) -> dict[str, float]:
    """検査値テキストを {項目名: 値} の辞書に変換する。"""
    result: dict[str, float] = {}
    for m in _RE_LAB.finditer(text):
        raw_key = m.group(1).strip()
        val = float(m.group(2))
        canonical = _normalize_key(raw_key)
        if canonical:
            result[canonical] = val
    return result


# ===========================================================================
# フラグ評価
# ===========================================================================

def _evaluate_lab(key: str, value: float) -> LabFlag | None:
    ref = _REF.get(key)
    if ref is None:
        return None

    crit_low = ref.get("crit_low")
    warn_low = ref.get("warn_low")
    warn_high = ref.get("warn_high")
    crit_high = ref.get("crit_high")

    if crit_low is not None and value < crit_low:
        status = "critical_low"
        msg = ref.get("crit_low_msg") or ref.get("low_msg") or f"{ref['name']} 危機的低値"
    elif crit_high is not None and value > crit_high:
        status = "critical_high"
        msg = ref.get("crit_high_msg") or ref.get("high_msg") or f"{ref['name']} 危機的高値"
    elif warn_low is not None and value < warn_low:
        status = "low"
        msg = ref.get("low_msg") or f"{ref['name']} 低値"
    elif warn_high is not None and value > warn_high:
        status = "high"
        msg = ref.get("high_msg") or f"{ref['name']} 高値"
    else:
        return None   # 正常 → None (フラグなし)

    return LabFlag(
        name=ref["name"],
        value=value,
        status=status,
        unit=ref["unit"],
        message=f"{ref['name']} {value}{ref['unit']} — {msg}",
        ref_range=ref.get("ref_range", ""),
    )


# ===========================================================================
# メインインターフェース
# ===========================================================================

def interpret_labs(data: str | dict[str, float]) -> LabResult:
    """検査値を解釈してフラグと要約を返す。

    Parameters
    ----------
    data : str | dict
        テキスト形式 ("WBC 14000, CRP 8.5") または辞書形式 {"WBC": 14000}

    Returns
    -------
    LabResult
        flags: 異常フラグのリスト
        summary: 総合サマリー文字列
        parsed: パース・正規化できた項目の辞書
    """
    if isinstance(data, str):
        parsed_raw = parse_lab_string(data)
    else:
        # 辞書キーを正規化
        parsed_raw = {}
        for k, v in data.items():
            canonical = _normalize_key(k)
            if canonical:
                parsed_raw[canonical] = float(v)
            else:
                # 正規化できなくてもそのままキーを保存
                parsed_raw[k.upper()] = float(v)

    flags: list[LabFlag] = []
    for key, value in parsed_raw.items():
        flag = _evaluate_lab(key, value)
        if flag is not None:
            flags.append(flag)

    # 重症度順ソート
    severity_order = {"critical_high": 0, "critical_low": 0, "high": 1, "low": 1}
    flags.sort(key=lambda f: severity_order.get(f.status, 2))

    # サマリー生成
    critical_flags = [f for f in flags if f.status.startswith("critical")]
    warning_flags = [f for f in flags if not f.status.startswith("critical")]

    if critical_flags:
        crit_names = "、".join(f.name for f in critical_flags)
        summary = f"【緊急】危機的異常値: {crit_names}。即時対応が必要です。"
    elif warning_flags:
        warn_names = "、".join(f.name for f in warning_flags)
        summary = f"【要注意】異常値あり: {warn_names}。精査・フォローアップを推奨します。"
    else:
        summary = "検査値に明らかな異常は認めません。"

    return LabResult(flags=flags, summary=summary, parsed=parsed_raw)


# ===========================================================================
# デモ
# ===========================================================================

if __name__ == "__main__":
    samples = [
        "WBC 14000, CRP 8.5, TnI 0.8, BNP 450, D-dimer 2.5, Cr 2.1",
        "Na 122, K 6.8, pH 7.18, Lactate 5.2, PLT 18, Fibrinogen 90",
        "AST 1200, ALT 890, T-Bil 6.5, INR 2.8",
        {"WBC": 5200, "CRP": 0.2, "HbA1c": 7.3, "BUN": 15, "Cr": 0.9},
    ]

    for sample in samples:
        print("=" * 60)
        if isinstance(sample, str):
            print(f"入力: {sample}")
        else:
            print(f"入力 (dict): {sample}")
        result = interpret_labs(sample)
        print(f"サマリー: {result.summary}")
        if result.flags:
            print("異常フラグ:")
            for flag in result.flags:
                status_label = {
                    "critical_high": "CRITICAL↑",
                    "critical_low": "CRITICAL↓",
                    "high": "HIGH↑",
                    "low": "LOW↓",
                }.get(flag.status, flag.status)
                print(f"  [{status_label}] {flag.message}")
                print(f"           参考範囲: {flag.ref_range}")
        print()
