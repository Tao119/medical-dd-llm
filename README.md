# Medical DD-LLM — 鑑別診断構造化言語モデル

医療文献を知識ベースにした RAG + LLM による**構造化鑑別診断生成システム**。クリニカル推論エンジン、リスクスコアリング、臨床意思決定ツール群を統合する。

## 出力形式

```json
{
  "primary":      {"disease": "急性心筋梗塞", "probability": 0.72, "basis": "胸痛+ST変化", "source_refs": ["Braunwald 2023 p.412"]},
  "differentials": [
    {"disease": "大動脈解離",  "probability": 0.15, "distinguishing_features": "血圧左右差"},
    {"disease": "肺塞栓症",    "probability": 0.08, "distinguishing_features": "片側浮腫"}
  ],
  "red_flags":   ["BP 90/60 ショック", "SpO2 94%"],
  "next_steps":  ["12誘導心電図", "TnI採血", "循環器コール"],
  "urgency":     "immediate"
}
```

## ディレクトリ構成

```
medical-dd-llm/
├── config.py                       # モデル・プロンプト設定
├── train.py                        # QLoRA ファインチューニング
├── infer.py                        # 推論 (demo / interactive)
│
├── model/
│   ├── dd_engine.py                # 診断エンジン (メインロジック)
│   ├── dd_generator.py             # DDGenerator クラス
│   ├── dd_rules_extended.py        # 30+ 疾患グループのルールベース
│   └── dd_template.py              # プロンプトテンプレート
│
├── clinical/                       # 臨床モジュール群
│   ├── vitals.py                   # バイタルサイン解析
│   ├── risk_scores.py              # CURB-65, qSOFA, HEART score, SOFA
│   ├── lab_interpreter.py          # 検査値異常判定
│   ├── icd10.py                    # ICD-10 コード検索・提案
│   ├── drug_interactions.py        # 薬物相互作用チェック
│   ├── drug_dosing.py              # 薬剤投与量計算
│   ├── pediatric.py                # 小児特化 (体重・年齢換算)
│   ├── triage.py                   # Manchester Triage System
│   ├── treatment_protocols.py      # 疾患別治療プロトコル
│   ├── nlp_processor.py            # 臨床テキスト解析 (NLP)
│   └── clinical_guidelines.py      # 診療ガイドライン参照
│
├── viz/                            # 可視化・意思決定ツール
│   ├── decision_tree.py            # ASCII + Mermaid 臨床決定木
│   └── symptom_checker.py          # インタラクティブ症状チェッカー
│
├── rag/
│   └── indexer.py                  # 医療文献 → Faiss インデックス
│
├── api/
│   └── main.py                     # FastAPI サーバー (15+ エンドポイント)
│
├── eval/
│   ├── evaluator.py                # 鑑別診断評価指標
│   ├── benchmark.py                # ベンチマーク実行
│   └── benchmark_report.txt        # ベンチマーク結果
│
└── scripts/
    ├── prepare_training_data.py    # 訓練データ生成
    ├── build_full_training_data.py # 全量データ構築
    └── download_training_data.py   # データダウンロード
```

## 疾患グループ (30+)

| カテゴリ | 主な疾患 |
|---------|---------|
| 心疾患 | STEMI, NSTEMI, 心房細動, 心不全, 大動脈解離 |
| 呼吸器 | 肺炎, COPD増悪, 気胸, 肺塞栓症, 喘息 |
| 神経 | 脳梗塞, 脳出血, SAH, 髄膜炎, てんかん |
| 消化器 | 急性腹症, 胆嚢炎, 虫垂炎, 消化管出血 |
| 感染症 | 敗血症, 尿路感染, 蜂窩織炎, COVID-19 |
| 代謝・内分泌 | DKA, HHS, 甲状腺クリーゼ, 副腎不全 |
| 外傷 | 頭部外傷, 骨折, 熱傷 |

## 臨床モジュール

### リスクスコアリング

```python
from clinical.risk_scores import calc_curb65, calc_qsofa, calc_heart_score

# CURB-65 (肺炎重症度)
score, severity = calc_curb65(
    confusion=True, urea=8.5, rr=26, sbp=90, age=72
)

# qSOFA (敗血症スクリーニング)
result = calc_qsofa(rr=24, mental_status="alert", sbp=95)

# HEART score (胸痛リスク層別化)
heart = calc_heart_score(history=2, ecg=1, age=1, risk=2, troponin=2)
```

### バイタルサイン解析

```python
from clinical.vitals import parse_vitals, assess_vitals

vitals = parse_vitals("BP 90/60, HR 110, SpO2 94%, RR 24, T 38.9")
assessment = assess_vitals(vitals)
# → {"flags": ["低血圧", "頻脈", "低酸素"], "urgency": "immediate"}
```

### 検査値解析

```python
from clinical.lab_interpreter import interpret_labs

flags = interpret_labs({
    "WBC": 18500,
    "CRP": 15.2,
    "TnI": 2.1,
    "D-dimer": 3.8,
    "Cr": 2.3,
})
# → [{"item": "TnI", "flag": "HIGH", "concern": "心筋障害"}, ...]
```

### 薬物相互作用

```python
from clinical.drug_interactions import check_interactions

result = check_interactions(["ワルファリン", "アスピリン", "イブプロフェン"])
# → 出血リスクの相互作用を検出
```

### Manchester Triage

```python
from clinical.triage import triage_patient

result = triage_patient(
    chief_complaint="胸痛", vitals="BP 80/50, HR 125, SpO2 90%"
)
# → {"category": 1, "color": "赤", "wait": "即時", "rationale": "..."}
```

### 小児モジュール

```python
from clinical.pediatric import calc_pediatric_dose, assess_pediatric_vitals

dose = calc_pediatric_dose(drug="アモキシシリン", weight_kg=15)
vitals_ok = assess_pediatric_vitals(age_months=24, hr=140, rr=32, sbp=85)
```

## 臨床決定木 (viz/)

```python
from viz.decision_tree import get_decision_tree, export_mermaid

# ASCII 決定木
print(get_decision_tree("chest_pain"))   # 胸痛トリアージ
print(get_decision_tree("sepsis"))       # 敗血症スクリーニング
print(get_decision_tree("dyspnea"))      # 呼吸困難ワークアップ

# Mermaid 形式 (Web レンダリング用)
mermaid_code = export_mermaid("chest_pain")
```

決定木の例 (胸痛トリアージ):
```
【胸痛トリアージ】
├─ ST上昇あり？
│  ├─ Yes → STEMI → 即時PCI (door-to-balloon <90min)
│  └─ No  ↓
├─ TnI上昇あり？
│  ├─ Yes → NSTEMI → リスク層別化
│  └─ No  ↓
└─ HEART score
   ├─ ≥7 → High risk → 24h以内PCI
   ├─ 4-6 → Medium → 入院観察
   └─ ≤3 → Low → 外来フォロー
```

## 症状チェッカー (viz/)

```python
from viz.symptom_checker import SymptomChecker

checker = SymptomChecker()
print(checker.start())           # 最初の質問
result = checker.answer("胸痛")  # 症状選択
result = checker.answer("圧迫感・放散痛")  # 分岐
# ... 4-6 質問後に DiagnosisResult が返る
print(checker.get_path())        # 診断経路
```

対応症状ツリー: 胸痛 / 呼吸困難 / 発熱+頭痛

## API (15+ エンドポイント)

```bash
uvicorn api.main:app --reload
```

| エンドポイント | メソッド | 概要 |
|--------------|--------|------|
| `/` | GET | ヘルスチェック + バージョン |
| `/health` | GET | サービス状態 |
| `/diagnose` | POST | 鑑別診断生成 (メイン) |
| `/vitals` | POST | バイタルサイン解析 |
| `/labs` | POST | 検査値解析 |
| `/icd10/search` | GET | ICD-10 コード検索 |
| `/risk/curb65` | POST | CURB-65 スコア |
| `/risk/qsofa` | POST | qSOFA スコア |
| `/drugs/check` | POST | 薬物相互作用チェック |
| `/pediatric/vitals` | POST | 小児バイタル評価 |
| `/pediatric/dose` | POST | 小児薬剤投与量 |
| `/pediatric/fluid` | POST | 小児輸液量計算 |
| `/protocol/{diagnosis}` | GET | 治療プロトコル |
| `/triage` | POST | Manchester Triage |
| `/dose` | POST | 薬剤投与量計算 |

### 診断 API の使用例

```bash
curl -X POST http://localhost:8000/diagnose \
  -H "Content-Type: application/json" \
  -d '{
    "chief_complaint": "胸痛・冷汗",
    "symptoms": ["前胸部圧迫感", "左肩放散痛", "冷汗"],
    "vitals": "BP 90/60, HR 110, SpO2 94%, RR 24",
    "history": "高血圧・糖尿病・喫煙歴15年",
    "labs": {"TnI": 2.1, "BNP": 850}
  }'
```

## NLP モジュール

```python
from clinical.nlp_processor import extract_symptoms, extract_vitals_from_text
from clinical.clinical_guidelines import get_guideline

# 臨床テキストから症状抽出
symptoms = extract_symptoms("患者は胸痛と息切れを訴え、冷汗を伴っている")

# ガイドライン参照
guideline = get_guideline("STEMI")
```

## ベンチマーク結果

| 指標 | 説明 | 重み | スコア |
|------|------|------|-------|
| primary_match | 第一診断一致率 | 35% | 実行時評価 |
| primary_prob_error | 確率誤差 | 15% | 実行時評価 |
| differential_recall | 鑑別診断再現率 | 25% | 実行時評価 |
| red_flag_recall | Red Flag 再現率 | 15% | 実行時評価 |
| urgency_match | 緊急度一致 | 10% | 実行時評価 |

```bash
python eval/benchmark.py   # 詳細結果は eval/benchmark_report.txt
```

## クイックスタート

```bash
# 1. 依存関係インストール
pip install fastapi uvicorn pydantic transformers peft datasets torch faiss-cpu

# 2. RAG インデックス構築 (医療文献がある場合)
python rag/indexer.py data/raw data/index

# 3. 訓練データ生成
python scripts/prepare_training_data.py

# 4. 推論デモ
python infer.py

# 5. API サーバー起動
uvicorn api.main:app --reload

# 6. 臨床決定木デモ
python viz/decision_tree.py

# 7. 症状チェッカーデモ
python viz/symptom_checker.py
```

## 環境要件

```
Python 3.9+
transformers >= 4.36
peft >= 0.6
torch >= 2.0
fastapi >= 0.100
faiss-cpu >= 1.7
pydantic >= 2.0
```
