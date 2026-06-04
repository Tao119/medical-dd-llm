"""
Infectious Disease specialist clinical tools.

Includes:
  - Antibiotic selection guide (organism + site + severity + allergy)
  - Empirical antibiotic regimens for common syndromes
  - Antimicrobial stewardship tool (de-escalation guidance)
  - Travel medicine screening (vaccines + prophylaxis)
  - HIV risk assessment and PEP/PrEP guidance
"""

from dataclasses import dataclass, field
from typing import Optional


# ---------------------------------------------------------------------------
# Antibiotic Selection Guide
# ---------------------------------------------------------------------------

@dataclass
class AntibioticRecommendation:
    syndrome: str
    first_line: str
    dose_duration: str
    alternatives: list[str]
    allergy_substitution: Optional[str]
    mrsa_coverage: bool
    de_escalation_note: str


_ANTIBIOTIC_GUIDE: dict[tuple, AntibioticRecommendation] = {
    # (organism_hint, site, severity)
    ("streptococcus", "pharyngitis", "mild"): AntibioticRecommendation(
        syndrome="A群溶連菌性咽頭炎",
        first_line="アモキシシリン 500mg 1日3回",
        dose_duration="10日間",
        alternatives=["フェノキシメチルペニシリン 250mg 1日4回"],
        allergy_substitution="アジスロマイシン 500mg 1日1回 × 3日",
        mrsa_coverage=False,
        de_escalation_note="培養感受性でペニシリン感受性確認後は継続",
    ),
    ("e_coli", "uti", "mild"): AntibioticRecommendation(
        syndrome="単純性膀胱炎",
        first_line="フォスホマイシン 3g 単回投与",
        dose_duration="単回",
        alternatives=["ニトロフラントイン 100mg 1日2回", "ST合剤 1錠 1日2回"],
        allergy_substitution="セファレキシン 500mg 1日4回 × 7日",
        mrsa_coverage=False,
        de_escalation_note="尿培養結果で感受性確認後に最狭域抗菌薬へ変更",
    ),
    ("e_coli", "uti", "severe"): AntibioticRecommendation(
        syndrome="複雑性UTI/腎盂腎炎",
        first_line="セフトリアキソン 2g 静注 1日1回",
        dose_duration="7-14日(経口へのde-escalation可)",
        alternatives=["シプロフロキサシン 500mg 経口 1日2回(感受性確認後)"],
        allergy_substitution="アズトレオナム 2g 静注 8時間毎",
        mrsa_coverage=False,
        de_escalation_note="血液培養/尿培養72時間後に経口薬へ切り替え検討",
    ),
    ("staphylococcus", "skin", "mild"): AntibioticRecommendation(
        syndrome="皮膚軟部組織感染(MSSA想定)",
        first_line="セファレキシン 500mg 経口 1日4回",
        dose_duration="5-7日",
        alternatives=["クリンダマイシン 300mg 1日3回"],
        allergy_substitution="クリンダマイシン 300mg 1日3回 × 5-7日",
        mrsa_coverage=False,
        de_escalation_note="MRSA疑い(化膿・難治)はトリメトプリム/ST合剤へ切り替え",
    ),
    ("mrsa", "skin", "severe"): AntibioticRecommendation(
        syndrome="MRSA皮膚軟部組織感染(重症)",
        first_line="バンコマイシン 15-20mg/kg 静注 8-12時間毎",
        dose_duration="7-14日(AUC/MIC=400-600目標)",
        alternatives=["ダプトマイシン 4-6mg/kg 静注 1日1回"],
        allergy_substitution="ラインゾリド 600mg 静注/経口 1日2回",
        mrsa_coverage=True,
        de_escalation_note="培養でMSSAなら抗MSSA薬(ナフシリン/セファゾリン)へde-escalation",
    ),
    ("gram_negative", "bacteremia", "severe"): AntibioticRecommendation(
        syndrome="グラム陰性桿菌菌血症",
        first_line="セフェピム 2g 静注 8時間毎",
        dose_duration="7-14日",
        alternatives=["ピペラシリン/タゾバクタム 4.5g 静注 6時間毎", "メロペネム 1g 静注 8時間毎(重症/ESBL疑い)"],
        allergy_substitution="アズトレオナム 2g 静注 8時間毎 + メトロニダゾール(腹腔内感染)",
        mrsa_coverage=False,
        de_escalation_note="血液培養72h後に感受性確認: β-ラクタム感受性あれば最狭域へ",
    ),
}


def select_antibiotic(
    suspected_organism: str,
    infection_site: str,
    severity: str = "mild",
    penicillin_allergy: bool = False,
    mrsa_risk: bool = False,
) -> AntibioticRecommendation:
    """
    Return antibiotic recommendation based on organism, site, severity.
    Falls back to syndrome-based recommendation if exact match not found.
    """
    org = suspected_organism.lower().replace(" ", "_")
    site = infection_site.lower()
    sev = severity.lower()

    if mrsa_risk:
        org = "mrsa"

    key = (org, site, sev)
    if key in _ANTIBIOTIC_GUIDE:
        rec = _ANTIBIOTIC_GUIDE[key]
    else:
        # Fallback: site-severity match
        for k, v in _ANTIBIOTIC_GUIDE.items():
            if k[1] == site and k[2] == sev:
                rec = v
                break
        else:
            rec = _ANTIBIOTIC_GUIDE[("gram_negative", "bacteremia", "severe")]

    if penicillin_allergy and rec.allergy_substitution:
        note = f"ペニシリンアレルギーあり → {rec.allergy_substitution} を使用"
        return AntibioticRecommendation(
            syndrome=rec.syndrome,
            first_line=rec.allergy_substitution,
            dose_duration=rec.dose_duration,
            alternatives=rec.alternatives,
            allergy_substitution=None,
            mrsa_coverage=rec.mrsa_coverage,
            de_escalation_note=note + " | " + rec.de_escalation_note,
        )
    return rec


# ---------------------------------------------------------------------------
# Empirical Antibiotic Regimens for Common Syndromes
# ---------------------------------------------------------------------------

@dataclass
class EmpiricalRegimen:
    syndrome: str
    severity: str
    regimen: str
    dose: str
    duration: str
    mrsa_considerations: str
    de_escalation: str
    notes: str


_EMPIRICAL: dict[str, list[EmpiricalRegimen]] = {
    "cap": [
        EmpiricalRegimen("市中肺炎(CAP) — 軽症外来", "mild",
                         "アモキシシリン/クラブラン酸 875/125mg 経口 1日2回",
                         "アモキシシリン/クラブラン酸 875mg 1日2回",
                         "5日間(症状改善で終了可)",
                         "市中MRSAは稀: 非定型病原体カバーにマクロライド併用も検討",
                         "入院不要なら抗菌薬終了後外来フォロー",
                         "PSI/PORT ScoreまたはCURB-65で入院適応を評価"),
        EmpiricalRegimen("CAP — 中等症入院", "moderate",
                         "セフトリアキソン 2g 静注 1日1回 + アジスロマイシン 500mg 静注 1日1回",
                         "上記",
                         "5-7日",
                         "MRSA危険因子(最近の入院/MRSA既往)あればバンコマイシン追加",
                         "培養陰性かつ改善なら3-5日で評価、改善あれば経口切り替え",
                         "血液培養 × 2セット + 尿中抗原(肺炎球菌・レジオネラ)"),
        EmpiricalRegimen("CAP — 重症ICU", "severe",
                         "セフトリアキソン + アジスロマイシン + バンコマイシン(MRSA疑い時)",
                         "セフトリアキソン 2g, アジスロマイシン 500mg, バンコマイシン 25mg/kg",
                         "最小7日、臨床改善を確認",
                         "重症ICU CAP: バンコマイシン経験的追加を推奨",
                         "血液培養/痰培養/BAL培養結果で72h以内に見直し",
                         "PseudomonasリスクあればPIPCまたはセフェピムへ変更"),
    ],
    "hap_vap": [
        EmpiricalRegimen("院内肺炎/人工呼吸器関連肺炎(HAP/VAP)", "severe",
                         "ピペラシリン/タゾバクタム 4.5g 静注 6時間毎 + バンコマイシン",
                         "PIPC/TAZ 4.5g q6h + バンコマイシン AUC/MIC誘導",
                         "7日間(HAP); 8日間(VAP)",
                         "VAP MRSA: バンコマイシンまたはラインゾリド",
                         "培養72h後にde-escalation: グラム陰性のみ確認でMRSAカバー中止",
                         "多剤耐性リスクあればカルバペネムも考慮"),
    ],
    "uti": [
        EmpiricalRegimen("単純性膀胱炎", "mild",
                         "フォスホマイシン 3g 単回",
                         "3g 単回",
                         "1日",
                         "市中UTIはMRSAほぼ無関係",
                         "尿培養感受性確認後に第一選択薬継続確認",
                         "再発性の場合はイメージング検査"),
        EmpiricalRegimen("腎盂腎炎", "moderate",
                         "セフトリアキソン 1g 静注 1日1回",
                         "1g IV q24h → 経口セファレキシン 500mg q6h",
                         "7-14日",
                         "MRSA UTI: バンコマイシン(感受性確認時のみ使用)",
                         "血液培養/尿培養陰性かつ解熱後は経口切り替え",
                         "ESBL大腸菌リスクあればメロペネム"),
    ],
    "skin_soft_tissue": [
        EmpiricalRegimen("蜂窩織炎/丹毒(化膿なし)", "mild",
                         "セファレキシン 500mg 経口 q6h",
                         "500mg q6h",
                         "5-7日",
                         "化膿あり: ST合剤(MRSA)", "5日で評価",
                         "糖尿病患者は広域カバー検討"),
        EmpiricalRegimen("壊死性筋膜炎", "severe",
                         "バンコマイシン + ピペラシリン/タゾバクタム + クリンダマイシン",
                         "バンコマイシン 25mg/kg, PIPC/TAZ 4.5g q6h, クリンダマイシン 600mg q8h",
                         "外科的デブリードマン後に培養ガイド",
                         "MRSA: バンコマイシン必須",
                         "培養で原因菌確定後に最狭域へde-escalation",
                         "緊急外科コンサルト必須(デブリードマン)"),
    ],
    "intraabdominal": [
        EmpiricalRegimen("腹腔内感染(軽〜中等症)", "moderate",
                         "セフォキシチン 2g 静注 6時間毎 または アモキシシリン/クラブラン酸",
                         "セフォキシチン 2g q6h",
                         "4-7日",
                         "MRSA腹腔内感染は稀: 通常不要",
                         "ドレナージ培養結果で感受性確認後に変更",
                         "S.aureus腸腔外感染なら2週間"),
        EmpiricalRegimen("腹腔内感染(重症/術後)", "severe",
                         "メロペネム 1g 静注 8時間毎",
                         "1g q8h",
                         "7日以上",
                         "MRSA: メロペネム + バンコマイシン",
                         "血液培養/術中培養72h後に必ずde-escalation検討",
                         "免疫不全では真菌カバー(フルコナゾール)も検討"),
    ],
    "bacteremia": [
        EmpiricalRegimen("菌血症(市中原発不明)", "severe",
                         "バンコマイシン + セフトリアキソン 2g",
                         "バンコマイシン + セフトリアキソン 2g IV q24h",
                         "血液培養陽性日から14日以上(黄色ブドウ球菌は最短14日)",
                         "MRSA: バンコマイシン必須 AUC/MIC=400-600",
                         "血液培養72h後に原因菌感受性でde-escalation",
                         "感染源検索必須: 心エコー(IE除外), CT"),
    ],
    "meningitis": [
        EmpiricalRegimen("細菌性髄膜炎(成人)", "severe",
                         "セフトリアキソン 2g 静注 12時間毎 + アンピシリン 2g 8時間毎 + デキサメタゾン",
                         "セフトリアキソン 2g q12h + ABPC 2g q8h(リステリアカバー≥50歳/免疫低下)",
                         "10-14日(肺炎球菌); 21日(リステリア)",
                         "MRSA髄膜炎: バンコマイシン + リファンピシン",
                         "髄液培養陽性後に原因菌でde-escalation",
                         "デキサメタゾン 0.15mg/kg q6h × 4日は抗菌薬直前に投与"),
    ],
}


def empirical_antibiotic(
    syndrome: str,
    severity: str = "moderate",
) -> list[EmpiricalRegimen]:
    """
    Return empirical antibiotic regimen(s) for common infectious syndromes.
    syndrome: 'cap' | 'hap_vap' | 'uti' | 'skin_soft_tissue' | 'intraabdominal' | 'bacteremia' | 'meningitis'
    """
    syndrome_key = syndrome.lower().replace("-", "_").replace(" ", "_")
    regimens = _EMPIRICAL.get(syndrome_key, [])
    if not regimens:
        return [EmpiricalRegimen(
            syndrome=f"不明症候群: {syndrome}",
            severity=severity,
            regimen="専門家に相談してください",
            dose="N/A", duration="N/A",
            mrsa_considerations="感受性結果待ち",
            de_escalation="N/A", notes="ID専門医コンサルト推奨",
        )]

    sev = severity.lower()
    matched = [r for r in regimens if r.severity == sev]
    return matched if matched else regimens


# ---------------------------------------------------------------------------
# Antimicrobial Stewardship Tool
# ---------------------------------------------------------------------------

@dataclass
class StewardshipReview:
    current_day: int
    assessment: str
    de_escalation_possible: bool
    de_escalation_suggestion: Optional[str]
    duplicate_coverage: list[str]
    unnecessarily_broad: bool
    recommendation: str
    stop_signal: bool


def stewardship_review(
    antibiotic: str,
    started_days_ago: int,
    culture_results: Optional[str] = None,   # e.g. "E.coli sensitive to cipro"
    clinical_improvement: bool = True,
    other_antibiotics: Optional[list[str]] = None,
) -> StewardshipReview:
    """
    Antimicrobial stewardship: evaluate need for de-escalation or discontinuation.
    Reviews after ≥3 days on antibiotics.
    """
    other = [a.lower() for a in (other_antibiotics or [])]
    ab = antibiotic.lower()

    duplicates = []
    if "vancomycin" in ab or "バンコマイシン" in ab:
        if any("linezolid" in o or "ラインゾリド" in o or "daptomycin" in o for o in other):
            duplicates.append("バンコマイシン + ラインゾリド/ダプトマイシン: 重複グラム陽性カバー")
    if ("piperacillin" in ab or "pipc" in ab) and any("carba" in o or "meropenem" in o for o in other):
        duplicates.append("ピペラシリン + カルバペネム: 重複広域グラム陰性カバー")
    if ("metronidazole" in ab or "メトロ" in ab) and any("pipc" in o or "carba" in o for o in other):
        duplicates.append("メトロニダゾール + PIPC/TAZ or カルバペネム: 嫌気性菌二重カバー")

    broadly = any(k in ab for k in ["meropenem", "メロペネム", "imipenem", "ertapenem"])

    de_esc = None
    de_possible = False

    if culture_results:
        c = culture_results.lower()
        if "sensitive" in c or "susceptible" in c or "感受性" in c:
            de_possible = True
            if "cipro" in c or "ciprofloxacin" in c:
                de_esc = "シプロフロキサシン経口(感受性確認済)へde-escalation"
            elif "ampicillin" in c or "amoxicillin" in c:
                de_esc = "アモキシシリン/ペニシリン系へde-escalation"
            elif "ceftriaxone" in c or "cephalosporin" in c:
                de_esc = "セフトリアキソン/セファレキシン経口へde-escalation"
            else:
                de_esc = "感受性確認済の最狭域薬剤へde-escalation"
    elif started_days_ago >= 3 and clinical_improvement:
        de_possible = True
        de_esc = "臨床改善あり: 経口抗菌薬への切り替えを検討 (IV→PO switch)"

    stop_signal = started_days_ago >= 7 and clinical_improvement and not culture_results

    if started_days_ago < 3:
        assessment = f"開始{started_days_ago}日目: まだde-escalationの時期ではない"
        rec = "培養結果を待ち72時間後に再評価"
    elif de_possible and de_esc:
        assessment = f"開始{started_days_ago}日目: de-escalation推奨"
        rec = de_esc
    elif stop_signal:
        assessment = f"開始{started_days_ago}日目: 終了基準を評価"
        rec = "臨床改善済: 抗菌薬終了または経口薬への切り替えを検討"
    else:
        assessment = f"開始{started_days_ago}日目: 継続妥当"
        rec = "培養結果で感受性確認後に最狭域薬へde-escalation"

    return StewardshipReview(
        current_day=started_days_ago,
        assessment=assessment,
        de_escalation_possible=de_possible,
        de_escalation_suggestion=de_esc,
        duplicate_coverage=duplicates,
        unnecessarily_broad=broadly,
        recommendation=rec,
        stop_signal=stop_signal,
    )


# ---------------------------------------------------------------------------
# Travel Medicine Screening
# ---------------------------------------------------------------------------

@dataclass
class TravelMedicineAdvice:
    destination: str
    duration_days: int
    recommended_vaccines: list[str]
    prophylaxis: list[str]
    precautions: list[str]
    food_water_safety: list[str]
    post_travel_screening: list[str]


_VACCINE_MAP = {
    "sub_saharan_africa": ["A型肝炎", "腸チフス", "黄熱(必須/推奨)", "髄膜炎菌", "狂犬病(長期滞在/アウトドア)", "ポリオ"],
    "south_asia": ["A型肝炎", "腸チフス", "狂犬病(長期滞在)", "日本脳炎(一部地域)", "髄膜炎菌"],
    "southeast_asia": ["A型肝炎", "腸チフス", "日本脳炎", "狂犬病(長期滞在/アウトドア)"],
    "east_asia": ["A型肝炎", "日本脳炎(農村部)", "腸チフス(一部地域)"],
    "latin_america": ["A型肝炎", "腸チフス", "黄熱(アマゾン地域)", "狂犬病(アウトドア)"],
    "middle_east": ["A型肝炎", "腸チフス", "髄膜炎菌(ハッジ参加者は必須)"],
    "europe": ["A型肝炎(東欧)", "TBE(中央ヨーロッパ森林地帯)"],
    "north_america": ["一般的な旅行では追加接種不要"],
    "oceania": ["一般的な旅行では追加接種不要"],
}

_MALARIA_MAP = {
    "sub_saharan_africa": "アトバコン/プログアニル(マラロン) 1日1回または ドキシサイクリン 100mg 1日1回",
    "south_asia": "アトバコン/プログアニル または クロロキン(感受性地域のみ)",
    "southeast_asia": "アトバコン/プログアニル (メフロキン耐性地域あり)",
    "latin_america": "アトバコン/プログアニル または クロロキン(感受性確認)",
}


def travel_medicine_screening(
    destination: str,
    duration_days: int,
    activities: Optional[list[str]] = None,
) -> TravelMedicineAdvice:
    """
    Travel medicine recommendation: vaccines, prophylaxis, precautions.
    destination: region key (sub_saharan_africa, south_asia, southeast_asia, etc.)
    """
    acts = set(a.lower() for a in (activities or []))
    dest_key = destination.lower().replace(" ", "_").replace("-", "_")

    vaccines = _VACCINE_MAP.get(dest_key, ["A型肝炎", "腸チフス(不明地域)"])
    # Always ensure Hep B is checked
    vaccines_final = vaccines + ["B型肝炎(未接種の場合)"]

    prophylaxis = []
    malaria_rx = _MALARIA_MAP.get(dest_key)
    if malaria_rx:
        prophylaxis.append(f"マラリア予防: {malaria_rx} (出発1-2日前〜帰国1週間後まで)")
    if duration_days > 30:
        prophylaxis.append("旅行者下痢症予防: アジスロマイシン携帯(自己治療用)")

    precautions = [
        "飲料水は市販ペットボトルまたは煮沸水のみ",
        "氷・生野菜・屋台の食事に注意",
        "虫除けスプレー(DEET 20-50%)使用",
        "長袖・長ズボン着用(日没後特に重要)",
        "海外旅行保険加入",
    ]

    if "scuba_diving" in acts or "diving" in acts:
        precautions.append("スキューバダイビング: 近くに減圧症治療施設を確認")
    if "hiking" in acts or "trekking" in acts:
        precautions.append("高度病対策: アセタゾラミド 250mg 1日2回(3000m以上)")
        precautions.append("ダニ対策: TBE/ライム病リスク地域では定期的なチェック")
    if "animals" in acts or "wildlife" in acts:
        precautions.append("動物接触後は速やかに創部洗浄, 狂犬病ワクチン未接種なら24h以内にPEP")

    food_water = [
        "Boil it, Cook it, Peel it, or Forget it",
        "生水・氷・サラダは避ける",
        "果物は自分で皮を剥く",
        "加熱された食品を温かいうちに食べる",
    ]

    post_travel = ["発熱(2週間以内): マラリア除外最優先", "下痢(>2週間持続): 寄生虫/腸チフス検査",
                   "皮膚病変: ツツガムシ病/皮膚リーシュマニア",
                   "長期滞在(>3ヶ月): 帰国後スクリーニング(TB/血液寄生虫/性感染症)"]

    return TravelMedicineAdvice(
        destination=destination,
        duration_days=duration_days,
        recommended_vaccines=vaccines_final,
        prophylaxis=prophylaxis,
        precautions=precautions,
        food_water_safety=food_water,
        post_travel_screening=post_travel,
    )


# ---------------------------------------------------------------------------
# HIV Risk Assessment + PEP/PrEP
# ---------------------------------------------------------------------------

@dataclass
class HIVRiskAssessment:
    exposure_type: str
    hours_since_exposure: Optional[int]
    pep_eligible: bool
    pep_regimen: Optional[str]
    pep_deadline_hours: int          # 72h window
    prep_indicated: bool
    prep_regimen: Optional[str]
    baseline_tests: list[str]
    counseling_points: list[str]
    risk_per_act_pct: float


_EXPOSURE_RISK = {
    "receptive_anal_intercourse": 1.4,       # per act %
    "insertive_anal_intercourse": 0.11,
    "receptive_vaginal_intercourse": 0.08,
    "insertive_vaginal_intercourse": 0.04,
    "needle_sharing_iv_drug": 0.63,
    "needlestick_healthcare": 0.23,
    "oral_sex": 0.01,
    "blood_transfusion_hiv": 92.5,
}


def assess_hiv_risk(
    exposure_type: str,        # key from _EXPOSURE_RISK or describe
    source_hiv_status: str,    # "positive" | "unknown" | "negative"
    hours_since_exposure: Optional[int] = None,
    ongoing_risk: bool = False,  # for PrEP evaluation
    source_on_arvs_undetectable: bool = False,
) -> HIVRiskAssessment:
    """
    HIV exposure risk assessment with PEP eligibility and PrEP guidance.
    PEP window: ≤72 hours since exposure.
    """
    exp_key = exposure_type.lower().replace(" ", "_")
    risk_pct = _EXPOSURE_RISK.get(exp_key, 0.1)

    # U=U: Undetectable = Untransmittable
    if source_on_arvs_undetectable and source_hiv_status == "positive":
        risk_pct = 0.0
        pep_eligible = False
        pep_regimen = None
        counseling = ["源患者がART管理下で検出不能(U=U): HIV感染リスクは実質ゼロ",
                      "性感染症(STI)リスクは依然存在するため定期検査を継続"]
    elif source_hiv_status == "negative":
        risk_pct = 0.0
        pep_eligible = False
        pep_regimen = None
        counseling = ["源が陰性ならPEPは不要", "ただしウィンドウ期間内であれば再確認を"]
    else:
        within_72h = hours_since_exposure is not None and hours_since_exposure <= 72
        pep_eligible = within_72h and source_hiv_status in ("positive", "unknown") and risk_pct > 0.01
        pep_regimen = "テノホビル/エムトリシタビン(TDF/FTC) + ドルテグラビル 50mg 1日1回 × 28日" if pep_eligible else None
        counseling = []
        if hours_since_exposure is not None:
            if hours_since_exposure > 72:
                counseling.append(f"曝露後{hours_since_exposure}時間経過: PEP有効期間(72時間)を超過")
            elif hours_since_exposure > 48:
                counseling.append(f"曝露後{hours_since_exposure}時間: PEP開始は遅れるほど効果低下 — 直ちに開始")
            else:
                counseling.append(f"曝露後{hours_since_exposure}時間: PEP有効範囲内")
        counseling += [
            "PEP開始後28日間服薬厳守(中断は耐性リスク)",
            "PEP終了後4〜6週間後にHIV検査(4th世代検査)",
            "性感染症(梅毒/淋菌/クラミジア)同時スクリーニング",
        ]

    prep_indicated = ongoing_risk and source_hiv_status != "negative"
    prep_regimen = "テノホビル/エムトリシタビン(TDF/FTC) 1錠 1日1回(毎日PrEP)" if prep_indicated else None
    if prep_indicated:
        counseling.append("PrEP適応: 腎機能(Cr/eGFR)・B型肝炎検査後に開始。3ヶ月毎にフォロー")

    baseline = [
        "HIV抗原抗体検査(4th世代 combo assay)",
        "B型/C型肝炎",
        "梅毒RPR",
        "淋菌/クラミジアNAAT",
        "CBC, Cr(腎機能)",
        "妊娠検査(女性)",
    ]

    return HIVRiskAssessment(
        exposure_type=exposure_type,
        hours_since_exposure=hours_since_exposure,
        pep_eligible=pep_eligible,
        pep_regimen=pep_regimen,
        pep_deadline_hours=72,
        prep_indicated=prep_indicated,
        prep_regimen=prep_regimen,
        baseline_tests=baseline,
        counseling_points=counseling,
        risk_per_act_pct=risk_pct,
    )


# ---------------------------------------------------------------------------
# __main__ demo
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("=" * 60)
    print("Antibiotic Selection Guide Demo")
    print("=" * 60)
    rec = select_antibiotic("e_coli", "uti", "severe", penicillin_allergy=False)
    print(f"Syndrome: {rec.syndrome}")
    print(f"First line: {rec.first_line}")
    print(f"Duration: {rec.dose_duration}")
    print(f"De-escalation: {rec.de_escalation_note}")

    print("\n" + "=" * 60)
    print("Empirical Regimen (CAP moderate) Demo")
    print("=" * 60)
    regs = empirical_antibiotic("cap", "moderate")
    for r in regs:
        print(f"Syndrome: {r.syndrome}")
        print(f"Regimen: {r.regimen}")
        print(f"MRSA: {r.mrsa_considerations}")
        print(f"De-escalation: {r.de_escalation}")

    print("\n" + "=" * 60)
    print("Antimicrobial Stewardship Demo")
    print("=" * 60)
    sr = stewardship_review(
        antibiotic="meropenem",
        started_days_ago=4,
        culture_results="E.coli sensitive to ceftriaxone",
        clinical_improvement=True,
        other_antibiotics=["vancomycin"],
    )
    print(f"Assessment: {sr.assessment}")
    print(f"De-escalation possible: {sr.de_escalation_possible}")
    print(f"Suggestion: {sr.de_escalation_suggestion}")
    print(f"Duplicate coverage: {sr.duplicate_coverage}")
    print(f"Recommendation: {sr.recommendation}")

    print("\n" + "=" * 60)
    print("Travel Medicine Demo (Southeast Asia, 14 days, trekking)")
    print("=" * 60)
    tm = travel_medicine_screening("southeast_asia", 14, ["trekking", "wildlife"])
    print(f"Vaccines: {tm.recommended_vaccines}")
    print(f"Prophylaxis: {tm.prophylaxis}")
    print(f"Precautions: {tm.precautions[:3]}")

    print("\n" + "=" * 60)
    print("HIV Risk Assessment + PEP Demo")
    print("=" * 60)
    hiv = assess_hiv_risk(
        exposure_type="receptive_anal_intercourse",
        source_hiv_status="unknown",
        hours_since_exposure=18,
        ongoing_risk=False,
    )
    print(f"Exposure risk per act: {hiv.risk_per_act_pct}%")
    print(f"PEP eligible: {hiv.pep_eligible}")
    print(f"PEP regimen: {hiv.pep_regimen}")
    print(f"Counseling: {hiv.counseling_points[:3]}")
    print(f"Baseline tests: {hiv.baseline_tests}")
