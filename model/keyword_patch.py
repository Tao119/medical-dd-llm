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

# ── 専門科ルール追加分キーワードパッチ ──────────────────────────
KEYWORD_PATCHES.update({
    # 急性白血病
    "ACUTE_LEUKEMIA": {
        "add_keywords": ["白血病 出血", "白血病 発熱 貧血", "芽球 骨髄抑制", "AML ALL 診断", "血球減少 発熱"],
        "min_match": 1,
    },
    # 悪性貧血
    "PERNICIOUS_ANEMIA": {
        "add_keywords": ["B12欠乏 貧血", "大球性貧血 神経症状", "内因子欠乏", "MCV高値 神経"],
        "min_match": 1,
    },
    # 鉄欠乏性貧血
    "IRON_DEFICIENCY_ANEMIA": {
        "add_keywords": ["小球性低色素性", "フェリチン低値", "Plummer-Vinson", "月経過多 貧血"],
        "min_match": 1,
    },
    # TTP
    "TTP": {
        "add_keywords": ["溶血性貧血 血小板減少 神経", "破砕赤血球", "ADAMTS13", "MAHA 発熱"],
        "min_match": 1,
    },
    # ITP
    "ITP": {
        "add_keywords": ["血小板減少 出血斑のみ", "孤立性血小板減少 骨髄正常", "抗血小板抗体"],
        "min_match": 1,
    },
    # 多発性骨髄腫
    "MULTIPLE_MYELOMA": {
        "add_keywords": ["CRAB基準", "骨痛 高Ca 腎不全 貧血", "免疫グロブリン異常", "形質細胞腫"],
        "min_match": 1,
    },
    # 過白血球症
    "HYPERLEUKOCYTOSIS": {
        "add_keywords": ["白血球著増 呼吸不全", "WBC10万以上", "白血球分離"],
        "min_match": 1,
    },
    # SJS
    "SJS": {
        "add_keywords": ["薬疹 粘膜びらん", "Stevens-Johnson", "SCORTEN", "皮膚剥離 薬剤"],
        "min_match": 1,
    },
    # TEN
    "TEN": {
        "add_keywords": ["表皮広範囲剥離", "Lyell症候群", "ニコルスキー 皮疹", "致死的薬疹"],
        "min_match": 1,
    },
    # 蜂窩織炎
    "CELLULITIS": {
        "add_keywords": ["皮膚発赤腫脹 境界不明瞭", "下腿発赤 腫脹", "蜂窩織炎 抗菌薬"],
        "min_match": 1,
    },
    # 壊死性筋膜炎
    "NECROTIZING_FASCIITIS": {
        "add_keywords": ["筋膜炎 急速進行", "痛みが激しい 皮膚変色", "捻髪音 外傷後", "壊死性感染"],
        "min_match": 1,
    },
    # 帯状疱疹
    "HERPES_ZOSTER": {
        "add_keywords": ["片側水疱 神経痛", "VZV再活性化", "分節状皮疹", "ゾスタ"],
        "min_match": 1,
    },
    # 薬疹
    "DRUG_ERUPTION": {
        "add_keywords": ["薬剤開始後 皮疹", "薬物過敏", "DRESS症候群", "固定薬疹"],
        "min_match": 1,
    },
    # CRAO
    "CRAO": {
        "add_keywords": ["突然視力消失 片眼", "cherry red spot", "網膜虚血", "視力消失 痛みなし 高齢"],
        "min_match": 1,
    },
    # 網膜剥離
    "RETINAL_DETACHMENT": {
        "add_keywords": ["視野のカーテン", "飛蚊症 光視症 急増", "網膜はがれ", "視野が欠ける"],
        "min_match": 1,
    },
    # GCA
    "GCA_VISION": {
        "add_keywords": ["側頭動脈炎", "顎が痛い 高齢 頭痛", "ESR著明上昇 高齢", "視力消失 高齢 側頭部痛"],
        "min_match": 1,
    },
    # 急性統合失調症
    "ACUTE_PSYCHOSIS": {
        "add_keywords": ["幻聴 妄想 急性", "精神病急性発症", "統合失調症 初発"],
        "min_match": 1,
    },
    # 躁状態
    "BIPOLAR_MANIA": {
        "add_keywords": ["躁状態 睡眠不要", "誇大妄想 活動亢進", "双極性 躁エピソード"],
        "min_match": 1,
    },
    # 重篤なうつ病
    "SEVERE_DEPRESSION": {
        "add_keywords": ["死にたい 抑うつ", "自殺念慮 強い", "うつ病 精神運動抑制"],
        "min_match": 1,
    },
    # アルコール離脱
    "ALCOHOL_WITHDRAWAL": {
        "add_keywords": ["断酒後 振戦 発汗", "アルコール依存症 禁断", "CIWA 離脱症状", "飲酒中断 けいれん"],
        "min_match": 1,
    },
    # 精巣捻転
    "TESTICULAR_TORSION": {
        "add_keywords": ["精巣痛 突然 若年", "睾丸捻転", "陰嚢 急性疼痛", "精巣血流消失"],
        "min_match": 1,
    },
    # 急性前立腺炎
    "ACUTE_PROSTATITIS": {
        "add_keywords": ["前立腺痛み 高熱", "会陰部激痛 発熱", "前立腺炎 排尿困難 発熱"],
        "min_match": 1,
    },
    # コンパートメント症候群
    "COMPARTMENT_SYNDROME": {
        "add_keywords": ["外傷後 筋硬直 激痛", "5P症状 外傷", "区画内圧上昇", "筋膜切開"],
        "min_match": 1,
    },
    # 化膿性関節炎
    "SEPTIC_ARTHRITIS": {
        "add_keywords": ["関節液混濁 発熱", "膿関節炎", "単関節 CRP著増 発熱"],
        "min_match": 1,
    },
    # 痛風
    "GOUT_ATTACK": {
        "add_keywords": ["足親指 急性炎症", "痛風 尿酸高い", "MTP関節 急性疼痛", "痛風 夜間発作"],
        "min_match": 1,
    },
    # 偽痛風
    "PSEUDOGOUT": {
        "add_keywords": ["膝関節 急性炎症 高齢", "軟骨石灰化 急性関節炎", "CPPD関節炎"],
        "min_match": 1,
    },
    # 骨粗鬆症性骨折
    "OSTEOPOROTIC_FRACTURE": {
        "add_keywords": ["高齢女性 腰痛 急性", "骨粗鬆症 椎体骨折", "身長が縮む 腰痛"],
        "min_match": 1,
    },
    # OHSS
    "OHSS": {
        "add_keywords": ["体外受精後 腹水", "排卵誘発 腹痛 腫脹", "不妊治療 呼吸困難"],
        "min_match": 1,
    },
    # 前置胎盤
    "PLACENTA_PREVIA": {
        "add_keywords": ["妊娠後半 出血 痛みなし", "妊娠 鮮血 無痛", "前置胎盤 帝王切開"],
        "min_match": 1,
    },
    # 常位胎盤早期剥離
    "PLACENTAL_ABRUPTION": {
        "add_keywords": ["妊娠 腹痛 板状硬", "胎盤剥離 出血", "妊娠後期 突然腹痛 胎児仮死"],
        "min_match": 1,
    },
    # 原発性アルドステロン症
    "PRIMARY_ALDOSTERONISM": {
        "add_keywords": ["低K 高血圧 コン症候群", "アルドステロン過剰", "副腎腫瘍 高血圧 低K"],
        "min_match": 1,
    },
    # 高プロラクチン血症
    "HYPERPROLACTINEMIA": {
        "add_keywords": ["乳汁 無月経 下垂体", "プロラクチン高値 無排卵", "下垂体腺腫 乳汁分泌"],
        "min_match": 1,
    },
    # 先端巨大症
    "ACROMEGALY": {
        "add_keywords": ["手足大きい 顔変化", "GH過剰 下垂体", "IGF-1高値 先端肥大"],
        "min_match": 1,
    },
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
