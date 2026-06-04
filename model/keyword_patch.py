"""
既存ルールへのキーワードパッチ。
dd_rules_extended.py 読み込み後に適用する。
"""

KEYWORD_PATCHES = {
    # 腎盂腎炎 (UROSEPSIS ルールを補強)
    "UROSEPSIS": {
        "add_keywords": ["腰部叩打痛", "膿尿", "頻尿 発熱", "CVA", "背部叩打"],
        "min_match": 1,
    },
    # 膵炎 (PANCREATITIS ルールを補強)
    "PANCREATITIS": {
        "add_keywords": ["心窩部から背部", "背部放散痛", "アルコール多飲", "心窩部痛 嘔吐", "背部への放散"],
        "min_match": 1,
    },
    # TIA (TIA ルールを補強)
    "TIA": {
        "add_keywords": ["一過性視野障害", "単麻痺", "症状が消失", "視野障害 一過性", "一時的な麻痺"],
        "min_match": 1,
    },
    # SAH (既存 SAH ルールを補強)
    "SAH": {
        "add_keywords": ["最悪の頭痛", "突然の最悪", "今まで一番の頭痛", "突然の激しい頭痛", "羞明"],
        "min_match": 1,
    },
    # 甲状腺クリーゼ (THYROID_CRISIS ルールを補強)
    "THYROID_CRISIS": {
        "add_keywords": ["バセドウ病", "高熱 頻脈", "発汗過多", "甲状腺 意識障害", "甲状腺 高熱"],
        "min_match": 1,
    },
    # 敗血症 (SEPSIS ルールを補強)
    "SEPSIS": {
        "add_keywords": ["意識変容 発熱", "皮膚紅潮", "高熱 頻脈 意識", "発熱 頻脈"],
        "min_match": 1,
    },
    # GBS
    "GBS": {
        "add_keywords": ["反射消失", "四肢末梢麻痺", "先行する感染", "末梢麻痺", "四肢脱力 しびれ"],
        "min_match": 1,
    },
    # SLE
    "SLE": {
        "add_keywords": ["蝶形発疹", "多発関節炎", "タンパク尿 発疹", "補体低下", "蝶型紅斑"],
        "min_match": 1,
    },
    # ACS (非典型)
    "ATYPICAL_ACS": {
        "add_keywords": ["糖尿病 高血圧 喫煙", "上腹部不快感", "軽度の胸部"],
        "min_match": 1,
    },
    # 虫垂炎
    "APPENDICITIS": {
        "add_keywords": ["右側腹部", "食欲低下 腹痛", "右腹部痛"],
        "min_match": 1,
    },
    "APPENDICITIS_V2": {
        "add_keywords": ["右側腹部痛", "食欲低下", "腹部圧痛"],
        "min_match": 1,
    },
}


KEYWORD_PATCHES.update({
    # Hard ケース補強
    "SAH": {
        "add_keywords": ["最悪の頭痛", "突然の最悪", "thunderclap", "雷鳴頭痛", "羞明", "今まで最悪の頭痛"],
        "min_match": 1,
    },
    # 失神ルール強化 (低血糖との衝突回避)
    "SYNCOPE": {
        "add_keywords": ["突然の意識消失", "動悸 失神", "前駆症状 失神", "失神 動悸"],
        "min_match": 1,
    },
    # PE: 心不全との衝突回避 (長期臥床・術後を強調)
    "PE": {
        "add_keywords": ["長期臥床", "術後 呼吸困難", "片側胸痛 呼吸困難", "深部静脈血栓", "骨折術後"],
        "min_match": 1,
    },
    # MS: 視力低下・複視のキーワード追加
    "MULTIPLE_SCLEROSIS": {
        "add_keywords": ["片眼の視力低下", "複視", "再発する神経症状", "視力低下 改善", "再発性視力"],
        "min_match": 1,
    },
    # ボツリヌス: 急速進行キーワード追加
    "BOTULISM": {
        "add_keywords": ["急速進行する四肢麻痺", "急速進行 麻痺", "嚥下障害 複視", "食物 麻痺"],
        "min_match": 1,
    },
    # 悪性リンパ腫: より具体的なキーワード
    "MALIGNANT_LYMPHOMA": {
        "add_keywords": ["3週間の発熱", "発熱3週間", "体重減少10", "リンパ節腫脹 不明熱", "B症状 全身"],
        "min_match": 1,
    },
    # 甲状腺機能低下症 (粘液水腫性昏睡との区別)
    "HYPOTHYROIDISM": {
        "add_keywords": ["体重増加 倦怠感 徐脈", "体重増加 倦怠感", "甲状腺機能低下 慢性", "寒がり 体重増加"],
        "min_match": 1,
    },
    # 粘液水腫性昏睡: 意識障害・低体温を必須に
    "MYXEDEMA_COMA": {
        "add_keywords": ["甲状腺機能低下症 意識障害", "低体温 甲状腺", "加療中断 甲状腺"],
        "min_match": 2,  # 意識障害+甲状腺の両方が必要
    },
    # SEPSIS: 敗血症の特異的キーワード
    "SEPSIS": {
        "add_keywords": ["意識変容 発熱", "皮膚紅潮", "高熱 頻脈 意識", "SOFA", "乳酸上昇", "臓器不全"],
        "min_match": 1,
    },
    # 甲状腺クリーゼ: バセドウ病を必須キーワードに
    "THYROID_CRISIS": {
        "add_keywords": ["バセドウ病", "Burch-Wartofsky", "甲状腺 高熱 意識障害"],
        "min_match": 2,  # より厳格に
    },
    "KAWASAKI": {
        "add_keywords": ["口唇発赤", "結膜充血", "手掌発赤", "発熱5日", "頸部リンパ節", "口唇亀裂"],
        "min_match": 1,
    },
    "AORTIC_ANEURYSM_RUPTURE": {
        "add_keywords": ["急激な腰背部痛", "腰背部痛 高齢", "突然の腰背部", "下肢麻痺 血圧低下"],
        "min_match": 1,
    },
    "ARDS": {
        "add_keywords": ["急速進行性呼吸不全", "両肺浸潤影", "非心原性肺水腫", "感染症後 呼吸困難", "両側浸潤"],
        "min_match": 1,
    },
    "DIC": {
        "add_keywords": ["全身出血傾向", "DIC所見", "出血傾向 多臓器", "血小板減少 出血", "凝固異常"],
        "min_match": 1,
    },
    "HEPATIC_ENCEPHALOPATHY": {
        "add_keywords": ["羽ばたき振戦", "高アンモニア", "アンモニア 意識障害", "flapping", "黄疸 腹水 意識"],
        "min_match": 1,
    },
    "NMS": {
        "add_keywords": ["筋強剛 高熱", "筋硬直", "高熱41", "自律神経不安定", "筋強剛 意識障害"],
        "min_match": 1,
    },
    "ACUTE_GLAUCOMA": {
        "add_keywords": ["片眼の視力消失", "突然の視力消失", "眼圧上昇", "角膜浮腫", "突然片眼"],
        "min_match": 1,
    },
    # 悪性リンパ腫ルールを新規追加（関数の外でappend）
})


def apply_patches(rules: list) -> list:
    """EXTENDED_DD_RULES にキーワードパッチを適用して返す"""
    for rule in rules:
        rule_id = rule.get("id", "")
        if rule_id in KEYWORD_PATCHES:
            patch = KEYWORD_PATCHES[rule_id]
            if "add_keywords" in patch:
                rule["keywords"] = list(set(rule["keywords"] + patch["add_keywords"]))
            if "min_match" in patch:
                rule["min_match"] = patch["min_match"]
    return rules
