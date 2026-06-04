import json
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pathlib import Path
from rag.indexer import MedicalIndexer
from config import EMBED_MODEL, SYSTEM_PROMPT


SYNTHETIC_CASES = [
    {
        "chief_complaint": "胸痛・息切れ",
        "symptoms": ["前胸部圧迫感", "冷汗", "左肩への放散痛", "呼吸困難"],
        "vitals": "BP 90/60, HR 110, SpO2 94%, RR 24",
        "history": "高血圧・糖尿病・喫煙歴20年",
        "demographics": "65歳男性",
        "answer": {
            "primary": {
                "disease": "急性冠症候群（ACS）",
                "probability": 0.72,
                "basis": "典型的な胸痛+冷汗+放散痛+危険因子",
                "source_refs": []
            },
            "differentials": [
                {"disease": "大動脈解離", "probability": 0.15,
                 "distinguishing_features": "血圧左右差・引き裂く痛み"},
                {"disease": "肺塞栓症", "probability": 0.08,
                 "distinguishing_features": "片側下肢浮腫・旅行歴"},
                {"disease": "急性心膜炎", "probability": 0.05,
                 "distinguishing_features": "体位による痛みの変化"}
            ],
            "red_flags": ["BP 90/60 (ショック)", "SpO2 94%", "糖尿病性無症候性梗塞の可能性"],
            "next_steps": ["12誘導心電図", "採血(TnI, CK-MB, BNP)", "胸部X線", "循環器緊急コール"],
            "urgency": "immediate"
        }
    },
    {
        "chief_complaint": "突然の激頭痛",
        "symptoms": ["突発する「人生最悪」の頭痛", "嘔吐", "項部硬直", "光過敏"],
        "vitals": "BP 170/100, HR 88, 体温 37.2",
        "history": "喫煙歴・家族性脳動脈瘤なし",
        "demographics": "42歳女性",
        "answer": {
            "primary": {
                "disease": "くも膜下出血（SAH）",
                "probability": 0.78,
                "basis": "thunderclap headache + 項部硬直",
                "source_refs": []
            },
            "differentials": [
                {"disease": "細菌性髄膜炎", "probability": 0.12,
                 "distinguishing_features": "発熱・意識障害・皮疹"},
                {"disease": "高血圧性頭痛", "probability": 0.06,
                 "distinguishing_features": "徐々に増強・BP制御で改善"},
                {"disease": "偏頭痛", "probability": 0.04,
                 "distinguishing_features": "既往歴・前兆"}
            ],
            "red_flags": ["thunderclap headache = SAH否定まで緊急扱い", "項部硬直"],
            "next_steps": ["頭部CT（造影なし）", "LP（CT正常ならキサントクロミア確認）", "脳外科コール"],
            "urgency": "immediate"
        }
    },
    {
        "chief_complaint": "発熱・咳嗽 3日間",
        "symptoms": ["38.5℃発熱", "湿性咳嗽", "右下肺の打診濁音"],
        "vitals": "BP 128/82, HR 96, SpO2 96%, RR 20",
        "history": "特になし",
        "demographics": "35歳男性",
        "answer": {
            "primary": {
                "disease": "市中肺炎（CAP）",
                "probability": 0.80,
                "basis": "発熱+湿性咳嗽+打診濁音",
                "source_refs": []
            },
            "differentials": [
                {"disease": "結核", "probability": 0.08,
                 "distinguishing_features": "海外渡航歴・夜間発汗・長期経過"},
                {"disease": "肺癌+閉塞性肺炎", "probability": 0.07,
                 "distinguishing_features": "喫煙歴・繰り返す肺炎"},
                {"disease": "非定型肺炎", "probability": 0.05,
                 "distinguishing_features": "乾性咳・β-ラクタム無効"}
            ],
            "red_flags": ["PSI/CURB-65スコアで重症度判定必須"],
            "next_steps": ["胸部X線", "採血(CBC, CRP, PCT)", "喀痰グラム染色+培養", "PSIスコア算定"],
            "urgency": "urgent"
        }
    },
]


def build_instruction(case: dict, context: str = "") -> dict:
    case_text = (
        f"主訴: {case['chief_complaint']}\n"
        f"症状: {', '.join(case['symptoms'])}\n"
        f"バイタル: {case['vitals']}\n"
        f"既往歴: {case.get('history', 'なし')}\n"
        f"患者背景: {case['demographics']}"
    )
    if context:
        instruction = f"以下の患者情報と参考文献をもとに鑑別診断をJSON形式で行ってください。\n\n参考文献:\n{context}\n\n{case_text}"
    else:
        instruction = f"以下の患者情報をもとに鑑別診断をJSON形式で行ってください。\n\n{case_text}"
    output = json.dumps(case["answer"], ensure_ascii=False, indent=2)
    return {
        "instruction": instruction,
        "input": "",
        "output": output,
    }


def main():
    out_dir = Path("data/processed")
    out_dir.mkdir(parents=True, exist_ok=True)

    index_dir = Path("data/index")
    use_rag = index_dir.exists() and (index_dir / "chunks.json").exists()

    if use_rag:
        print("RAG index found, augmenting cases with retrieved context...")
        indexer = MedicalIndexer(EMBED_MODEL)
        indexer.load(str(index_dir))

    records = []
    for case in SYNTHETIC_CASES:
        context = ""
        if use_rag:
            query = f"{case['chief_complaint']} {' '.join(case['symptoms'][:3])}"
            docs = indexer.retrieve(query, top_k=3)
            context = "\n\n".join(
                f"[{d['source']}] {d['text'][:250]}" for d in docs
            )
        records.append(build_instruction(case, context))

    out_path = out_dir / "dd_training.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)
    print(f"Saved {len(records)} training samples → {out_path}")


if __name__ == "__main__":
    main()
