#!/usr/bin/env python3
"""
Medical DD-LLM 包括的デモスクリプト
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import json
from model.dd_engine import diagnose
from clinical.vitals import parse_vitals, assess_vitals
from clinical.risk_scores import calc_curb65, calc_qsofa
from clinical.lab_interpreter import interpret_labs
from clinical.cardiology_specialist import interpret_ecg, calc_cha2ds2vasc, classify_shock
from clinical.pulmonology_specialist import interpret_spirometry, calc_pe_probability
from clinical.neurology_specialist import check_tpa_eligibility
from clinical.icu_scoring import calc_news2, calc_sofa
from clinical.calculators import calc_egfr_ckdepi, calc_anion_gap, calc_alvarado
from clinical.drug_interactions import check_interactions
from viz.decision_tree import get_decision_tree

DEMO_CASES = [
    {
        "title": "症例1: 65歳男性 胸痛・冷汗（ACS）",
        "case": {
            "chief_complaint": "前胸部圧迫感・冷汗",
            "symptoms": ["前胸部圧迫感", "左肩放散痛", "冷汗", "呼吸困難"],
            "vitals": "BP 90/60, HR 112, SpO2 93%, RR 24",
            "history": "高血圧・糖尿病・喫煙歴20年",
            "demographics": "65歳男性",
        },
        "labs": "TnI 0.8, BNP 650, WBC 14000, CRP 3.5",
    },
    {
        "title": "症例2: 42歳女性 雷鳴頭痛（SAH）",
        "case": {
            "chief_complaint": "突然の最悪の頭痛",
            "symptoms": ["雷鳴頭痛", "嘔吐", "項部硬直"],
            "vitals": "BP 172/108, HR 88, SpO2 99%",
            "history": "なし",
            "demographics": "42歳女性",
        },
        "labs": "",
    },
    {
        "title": "症例3: 19歳男性 発熱・点状出血・ショック（髄膜炎）",
        "case": {
            "chief_complaint": "高熱・頸部硬直・意識障害",
            "symptoms": ["高熱39.8℃", "頸部硬直", "意識障害", "点状出血"],
            "vitals": "BP 85/50, HR 132, SpO2 95%, RR 28",
            "history": "大学生",
            "demographics": "19歳男性",
        },
        "labs": "WBC 28000, CRP 18.5, PCT 12",
    },
    {
        "title": "症例4: 22歳女性 クスマウル呼吸・1型DM（DKA）",
        "case": {
            "chief_complaint": "意識障害・クスマウル呼吸",
            "symptoms": ["クスマウル呼吸", "脱水", "嘔吐", "腹痛"],
            "vitals": "BP 100/70, HR 118, RR 30（深く速い）",
            "history": "1型糖尿病（インスリン中断）",
            "demographics": "22歳女性",
        },
        "labs": "血糖 520, ケトン体 3+, pH 7.20, BUN 28",
    },
    {
        "title": "症例5: 70歳男性 片麻痺・失語（急性脳梗塞）",
        "case": {
            "chief_complaint": "突然の右半身麻痺・失語",
            "symptoms": ["右半身麻痺", "失語", "顔面神経麻痺"],
            "vitals": "BP 192/115, HR 88, SpO2 97%",
            "history": "心房細動（抗凝固なし）",
            "demographics": "70歳男性",
        },
        "labs": "",
    },
]


def print_banner(title: str):
    print("\n" + "="*65)
    print(f"  {title}")
    print("="*65)


def print_diagnosis(result):
    p = result.primary
    icd = result.icd10 or {}
    print(f"\n【第一診断】{p['disease']}  確率: {p['probability']:.0%}")
    if icd.get('code'):
        print(f"  ICD-10: {icd['code']}")
    print(f"  根拠: {p.get('basis', '')}")

    if result.differentials:
        print("\n【鑑別診断】")
        for d in result.differentials[:3]:
            if d['disease'] != 'その他の疾患':
                print(f"  ・{d['disease']} ({d['probability']:.0%})")

    urgency_icon = {"immediate": "🔴", "urgent": "🟡", "routine": "🟢"}.get(result.urgency, "⚪")
    print(f"\n【緊急度】{urgency_icon} {result.urgency.upper()}")

    if result.vital_assessment:
        sev = result.vital_assessment.get('severity', 'unknown')
        flags = result.vital_assessment.get('flags', [])
        if flags:
            print(f"\n【バイタル評価】{sev}")
            for f in flags[:3]:
                print(f"  ⚠ {f['message'][:60]}")

    if result.risk_scores:
        print("\n【リスクスコア】")
        for name, score in result.risk_scores.items():
            print(f"  {name}: {score.get('score', '?')} → {score.get('interpretation', score.get('category', ''))[:40]}")

    if result.lab_flags:
        critical = [f for f in result.lab_flags if 'critical' in f['status']]
        if critical:
            print(f"\n【検査値 CRITICAL ({len(critical)}件)】")
            for f in critical[:3]:
                print(f"  [{f['name']}] {f['value']} {f['unit']} → {f['message'][:50]}")

    print("\n【Red Flags】")
    for rf in result.red_flags[:4]:
        print(f"  ! {rf}")

    print("\n【次の対応】")
    for ns in result.next_steps[:4]:
        print(f"  ✓ {ns}")


def run_specialist_demos():
    print_banner("専門科モジュール デモ")

    print("\n--- ECG 解析 ---")
    ecg = interpret_ecg("ST上昇 V1-V4, 新規LBBB, QTc 510ms")
    print(f"解釈: {ecg.interpretation}")
    print(f"緊急: {ecg.urgent_flags}")

    print("\n--- CHA2DS2-VASc ---")
    ch = calc_cha2ds2vasc(age=74, sex="男", chf=True, hypertension=True, diabetes=True)
    print(f"Score: {ch['score']} → 年間脳卒中リスク {ch['annual_stroke_risk_pct']}%  {ch['recommendation']}")

    print("\n--- ショック分類 ---")
    shock = classify_shock(sbp=82, hr=128,
                           symptoms=["敗血症", "感染源", "発熱"],
                           history=["尿路感染"])
    print(f"タイプ: {shock['type']}  対応: {shock['management'][0]}")

    print("\n--- PE確率 (Wells) ---")
    pe = calc_pe_probability(hr=115, dvt_signs=True, pe_more_likely=True,
                             immobilization=True, prior_dvt_pe=False,
                             hemoptysis=False, cancer=False)
    print(f"Wells={pe['wells_score']} → {pe['wells_probability']} → {pe['next_step']}")

    print("\n--- tPA適応チェック ---")
    tpa = check_tpa_eligibility(nihss=14, onset_hours=3.2, age=70,
                                bp_systolic=178, glucose=95, platelets=220000)
    print(f"tPA適応: {'YES' if tpa['eligible'] else 'NO'}  {tpa.get('dose_mgkg', '')}mg/kg")
    if tpa.get('exclusions_present'):
        print(f"除外: {tpa['exclusions_present']}")

    print("\n--- NEWS2スコア ---")
    news = calc_news2(rr=26, spo2=93, supplemental_o2=True,
                      sbp=92, hr=128, consciousness="V", temp=38.9)
    print(f"NEWS2={news.score} → {news.risk_category}  {news.recommendation}")

    print("\n--- 臨床計算機 ---")
    egfr = calc_egfr_ckdepi(creatinine=1.8, age=70, sex="M")
    print(f"eGFR: {egfr.value:.0f} {egfr.unit} → {egfr.category}")
    ag = calc_anion_gap(na=140, cl=102, hco3=14, albumin=3.8)
    print(f"Anion Gap: {ag.value:.1f} → {ag.interpretation}")
    alv = calc_alvarado(migrating_pain=True, anorexia=True, nausea_vomiting=True,
                        rb_tenderness=True, rebound_tenderness=True,
                        elevated_temp=True, leukocytosis=True, left_shift=False)
    print(f"Alvarado: {alv.value} → {alv.category}")


def run_drug_interaction_demo():
    print_banner("薬物相互作用チェック")
    drugs = ["ワルファリン", "アスピリン", "アミオダロン", "ジゴキシン", "シルデナフィル", "硝酸薬"]
    print(f"薬剤: {drugs}")
    interactions = check_interactions(drugs)
    severity_order = {"contraindicated": 0, "major": 1, "moderate": 2, "minor": 3}
    interactions.sort(key=lambda x: severity_order.get(x["severity"], 9))
    print(f"\n相互作用 ({len(interactions)}件):")
    for i in interactions[:4]:
        print(f"  [{i['severity'].upper()}] {i['drug1']} × {i['drug2']}")
        print(f"    → {i['clinical_effect'][:60]}")
        print(f"    管理: {i['management'][:60]}")


def run_decision_tree_demo():
    print_banner("臨床決定木 (胸痛トリアージ)")
    tree = get_decision_tree("chest_pain")
    print(tree[:800])


def main():
    print("\n" + "★"*35)
    print("  Medical DD-LLM v2.0 デモ")
    print(f"  疾患ルール: 118群 / RAG: 62チャンク")
    print("★"*35)

    # RAG インデックスロード
    indexer = None
    try:
        from rag.indexer import MedicalIndexer
        from config import EMBED_MODEL
        indexer = MedicalIndexer(EMBED_MODEL)
        indexer.load("data/index")
        print(f"\n[RAG] {len(indexer.chunks)} chunks loaded")
    except Exception as e:
        print(f"\n[RAG] 利用不可: {e}")

    # 症例診断デモ
    for demo in DEMO_CASES:
        print_banner(demo["title"])
        docs = []
        if indexer:
            q = demo["case"]["chief_complaint"] + " " + " ".join(demo["case"]["symptoms"][:3])
            docs = indexer.retrieve(q, top_k=2)
        result = diagnose(demo["case"], retrieved_docs=docs, labs_text=demo.get("labs", ""))
        print_diagnosis(result)

    # 専門科モジュールデモ
    run_specialist_demos()

    # 薬物相互作用デモ
    run_drug_interaction_demo()

    # 決定木デモ
    run_decision_tree_demo()

    print("\n\n" + "="*65)
    print("  デモ完了")
    print("  API: python3 -m uvicorn api.main:app --port 8765")
    print("  ベンチマーク: PYTHONPATH=. python3 eval/benchmark.py")
    print("="*65)


if __name__ == "__main__":
    main()
