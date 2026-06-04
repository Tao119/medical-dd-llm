"""
decision_tree.py — Clinical Decision Trees (ASCII + Mermaid)

Implements ASCII decision trees and Mermaid diagram export for:
  1. Chest pain triage (6-level STEMI/NSTEMI/HEART score)
  2. Sepsis screening (qSOFA/SOFA/vasopressors)
  3. Dyspnea workup (SpO2/PE/pneumonia/CHF/COPD branches)

Usage:
  from viz.decision_tree import get_decision_tree, export_mermaid

  print(get_decision_tree("chest_pain"))
  print(export_mermaid("sepsis"))
"""

from __future__ import annotations


# ─────────────────────────────────────────────────────────────
# ASCII Decision Trees
# ─────────────────────────────────────────────────────────────

_CHEST_PAIN_TREE = """
【胸痛トリアージ】
├─ ST上昇あり？
│  ├─ Yes → STEMI → 即時PCI (door-to-balloon <90min)
│  │         ├─ 広範前壁: LAD責任病変
│  │         └─ 下壁: RCA責任病変 → 右室梗塞除外
│  └─ No  ↓
├─ TnI/TnT上昇あり？
│  ├─ Yes → NSTEMI → リスク層別化
│  │         ├─ 高リスク: 24h以内PCI
│  │         └─ 中リスク: 入院・連続TnI測定
│  └─ No  ↓
├─ HEART score評価
│  ├─ ≥7 → High risk → 入院・24h以内PCI
│  ├─ 4–6 → Medium risk → 入院観察・6h後TnI再測定
│  └─ ≤3 → Low risk → 外来フォロー可能
│
├─ 除外すべき重大疾患
│  ├─ 大動脈解離: 血圧左右差 >20mmHg / 胸部X線縦隔拡大
│  │   └─ Yes → 造影CT緊急施行・心臓血管外科コール
│  ├─ 肺塞栓症: Wells score + D-dimer / CTPA
│  │   └─ Yes → 抗凝固療法開始 (UFH or NOAC)
│  └─ 緊張性気胸: 呼吸音消失 + 頸静脈怒張
│      └─ Yes → 緊急脱気 (18G針/第2肋間鎖骨中線)
│
└─ モニタリング
   ├─ 12誘導心電図 (初診時 + 6h後)
   ├─ TnI/TnT (0h, 3h, 6h)
   └─ 心エコー (壁運動異常確認)
"""

_SEPSIS_TREE = """
【敗血症スクリーニング】
├─ 感染症が疑われる？
│  └─ No → 敗血症の可能性低い → 他疾患検索
├─ qSOFA スコア評価
│  ├─ 呼吸数 ≥22回/min    (+1)
│  ├─ GCS <15             (+1)
│  └─ 収縮期BP ≤100mmHg  (+1)
│
├─ qSOFA ≥2？
│  ├─ Yes → 敗血症ワークアップ開始
│  │         ├─ 血液培養 (2セット) → 採取後すぐに抗菌薬投与
│  │         ├─ 乳酸値測定
│  │         └─ ICU連絡
│  └─ No  → 定期的再評価 (1–2h毎)
│
├─ SOFA score ≥2の臓器障害？
│  ├─ 呼吸: PaO2/FiO2 <300
│  ├─ 肝臓: ビリルビン >2mg/dL
│  ├─ 凝固: 血小板 <150,000
│  ├─ 腎臓: クレアチニン >1.2mg/dL
│  ├─ 神経: GCS <15
│  └─ 循環: 平均動脈圧 <70mmHg
│
├─ 昇圧薬が必要？ (MAP <65mmHg after fluid)
│  ├─ Yes → 敗血症性ショック
│  │         ├─ Norepinephrine 第一選択
│  │         ├─ 乳酸 ≥2mmol/L: 輸液蘇生 + 再評価
│  │         └─ 30mL/kg 晶質液投与 (1h以内)
│  └─ No  → 敗血症 (ショックなし)
│
└─ Hour-1 Bundle (生存のための1時間バンドル)
   ├─ 乳酸値測定
   ├─ 血液培養採取 (抗菌薬前)
   ├─ 広域抗菌薬投与
   ├─ 30mL/kg 晶質液投与
   └─ 昇圧薬 (MAP <65mmHg持続時)
"""

_DYSPNEA_TREE = """
【呼吸困難ワークアップ】
├─ SpO2 <90% (室内気)?
│  ├─ Yes → 即時介入
│  │         ├─ 酸素投与 (目標SpO2 ≥94%)
│  │         ├─ 呼吸補助 (HFNC / NIV / 挿管)
│  │         └─ 緊急原因検索
│  └─ No  → 安定評価へ
│
├─ 発症は突然 vs 緩徐？
│  ├─ 突然発症
│  │   ├─ 胸痛あり? → 肺塞栓症 / 気胸 / 急性冠症候群
│  │   └─ 胸痛なし? → 気胸 / 不整脈 / 過換気
│  └─ 緩徐発症 → 心不全 / COPD増悪 / 肺炎
│
├─ 身体所見
│  ├─ 片側呼吸音低下
│  │   ├─ 胸部X線: 虚脱 → 気胸 → 胸腔穿刺/ドレーン
│  │   └─ 胸部X線: 陰影 → 胸水 → 穿刺・原因検索
│  ├─ 両側ラ音
│  │   ├─ 湿性ラ音 (肺底部) → うっ血性心不全
│  │   │   ├─ BNP/NT-proBNP測定
│  │   │   ├─ 心エコー (EF評価)
│  │   │   └─ 利尿薬 + 後負荷軽減
│  │   └─ 乾性ラ音 (びまん性) → 肺炎 / 間質性肺疾患
│  ├─ 喘鳴
│  │   ├─ 既往に喘息/COPD → 増悪 → 気管支拡張薬
│  │   └─ 新規発症 → アレルギー / 心臓喘息除外
│  └─ 所見なし → 肺塞栓症 / 貧血 / 不安
│
├─ 主な鑑別診断
│  ├─ 肺塞栓症 (PE)
│  │   ├─ Wells score ≥5 or D-dimer陽性
│  │   ├─ CTPA (診断的検査)
│  │   └─ UFH開始 (疑いが高ければ検査前から)
│  ├─ 肺炎
│  │   ├─ 発熱 + 湿性咳 + CRP/PCT上昇
│  │   ├─ 胸部X線/CT: 浸潤影
│  │   └─ 原因微生物同定 → 抗菌薬
│  ├─ うっ血性心不全 (CHF)
│  │   ├─ 起座呼吸 + 両下腿浮腫
│  │   ├─ BNP >100 pg/mL
│  │   └─ ループ利尿薬 (フロセミド) + 酸素
│  └─ COPD増悪
│       ├─ 喫煙歴 + 呼気延長 + 樽状胸
│       ├─ PaCO2上昇 → CO2ナルコーシスに注意
│       └─ 気管支拡張薬 + 全身ステロイド + 必要に応じNIV
│
└─ 緊急度分類
   ├─ 即時対応: SpO2<90% / 呼吸数>30 / 意識障害
   ├─ 緊急: SpO2 90–94% / 増悪傾向
   └─ 準緊急: 安定だが原因未確定
"""

_TREES: dict[str, str] = {
    "chest_pain": _CHEST_PAIN_TREE,
    "sepsis": _SEPSIS_TREE,
    "dyspnea": _DYSPNEA_TREE,
}

SUPPORTED_CONDITIONS = list(_TREES.keys())


def get_decision_tree(condition: str) -> str:
    """
    Returns ASCII decision tree for the given condition.

    Parameters
    ----------
    condition : str
        One of 'chest_pain', 'sepsis', 'dyspnea'

    Returns
    -------
    str
        Multi-line ASCII decision tree text.

    Raises
    ------
    ValueError
        If condition is not supported.
    """
    key = condition.lower().replace(" ", "_").replace("-", "_")
    if key not in _TREES:
        raise ValueError(
            f"Unknown condition: '{condition}'. "
            f"Supported: {SUPPORTED_CONDITIONS}"
        )
    return _TREES[key]


# ─────────────────────────────────────────────────────────────
# Mermaid Export
# ─────────────────────────────────────────────────────────────

_CHEST_PAIN_MERMAID = """flowchart TD
    A[胸痛患者] --> B{{ST上昇あり?}}
    B -->|Yes| C[STEMI]
    C --> C1[即時PCI\\ndoor-to-balloon &lt;90min]
    C1 --> C2[前壁: LAD]
    C1 --> C3[下壁: RCA\\n右室梗塞除外]
    B -->|No| D{{TnI/TnT上昇?}}
    D -->|Yes| E[NSTEMI]
    E --> E1[高リスク: 24h以内PCI]
    E --> E2[中リスク: 入院・連続TnI]
    D -->|No| F{{HEART score}}
    F -->|≥7| G[High risk\\n入院・24h以内PCI]
    F -->|4-6| H[Medium risk\\n入院観察]
    F -->|≤3| I[Low risk\\n外来フォロー]
    A --> J{{大動脈解離除外}}
    J -->|血圧左右差>20 or 縦隔拡大| K[造影CT緊急\\n心臓血管外科コール]
    A --> L{{肺塞栓症除外}}
    L -->|Wells高スコア/D-dimer陽性| M[CTPA\\n抗凝固療法]
    A --> N{{緊張性気胸除外}}
    N -->|呼吸音消失+頸静脈怒張| O[緊急脱気\\n第2肋間鎖骨中線]
"""

_SEPSIS_MERMAID = """flowchart TD
    A[感染症疑い] --> B{{qSOFA評価}}
    B --> B1[呼吸数≥22: +1]
    B --> B2[GCS<15: +1]
    B --> B3[収縮期BP≤100: +1]
    B1 & B2 & B3 --> C{{qSOFA ≥2?}}
    C -->|Yes| D[敗血症ワークアップ]
    D --> D1[血液培養×2セット]
    D --> D2[乳酸値測定]
    D --> D3[広域抗菌薬投与]
    C -->|No| E[1-2h毎に再評価]
    D --> F{{SOFA ≥2?}}
    F -->|Yes| G[臓器障害あり: 敗血症]
    G --> H{{昇圧薬必要?\\nMAP<65mmHg}}
    H -->|Yes| I[敗血症性ショック\\nNorepinephrine]
    H -->|No| J[敗血症\\nショックなし]
    D --> K[Hour-1 Bundle]
    K --> K1[輸液 30mL/kg]
    K --> K2[培養→抗菌薬]
    K --> K3[昇圧薬準備]
"""

_DYSPNEA_MERMAID = """flowchart TD
    A[呼吸困難] --> B{{SpO2 <90%?}}
    B -->|Yes| C[即時介入\\n酸素/HFNC/NIV]
    B -->|No| D{{発症様式}}
    D -->|突然| E{{胸痛あり?}}
    E -->|Yes| F[PE / 気胸 / ACS]
    E -->|No| G[気胸 / 不整脈]
    D -->|緩徐| H[心不全 / COPD / 肺炎]
    A --> I{{身体所見}}
    I -->|片側呼吸音低下| J[胸部X線]
    J -->|虚脱| K[気胸→脱気]
    J -->|陰影| L[胸水→穿刺]
    I -->|両側湿性ラ音| M[CHF\\nBNP/心エコー\\n利尿薬]
    I -->|喘鳴| N{{既往?}}
    N -->|喘息/COPD| O[増悪→気管支拡張薬]
    N -->|新規| P[アレルギー/心臓喘息除外]
    A --> Q[主な鑑別]
    Q --> Q1[PE: Wells→CTPA→UFH]
    Q --> Q2[肺炎: CRP/PCT→抗菌薬]
    Q --> Q3[CHF: BNP→利尿薬]
    Q --> Q4[COPD: CO2注意→NIV]
"""

_MERMAID: dict[str, str] = {
    "chest_pain": _CHEST_PAIN_MERMAID,
    "sepsis": _SEPSIS_MERMAID,
    "dyspnea": _DYSPNEA_MERMAID,
}


def export_mermaid(condition: str) -> str:
    """
    Returns Mermaid diagram syntax for the given condition.

    Parameters
    ----------
    condition : str
        One of 'chest_pain', 'sepsis', 'dyspnea'

    Returns
    -------
    str
        Mermaid flowchart diagram string.
    """
    key = condition.lower().replace(" ", "_").replace("-", "_")
    if key not in _MERMAID:
        raise ValueError(
            f"Unknown condition: '{condition}'. "
            f"Supported: {SUPPORTED_CONDITIONS}"
        )
    return _MERMAID[key]


# ─────────────────────────────────────────────────────────────
# Demo
# ─────────────────────────────────────────────────────────────

if __name__ == '__main__':
    separator = "\n" + "=" * 60 + "\n"

    print(separator)
    print("DEMO: Clinical Decision Trees")
    print(separator)

    for condition in SUPPORTED_CONDITIONS:
        print(f"\n{'─'*60}")
        print(f"  Condition: {condition}")
        print(f"{'─'*60}")
        print(get_decision_tree(condition))

    print(separator)
    print("DEMO: Mermaid Export (chest_pain)")
    print(separator)
    print(export_mermaid("chest_pain"))

    print(separator)
    print("DEMO: Mermaid Export (sepsis)")
    print(separator)
    print(export_mermaid("sepsis"))
