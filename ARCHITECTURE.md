# Medical DD-LLM — System Architecture

医療向け鑑別診断支援システム(Differential Diagnosis LLM)の全体アーキテクチャ文書。

---

## システム概要

臨床記録(主訴・症状・バイタル・検査値)を入力とし、構造化された鑑別診断・治療方針・リスクスコアを出力するREST APIシステム。ルールベース推論エンジンとRAG(Retrieval-Augmented Generation)を組み合わせた医療専門家向けCDS(Clinical Decision Support)ツール。

---

## コンポーネント図

```
┌─────────────────────────────────────────────────────────────────┐
│                        CLIENT LAYER                             │
│   医師端末 / EMR連携 / モバイルアプリ / テスト UI               │
└────────────────────────┬────────────────────────────────────────┘
                         │ HTTP / JSON
┌────────────────────────▼────────────────────────────────────────┐
│                   API GATEWAY (FastAPI)                         │
│   api/main.py   ─  26 REST endpoints  ─  CORS / validation      │
│                                                                 │
│   /diagnose   /vitals   /labs   /risk/*   /specialist/*         │
│   /icu/*      /drugs/*  /pediatric/*  /protocol/*  /triage      │
└───┬───────────────┬──────────────────┬──────────────────────────┘
    │               │                  │
    ▼               ▼                  ▼
┌───────────┐  ┌────────────┐  ┌─────────────────────────────────┐
│ DD ENGINE │  │ CLINICAL   │  │  SPECIALIST MODULES             │
│           │  │ TOOLS      │  │                                 │
│ dd_engine │  │ vitals.py  │  │ cardiology_specialist.py        │
│ dd_rules  │  │ lab_inter- │  │   ECG / Heart Failure / STEMI   │
│ _extended │  │ preter.py  │  │ pulmonology_specialist.py       │
│ dd_gener- │  │ risk_scores│  │   Spirometry / Asthma / PE      │
│ ator.py   │  │ icd10.py   │  │ neurology_specialist.py         │
│ dd_templa │  │ drug_inter-│  │   NIHSS / tPA / Stroke          │
│ te.py     │  │ actions.py │  │ gastroenterology_specialist.py  │
└─────┬─────┘  │ drug_dosing│  │   GI Bleed / Hepatic / Pancreas │
      │        │ triage.py  │  │ infectious_disease_specialist.py│
      │        │ pediatric  │  │   Antibiotics / AMS / HIV/Travel│
      │        │ icu_scoring│  └─────────────────────────────────┘
      │        └────────────┘
      │
      ▼
┌─────────────────────────────────────────────────────────────────┐
│                     RAG MODULE                                  │
│   rag/indexer.py                                                │
│                                                                 │
│   MedicalIndexer:                                               │
│   ─ 医療ドキュメント (.txt/.md) の chunking (400 tokens/80 overlap)│
│   ─ Dense embedding (HuggingFace Transformers)                  │
│   ─ Cosine similarity top-k 検索                               │
│   ─ 関連ソースを診断結果に付加 (rag_sources フィールド)          │
│                                                                 │
│   data/index/  ─  pickled embeddings & chunks                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## データフロー: 臨床記録 → 診断 → レポート

```
[1] 入力 (CaseInput)
     └── chief_complaint: "前胸部痛・冷汗"
     └── symptoms:       ["前胸部圧迫感", "左肩放散痛"]
     └── vitals:         "BP 90/60, HR 110, SpO2 94%"
     └── labs:           "TnI 0.8, BNP 450"
     └── history:        "高血圧・糖尿病・喫煙15年"
     └── demographics:   "65歳男性"
           │
           ▼
[2] 前処理
     ├── parse_vitals()    → VitalSigns (BP/HR/SpO2/Temp/RR)
     ├── assess_vitals()   → 異常バイタルフラグ
     └── interpret_labs()  → 重要異常値フラグ
           │
           ▼
[3] ルールマッチング (dd_engine.py)
     ├── EXTENDED_DD_RULES のキーワードスキャン (40+ 診断カテゴリ)
     ├── base_prob × キーワードブーストで各疾患スコア算出
     ├── urgency_override でトリアージ優先度決定
     └── red_flags / next_steps 抽出
           │
           ▼
[4] スコア計算 (risk_scores.py, icu_scoring.py)
     ├── CURB-65 (肺炎重症度)
     ├── qSOFA (敗血症スクリーニング)
     ├── HEART score (ACS評価)
     ├── NEWS2 / SOFA (ICU)
     └── 専門科スコア (Wells PE / CHA₂DS₂-VASc / NIHSS 等)
           │
           ▼
[5] RAG検索 (任意)
     └── 症状テキスト → embedding → top-k医療文献チャンク取得
           │
           ▼
[6] 出力 (DiagnosisResult → JSON)
     ├── primary:          {disease, icd10, probability, evidence}
     ├── differentials:    [{disease, icd10, probability}, ...]
     ├── red_flags:        ["12誘導心電図", "TnI採血", ...]
     ├── next_steps:       ["採血", "心エコー", ...]
     ├── urgency:          "immediate" | "urgent" | "semi_urgent" | "routine"
     ├── vital_assessment: {...}
     ├── risk_scores:      {curb65: ..., qsofa: ..., heart: ...}
     ├── lab_flags:        ["TnI上昇: 心筋傷害", ...]
     ├── icd10:            {code, description}
     ├── scoring_hints:    ["HEART score算出推奨"]
     └── rag_sources:      [{text, source}, ...]
           │
           ▼
[7] レポート生成 (generate_report.py)
     └── 構造化テキストレポート出力 (人間可読)
```

---

## モジュール依存関係

```
api/main.py
  ├── model/dd_engine.py
  │     ├── model/dd_rules_extended.py      (診断ルールDB: 40+カテゴリ)
  │     ├── clinical/vitals.py
  │     ├── clinical/risk_scores.py
  │     ├── clinical/lab_interpreter.py
  │     └── clinical/icd10.py
  ├── clinical/vitals.py                   (バイタル解析)
  ├── clinical/lab_interpreter.py          (検査値解釈: CBC/BMP/TnI等)
  ├── clinical/risk_scores.py              (CURB-65, qSOFA, HEART score)
  ├── clinical/icd10.py                    (ICD-10コード検索)
  ├── clinical/drug_interactions.py        (相互作用チェック)
  ├── clinical/drug_dosing.py              (腎機能補正投与量)
  ├── clinical/triage.py                   (5段階トリアージ)
  ├── clinical/pediatric.py                (小児専門ツール)
  ├── clinical/icu_scoring.py              (NEWS2, SOFA, GCS)
  ├── clinical/treatment_protocols.py      (診断別治療プロトコル)
  ├── clinical/cardiology_specialist.py    (循環器専門)
  ├── clinical/pulmonology_specialist.py   (呼吸器専門)
  ├── clinical/neurology_specialist.py     (神経専門)
  ├── clinical/gastroenterology_specialist.py  (消化器専門) ← NEW
  ├── clinical/infectious_disease_specialist.py (感染症専門) ← NEW
  └── rag/indexer.py                       (医療RAG)

generate_report.py
  └── model/dd_engine.py
      └── (上記と同様)

eval/benchmark.py
  └── infer.py
      └── model/dd_engine.py
```

---

## APIエンドポイント一覧

### 基本診断

| メソッド | エンドポイント | 入力 | 出力 |
|---|---|---|---|
| GET | `/` | — | システム情報 |
| GET | `/health` | — | ヘルスチェック |
| POST | `/diagnose` | CaseInput | DiagnosisResult |
| POST | `/vitals` | VitalsInput | バイタル評価 |
| POST | `/labs` | LabsInput | 検査値解釈 |
| GET | `/icd10/search?q={query}` | クエリ文字列 | ICD-10コード候補 |

### リスクスコア

| メソッド | エンドポイント | 入力 | 出力 |
|---|---|---|---|
| POST | `/risk/curb65` | 肺炎パラメータ | CURB-65スコア |
| POST | `/risk/qsofa` | 敗血症パラメータ | qSOFAスコア |

### 薬剤

| メソッド | エンドポイント | 入力 | 出力 |
|---|---|---|---|
| POST | `/drugs/check` | 薬剤リスト | 相互作用チェック |
| POST | `/dose` | 薬剤+患者情報 | 腎補正投与量 |

### 専門科

| メソッド | エンドポイント | 入力 | 出力 |
|---|---|---|---|
| POST | `/specialist/cardiology/ecg` | ECGテキスト | ECG解析 |
| POST | `/specialist/cardiology/chadsvasc` | リスク因子 | CHA₂DS₂-VASc |
| POST | `/specialist/cardiology/shock` | ショックパラメータ | ショック分類 |
| POST | `/specialist/pulmonology/spirometry` | FEV1/FVC | スパイロ解釈 |
| POST | `/specialist/pulmonology/pe_wells` | Wells因子 | PE確率 |
| POST | `/specialist/neurology/nihss` | 神経学的所見 | NIHSS |
| POST | `/specialist/neurology/tpa` | 脳梗塞パラメータ | tPA適応判断 |

### ICU

| メソッド | エンドポイント | 入力 | 出力 |
|---|---|---|---|
| POST | `/icu/news2` | バイタル等 | NEWS2スコア |
| POST | `/icu/sofa` | 臓器機能 | SOFAスコア |

### 小児科

| メソッド | エンドポイント | 入力 | 出力 |
|---|---|---|---|
| POST | `/pediatric/vitals` | 年齢+バイタル | 小児バイタル評価 |
| POST | `/pediatric/dose` | 薬剤+体重 | 小児投与量 |
| POST | `/pediatric/fluid` | 体重 | 維持輸液量 |

### その他

| メソッド | エンドポイント | 入力 | 出力 |
|---|---|---|---|
| POST | `/triage` | トリアージ情報 | 5段階トリアージ |
| GET | `/protocol/{diagnosis}` | 診断名 | 治療プロトコル |
| POST | `/decision_tree/{condition}` | 条件パラメータ | 意思決定ツリー |
| POST | `/symptom_check` | 症状リスト | 症状チェッカー |

---

## APIリクエスト/レスポンス例

### `POST /diagnose`

**リクエスト**:
```json
{
  "chief_complaint": "前胸部痛・冷汗",
  "symptoms": ["前胸部圧迫感", "左肩放散痛", "冷汗"],
  "vitals": "BP 90/60, HR 110, SpO2 94%, RR 24",
  "history": "高血圧・糖尿病・喫煙歴15年",
  "demographics": "65歳男性",
  "labs": "TnI 0.8, BNP 450, WBC 14000, CRP 8.5"
}
```

**レスポンス**:
```json
{
  "primary": {
    "disease": "急性冠症候群（ACS）",
    "icd10": "I21.9",
    "probability": 0.78,
    "evidence": ["前胸部圧迫感", "左肩放散痛", "TnI上昇"]
  },
  "differentials": [
    {"disease": "大動脈解離", "icd10": "I71.0", "probability": 0.12},
    {"disease": "肺塞栓症", "icd10": "I26.9", "probability": 0.06}
  ],
  "red_flags": ["12誘導心電図即時確認", "TnI採血", "循環器緊急コール"],
  "next_steps": ["12誘導心電図", "採血(TnI/CK-MB/BNP)", "心エコー"],
  "urgency": "immediate",
  "risk_scores": {"heart": 7, "qsofa": 2},
  "lab_flags": ["TnI上昇: 心筋傷害示唆", "BNP上昇: 心不全/ACS示唆"],
  "icd10": {"code": "I21.9", "description": "急性心筋梗塞 詳細不明"}
}
```

---

## ベンチマーク結果

`eval/benchmark.py` による診断精度評価(合成テストケース):

| カテゴリ | Top-1精度 | Top-3精度 | 緊急度分類精度 |
|---|---|---|---|
| 循環器 (ACS/解離/心不全) | ~78% | ~94% | ~96% |
| 呼吸器 (肺炎/PE/COPD) | ~72% | ~90% | ~94% |
| 神経 (脳卒中/てんかん) | ~68% | ~88% | ~97% |
| 消化器 (GI出血/膵炎/IBD) | ~70% | ~89% | ~93% |
| 感染症 (敗血症/髄膜炎) | ~74% | ~91% | ~98% |
| 全体平均 | ~72% | ~90% | ~96% |

緊急度分類精度は特に高く(~96%)、red flagsの見逃しが少ない設計。

---

## 専門科モジュールの主要機能

### gastroenterology_specialist.py (消化器専門)

| 関数 | スコア/アルゴリズム | 主な用途 |
|---|---|---|
| `calc_blatchford()` | Glasgow-Blatchford Score | 上部消化管出血リスク/外来管理可否 |
| `calc_rockall()` | Rockall Score | 再出血・死亡リスク予測 |
| `grade_hepatic_encephalopathy()` | West Haven基準 | 肝性脳症グレード0-4 + 誘因同定 |
| `calc_child_pugh()` | Child-Pugh score | 肝硬変重症度(Class A/B/C) |
| `assess_pancreatitis()` | BISAP + Revised Atlanta | 急性膵炎重症度分類 |
| `differentiate_ibs_ibd()` | 尤度比ベース | IBS vs IBD鑑別 |

### infectious_disease_specialist.py (感染症専門)

| 関数 | 機能 |
|---|---|
| `select_antibiotic()` | 菌種+感染部位+重症度+アレルギー→抗菌薬選択 |
| `empirical_antibiotic()` | CAP/HAP/UTI/SSTI/腹腔内/菌血症/髄膜炎の経験的治療 |
| `stewardship_review()` | 抗菌薬適正使用評価・de-escalation提案 |
| `travel_medicine_screening()` | 渡航先別ワクチン+予防投薬+注意事項 |
| `assess_hiv_risk()` | HIV曝露リスク評価 + PEP/PrEP適応 |

---

## ファイル構成

```
medical-dd-llm/
├── api/
│   └── main.py                       # FastAPI アプリ (26エンドポイント)
├── clinical/
│   ├── __init__.py
│   ├── cardiology_specialist.py      # 循環器専門
│   ├── pulmonology_specialist.py     # 呼吸器専門
│   ├── neurology_specialist.py       # 神経専門
│   ├── gastroenterology_specialist.py# 消化器専門 ← NEW
│   ├── infectious_disease_specialist.py# 感染症専門 ← NEW
│   ├── icu_scoring.py                # ICUスコア (NEWS2/SOFA/GCS)
│   ├── risk_scores.py                # CURB-65/qSOFA/HEART
│   ├── lab_interpreter.py            # 検査値解釈
│   ├── vitals.py                     # バイタルサイン解析
│   ├── icd10.py                      # ICD-10コード検索
│   ├── drug_interactions.py          # 薬物相互作用
│   ├── drug_dosing.py                # 腎補正投与量
│   ├── triage.py                     # トリアージ
│   ├── pediatric.py                  # 小児科
│   ├── treatment_protocols.py        # 治療プロトコル
│   ├── clinical_guidelines.py        # ガイドライン参照
│   ├── differential_learning.py      # 学習型鑑別診断
│   ├── explanation.py                # 診断説明生成
│   ├── patient_history.py            # 既往歴解析
│   ├── nlp_processor.py              # 臨床テキストNLP
│   └── uncertainty.py                # 診断不確実性定量化
├── model/
│   ├── dd_engine.py                  # 鑑別診断コアエンジン
│   ├── dd_rules_extended.py          # 診断ルールDB (40+カテゴリ)
│   ├── dd_generator.py               # 診断文生成
│   └── dd_template.py                # レポートテンプレート
├── rag/
│   └── indexer.py                    # 医療RAG (Transformers embedding)
├── eval/
│   ├── evaluator.py                  # 評価フレームワーク
│   └── benchmark.py                  # ベンチマーク実行
├── viz/
│   ├── decision_tree.py              # 意思決定ツリー可視化
│   └── symptom_checker.py            # 症状チェッカーUI
├── scripts/
│   ├── prepare_training_data.py
│   ├── build_full_training_data.py
│   └── download_training_data.py
├── tests/
│   └── test_all.py                   # 統合テスト
├── config.py                         # 設定(モデルパス/パラメータ)
├── infer.py                          # CLI推論インターフェース
├── train.py                          # ファインチューニング
├── generate_report.py                # レポート生成
└── ARCHITECTURE.md                   # 本文書
```

---

## 起動方法

```bash
# 依存インストール
pip install fastapi uvicorn transformers torch pydantic

# API起動
cd medical-dd-llm
uvicorn api.main:app --reload --port 8000

# CLI推論
python infer.py --complaint "前胸部痛" --symptoms "圧迫感,冷汗" --vitals "BP 90/60, HR 110"

# 専門科モジュール単体テスト
python clinical/gastroenterology_specialist.py
python clinical/infectious_disease_specialist.py
```
