import json
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pathlib import Path
from config import EMBED_MODEL, SYSTEM_PROMPT

EXTENDED_CASES = [
    {
        "chief_complaint": "胸痛・息切れ",
        "symptoms": ["前胸部圧迫感", "冷汗", "左肩への放散痛", "呼吸困難"],
        "vitals": "BP 90/60, HR 110, SpO2 94%, RR 24",
        "history": "高血圧・糖尿病・喫煙歴20年",
        "demographics": "65歳男性",
        "answer": {
            "primary": {"disease": "急性冠症候群（ACS）", "probability": 0.72,
                        "basis": "典型的な胸痛+冷汗+放散痛+危険因子蓄積", "source_refs": []},
            "differentials": [
                {"disease": "大動脈解離", "probability": 0.15, "distinguishing_features": "血圧左右差・引き裂く痛み"},
                {"disease": "肺塞栓症", "probability": 0.08, "distinguishing_features": "片側下肢浮腫・旅行歴"},
                {"disease": "急性心膜炎", "probability": 0.05, "distinguishing_features": "体位変換で痛み変化"}
            ],
            "red_flags": ["BP 90/60 ショック疑い", "SpO2 94% 低酸素血症", "糖尿病による無症候性梗塞の可能性"],
            "next_steps": ["12誘導心電図", "採血(TnI/CK-MB/BNP)", "胸部X線", "循環器緊急コール"],
            "urgency": "immediate"
        }
    },
    {
        "chief_complaint": "突然の激頭痛",
        "symptoms": ["雷鳴頭痛", "嘔吐", "項部硬直", "羞明"],
        "vitals": "BP 170/100, HR 88, 体温 37.2℃",
        "history": "特記事項なし",
        "demographics": "42歳女性",
        "answer": {
            "primary": {"disease": "くも膜下出血（SAH）", "probability": 0.78,
                        "basis": "thunderclap headache + 項部硬直の組み合わせ", "source_refs": []},
            "differentials": [
                {"disease": "細菌性髄膜炎", "probability": 0.12, "distinguishing_features": "高熱・意識障害・皮疹"},
                {"disease": "高血圧性頭痛", "probability": 0.06, "distinguishing_features": "徐々に増強・降圧で改善"},
                {"disease": "偏頭痛", "probability": 0.04, "distinguishing_features": "既往歴・前兆・光過敏のみ"}
            ],
            "red_flags": ["thunderclap headache はSAH否定まで緊急扱い", "項部硬直は髄膜刺激徴候"],
            "next_steps": ["頭部単純CT（造影なし）", "CT正常ならLP（キサントクロミア確認）", "脳外科緊急コール"],
            "urgency": "immediate"
        }
    },
    {
        "chief_complaint": "発熱・咳嗽 3日間",
        "symptoms": ["38.5℃発熱", "湿性咳嗽", "右下肺打診濁音", "CRP上昇"],
        "vitals": "BP 128/82, HR 96, SpO2 96%, RR 20",
        "history": "特記事項なし",
        "demographics": "35歳男性",
        "answer": {
            "primary": {"disease": "市中肺炎（CAP）", "probability": 0.80,
                        "basis": "発熱+湿性咳嗽+打診濁音の三徴", "source_refs": []},
            "differentials": [
                {"disease": "肺結核", "probability": 0.08, "distinguishing_features": "海外渡航歴・夜間発汗・長期経過"},
                {"disease": "肺癌+閉塞性肺炎", "probability": 0.07, "distinguishing_features": "喫煙歴・繰り返す肺炎"},
                {"disease": "非定型肺炎", "probability": 0.05, "distinguishing_features": "乾性咳・β-ラクタム無効"}
            ],
            "red_flags": ["CURB-65スコアで入院適応を判定"],
            "next_steps": ["胸部X線", "採血(CBC/CRP/PCT)", "喀痰グラム染色+培養", "CURB-65スコア算定"],
            "urgency": "urgent"
        }
    },
    {
        "chief_complaint": "意識障害・血糖異常",
        "symptoms": ["意識レベル低下", "深大呼吸（クスマウル呼吸）", "脱水", "嘔吐"],
        "vitals": "BP 100/70, HR 120, RR 30（深く速い）, 体温 37.8℃",
        "history": "1型糖尿病（インスリン中断）",
        "demographics": "22歳女性",
        "answer": {
            "primary": {"disease": "糖尿病性ケトアシドーシス（DKA）", "probability": 0.85,
                        "basis": "1型糖尿病+インスリン中断+クスマウル呼吸+脱水", "source_refs": []},
            "differentials": [
                {"disease": "高血糖高浸透圧症候群（HHS）", "probability": 0.08, "distinguishing_features": "2型DM・血糖>600・ケトーシス軽度"},
                {"disease": "乳酸アシドーシス", "probability": 0.04, "distinguishing_features": "ビグアナイド服用・腎不全・ショック"},
                {"disease": "アルコール性ケトアシドーシス", "probability": 0.03, "distinguishing_features": "大量飲酒歴・血糖正常〜低値"}
            ],
            "red_flags": ["クスマウル呼吸は重篤な代謝性アシドーシスのサイン", "意識障害あり"],
            "next_steps": ["血糖・血液ガス・電解質・ケトン体", "大口径ルート2本確保", "輸液（NS 1L/h）開始", "インスリン持続投与"],
            "urgency": "immediate"
        }
    },
    {
        "chief_complaint": "突然の片麻痺・構音障害",
        "symptoms": ["右半身麻痺（突然発症）", "構音障害", "顔面神経麻痺", "発症1時間"],
        "vitals": "BP 190/110, HR 82, SpO2 98%",
        "history": "心房細動・抗凝固薬（アピキサバン）内服",
        "demographics": "70歳男性",
        "answer": {
            "primary": {"disease": "急性脳梗塞（心原性塞栓症）", "probability": 0.85,
                        "basis": "突然発症+心房細動+片麻痺+構音障害", "source_refs": []},
            "differentials": [
                {"disease": "脳出血", "probability": 0.10, "distinguishing_features": "抗凝固薬内服・頭痛・嘔吐"},
                {"disease": "TIA", "probability": 0.03, "distinguishing_features": "症状消失（現在持続中なので可能性低）"},
                {"disease": "Todd麻痺", "probability": 0.02, "distinguishing_features": "先行するけいれんの有無"}
            ],
            "red_flags": ["発症1時間以内→tPA適応ウィンドウ内", "DOAC内服→出血リスク評価必須"],
            "next_steps": ["頭部CT（出血除外）", "NIHSS評価", "DOAC最終服用時刻確認", "脳卒中チーム緊急コール"],
            "urgency": "immediate"
        }
    },
    {
        "chief_complaint": "腹痛・発熱",
        "symptoms": ["右下腹部痛（McBurney点圧痛）", "38.2℃発熱", "悪心・嘔吐", "WBC 14000"],
        "vitals": "BP 125/80, HR 100, 体温 38.2℃",
        "history": "特記事項なし",
        "demographics": "25歳女性",
        "answer": {
            "primary": {"disease": "急性虫垂炎", "probability": 0.70,
                        "basis": "McBurney点圧痛+発熱+白血球増加", "source_refs": []},
            "differentials": [
                {"disease": "卵巣捻転", "probability": 0.12, "distinguishing_features": "突然発症の間歇的骨盤痛・超音波で腫大卵巣"},
                {"disease": "異所性妊娠", "probability": 0.10, "distinguishing_features": "月経周期確認・尿妊娠反応必須"},
                {"disease": "卵巣嚢腫破裂", "probability": 0.05, "distinguishing_features": "突然の激痛・超音波で腹水"},
                {"disease": "腸管膜リンパ節炎", "probability": 0.03, "distinguishing_features": "先行する上気道炎"}
            ],
            "red_flags": ["女性の腹痛は必ず妊娠検査（β-hCG）を確認"],
            "next_steps": ["尿妊娠反応（最優先）", "経腟超音波", "腹部CT（造影）", "外科コンサルト"],
            "urgency": "urgent"
        }
    },
    {
        "chief_complaint": "呼吸困難・下腿浮腫",
        "symptoms": ["労作時呼吸困難", "起座呼吸", "両下腿浮腫", "体重増加3kg/週"],
        "vitals": "BP 160/100, HR 110, SpO2 90%, RR 28",
        "history": "陳旧性心筋梗塞・高血圧",
        "demographics": "72歳男性",
        "answer": {
            "primary": {"disease": "急性心不全（急性代償不全）", "probability": 0.80,
                        "basis": "心筋梗塞既往+起座呼吸+両下腿浮腫+体重増加", "source_refs": []},
            "differentials": [
                {"disease": "肺塞栓症", "probability": 0.10, "distinguishing_features": "突然発症・片側下腿浮腫・胸膜性胸痛"},
                {"disease": "COPD増悪", "probability": 0.06, "distinguishing_features": "喫煙歴・慢性咳嗽・過膨張"},
                {"disease": "肺炎", "probability": 0.04, "distinguishing_features": "発熱・片側浸潤影・膿性痰"}
            ],
            "red_flags": ["SpO2 90% 低酸素血症", "起座呼吸は重篤な肺うっ血"],
            "next_steps": ["胸部X線（バット翼陰影確認）", "BNP/NT-proBNP", "心エコー", "ニトログリセリン+フロセミド静注"],
            "urgency": "immediate"
        }
    },
    {
        "chief_complaint": "発熱・意識障害",
        "symptoms": ["39℃発熱", "意識混濁（GCS 12）", "頸部硬直", "皮膚に点状出血"],
        "vitals": "BP 85/50, HR 130, SpO2 95%, RR 28",
        "history": "特記事項なし（大学生）",
        "demographics": "19歳男性",
        "answer": {
            "primary": {"disease": "細菌性髄膜炎（髄膜炎菌性敗血症）", "probability": 0.82,
                        "basis": "頸部硬直+点状出血+敗血症性ショック+若年者", "source_refs": []},
            "differentials": [
                {"disease": "ウイルス性脳炎（ヘルペス）", "probability": 0.08, "distinguishing_features": "局所神経症状・側頭葉病変"},
                {"disease": "敗血症性ショック（他起源）", "probability": 0.06, "distinguishing_features": "髄膜刺激徴候なし"},
                {"disease": "劇症型A群連鎖球菌感染症", "probability": 0.04, "distinguishing_features": "皮膚感染巣・壊死性筋膜炎"}
            ],
            "red_flags": ["点状出血→紫斑への進行はDIC・Waterhouse-Friderichsen症候群を示唆", "BP 85/50 ショック"],
            "next_steps": ["血液培養2セット採取後に即セフトリアキソン2g静注", "デキサメサゾン0.15mg/kg（抗菌薬前）", "ICU管理", "感染科コール"],
            "urgency": "immediate"
        }
    },
    {
        "chief_complaint": "上腹部痛・黄疸",
        "symptoms": ["右季肋部〜心窩部痛", "38.8℃発熱", "黄疸（眼球黄染）", "悪寒戦慄"],
        "vitals": "BP 105/65, HR 118, 体温 38.8℃",
        "history": "胆石症の既往",
        "demographics": "55歳女性",
        "answer": {
            "primary": {"disease": "急性胆管炎", "probability": 0.75,
                        "basis": "Charcot三徴（腹痛+発熱+黄疸）+胆石既往", "source_refs": []},
            "differentials": [
                {"disease": "急性胆嚢炎", "probability": 0.12, "distinguishing_features": "黄疸なし・Murphy徴候・総胆管石なし"},
                {"disease": "急性膵炎", "probability": 0.08, "distinguishing_features": "背部放散痛・アミラーゼ/リパーゼ著明上昇"},
                {"disease": "肝膿瘍", "probability": 0.05, "distinguishing_features": "アメーバ/化膿性・CT所見"}
            ],
            "red_flags": ["BP 105/65 + 悪寒戦慄→敗血症性ショック移行を監視", "Reynolds五徴（Charcot三徴+意識障害+ショック）は重症"],
            "next_steps": ["腹部超音波（胆管拡張確認）", "採血（肝機能・胆道系酵素・培養）", "抗菌薬投与", "緊急ERCP/PTCD検討"],
            "urgency": "urgent"
        }
    },
    {
        "chief_complaint": "全身倦怠感・体重減少",
        "symptoms": ["3ヶ月で5kgの体重減少", "全身倦怠感", "夜間発汗", "持続する微熱"],
        "vitals": "BP 118/75, HR 88, 体温 37.6℃",
        "history": "海外渡航歴（東南アジア）6ヶ月前",
        "demographics": "38歳男性",
        "answer": {
            "primary": {"disease": "肺結核", "probability": 0.55,
                        "basis": "体重減少+夜間発汗+微熱+渡航歴+慢性経過", "source_refs": []},
            "differentials": [
                {"disease": "悪性リンパ腫", "probability": 0.20, "distinguishing_features": "B症状（発熱・夜汗・体重減少）+リンパ節腫大"},
                {"disease": "HIV/AIDS", "probability": 0.12, "distinguishing_features": "リスク行動歴・日和見感染"},
                {"disease": "消化器癌", "probability": 0.10, "distinguishing_features": "消化器症状・腫瘍マーカー"},
                {"disease": "甲状腺機能亢進症", "probability": 0.03, "distinguishing_features": "動悸・発汗・甲状腺腫"}
            ],
            "red_flags": ["結核は感染対策（陰圧個室・N95マスク）を先行させる"],
            "next_steps": ["胸部X線/CT", "喀痰3回抗酸菌塗沫+培養+GeneXpert", "HIV抗体検査", "IGRA（インターフェロンγ遊離試験）"],
            "urgency": "urgent"
        }
    },
]


def build_dd_records(cases, indexer=None):
    records = []
    for case in cases:
        context = ""
        if indexer:
            query = f"{case['chief_complaint']} {' '.join(case['symptoms'][:3])}"
            docs = indexer.retrieve(query, top_k=3)
            context = "\n\n".join(
                f"[{d['source']}] {d['text'][:300]}" for d in docs
            )
        if context:
            instruction = (
                f"以下の患者情報と参考文献をもとに鑑別診断をJSON形式で行ってください。\n\n"
                f"参考文献:\n{context}\n\n"
                f"主訴: {case['chief_complaint']}\n"
                f"症状: {', '.join(case['symptoms'])}\n"
                f"バイタル: {case['vitals']}\n"
                f"既往歴: {case.get('history', 'なし')}\n"
                f"患者背景: {case['demographics']}"
            )
        else:
            instruction = (
                f"以下の患者情報をもとに鑑別診断をJSON形式で行ってください。\n\n"
                f"主訴: {case['chief_complaint']}\n"
                f"症状: {', '.join(case['symptoms'])}\n"
                f"バイタル: {case['vitals']}\n"
                f"既往歴: {case.get('history', 'なし')}\n"
                f"患者背景: {case['demographics']}"
            )
        records.append({
            "instruction": instruction,
            "input": "",
            "output": json.dumps(case["answer"], ensure_ascii=False, indent=2),
        })
    return records


def sample_apollo(apollo_path, n=500):
    with open(apollo_path, encoding="utf-8") as f:
        data = json.load(f)
    import random
    random.seed(42)
    sampled = random.sample(data, min(n, len(data)))
    filtered = []
    for item in sampled:
        inst = item.get("instruction", "")
        out = item.get("output", "")
        if inst and out and len(inst) > 20 and len(out) > 20:
            filtered.append({"instruction": inst, "input": "", "output": out})
    return filtered


def main():
    out_dir = Path("data/processed")
    out_dir.mkdir(parents=True, exist_ok=True)

    index_dir = Path("data/index")
    indexer = None
    if index_dir.exists() and (index_dir / "chunks.json").exists():
        print("Loading RAG index...")
        import sys, os
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from rag.indexer import MedicalIndexer
        from config import EMBED_MODEL
        indexer = MedicalIndexer(EMBED_MODEL)
        indexer.load(str(index_dir))

    dd_records = build_dd_records(EXTENDED_CASES, indexer)
    print(f"DD cases: {len(dd_records)}")

    apollo_path = out_dir / "apollocorpus_sample.json"
    apollo_records = []
    if apollo_path.exists():
        apollo_records = sample_apollo(str(apollo_path), n=500)
        print(f"ApolloCorpus samples: {len(apollo_records)}")

    all_records = dd_records + apollo_records
    import random; random.seed(42); random.shuffle(all_records)

    out_path = out_dir / "dd_training_full.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(all_records, f, ensure_ascii=False, indent=2)
    print(f"Total training samples: {len(all_records)} → {out_path}")

    split = int(len(all_records) * 0.9)
    train_path = out_dir / "train.json"
    val_path = out_dir / "val.json"
    with open(train_path, "w", encoding="utf-8") as f:
        json.dump(all_records[:split], f, ensure_ascii=False, indent=2)
    with open(val_path, "w", encoding="utf-8") as f:
        json.dump(all_records[split:], f, ensure_ascii=False, indent=2)
    print(f"Train: {split}, Val: {len(all_records)-split}")


if __name__ == "__main__":
    main()
