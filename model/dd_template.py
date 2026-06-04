import re
import json
from typing import Optional


URGENCY_KEYWORDS = {
    "immediate": ["ショック", "失神", "SpO2 9", "BP 8", "BP 7", "GCS", "意識消失",
                  "心停止", "気道閉塞", "出血多量", "大動脈", "クスマウル",
                  "意識障害", "麻痺", "頸部硬直", "点状出血", "雷鳴頭痛"],
    "urgent":    ["発熱", "呼吸困難", "腹痛", "頭痛", "胸痛", "嘔吐", "黄疸"],
}

DD_RULES = [
    {
        "keywords": ["前胸部", "胸痛", "圧迫感", "放散痛", "冷汗", "ST"],
        "diagnoses": [
            {"disease": "急性冠症候群（ACS）", "base_prob": 0.70,
             "boost_kw": ["ST上昇", "TnI", "心電図", "糖尿病", "高血圧", "喫煙"]},
            {"disease": "大動脈解離",           "base_prob": 0.15,
             "boost_kw": ["引き裂く", "血圧左右差", "背部痛"]},
            {"disease": "肺塞栓症",             "base_prob": 0.08,
             "boost_kw": ["下肢浮腫", "旅行歴", "術後", "Wells"]},
            {"disease": "急性心膜炎",           "base_prob": 0.07,
             "boost_kw": ["体位", "摩擦音", "若年"]},
        ],
        "red_flags": ["心電図 12誘導即時確認", "TnI/BNP採血", "循環器緊急コール"],
        "next_steps": ["12誘導心電図", "採血(TnI/CK-MB/BNP)", "胸部X線", "心エコー"],
    },
    {
        "keywords": ["頭痛", "thunder", "雷鳴", "項部", "羞明"],
        "diagnoses": [
            {"disease": "くも膜下出血（SAH）",   "base_prob": 0.70,
             "boost_kw": ["雷鳴", "突然", "最悪", "項部硬直"]},
            {"disease": "細菌性髄膜炎",          "base_prob": 0.15,
             "boost_kw": ["発熱", "意識", "皮疹", "点状出血"]},
            {"disease": "高血圧性頭痛",          "base_prob": 0.10,
             "boost_kw": ["高血圧", "徐々に"]},
            {"disease": "偏頭痛",               "base_prob": 0.05,
             "boost_kw": ["既往", "前兆", "女性"]},
        ],
        "red_flags": ["SAH否定まで緊急扱い", "CT後にLP施行（キサントクロミア確認）"],
        "next_steps": ["頭部単純CT（造影なし）", "LP（CT陰性時）", "脳外科コール"],
    },
    {
        "keywords": ["発熱", "咳", "呼吸困難", "打診", "浸潤"],
        "diagnoses": [
            {"disease": "市中肺炎（CAP）",       "base_prob": 0.72,
             "boost_kw": ["湿性咳", "打診濁音", "CRP上昇"]},
            {"disease": "肺結核",               "base_prob": 0.12,
             "boost_kw": ["渡航歴", "夜間発汗", "体重減少", "上葉"]},
            {"disease": "肺塞栓症",             "base_prob": 0.10,
             "boost_kw": ["突然", "呼吸困難", "胸膜痛"]},
            {"disease": "非定型肺炎",           "base_prob": 0.06,
             "boost_kw": ["乾性咳", "若年", "β-ラクタム無効"]},
        ],
        "red_flags": ["CURB-65スコアで入院適応判定", "結核疑いは陰圧個室+N95マスク"],
        "next_steps": ["胸部X線", "採血(CBC/CRP)", "喀痰培養", "CURB-65算定"],
    },
    {
        "keywords": ["右下腹部", "McBurney", "虫垂", "腹痛", "嘔吐"],
        "diagnoses": [
            {"disease": "急性虫垂炎",            "base_prob": 0.65,
             "boost_kw": ["McBurney", "反跳痛", "WBC上昇"]},
            {"disease": "卵巣捻転",             "base_prob": 0.15,
             "boost_kw": ["女性", "骨盤痛", "卵巣"]},
            {"disease": "異所性妊娠",           "base_prob": 0.12,
             "boost_kw": ["女性", "月経", "妊娠"]},
            {"disease": "腸管膜リンパ節炎",     "base_prob": 0.08,
             "boost_kw": ["上気道炎", "小児", "若年"]},
        ],
        "red_flags": ["女性は必ず尿妊娠反応（β-hCG）を確認"],
        "next_steps": ["尿妊娠反応（女性優先）", "腹部超音波", "腹部CT", "外科コンサルト"],
    },
    {
        "keywords": ["意識障害", "クスマウル", "DKA", "ケトン", "血糖", "糖尿"],
        "diagnoses": [
            {"disease": "糖尿病性ケトアシドーシス（DKA）", "base_prob": 0.78,
             "boost_kw": ["1型", "インスリン中断", "クスマウル", "ケトン"]},
            {"disease": "高血糖高浸透圧症候群（HHS）",    "base_prob": 0.10,
             "boost_kw": ["2型", "高浸透圧", "ケトーシス軽度"]},
            {"disease": "低血糖",              "base_prob": 0.08,
             "boost_kw": ["冷汗", "振戦", "インスリン過量"]},
            {"disease": "乳酸アシドーシス",    "base_prob": 0.04,
             "boost_kw": ["ビグアナイド", "腎不全", "ショック"]},
        ],
        "red_flags": ["クスマウル呼吸は重篤な代謝性アシドーシスのサイン"],
        "next_steps": ["血糖・血液ガス・電解質", "輸液（NS 1L/h）", "インスリン投与開始"],
    },
    {
        "keywords": ["呼吸困難", "起座呼吸", "浮腫", "体重増加", "BNP", "心不全"],
        "diagnoses": [
            {"disease": "急性心不全（急性代償不全）", "base_prob": 0.72,
             "boost_kw": ["起座呼吸", "両下腿浮腫", "心筋梗塞", "BNP"]},
            {"disease": "肺塞栓症", "base_prob": 0.14, "boost_kw": ["突然", "片側浮腫"]},
            {"disease": "COPD増悪", "base_prob": 0.09, "boost_kw": ["喫煙歴", "慢性"]},
            {"disease": "肺炎", "base_prob": 0.05, "boost_kw": ["発熱", "片側浸潤"]},
        ],
        "red_flags": ["SpO2 90% 低酸素血症", "起座呼吸は重篤な肺うっ血"],
        "next_steps": ["胸部X線（バット翼陰影）", "BNP/NT-proBNP", "心エコー", "ニトログリセリン+フロセミド"],
    },
    {
        "keywords": ["発熱", "頸部硬直", "髄膜", "Kernig", "Brudzinski", "点状出血"],
        "diagnoses": [
            {"disease": "細菌性髄膜炎", "base_prob": 0.75,
             "boost_kw": ["頸部硬直", "点状出血", "意識障害", "若年"]},
            {"disease": "ウイルス性脳炎", "base_prob": 0.13, "boost_kw": ["局所神経", "側頭葉"]},
            {"disease": "敗血症性ショック", "base_prob": 0.08, "boost_kw": ["ショック", "臓器不全"]},
            {"disease": "熱中症", "base_prob": 0.04, "boost_kw": ["高温環境", "夏季"]},
        ],
        "red_flags": ["抗菌薬投与を30分以内に開始", "点状出血はDICのサイン"],
        "next_steps": ["血液培養2セット採取", "セフトリアキソン2g静注", "デキサメサゾン（抗菌薬前）", "ICU管理"],
    },
    {
        "keywords": ["黄疸", "胆管", "Charcot", "胆石", "Murphy", "季肋部"],
        "diagnoses": [
            {"disease": "急性胆管炎", "base_prob": 0.65,
             "boost_kw": ["黄疸", "Charcot", "胆石", "胆管"]},
            {"disease": "急性胆嚢炎", "base_prob": 0.20, "boost_kw": ["Murphy", "壁肥厚"]},
            {"disease": "急性膵炎", "base_prob": 0.10, "boost_kw": ["背部放散痛", "アミラーゼ"]},
            {"disease": "肝膿瘍", "base_prob": 0.05, "boost_kw": ["海外", "アメーバ"]},
        ],
        "red_flags": ["Charcot三徴=胆管炎（黄疸+発熱+腹痛）", "敗血症性ショック移行に注意"],
        "next_steps": ["腹部超音波", "採血（肝機能・培養）", "抗菌薬投与", "緊急ERCP/PTCD"],
    },
    {
        "keywords": ["体重減少", "夜間発汗", "結核", "渡航", "血痰", "抗酸菌"],
        "diagnoses": [
            {"disease": "肺結核", "base_prob": 0.55,
             "boost_kw": ["渡航歴", "夜間発汗", "体重減少", "血痰"]},
            {"disease": "悪性リンパ腫", "base_prob": 0.20, "boost_kw": ["リンパ節腫大", "B症状"]},
            {"disease": "HIV/AIDS", "base_prob": 0.12, "boost_kw": ["リスク行動", "日和見感染"]},
            {"disease": "消化器癌", "base_prob": 0.08, "boost_kw": ["消化器症状", "腫瘍"]},
            {"disease": "甲状腺機能亢進症", "base_prob": 0.05, "boost_kw": ["動悸", "甲状腺"]},
        ],
        "red_flags": ["結核は感染対策先行（陰圧個室・N95マスク）"],
        "next_steps": ["胸部X線/CT", "喀痰3回塗沫+GeneXpert", "HIV抗体検査", "IGRA"],
    },
    {
        "keywords": ["片麻痺", "構音障害", "顔面神経麻痺", "脳卒中", "NIHSS"],
        "diagnoses": [
            {"disease": "急性脳梗塞",           "base_prob": 0.75,
             "boost_kw": ["心房細動", "突然発症", "片麻痺"]},
            {"disease": "脳出血",               "base_prob": 0.15,
             "boost_kw": ["抗凝固薬", "高血圧", "頭痛"]},
            {"disease": "TIA",                  "base_prob": 0.07,
             "boost_kw": ["症状消失", "短時間"]},
            {"disease": "Todd麻痺",            "base_prob": 0.03,
             "boost_kw": ["けいれん後", "一過性"]},
        ],
        "red_flags": ["発症時刻確認必須（tPA/血栓回収の適応判断）"],
        "next_steps": ["頭部CT（出血除外）", "NIHSS評価", "脳卒中チーム緊急コール", "12誘導心電図"],
    },
]


def infer_urgency(symptoms_text: str, vitals: str) -> str:
    combined = symptoms_text + " " + vitals
    for level in ["immediate", "urgent"]:
        if any(kw in combined for kw in URGENCY_KEYWORDS[level]):
            return level
    return "routine"


def match_rule(case_text: str) -> Optional[dict]:
    best_rule = None
    best_score = 0
    for rule in DD_RULES:
        score = sum(1 for kw in rule["keywords"] if kw in case_text)
        if score > best_score:
            best_score = score
            best_rule = rule
    return best_rule if best_score >= 2 else None


def normalize_probs(diagnoses: list[dict]) -> list[dict]:
    total = sum(d["base_prob"] for d in diagnoses)
    for d in diagnoses:
        d["probability"] = round(d["base_prob"] / total, 3)
    return diagnoses


def generate_dd(case: dict, retrieved_docs: list[dict]) -> dict:
    case_text = (
        f"{case.get('chief_complaint', '')} "
        f"{' '.join(case.get('symptoms', []))} "
        f"{case.get('history', '')} "
        f"{case.get('demographics', '')}"
    )
    # rule matching は case_text のみ（RAGテキストは症状パターンを汚染するため使わない）
    rule = match_rule(case_text)
    full_text = case_text  # boost_kw 計算用
    if rule is None:
        return {
            "primary": {"disease": "精査必要", "probability": 0.50,
                        "basis": "症状パターンが特定できません。専門医に相談してください。",
                        "source_refs": [d["source"] for d in retrieved_docs]},
            "differentials": [],
            "red_flags": ["専門医への紹介を検討"],
            "next_steps": ["バイタル安定化", "詳細な病歴聴取"],
            "urgency": infer_urgency(case_text, case.get("vitals", "")),
        }

    diagnoses = [dict(d) for d in rule["diagnoses"]]
    for d in diagnoses:
        boost = sum(1 for kw in d.get("boost_kw", []) if kw in full_text)
        d["base_prob"] = d["base_prob"] + boost * 0.03
    diagnoses = normalize_probs(diagnoses)

    primary = diagnoses[0]
    refs = list({d["source"] for d in retrieved_docs})

    return {
        "primary": {
            "disease": primary["disease"],
            "probability": primary["probability"],
            "basis": f"{case.get('chief_complaint','')}+{', '.join(case.get('symptoms',[])[:3])}",
            "source_refs": refs,
        },
        "differentials": [
            {"disease": d["disease"],
             "probability": d["probability"],
             "distinguishing_features": ""}
            for d in diagnoses[1:]
        ],
        "red_flags": rule["red_flags"],
        "next_steps": rule["next_steps"],
        "urgency": infer_urgency(case_text, case.get("vitals", "")),
    }
