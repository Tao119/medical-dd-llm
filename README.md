# Medical DD-LLM — 鑑別診断構造化言語モデル

医療文献を知識ベースにした RAG + LLM による**構造化鑑別診断生成システム**。

## 新しいコンセプト

従来の医療 LLM がフリーテキストで回答するのに対し、本システムは**必ず JSON スキーマで出力**する。

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

**利点:**
- 構造化 = 電子カルテ・意思決定支援システムと直接連携可能
- 確率表示 = 誤診リスクの可視化
- 根拠引用 = RAG で文献の何ページから来た判断かを明示
- Red flag 分離 = 緊急対応の見落とし防止

## ディレクトリ構成

```
medical-dd-llm/
├── config.py                      # モデル・プロンプト設定
├── train.py                       # QLoRA ファインチューニング
├── infer.py                       # 推論 (demo / interactive)
├── rag/
│   └── indexer.py                 # 医療文献 → Faiss インデックス
├── model/
│   └── dd_generator.py            # DDGenerator クラス
├── eval/
│   └── evaluator.py               # 鑑別診断評価指標
├── scripts/
│   └── prepare_training_data.py   # 訓練データ生成
└── data/
    ├── raw/                        # 医療文献 (.txt / .pdf)
    ├── processed/                  # 生成済み訓練データ
    └── index/                      # RAG インデックス
```

## クイックスタート

### 1. 医療文献を配置

```bash
cp your_papers.txt data/raw/
cp your_guidelines.pdf data/raw/
```

### 2. RAG インデックス構築

```bash
python3 rag/indexer.py data/raw data/index
```

### 3. 訓練データ生成（文献を加味した合成 QA）

```bash
python3 scripts/prepare_training_data.py
```

### 4. ファインチューニング

```bash
python3 train.py --data data/processed/dd_training.json --epochs 10
```

### 5. 推論

```bash
# デモ症例
python3 infer.py

# インタラクティブ
python3 infer.py --interactive

# ファインチューニング済みモデルで
python3 infer.py --model model/dd_finetuned --interactive
```

## 評価指標

| 指標 | 説明 | 重み |
|------|------|------|
| primary_match | 第一診断の一致率（形態素ベース） | 35% |
| primary_prob_error | 確率誤差（低いほど良） | 15% |
| differential_recall | 鑑別診断の再現率 | 25% |
| red_flag_recall | Red Flag の再現率 | 15% |
| urgency_match | 緊急度の一致 | 10% |

## 必要環境

```bash
pip install transformers peft datasets torch faiss-cpu pdfplumber
```
