from dataclasses import dataclass, field
from typing import Optional

# 推奨ベースモデル（用途別）
# Mac MPS (16GB+): Swallow-8B (MLX or HuggingFace)
# A100 40GB: Qwen2.5-7B with QLoRA
# 評価ベースライン: pfnet/Preferred-MedLLM-Qwen-72B (推論のみ)
BASE_MODEL = "tokyotech-llm/Llama-3.1-Swallow-8B-Instruct-v0.5"
BASE_MODEL_SMALL = "rinna/japanese-gpt2-medium"   # 動作確認用
EMBED_MODEL = "cl-tohoku/bert-base-japanese-v3"

# 評価データセット (stardust-coder/japanese-lm-med-harness)
IGAKUQA_BENCHMARK = "stardust-coder/IgakuQA"
APOLLOCORPUS_JA   = "kunishou/ApolloCorpus-ja"

DD_SCHEMA = {
    "primary": {
        "disease": "str",
        "icd10": "str (optional)",
        "probability": "float 0-1",
        "basis": "str (clinical reasoning)",
        "source_refs": "list[str]",
    },
    "differentials": [
        {
            "disease": "str",
            "probability": "float 0-1",
            "distinguishing_features": "str",
        }
    ],
    "red_flags": "list[str]",
    "next_steps": "list[str]",
    "urgency": "str: immediate | urgent | routine",
}

SYSTEM_PROMPT = """あなたは経験豊富な内科医として、根拠に基づいた鑑別診断を行います。
患者情報と参考文献を踏まえ、以下の JSON スキーマで必ず回答してください。

スキーマ:
- primary: 最有力診断 (disease, probability, basis, source_refs)
- differentials: 鑑別診断リスト (disease, probability, distinguishing_features)
- red_flags: 見逃してはならない緊急所見
- next_steps: 推奨される次の検査・処置
- urgency: immediate / urgent / routine

確率の合計が1になるよう調整し、根拠を必ず示してください。"""

RAG_TOP_K = 5
MAX_NEW_TOKENS = 512
TEMPERATURE = 0.1
