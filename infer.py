import json
import argparse
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from pathlib import Path
from rag.indexer import MedicalIndexer
from model.dd_generator import DDGenerator
from model.dd_template import generate_dd
from config import BASE_MODEL, EMBED_MODEL, RAG_TOP_K


def print_dd(result: dict):
    print("\n" + "=" * 60)
    print("鑑別診断結果")
    print("=" * 60)

    if result.get("parse_error"):
        print("[警告] JSON解析失敗 - 生出力:")
        print(result.get("raw_output", ""))
        return

    if "primary" in result:
        p = result["primary"]
        print(f"\n【第一診断】{p.get('disease', '不明')} (確率: {p.get('probability', 0):.0%})")
        print(f"  根拠: {p.get('basis', '')}")
        if p.get("source_refs"):
            print(f"  参照: {', '.join(p['source_refs'])}")

    if "differentials" in result:
        print("\n【鑑別診断】")
        for d in result["differentials"]:
            print(f"  ・{d.get('disease', '')} ({d.get('probability', 0):.0%})")
            if d.get("distinguishing_features"):
                print(f"    → {d['distinguishing_features']}")

    if "red_flags" in result:
        print("\n【⚠ Red Flags】")
        for r in result["red_flags"]:
            print(f"  ! {r}")

    if "next_steps" in result:
        print("\n【推奨検査・処置】")
        for s in result["next_steps"]:
            print(f"  ✓ {s}")

    urgency = result.get("urgency", "不明")
    urgency_map = {"immediate": "🔴 即時対応", "urgent": "🟡 緊急", "routine": "🟢 通常"}
    print(f"\n【緊急度】{urgency_map.get(urgency, urgency)}")

    if result.get("_retrieved_sources"):
        print(f"\n【参照文献】{', '.join(result['_retrieved_sources'])}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model",      default=None,
                        help="Fine-tuned model path (default: BASE_MODEL from config)")
    parser.add_argument("--index",      default="data/index")
    parser.add_argument("--case",       default=None,
                        help="JSON file with patient case")
    parser.add_argument("--interactive", action="store_true")
    args = parser.parse_args()

    model_path = args.model  # None = template mode

    index_dir = Path(args.index)
    if index_dir.exists() and (index_dir / "chunks.json").exists():
        indexer = MedicalIndexer(EMBED_MODEL)
        indexer.load(args.index)
        use_rag = True
    else:
        print("RAG index not found. Run: python rag/indexer.py to build index.")
        indexer = None
        use_rag = False

    use_llm = model_path is not None
    generator = DDGenerator(model_path) if use_llm else None
    if not use_llm:
        print("モード: RAG + テンプレートベース鑑別診断（--model でLLMを指定可）")

    if args.case:
        with open(args.case, encoding="utf-8") as f:
            case = json.load(f)
        docs = indexer.retrieve(
            f"{case.get('chief_complaint', '')} {' '.join(case.get('symptoms', [])[:3])}",
            top_k=RAG_TOP_K
        ) if use_rag else []
        result = (generator.diagnose(case, docs) if use_llm
                  else generate_dd(case, docs))
        print_dd(result)

    elif args.interactive:
        print("鑑別診断システム (interactive mode)")
        print("Ctrl+C で終了\n")
        while True:
            print("-" * 40)
            chief = input("主訴: ")
            symptoms_str = input("症状 (カンマ区切り): ")
            vitals = input("バイタル: ")
            history = input("既往歴 (なければEnter): ") or "なし"
            demographics = input("年齢・性別: ")
            case = {
                "chief_complaint": chief,
                "symptoms": [s.strip() for s in symptoms_str.split(",")],
                "vitals": vitals,
                "history": history,
                "demographics": demographics,
            }
            query = f"{chief} {symptoms_str}"
            docs = indexer.retrieve(query, top_k=RAG_TOP_K) if use_rag else []
            if docs:
                print(f"\n[RAG] {len(docs)}件の関連文献を参照中...")
            result = (generator.diagnose(case, docs) if use_llm
                      else generate_dd(case, docs))
            print_dd(result)
    else:
        demo_case = {
            "chief_complaint": "胸痛・冷汗",
            "symptoms": ["前胸部圧迫感", "左肩放散痛", "冷汗", "呼吸困難"],
            "vitals": "BP 95/65, HR 108, SpO2 93%",
            "history": "高血圧・喫煙歴15年",
            "demographics": "58歳男性",
        }
        print("デモ症例で実行中...\n")
        docs = indexer.retrieve(
            f"{demo_case['chief_complaint']} {' '.join(demo_case['symptoms'][:3])}",
            top_k=RAG_TOP_K
        ) if use_rag else []
        result = (generator.diagnose(demo_case, docs) if use_llm
                  else generate_dd(demo_case, docs))
        print_dd(result)


if __name__ == "__main__":
    main()
