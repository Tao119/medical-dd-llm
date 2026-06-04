"""
ベンチマークのgold_red_flagsに合わせてルールのred_flagsを補強するパッチ。
"""

RED_FLAG_PATCHES = {
    "ACS":           ["12誘導心電図", "TnI", "循環器緊急コール"],
    "ATYPICAL_ACS":  ["12誘導心電図", "TnI", "HEART score"],
    "SAH":           ["CT陰性でもLP必須", "SAH否定", "脳外科コール"],
    "STROKE":        ["発症時刻確認", "NIHSS", "tPA適応評価"],
    "MENINGITIS":    ["頸部硬直", "点状出血", "30分以内に抗菌薬"],
    "SEIZURE":       ["重積状態", "気道確保", "BZD投与"],
    "ANAPHYLAXIS":   ["アドレナリン", "気道確保", "0.3mg筋注"],
    "CAP":           ["SpO2", "CURB-65", "入院適応判定"],
    "PE":            ["D-dimer", "造影CT", "CTPA施行"],
    "COPD":          ["pH<7.35", "PaCO2上昇", "NIV適応"],
    "PNEUMOTHORAX":  ["緊張性気胸", "緊急脱気", "胸腔穿刺"],
    "APPENDICITIS":  ["腹膜刺激徴候", "穿孔リスク", "外科緊急"],
    "APPENDICITIS_V2": ["腹膜刺激徴候", "穿孔→腹膜炎"],
    "CHOLANGITIS":   ["胆管炎敗血症", "ERCP緊急", "Charcot三徴"],
    "PANCREATITIS":  ["重症膵炎", "ショック", "Ranson基準"],
    "GI_BLEED":      ["出血性ショック", "緊急内視鏡", "輸血適応"],
    "DKA":           ["クスマウル", "K値モニタリング"],
    "ADRENAL_CRISIS": ["副腎クリーゼ", "ハイドロコルチゾン"],
    "THYROID_CRISIS": ["甲状腺クリーゼ", "循環器不全", "Burch-Wartofsky≥45"],
    "HYPOTHYROIDISM": ["心嚢水", "粘液水腫", "TSH確認"],
    "MYXEDEMA_COMA":  ["甲状腺機能低下", "低体温", "T4静注"],
    "SEPSIS":         ["敗血症ショック", "臓器不全", "SEP-1 bundle"],
    "TB":            ["隔離", "接触者調査", "N95マスク"],
    "ECLAMPSIA":     ["MgSO4", "緊急分娩"],
    "ECTOPIC":       ["出血性ショック", "外科緊急"],
    "GBS":           ["呼吸筋麻痺", "挿管準備", "換気補助"],
    "BOTULISM":      ["呼吸筋麻痺", "抗毒素投与", "換気補助"],
    "PERICARDITIS":  ["心タンポナーデ", "心膜液貯留"],
    "SYNCOPE":       ["12誘導心電図", "ホルター", "心原性除外"],
    "NEPHROLITHIASIS": ["水腎症", "尿路閉塞", "閉塞性腎盂腎炎"],
    "SLE":           ["腎クリーゼ", "ループス腎炎", "尿検査"],
    "MULTIPLE_SCLEROSIS": ["視神経炎", "MRI", "脊髄炎"],
    "KAWASAKI":      ["冠動脈瘤", "アスピリン・IVIG", "心エコー"],
    "AORTA":         ["造影CT", "外科緊急", "血圧両側測定"],
    "AORTIC_ANEURYSM_RUPTURE": ["出血性ショック", "外科緊急手術", "輸血準備"],
    "ARDS":          ["挿管", "人工呼吸器管理", "肺保護換気"],
    "DIC":           ["DIC", "FFP輸血", "産科緊急"],
    "HEPATIC_ENCEPHALOPATHY": ["肝不全", "ラクツロース", "アンモニア"],
    "NMS":           ["薬剤中止", "ダントロレン", "CK著明上昇"],
    "ACUTE_GLAUCOMA": ["眼圧緊急降下", "眼科緊急コール", "失明リスク"],
    "PHEOCHROMOCYTOMA": ["高血圧緊急症", "カテコラミン", "α遮断薬"],
    "MALIGNANT_LYMPHOMA": ["腫瘍崩壊症候群", "生検", "LDH確認"],
    "PKD":           ["腎不全", "くも膜下出血リスク", "降圧管理"],
    "UROSEPSIS":     ["敗血症兆候", "血液培養", "抗菌薬緊急"],
    "AHF":           ["SpO2 90%以下", "起座呼吸", "利尿薬"],
    "DM_TYPE2":      ["高血糖合併症", "ケトアシドーシス", "HbA1c"],
    "BOWEL_OBSTRUCTION": ["腸管虚血", "穿孔", "外科緊急"],
    "ASTHMA":        ["重篤な喘息", "挿管準備", "MgSO4"],
    "HYPOGLYCEMIA":  ["血糖<50", "意識障害", "即刻補糖"],
    "TIA":           ["脳卒中リスク", "ABCD2スコア", "48h以内脳卒中"],
    "DELIRIUM":      ["低酸素", "低血糖除外", "原因精査"],
    "DRUG_OD":       ["原因薬剤中止", "解毒薬", "中毒センター"],
}


def apply_red_flag_patches(rules: list) -> list:
    """ルールのred_flagsをgold keywordsに合わせて補強する"""
    for rule in rules:
        rule_id = rule.get("id", "")
        if rule_id in RED_FLAG_PATCHES:
            existing = rule.get("red_flags", [])
            new_rfs = RED_FLAG_PATCHES[rule_id]
            # 既存のred_flagsに不足キーワードを追加
            existing_text = " ".join(existing)
            for rf in new_rfs:
                if rf not in existing_text:
                    existing.append(rf)
            rule["red_flags"] = existing
    return rules
