import re
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ECGInterpretation:
    findings: list[str]
    urgent_flags: list[str]
    interpretation: str
    recommended_actions: list[str]


def interpret_ecg(ecg_text: str) -> ECGInterpretation:
    text = ecg_text.lower()
    findings, urgent, actions = [], [], []

    patterns = {
        r"st[上昇|elevation]|stemi|st elevation": ("STEMI疑い", True, ["循環器緊急コール", "12誘導心電図再確認", "緊急PCI準備"]),
        r"lbbb|左脚ブロック": ("左脚ブロック(LBBB)", True, ["新規LBBBはSTEMI同等として管理", "循環器コール"]),
        r"af|心房細動|atrial fibrillation": ("心房細動(AF)", False, ["レートコントロール", "抗凝固評価(CHA2DS2-VASc)"]),
        r"vt|心室頻拍|ventricular tachycardia": ("心室頻拍(VT)", True, ["除細動準備", "アミオダロン静注準備"]),
        r"qtc\s*[>≥]\s*(?:480|500)|qt延長": ("QTc延長", True, ["QT延長薬剤確認", "電解質補正(K/Mg)"]),
        r"avb|av\s*block|房室ブロック": ("房室ブロック", False, ["ペーシング評価"]),
        r"rbbb|右脚ブロック": ("右脚ブロック(RBBB)", False, []),
        r"st低下|st depression": ("ST低下(虚血疑い)", True, ["TnI採血", "循環器コール"]),
    }

    interpretation = "正常洞調律"
    for pattern, (finding, is_urgent, action) in patterns.items():
        if re.search(pattern, text):
            findings.append(finding)
            if is_urgent:
                urgent.append(finding)
                actions.extend(action)
            interpretation = finding

    if not findings:
        findings.append("有意な異常所見なし")

    return ECGInterpretation(findings=findings, urgent_flags=urgent,
                             interpretation=interpretation, recommended_actions=list(set(actions)))


@dataclass
class HeartFailureStage:
    aha_acc_stage: str   # A/B/C/D
    nyha_class: int      # 1-4
    ef_category: str     # HFrEF/HFmrEF/HFpEF
    medication_targets: list[str]
    device_therapy: list[str]


def assess_heart_failure(ef: float, symptoms: list[str], bnp: float = None,
                         history: list[str] = None) -> HeartFailureStage:
    history = history or []
    symptoms_text = " ".join(symptoms).lower()

    if ef < 40:
        ef_cat = "HFrEF"
    elif ef < 50:
        ef_cat = "HFmrEF"
    else:
        ef_cat = "HFpEF"

    if any(k in symptoms_text for k in ["安静時", "重度", "動けない", "夜間"]):
        nyha = 4 if "安静時" in symptoms_text else 3
    elif any(k in symptoms_text for k in ["軽度", "階段", "労作"]):
        nyha = 2
    elif "リスク因子" in symptoms_text or not symptoms:
        nyha = 1
    else:
        nyha = 2

    if "心筋梗塞" in " ".join(history) or "弁膜症" in " ".join(history):
        stage = "C" if nyha >= 2 else "B"
    elif any(k in " ".join(history) for k in ["高血圧", "糖尿病", "肥満"]):
        stage = "A"
    else:
        stage = "C" if nyha >= 2 else "B"
    if nyha == 4 and (bnp or 0) > 1000:
        stage = "D"

    meds = []
    if ef_cat == "HFrEF":
        meds = ["ARNI(サクビトリル/バルサルタン) or ACE阻害薬/ARB", "β遮断薬(カルベジロール/ビソプロロール)",
                "MRA(スピロノラクトン)", "SGLT2阻害薬(ダパグリフロジン)"]
    elif ef_cat == "HFpEF":
        meds = ["SGLT2阻害薬", "利尿薬(症状緩和)", "基礎疾患管理(高血圧/AF)"]
    else:
        meds = ["SGLT2阻害薬", "ACE阻害薬/ARB", "β遮断薬"]

    devices = []
    if ef_cat == "HFrEF" and ef <= 35:
        devices.append("ICD(一次予防)")
    if ef_cat == "HFrEF" and ef <= 35:
        devices.append("CRT(QRS>150ms/LBBB)")

    return HeartFailureStage(aha_acc_stage=stage, nyha_class=nyha, ef_category=ef_cat,
                             medication_targets=meds, device_therapy=devices)


def calc_cha2ds2vasc(age: int, sex: str, chf: bool = False, hypertension: bool = False,
                     stroke: bool = False, vascular: bool = False, diabetes: bool = False) -> dict:
    score = 0
    if chf: score += 1
    if hypertension: score += 1
    if age >= 75: score += 2
    elif age >= 65: score += 1
    if diabetes: score += 1
    if stroke: score += 2
    if vascular: score += 1
    if sex.lower() in ("女", "f", "female"): score += 1

    annual_stroke_risk = {0: 0.0, 1: 1.3, 2: 2.2, 3: 3.2, 4: 4.0, 5: 6.7, 6: 9.8, 7: 9.6, 8: 12.5, 9: 15.2}
    risk = annual_stroke_risk.get(min(score, 9), 15.2)

    if sex.lower() in ("男", "m", "male"):
        oac_recommended = score >= 2
    else:
        oac_recommended = score >= 3

    return {"score": score, "annual_stroke_risk_pct": risk,
            "oac_recommended": oac_recommended,
            "recommendation": "DOAC推奨（腎機能に応じて用量調整）" if oac_recommended else "抗凝固療法不要"}


def classify_shock(sbp: float, hr: float, symptoms: list[str], history: list[str] = None) -> dict:
    history = history or []
    text = " ".join(symptoms + history).lower()
    shock_index = hr / max(sbp, 1)

    if sbp > 90:
        return {"type": "なし", "shock_index": round(shock_index, 2), "management": ["バイタル継続モニタリング"]}

    if any(k in text for k in ["心筋梗塞", "心不全", "低心拍出", "肺水腫", "狭心症"]):
        shock_type = "心原性ショック"
        mgmt = ["ドパミン/ドブタミン", "IABP検討", "緊急PCIまたはECMO", "肺動脈カテーテル"]
    elif any(k in text for k in ["敗血症", "感染", "発熱", "WBC"]):
        shock_type = "分布異常性ショック（敗血症性）"
        mgmt = ["NS 30mL/kg輸液", "ノルアドレナリン(MAP≥65)", "広域抗菌薬", "血液培養"]
    elif any(k in text for k in ["出血", "外傷", "嘔吐", "下痢", "脱水"]):
        shock_type = "循環血液量減少性ショック"
        mgmt = ["大量輸液(NS/LR)", "輸血(出血性)", "出血源コントロール"]
    elif any(k in text for k in ["気胸", "心タンポナーデ", "肺塞栓"]):
        shock_type = "閉塞性ショック"
        mgmt = ["原因除去優先", "気胸→脱気", "PE→rtPA", "タンポナーデ→心嚢穿刺"]
    else:
        shock_type = "未分類ショック"
        mgmt = ["原因検索", "輸液試験的投与", "昇圧薬準備"]

    return {"type": shock_type, "shock_index": round(shock_index, 2),
            "management": mgmt, "urgency": "immediate"}


def tni_kinetics(tni_0h: float, tni_3h: float) -> dict:
    delta = tni_3h - tni_0h
    upper_limit_normal = 0.04

    if tni_0h > 5 * upper_limit_normal:
        result = "rule_in"
        interpretation = "TnI著明上昇 → AMI診断"
    elif tni_0h < upper_limit_normal and tni_3h < upper_limit_normal:
        result = "rule_out"
        interpretation = "両時点で正常範囲 → AMI除外"
    elif abs(delta) >= 0.019 or (delta / max(tni_0h, 0.001)) >= 0.2:
        result = "rule_in"
        interpretation = f"ΔTnI={delta:.3f} → 急速上昇 → AMI確定"
    else:
        result = "observe"
        interpretation = "判定保留 → 6h時点でTnI再測定"

    return {"tni_0h": tni_0h, "tni_3h": tni_3h, "delta": round(delta, 4),
            "result": result, "interpretation": interpretation,
            "next_action": "循環器コール+PCI準備" if result == "rule_in" else "経過観察"}


if __name__ == "__main__":
    print("=== ECG解析 ===")
    ecg = interpret_ecg("ST上昇 V1-V4, 新規LBBB, QTc 480ms")
    print(f"  解釈: {ecg.interpretation}")
    print(f"  緊急: {ecg.urgent_flags}")
    print(f"  対応: {ecg.recommended_actions[:3]}")

    print("\n=== 心不全ステージング ===")
    hf = assess_heart_failure(ef=32, symptoms=["労作時呼吸困難", "起座呼吸"], bnp=850,
                              history=["陳旧性心筋梗塞"])
    print(f"  Stage: {hf.aha_acc_stage}  NYHA: {hf.nyha_class}  EF分類: {hf.ef_category}")
    print(f"  薬物: {hf.medication_targets[:2]}")

    print("\n=== CHA2DS2-VASc ===")
    ch = calc_cha2ds2vasc(age=72, sex="男", chf=True, hypertension=True, diabetes=True)
    print(f"  score={ch['score']}  年間脳卒中リスク={ch['annual_stroke_risk_pct']}%")
    print(f"  {ch['recommendation']}")

    print("\n=== TnIキネティクス ===")
    tk = tni_kinetics(0.02, 0.08)
    print(f"  0h={tk['tni_0h']} 3h={tk['tni_3h']} Δ={tk['delta']} → {tk['result']}: {tk['interpretation']}")
