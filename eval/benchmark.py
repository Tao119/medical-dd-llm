"""
eval/benchmark.py — Comprehensive Benchmark for the DD System.

50 benchmark cases:
  Easy   (20): textbook presentations
  Medium (20): atypical / comorbidities
  Hard   (10): rare diseases, pediatric, elderly

Metrics:
  1. Primary diagnosis accuracy (word-overlap ≥ 0.6)
  2. ICD-10 prefix accuracy (first 3 chars)
  3. Urgency level accuracy
  4. Red-flag recall
  5. Differential coverage (gold primary in top-3 differentials)
"""
from __future__ import annotations

import json
import os
import sys
import textwrap
from dataclasses import dataclass, field

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from model.dd_engine import diagnose


# ================================================================== #
# BenchmarkCase
# ================================================================== #

@dataclass
class BenchmarkCase:
    id: str
    case: dict
    gold_primary_disease: str
    gold_urgency: str
    gold_icd10_prefix: str       # first 3 chars of ICD-10 code
    gold_red_flags: list[str]
    difficulty: str              # "easy", "medium", "hard"


# ================================================================== #
# 50 Benchmark Cases
# ================================================================== #

BENCHMARK_CASES: list[BenchmarkCase] = [

    # ================================================================
    # EASY (20): classic textbook presentations
    # ================================================================

    BenchmarkCase(
        id="E001",
        case={
            "chief_complaint": "前胸部圧迫感・冷汗",
            "symptoms": ["前胸部圧迫感", "左肩放散痛", "冷汗", "呼吸困難"],
            "vitals": "BP 90/60, HR 112, SpO2 92%",
            "history": "高血圧・喫煙歴20年・糖尿病",
            "demographics": "62歳男性",
        },
        gold_primary_disease="急性冠症候群",
        gold_urgency="immediate",
        gold_icd10_prefix="I21",
        gold_red_flags=["12誘導心電図", "TnI"],
        difficulty="easy",
    ),
    BenchmarkCase(
        id="E002",
        case={
            "chief_complaint": "雷鳴頭痛",
            "symptoms": ["突然の激頭痛", "嘔吐", "項部硬直", "羞明"],
            "vitals": "BP 170/100, HR 88, SpO2 98%",
            "history": "なし",
            "demographics": "40歳女性",
        },
        gold_primary_disease="くも膜下出血",
        gold_urgency="immediate",
        gold_icd10_prefix="I60",
        gold_red_flags=["CT陰性", "LP"],
        difficulty="easy",
    ),
    BenchmarkCase(
        id="E003",
        case={
            "chief_complaint": "発熱・右側腹部痛",
            "symptoms": ["発熱38.5℃", "右側腹部痛", "嘔気", "食欲低下"],
            "vitals": "BP 120/75, HR 98, Temp 38.5",
            "history": "なし",
            "demographics": "22歳男性",
        },
        gold_primary_disease="急性虫垂炎",
        gold_urgency="urgent",
        gold_icd10_prefix="K37",
        gold_red_flags=["腹膜刺激徴候"],
        difficulty="easy",
    ),
    BenchmarkCase(
        id="E004",
        case={
            "chief_complaint": "片麻痺・構音障害",
            "symptoms": ["突然の片麻痺", "構音障害", "顔面神経麻痺", "失語"],
            "vitals": "BP 185/110, HR 82, SpO2 97%",
            "history": "心房細動",
            "demographics": "72歳男性",
        },
        gold_primary_disease="急性脳梗塞",
        gold_urgency="immediate",
        gold_icd10_prefix="I63",
        gold_red_flags=["発症時刻確認", "NIHSS"],
        difficulty="easy",
    ),
    BenchmarkCase(
        id="E005",
        case={
            "chief_complaint": "発熱・頸部硬直",
            "symptoms": ["高熱39.8℃", "頸部硬直", "意識障害", "点状出血"],
            "vitals": "BP 95/60, HR 118, Temp 39.8",
            "history": "なし",
            "demographics": "19歳男性",
        },
        gold_primary_disease="細菌性髄膜炎",
        gold_urgency="immediate",
        gold_icd10_prefix="G00",
        gold_red_flags=["頸部硬直", "点状出血"],
        difficulty="easy",
    ),
    BenchmarkCase(
        id="E006",
        case={
            "chief_complaint": "呼吸困難・起座呼吸",
            "symptoms": ["起座呼吸", "両下腿浮腫", "体重増加5kg", "夜間発作性呼吸困難"],
            "vitals": "BP 155/95, HR 105, SpO2 88%",
            "history": "心筋梗塞既往・高血圧",
            "demographics": "70歳男性",
        },
        gold_primary_disease="急性心不全",
        gold_urgency="urgent",
        gold_icd10_prefix="I50",
        gold_red_flags=["SpO2 90%以下"],
        difficulty="easy",
    ),
    BenchmarkCase(
        id="E007",
        case={
            "chief_complaint": "引き裂くような背部痛",
            "symptoms": ["突然の引き裂く背部痛", "血圧左右差20mmHg", "縦隔拡大"],
            "vitals": "BP R:180/100 L:160/90, HR 102",
            "history": "高血圧・マルファン症候群",
            "demographics": "48歳男性",
        },
        gold_primary_disease="急性大動脈解離",
        gold_urgency="immediate",
        gold_icd10_prefix="I71",
        gold_red_flags=["造影CT", "外科緊急"],
        difficulty="easy",
    ),
    BenchmarkCase(
        id="E008",
        case={
            "chief_complaint": "発熱・咳嗽・呼吸困難",
            "symptoms": ["発熱38.8℃", "湿性咳嗽", "右下肺野肺炎浸潤影", "CRP上昇"],
            "vitals": "BP 130/80, HR 96, RR 24, SpO2 93%",
            "history": "なし",
            "demographics": "55歳女性",
        },
        gold_primary_disease="肺炎",
        gold_urgency="urgent",
        gold_icd10_prefix="J18",
        gold_red_flags=["SpO2"],
        difficulty="easy",
    ),
    BenchmarkCase(
        id="E009",
        case={
            "chief_complaint": "嘔気・腹痛・意識障害",
            "symptoms": ["嘔気", "腹痛", "クスマウル呼吸", "脱水"],
            "vitals": "BP 100/65, HR 115, RR 28",
            "history": "1型糖尿病",
            "demographics": "25歳女性",
        },
        gold_primary_disease="糖尿病性ケトアシドーシス",
        gold_urgency="immediate",
        gold_icd10_prefix="E10",
        gold_red_flags=["クスマウル"],
        difficulty="easy",
    ),
    BenchmarkCase(
        id="E010",
        case={
            "chief_complaint": "腰背部痛・血尿",
            "symptoms": ["突然の腰背部痛", "血尿", "嘔気", "疝痛"],
            "vitals": "BP 140/85, HR 92, Temp 37.0",
            "history": "尿路結石の既往",
            "demographics": "35歳男性",
        },
        gold_primary_disease="尿管結石",
        gold_urgency="urgent",
        gold_icd10_prefix="N20",
        gold_red_flags=["水腎症", "尿路閉塞"],
        difficulty="easy",
    ),
    BenchmarkCase(
        id="E011",
        case={
            "chief_complaint": "突然の呼吸困難・胸膜性胸痛",
            "symptoms": ["突然の呼吸困難", "片側性胸痛", "下肢浮腫", "旅行歴3日"],
            "vitals": "BP 115/75, HR 122, SpO2 91%, RR 26",
            "history": "術後2週間",
            "demographics": "65歳女性",
        },
        gold_primary_disease="肺塞栓症",
        gold_urgency="immediate",
        gold_icd10_prefix="I26",
        gold_red_flags=["D-dimer", "Wells"],
        difficulty="easy",
    ),
    BenchmarkCase(
        id="E012",
        case={
            "chief_complaint": "発熱・右季肋部痛",
            "symptoms": ["発熱38.5℃", "右季肋部痛", "Murphy徴候陽性", "嘔気"],
            "vitals": "BP 125/80, HR 95, Temp 38.5",
            "history": "胆石症の既往",
            "demographics": "45歳女性",
        },
        gold_primary_disease="急性胆嚢炎",
        gold_urgency="urgent",
        gold_icd10_prefix="K81",
        gold_red_flags=["腹膜刺激"],
        difficulty="easy",
    ),
    BenchmarkCase(
        id="E013",
        case={
            "chief_complaint": "発熱・頻尿・排尿時痛",
            "symptoms": ["発熱39.0℃", "腰部叩打痛", "頻尿", "膿尿"],
            "vitals": "BP 120/75, HR 104, Temp 39.0",
            "history": "なし",
            "demographics": "28歳女性",
        },
        gold_primary_disease="急性腎盂腎炎",
        gold_urgency="urgent",
        gold_icd10_prefix="N10",
        gold_red_flags=["敗血症兆候"],
        difficulty="easy",
    ),
    BenchmarkCase(
        id="E014",
        case={
            "chief_complaint": "心窩部痛・嘔吐",
            "symptoms": ["心窩部から背部への放散痛", "嘔吐", "アルコール多飲"],
            "vitals": "BP 130/80, HR 98, Temp 37.8",
            "history": "アルコール依存",
            "demographics": "50歳男性",
        },
        gold_primary_disease="急性膵炎",
        gold_urgency="urgent",
        gold_icd10_prefix="K85",
        gold_red_flags=["重症膵炎", "ショック"],
        difficulty="easy",
    ),
    BenchmarkCase(
        id="E015",
        case={
            "chief_complaint": "喘鳴・呼吸困難",
            "symptoms": ["喘鳴", "呼吸困難", "起坐呼吸", "SpO2低下"],
            "vitals": "BP 130/85, HR 110, SpO2 88%, RR 32",
            "history": "気管支喘息",
            "demographics": "30歳男性",
        },
        gold_primary_disease="喘息発作",
        gold_urgency="urgent",
        gold_icd10_prefix="J45",
        gold_red_flags=["重篤な喘息", "挿管準備"],
        difficulty="easy",
    ),
    BenchmarkCase(
        id="E016",
        case={
            "chief_complaint": "失神・動悸",
            "symptoms": ["突然の意識消失", "動悸", "冷汗", "短時間で改善"],
            "vitals": "BP 85/50 (発作時), HR 45 (発作時)",
            "history": "なし",
            "demographics": "55歳男性",
        },
        gold_primary_disease="失神",
        gold_urgency="urgent",
        gold_icd10_prefix="R55",
        gold_red_flags=["12誘導心電図", "ホルター"],
        difficulty="easy",
    ),
    BenchmarkCase(
        id="E017",
        case={
            "chief_complaint": "吐血",
            "symptoms": ["大量の吐血", "黒色便", "めまい", "起立性低血圧"],
            "vitals": "BP 85/50, HR 128, SpO2 97%",
            "history": "NSAIDs服用",
            "demographics": "60歳男性",
        },
        gold_primary_disease="上部消化管出血",
        gold_urgency="immediate",
        gold_icd10_prefix="K92",
        gold_red_flags=["出血性ショック", "緊急内視鏡"],
        difficulty="easy",
    ),
    BenchmarkCase(
        id="E018",
        case={
            "chief_complaint": "アレルギー反応・呼吸困難",
            "symptoms": ["全身蕁麻疹", "顔面浮腫", "呼吸困難", "血圧低下"],
            "vitals": "BP 75/40, HR 130, SpO2 90%",
            "history": "食物アレルギー（蕎麦）",
            "demographics": "25歳女性",
        },
        gold_primary_disease="アナフィラキシー",
        gold_urgency="immediate",
        gold_icd10_prefix="T78",
        gold_red_flags=["アドレナリン", "気道確保"],
        difficulty="easy",
    ),
    BenchmarkCase(
        id="E019",
        case={
            "chief_complaint": "発熱・関節痛",
            "symptoms": ["高熱40.0℃", "多発関節痛", "皮疹", "口内炎"],
            "vitals": "BP 120/75, HR 102, Temp 40.0",
            "history": "なし",
            "demographics": "35歳女性",
        },
        gold_primary_disease="全身性エリテマトーデス",
        gold_urgency="urgent",
        gold_icd10_prefix="M32",
        gold_red_flags=["腎障害", "神経障害"],
        difficulty="easy",
    ),
    BenchmarkCase(
        id="E020",
        case={
            "chief_complaint": "突然の単麻痺・一過性視野障害",
            "symptoms": ["突然の単麻痺", "一過性視野障害", "症状が1時間で消失"],
            "vitals": "BP 155/90, HR 78",
            "history": "高血圧・喫煙",
            "demographics": "62歳男性",
        },
        gold_primary_disease="一過性脳虚血発作",
        gold_urgency="urgent",
        gold_icd10_prefix="G45",
        gold_red_flags=["脳卒中リスク", "ABCD2スコア"],
        difficulty="easy",
    ),

    # ================================================================
    # MEDIUM (20): atypical or comorbidities
    # ================================================================

    BenchmarkCase(
        id="M001",
        case={
            "chief_complaint": "胸痛・上腹部痛",
            "symptoms": ["食後上腹部痛", "軽度の胸部不快感", "げっぷ"],
            "vitals": "BP 125/80, HR 75, SpO2 98%",
            "history": "糖尿病・高血圧・喫煙歴",
            "demographics": "68歳男性",
        },
        gold_primary_disease="急性冠症候群",
        gold_urgency="immediate",
        gold_icd10_prefix="I21",
        gold_red_flags=["12誘導心電図", "TnI"],
        difficulty="medium",
    ),
    BenchmarkCase(
        id="M002",
        case={
            "chief_complaint": "激しい頭痛",
            "symptoms": ["突然の最悪の頭痛", "嘔吐", "羞明"],
            "vitals": "BP 160/95, HR 82, SpO2 99%",
            "history": "偏頭痛の既往",
            "demographics": "32歳女性",
        },
        gold_primary_disease="くも膜下出血",
        gold_urgency="immediate",
        gold_icd10_prefix="I60",
        gold_red_flags=["CT陰性でもLP必須", "SAH否定"],
        difficulty="medium",
    ),
    BenchmarkCase(
        id="M003",
        case={
            "chief_complaint": "意識障害・低体温",
            "symptoms": ["意識混濁", "徐脈", "低体温35.2℃", "便秘"],
            "vitals": "BP 90/60, HR 45, Temp 35.2",
            "history": "甲状腺機能低下症の加療中断",
            "demographics": "75歳女性",
        },
        gold_primary_disease="粘液水腫性昏睡",
        gold_urgency="immediate",
        gold_icd10_prefix="E03",
        gold_red_flags=["甲状腺機能低下", "低体温"],
        difficulty="medium",
    ),
    BenchmarkCase(
        id="M004",
        case={
            "chief_complaint": "動悸・発汗・高血圧",
            "symptoms": ["発作性高血圧", "激しい発汗", "頭痛", "動悸"],
            "vitals": "BP 210/120 (発作時), HR 118",
            "history": "高血圧治療歴",
            "demographics": "45歳女性",
        },
        gold_primary_disease="褐色細胞腫",
        gold_urgency="urgent",
        gold_icd10_prefix="D35",
        gold_red_flags=["高血圧緊急症", "カテコラミン"],
        difficulty="medium",
    ),
    BenchmarkCase(
        id="M005",
        case={
            "chief_complaint": "下肢浮腫・呼吸困難",
            "symptoms": ["両下腿浮腫", "呼吸困難", "起座呼吸", "喀血"],
            "vitals": "BP 110/70, HR 115, SpO2 89%",
            "history": "長期臥床・骨折術後",
            "demographics": "78歳女性",
        },
        gold_primary_disease="肺塞栓症",
        gold_urgency="immediate",
        gold_icd10_prefix="I26",
        gold_red_flags=["D-dimer", "造影CT"],
        difficulty="medium",
    ),
    BenchmarkCase(
        id="M006",
        case={
            "chief_complaint": "高熱・意識障害",
            "symptoms": ["高熱40.5℃", "意識障害", "頻脈", "発汗過多"],
            "vitals": "BP 100/65, HR 140, Temp 40.5",
            "history": "バセドウ病の未治療",
            "demographics": "38歳女性",
        },
        gold_primary_disease="甲状腺クリーゼ",
        gold_urgency="immediate",
        gold_icd10_prefix="E05",
        gold_red_flags=["甲状腺クリーゼ", "循環器不全"],
        difficulty="medium",
    ),
    BenchmarkCase(
        id="M007",
        case={
            "chief_complaint": "腹痛・嘔吐・便秘",
            "symptoms": ["腹痛", "嘔吐", "腹部膨満", "排ガス停止"],
            "vitals": "BP 120/80, HR 92, Temp 37.2",
            "history": "開腹手術歴",
            "demographics": "55歳女性",
        },
        gold_primary_disease="腸閉塞",
        gold_urgency="urgent",
        gold_icd10_prefix="K56",
        gold_red_flags=["腸管虚血", "穿孔"],
        difficulty="medium",
    ),
    BenchmarkCase(
        id="M008",
        case={
            "chief_complaint": "倦怠感・多飲多尿・体重減少",
            "symptoms": ["著明な倦怠感", "多飲多尿", "3kgの体重減少", "視力低下"],
            "vitals": "BP 130/80, HR 88",
            "history": "なし",
            "demographics": "55歳男性",
        },
        gold_primary_disease="2型糖尿病",
        gold_urgency="routine",
        gold_icd10_prefix="E11",
        gold_red_flags=["高血糖合併症", "ケトアシドーシス"],
        difficulty="medium",
    ),
    BenchmarkCase(
        id="M009",
        case={
            "chief_complaint": "発熱・腰背部痛",
            "symptoms": ["発熱38.0℃", "腰背部痛", "体重減少", "夜間発汗"],
            "vitals": "BP 125/78, HR 88, Temp 38.0",
            "history": "HIV陽性・免疫不全",
            "demographics": "40歳男性",
        },
        gold_primary_disease="肺結核",
        gold_urgency="urgent",
        gold_icd10_prefix="A15",
        gold_red_flags=["隔離", "接触者調査"],
        difficulty="medium",
    ),
    BenchmarkCase(
        id="M010",
        case={
            "chief_complaint": "高熱・頻脈・意識障害",
            "symptoms": ["高熱39.5℃", "頻脈120/分", "意識変容", "皮膚紅潮"],
            "vitals": "BP 95/55, HR 128, Temp 39.5, RR 26",
            "history": "尿路感染症の既往",
            "demographics": "82歳女性",
        },
        gold_primary_disease="敗血症",
        gold_urgency="immediate",
        gold_icd10_prefix="A41",
        gold_red_flags=["敗血症ショック", "臓器不全"],
        difficulty="medium",
    ),
    BenchmarkCase(
        id="M011",
        case={
            "chief_complaint": "四肢脱力・しびれ",
            "symptoms": ["進行性の四肢末梢麻痺", "反射消失", "先行する感染症"],
            "vitals": "BP 125/80, HR 82, SpO2 96%",
            "history": "2週間前に上気道炎",
            "demographics": "35歳男性",
        },
        gold_primary_disease="ギラン・バレー症候群",
        gold_urgency="urgent",
        gold_icd10_prefix="G61",
        gold_red_flags=["呼吸筋麻痺", "挿管準備"],
        difficulty="medium",
    ),
    BenchmarkCase(
        id="M012",
        case={
            "chief_complaint": "胸痛・発熱",
            "symptoms": ["鋭い胸痛（体位変換で悪化）", "発熱37.8℃", "心膜摩擦音"],
            "vitals": "BP 125/78, HR 98, Temp 37.8",
            "history": "最近のウイルス感染症",
            "demographics": "28歳男性",
        },
        gold_primary_disease="急性心膜炎",
        gold_urgency="urgent",
        gold_icd10_prefix="I30",
        gold_red_flags=["心タンポナーデ", "心膜液貯留"],
        difficulty="medium",
    ),
    BenchmarkCase(
        id="M013",
        case={
            "chief_complaint": "腹痛・発熱・黄疸",
            "symptoms": ["右季肋部痛", "発熱38.9℃", "黄疸", "Charcotの三徴"],
            "vitals": "BP 110/70, HR 105, Temp 38.9",
            "history": "胆石症",
            "demographics": "58歳男性",
        },
        gold_primary_disease="急性胆管炎",
        gold_urgency="urgent",
        gold_icd10_prefix="K83",
        gold_red_flags=["胆管炎敗血症", "ERCP緊急"],
        difficulty="medium",
    ),
    BenchmarkCase(
        id="M014",
        case={
            "chief_complaint": "意識消失・痙攣",
            "symptoms": ["全般性強直間代発作", "発作後意識障害", "尿失禁"],
            "vitals": "BP 140/90, HR 110",
            "history": "てんかんなし",
            "demographics": "50歳男性",
        },
        gold_primary_disease="てんかん",
        gold_urgency="urgent",
        gold_icd10_prefix="G40",
        gold_red_flags=["重積状態", "気道確保"],
        difficulty="medium",
    ),
    BenchmarkCase(
        id="M015",
        case={
            "chief_complaint": "体重増加・倦怠感・徐脈",
            "symptoms": ["体重増加5kg", "著明な倦怠感", "皮膚乾燥", "便秘", "徐脈"],
            "vitals": "BP 105/65, HR 50, Temp 36.0",
            "history": "なし",
            "demographics": "45歳女性",
        },
        gold_primary_disease="甲状腺機能低下症",
        gold_urgency="routine",
        gold_icd10_prefix="E03",
        gold_red_flags=["心嚢水", "粘液水腫"],
        difficulty="medium",
    ),
    BenchmarkCase(
        id="M016",
        case={
            "chief_complaint": "高カルシウム血症・骨痛",
            "symptoms": ["骨痛", "嘔気", "多飲多尿", "意識障害", "腹痛"],
            "vitals": "BP 130/85, HR 90",
            "history": "なし",
            "demographics": "65歳女性",
        },
        gold_primary_disease="高カルシウム血症",
        gold_urgency="urgent",
        gold_icd10_prefix="E83",
        gold_red_flags=["Ca補正", "ECG変化"],
        difficulty="medium",
    ),
    BenchmarkCase(
        id="M017",
        case={
            "chief_complaint": "腹痛・低血圧・電解質異常",
            "symptoms": ["腹痛", "著明な倦怠感", "低血圧", "低ナトリウム・高カリウム"],
            "vitals": "BP 80/50, HR 112, Temp 37.5",
            "history": "長期副腎皮質ステロイド中断",
            "demographics": "40歳女性",
        },
        gold_primary_disease="副腎クリーゼ",
        gold_urgency="immediate",
        gold_icd10_prefix="E27",
        gold_red_flags=["副腎クリーゼ", "ハイドロコルチゾン"],
        difficulty="medium",
    ),
    BenchmarkCase(
        id="M018",
        case={
            "chief_complaint": "視力低下・複視",
            "symptoms": ["片眼の視力低下（数日で改善）", "再発する神経症状", "疲労感"],
            "vitals": "BP 120/75, HR 78",
            "history": "過去に感覚障害エピソード",
            "demographics": "32歳女性",
        },
        gold_primary_disease="多発性硬化症",
        gold_urgency="urgent",
        gold_icd10_prefix="G35",
        gold_red_flags=["視神経炎", "MRI"],
        difficulty="medium",
    ),
    BenchmarkCase(
        id="M019",
        case={
            "chief_complaint": "関節炎・発疹・尿所見異常",
            "symptoms": ["多発関節炎", "蝶形発疹", "タンパク尿", "補体低下"],
            "vitals": "BP 145/90, HR 88, Temp 38.2",
            "history": "なし",
            "demographics": "28歳女性",
        },
        gold_primary_disease="全身性エリテマトーデス",
        gold_urgency="urgent",
        gold_icd10_prefix="M32",
        gold_red_flags=["腎クリーゼ", "ループス腎炎"],
        difficulty="medium",
    ),
    BenchmarkCase(
        id="M020",
        case={
            "chief_complaint": "腹痛・高血圧・血尿",
            "symptoms": ["側腹部痛", "肉眼的血尿", "両側腎腫大"],
            "vitals": "BP 165/100, HR 82",
            "history": "家族に腎疾患",
            "demographics": "42歳男性",
        },
        gold_primary_disease="多発性嚢胞腎",
        gold_urgency="urgent",
        gold_icd10_prefix="Q61",
        gold_red_flags=["腎不全", "くも膜下出血リスク"],
        difficulty="medium",
    ),

    # ================================================================
    # HARD (10): rare diseases, pediatric, elderly multimorbidity
    # ================================================================

    BenchmarkCase(
        id="H001",
        case={
            "chief_complaint": "雷鳴頭痛・嘔吐",
            "symptoms": ["突然の最悪の頭痛（thunderclap）", "嘔吐", "頸部硬直なし"],
            "vitals": "BP 175/105, HR 88",
            "history": "OCP内服・偏頭痛",
            "demographics": "35歳女性",
        },
        gold_primary_disease="くも膜下出血",
        gold_urgency="immediate",
        gold_icd10_prefix="I60",
        gold_red_flags=["CT陰性でもLP必須", "SAH否定"],
        difficulty="hard",
    ),
    BenchmarkCase(
        id="H002",
        case={
            "chief_complaint": "発熱・皮膚変化（小児）",
            "symptoms": ["発熱5日以上", "結膜充血", "口唇発赤・亀裂", "頸部リンパ節腫脹", "手掌・足底発赤"],
            "vitals": "BP 100/65, HR 128, Temp 39.5",
            "history": "なし",
            "demographics": "3歳男児",
        },
        gold_primary_disease="川崎病",
        gold_urgency="urgent",
        gold_icd10_prefix="M30",
        gold_red_flags=["冠動脈瘤", "アスピリン・IVIG"],
        difficulty="hard",
    ),
    BenchmarkCase(
        id="H003",
        case={
            "chief_complaint": "急激な腰背部痛（高齢）",
            "symptoms": ["突然の腰背部痛", "下肢麻痺", "尿閉", "血圧低下"],
            "vitals": "BP 85/50, HR 118",
            "history": "高血圧・動脈硬化・腹部大動脈瘤",
            "demographics": "82歳男性",
        },
        gold_primary_disease="大動脈瘤破裂",
        gold_urgency="immediate",
        gold_icd10_prefix="I71",
        gold_red_flags=["出血性ショック", "外科緊急手術"],
        difficulty="hard",
    ),
    BenchmarkCase(
        id="H004",
        case={
            "chief_complaint": "感染症後の呼吸困難（ICU）",
            "symptoms": ["急速進行性呼吸不全", "両肺浸潤影", "低酸素血症", "非心原性肺水腫"],
            "vitals": "BP 110/70, HR 115, SpO2 82%, RR 35",
            "history": "敗血症から3日後",
            "demographics": "55歳男性",
        },
        gold_primary_disease="急性呼吸窮迫症候群",
        gold_urgency="immediate",
        gold_icd10_prefix="J80",
        gold_red_flags=["挿管", "人工呼吸器管理"],
        difficulty="hard",
    ),
    BenchmarkCase(
        id="H005",
        case={
            "chief_complaint": "四肢麻痺・呼吸困難（急速進行）",
            "symptoms": ["急速進行する四肢麻痺", "呼吸困難", "嚥下障害", "複視"],
            "vitals": "BP 130/80, HR 90, SpO2 92%",
            "history": "缶詰食品摂取",
            "demographics": "45歳男性",
        },
        gold_primary_disease="ボツリヌス症",
        gold_urgency="immediate",
        gold_icd10_prefix="A05",
        gold_red_flags=["呼吸筋麻痺", "抗毒素投与"],
        difficulty="hard",
    ),
    BenchmarkCase(
        id="H006",
        case={
            "chief_complaint": "出血傾向・多臓器不全",
            "symptoms": ["全身出血傾向", "血小板減少", "DIC所見", "腎機能障害"],
            "vitals": "BP 80/50, HR 138, Temp 39.2",
            "history": "産後2日",
            "demographics": "30歳女性",
        },
        gold_primary_disease="播種性血管内凝固",
        gold_urgency="immediate",
        gold_icd10_prefix="D65",
        gold_red_flags=["DIC", "FFP輸血", "産科緊急"],
        difficulty="hard",
    ),
    BenchmarkCase(
        id="H007",
        case={
            "chief_complaint": "高アンモニア血症・意識障害",
            "symptoms": ["意識障害", "羽ばたき振戦", "黄疸", "腹水"],
            "vitals": "BP 105/65, HR 98, Temp 37.5",
            "history": "アルコール性肝硬変",
            "demographics": "58歳男性",
        },
        gold_primary_disease="肝性脳症",
        gold_urgency="immediate",
        gold_icd10_prefix="K72",
        gold_red_flags=["肝不全", "ラクツロース"],
        difficulty="hard",
    ),
    BenchmarkCase(
        id="H008",
        case={
            "chief_complaint": "高熱・筋硬直・意識障害",
            "symptoms": ["高熱41℃", "筋強剛", "意識障害", "自律神経不安定"],
            "vitals": "BP 160/100, HR 135, Temp 41.0",
            "history": "抗精神病薬開始直後",
            "demographics": "35歳男性",
        },
        gold_primary_disease="悪性症候群",
        gold_urgency="immediate",
        gold_icd10_prefix="G21",
        gold_red_flags=["薬剤中止", "ダントロレン"],
        difficulty="hard",
    ),
    BenchmarkCase(
        id="H009",
        case={
            "chief_complaint": "不明熱・全身衰弱（高齢）",
            "symptoms": ["38.5℃の発熱3週間", "体重減少10kg", "夜間発汗", "リンパ節腫脹"],
            "vitals": "BP 110/70, HR 95, Temp 38.5",
            "history": "なし",
            "demographics": "75歳女性",
        },
        gold_primary_disease="悪性リンパ腫",
        gold_urgency="urgent",
        gold_icd10_prefix="C83",
        gold_red_flags=["腫瘍崩壊症候群", "生検"],
        difficulty="hard",
    ),
    BenchmarkCase(
        id="H010",
        case={
            "chief_complaint": "突然の視力消失・頭痛",
            "symptoms": ["突然片眼の視力消失", "眼痛", "眼圧上昇", "角膜浮腫"],
            "vitals": "BP 140/88, HR 78",
            "history": "遠視",
            "demographics": "65歳女性",
        },
        gold_primary_disease="急性緑内障発作",
        gold_urgency="immediate",
        gold_icd10_prefix="H40",
        gold_red_flags=["眼圧緊急降下", "眼科緊急コール"],
        difficulty="hard",
    ),
]


# ================================================================== #
# Scoring helpers
# ================================================================== #

def word_overlap(pred: str, gold: str) -> float:
    pred_w = set(pred.lower().split())
    gold_w = set(gold.lower().split())
    if not gold_w:
        return 0.0
    return len(pred_w & gold_w) / len(gold_w)


def char_overlap(pred: str, gold: str, min_len: int = 2) -> float:
    """Fuzzy match using character n-gram overlap."""
    if not gold or not pred:
        return 0.0
    pred_l, gold_l = pred.lower(), gold.lower()
    matched = sum(1 for ch in gold_l if ch in pred_l) / len(gold_l)
    return matched


def primary_accuracy(pred_disease: str, gold_disease: str) -> float:
    # 完全一致
    if pred_disease == gold_disease:
        return 1.0
    # 一方が他方を含む (例: "急性冠症候群" ⊂ "急性冠症候群（非典型）")
    if gold_disease in pred_disease or pred_disease in gold_disease:
        return 1.0
    # 主要語の一致 (括弧前の部分で比較)
    def strip_paren(s):
        return s.split("（")[0].split("(")[0].strip()
    if strip_paren(pred_disease) == strip_paren(gold_disease):
        return 1.0
    wo = word_overlap(pred_disease, gold_disease)
    if wo >= 0.6:
        return 1.0
    # 文字レベルのオーバーラップ (日本語対応)
    if char_overlap(pred_disease, gold_disease) >= 0.5:
        return 1.0
    return 0.0


def icd10_prefix_accuracy(pred_icd: str, gold_prefix: str) -> float:
    if not pred_icd or not gold_prefix:
        return 0.0
    return 1.0 if pred_icd.upper().startswith(gold_prefix.upper()) else 0.0


def urgency_accuracy(pred_urgency: str, gold_urgency: str) -> float:
    return 1.0 if pred_urgency == gold_urgency else 0.0


def red_flag_recall(pred_flags: list[str], gold_flags: list[str]) -> float:
    if not gold_flags:
        return 1.0
    pred_text = " ".join(pred_flags).lower()
    hit = sum(1 for gf in gold_flags
              if any(kw in pred_text for kw in gf.lower().split()))
    return hit / len(gold_flags)


def differential_coverage(differentials: list[dict], gold_primary: str) -> float:
    """Is the gold primary in the top-3 differentials?"""
    for d in differentials[:3]:
        if primary_accuracy(d.get("disease", ""), gold_primary):
            return 1.0
    return 0.0


# ================================================================== #
# Run Benchmark
# ================================================================== #

def run_benchmark() -> dict:
    results_by_case = []
    error_log: list[str] = []

    for bc in BENCHMARK_CASES:
        try:
            result = diagnose(bc.case, retrieved_docs=[])
        except Exception as e:
            error_log.append(f"{bc.id}: {e}")
            results_by_case.append({
                "id": bc.id,
                "difficulty": bc.difficulty,
                "primary_acc": 0.0,
                "icd3_acc":    0.0,
                "urgency_acc": 0.0,
                "rf_recall":   0.0,
                "diff_cov":    0.0,
                "error":       str(e),
            })
            continue

        pred_primary  = result.primary.get("disease", "")
        pred_urgency  = result.urgency or ""
        pred_icd10    = result.icd10.get("code", "") if result.icd10 else ""
        pred_flags    = result.red_flags or []
        pred_diffs    = result.differentials or []

        p_acc   = primary_accuracy(pred_primary, bc.gold_primary_disease)
        i_acc   = icd10_prefix_accuracy(pred_icd10, bc.gold_icd10_prefix)
        u_acc   = urgency_accuracy(pred_urgency, bc.gold_urgency)
        rf_rec  = red_flag_recall(pred_flags, bc.gold_red_flags)
        d_cov   = differential_coverage(pred_diffs, bc.gold_primary_disease)

        results_by_case.append({
            "id":          bc.id,
            "difficulty":  bc.difficulty,
            "gold":        bc.gold_primary_disease,
            "pred":        pred_primary,
            "pred_icd":    pred_icd10,
            "gold_icd":    bc.gold_icd10_prefix,
            "gold_urgency": bc.gold_urgency,
            "pred_urgency": pred_urgency,
            "primary_acc": p_acc,
            "icd3_acc":    i_acc,
            "urgency_acc": u_acc,
            "rf_recall":   rf_rec,
            "diff_cov":    d_cov,
            "error":       None,
        })

    return {"cases": results_by_case, "errors": error_log}


# ================================================================== #
# Report generation
# ================================================================== #

def generate_report(raw: dict) -> str:
    cases = raw["cases"]
    diffs = {"easy": [], "medium": [], "hard": []}
    for c in cases:
        diffs[c["difficulty"]].append(c)

    def _avg(lst, key):
        vals = [x[key] for x in lst]
        return sum(vals) / max(len(vals), 1)

    lines = []
    lines.append("=== DD System Benchmark v2.0 ===")
    lines.append(f"Total cases: {len(cases)} (Easy:{len(diffs['easy'])}, "
                 f"Medium:{len(diffs['medium'])}, Hard:{len(diffs['hard'])})")
    lines.append("")

    overall = cases
    lines.append("Accuracy by difficulty:")
    for diff in ["easy", "medium", "hard"]:
        g = diffs[diff]
        if not g:
            continue
        p = _avg(g, "primary_acc")
        u = _avg(g, "urgency_acc")
        i = _avg(g, "icd3_acc")
        r = _avg(g, "rf_recall")
        d = _avg(g, "diff_cov")
        lines.append(f"  {diff.capitalize():<8}: primary={p:.0%} / urgency={u:.0%} / "
                     f"ICD3={i:.0%} / rf_recall={r:.0%} / diff_cov={d:.0%}")

    p = _avg(overall, "primary_acc")
    u = _avg(overall, "urgency_acc")
    i = _avg(overall, "icd3_acc")
    r = _avg(overall, "rf_recall")
    d = _avg(overall, "diff_cov")
    lines.append(f"\nOverall: primary={p:.0%} / urgency={u:.0%} / ICD3={i:.0%} / "
                 f"rf_recall={r:.0%} / diff_cov={d:.0%}")

    # Top errors (cases where primary_acc == 0)
    errors = [c for c in cases if c["primary_acc"] == 0.0 and not c.get("error")]
    lines.append(f"\nTop prediction errors ({min(len(errors), 10)} of {len(errors)} failed cases):")
    error_counts: dict[str, int] = {}
    for c in errors:
        key = f"{c['gold']} → predicted as '{c['pred']}'"
        error_counts[key] = error_counts.get(key, 0) + 1
    for rank, (err, cnt) in enumerate(
        sorted(error_counts.items(), key=lambda x: -x[1])[:10], 1
    ):
        lines.append(f"  {rank}. {err} ({cnt} case{'s' if cnt > 1 else ''})")

    if raw["errors"]:
        lines.append(f"\nExceptions ({len(raw['errors'])}):")
        for e in raw["errors"][:5]:
            lines.append(f"  - {e}")

    lines.append(f"\nGenerated: benchmark_results.json")
    return "\n".join(lines)


# ================================================================== #
# __main__
# ================================================================== #

if __name__ == "__main__":
    base_dir = os.path.dirname(os.path.abspath(__file__))

    print("Running DD System Benchmark (50 cases)...\n")
    raw = run_benchmark()

    # Save JSON
    results_path = os.path.join(base_dir, "benchmark_results.json")
    with open(results_path, "w", encoding="utf-8") as f:
        json.dump(raw, f, ensure_ascii=False, indent=2)
    print(f"Results saved → {results_path}")

    # Generate and save report
    report = generate_report(raw)
    print("\n" + report)

    report_path = os.path.join(base_dir, "benchmark_report.txt")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"\nReport saved → {report_path}")
