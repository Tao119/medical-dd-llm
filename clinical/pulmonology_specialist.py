from dataclasses import dataclass


@dataclass
class SpirometryResult:
    pattern: str          # obstructive/restrictive/mixed/normal
    severity: str         # mild/moderate/severe/very severe
    gold_stage: str       # GOLD 1-4 (COPD only)
    interpretation: str


def interpret_spirometry(fev1_pct: float, fvc_pct: float, fev1_fvc: float) -> SpirometryResult:
    if fev1_fvc < 0.7:
        pattern = "obstructive"
        if fev1_pct >= 80:
            severity, gold = "mild", "GOLD 1"
        elif fev1_pct >= 50:
            severity, gold = "moderate", "GOLD 2"
        elif fev1_pct >= 30:
            severity, gold = "severe", "GOLD 3"
        else:
            severity, gold = "very severe", "GOLD 4"
        interp = f"閉塞性換気障害（{severity}）: FEV1/FVC={fev1_fvc:.2f}<0.7, FEV1={fev1_pct}% pred"
    elif fvc_pct < 80 and fev1_fvc >= 0.7:
        pattern = "restrictive"
        severity = "mild" if fvc_pct >= 60 else ("moderate" if fvc_pct >= 50 else "severe")
        gold = "N/A"
        interp = f"拘束性換気障害（{severity}）: FVC={fvc_pct}% pred, FEV1/FVC正常"
    elif fvc_pct < 80 and fev1_fvc < 0.7:
        pattern = "mixed"
        severity = "moderate"
        gold = "N/A"
        interp = f"混合性換気障害: FEV1/FVC={fev1_fvc:.2f}, FVC={fvc_pct}%"
    else:
        pattern = "normal"
        severity = "normal"
        gold = "N/A"
        interp = "正常スパイロメトリー"

    return SpirometryResult(pattern=pattern, severity=severity, gold_stage=gold, interpretation=interp)


def assess_asthma(symptoms_freq: str, nocturnal: bool, fev1_pct: float,
                  exacerbations_per_year: int = 0) -> dict:
    if symptoms_freq == "continuous" or exacerbations_per_year >= 2:
        severity = "重症持続型"
        gina_step = 5
        meds = ["高用量ICS+LABA", "抗コリン薬(チオトロピウム)", "生物学的製剤検討(抗IL-5/抗IgE)"]
    elif symptoms_freq == "daily" or (nocturnal and fev1_pct < 60):
        severity = "中等症持続型"
        gina_step = 4
        meds = ["中~高用量ICS+LABA", "LTRA追加"]
    elif symptoms_freq in ("weekly", "daily") or nocturnal:
        severity = "軽症持続型"
        gina_step = 3
        meds = ["低~中用量ICS+LABA", "または中用量ICS単独"]
    else:
        severity = "間欠型"
        gina_step = 1 if fev1_pct >= 80 else 2
        meds = ["SABA(発作時のみ)", "低用量ICS(Step2)"]

    return {"severity": severity, "gina_step": gina_step, "medications": meds,
            "controller": "必要" if gina_step >= 2 else "不要",
            "rescue": "SABA(サルブタモール) MDI"}


def calc_gold_copd(fev1_pct: float, cat_score: int, mmrc: int, exacerbations: int) -> dict:
    if fev1_pct >= 80:
        gold_grade = 1
    elif fev1_pct >= 50:
        gold_grade = 2
    elif fev1_pct >= 30:
        gold_grade = 3
    else:
        gold_grade = 4

    high_exacerbation = exacerbations >= 2 or (exacerbations >= 1 and "入院" in str(exacerbations))
    high_symptom = cat_score >= 10 or mmrc >= 2

    if high_exacerbation:
        group = "E"
        meds = ["LABA+LAMA", "ICS追加(血中好酸球≥300)"]
    elif high_symptom:
        group = "B"
        meds = ["LABA+LAMA", "肺リハビリ"]
    else:
        group = "A"
        meds = ["気管支拡張薬(SABA/LABA/LAMA)"]

    return {"gold_grade": gold_grade, "group": group, "medications": meds,
            "oxygen_therapy": "適応あり" if fev1_pct < 30 else "評価が必要",
            "pulmonary_rehab": "推奨" if mmrc >= 2 else "検討"}


def oxygen_therapy(spo2: float, rr: float, co2_retention_risk: bool) -> dict:
    if spo2 >= 95:
        return {"required": False, "target_spo2": "自然", "device": "不要", "flow": "不要"}

    if co2_retention_risk:
        target = "88-92%"
        if spo2 < 88:
            device = "ベンチュリマスク(FiO2 0.24-0.28)"
            flow = "2-4L/分"
        else:
            device = "低流量鼻カニューラ"
            flow = "0.5-1L/分"
    else:
        target = "≥94%"
        if spo2 < 90:
            device = "高流量酸素マスク/リザーバーマスク"
            flow = "10-15L/分"
        elif spo2 < 94:
            device = "鼻カニューラ"
            flow = "2-4L/分"
        else:
            device = "鼻カニューラ"
            flow = "1-2L/分"

    return {"required": True, "target_spo2": target, "device": device, "flow": flow,
            "warning": "CO2蓄積リスク: 目標SpO2 88-92%厳守" if co2_retention_risk else ""}


def calc_pe_probability(hr: int, dvt_signs: bool, pe_more_likely: bool,
                        immobilization: bool, prior_dvt_pe: bool,
                        hemoptysis: bool, cancer: bool,
                        spo2: float = 96, age: int = 50) -> dict:
    # Wells score
    w = 0
    if dvt_signs: w += 3
    if pe_more_likely: w += 3
    if hr > 100: w += 1.5
    if immobilization: w += 1.5
    if prior_dvt_pe: w += 1.5
    if hemoptysis: w += 1
    if cancer: w += 1
    if w > 6:
        wells_prob = "high"
    elif w > 2:
        wells_prob = "moderate"
    else:
        wells_prob = "low"

    # D-dimer threshold (age-adjusted)
    ddimer_threshold = max(500, age * 10)

    return {
        "wells_score": w, "wells_probability": wells_prob,
        "ddimer_threshold_ng_mL": ddimer_threshold,
        "next_step": "CTPA施行" if wells_prob in ("moderate","high") else f"D-dimer(<{ddimer_threshold}で除外)",
        "imaging_urgency": "緊急" if wells_prob == "high" else "準緊急"
    }


if __name__ == "__main__":
    print("=== スパイロメトリー ===")
    r = interpret_spirometry(fev1_pct=45, fvc_pct=85, fev1_fvc=0.55)
    print(f"  {r.interpretation}  GOLD: {r.gold_stage}")

    print("\n=== 喘息重症度 ===")
    a = assess_asthma("daily", nocturnal=True, fev1_pct=65, exacerbations_per_year=1)
    print(f"  {a['severity']}  GINA Step {a['gina_step']}  薬剤: {a['medications'][0]}")

    print("\n=== COPD (GOLD 2023) ===")
    c = calc_gold_copd(fev1_pct=45, cat_score=15, mmrc=3, exacerbations=2)
    print(f"  GOLD Grade {c['gold_grade']}  Group {c['group']}  {c['medications'][0]}")

    print("\n=== 酸素療法 ===")
    o = oxygen_therapy(spo2=88, rr=26, co2_retention_risk=True)
    print(f"  デバイス: {o['device']}  流量: {o['flow']}  目標: {o['target_spo2']}")
    if o['warning']:
        print(f"  ⚠ {o['warning']}")

    print("\n=== PE確率 (Wells) ===")
    p = calc_pe_probability(hr=112, dvt_signs=True, pe_more_likely=True,
                            immobilization=True, prior_dvt_pe=False,
                            hemoptysis=False, cancer=False, age=58)
    print(f"  Wells={p['wells_score']}  確率={p['wells_probability']}  次: {p['next_step']}")
