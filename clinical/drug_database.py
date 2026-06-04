"""
包括的薬剤データベース (80+ drugs)
臨床的に重要な薬剤の用量・相互作用・注意事項を網羅する。
"""
from dataclasses import dataclass, field
from typing import Optional
import difflib


@dataclass
class DrugInfo:
    name_ja: str
    name_en: str
    drug_class: str
    indications: list[str]
    adult_doses: dict[str, str]   # indication -> dose string
    contraindications: list[str]
    major_interactions: list[str]
    renal_adjustment: str
    hepatic_adjustment: str
    monitoring: list[str]
    side_effects: list[str]
    notes: str = ""


DRUG_DATABASE: dict[str, DrugInfo] = {
    # ── 抗血小板薬 ─────────────────────────────────────────────
    "アスピリン": DrugInfo(
        name_ja="アスピリン", name_en="Aspirin",
        drug_class="抗血小板薬/NSAID",
        indications=["ACS初期治療", "虚血性脳卒中予防", "心房細動（DOAC不適時）", "解熱鎮痛"],
        adult_doses={
            "ACS": "200-300mg 咀嚼投与（初回）",
            "二次予防": "75-100mg/日 経口",
            "解熱鎮痛": "500mg 1日3-4回（最大4g/日）",
        },
        contraindications=["アスピリン喘息", "活動性消化管出血", "妊娠後期", "小児ウイルス感染（Reye症候群リスク）"],
        major_interactions=["ワルファリン（出血↑）", "NSAIDs（潰瘍↑）", "メトトレキサート（毒性↑）", "イブプロフェン（抗血小板効果↓）"],
        renal_adjustment="重度腎不全で避ける（ナトリウム貯留・出血リスク）",
        hepatic_adjustment="重度肝障害で慎重投与",
        monitoring=["出血症状", "消化器症状", "腎機能（長期）"],
        side_effects=["胃腸障害", "出血", "アレルギー", "喘息発作（過敏患者）"],
        notes="PPI併用で胃腸副作用を軽減。低用量（75-100mg）でも消化管出血リスクあり",
    ),
    "クロピドグレル": DrugInfo(
        name_ja="クロピドグレル", name_en="Clopidogrel",
        drug_class="抗血小板薬（P2Y12阻害薬）",
        indications=["ACS（DAPT）", "心筋梗塞後二次予防", "虚血性脳卒中予防", "PAD"],
        adult_doses={
            "ACS": "600mgローディング→75mg/日",
            "二次予防": "75mg/日 経口",
            "脳卒中": "75mg/日",
        },
        contraindications=["活動性出血", "重度肝障害"],
        major_interactions=["PPI（オメプラゾール等のCYP2C19阻害→効果↓）", "ワルファリン（出血↑）", "アスピリン（DAPT：出血↑だが効果↑）"],
        renal_adjustment="特別な調整不要（重度では慎重）",
        hepatic_adjustment="重度肝障害では禁忌（CYP2C19依存）",
        monitoring=["出血症状", "血小板数", "CYP2C19遺伝子型検査"],
        side_effects=["出血", "下痢", "発疹", "血小板減少（まれ）"],
        notes="CYP2C19 poor metabolizerでは効果減弱。プラスグレルまたはチカグレロルに変更検討",
    ),
    "プラスグレル": DrugInfo(
        name_ja="プラスグレル", name_en="Prasugrel",
        drug_class="抗血小板薬（P2Y12阻害薬）",
        indications=["ACS（PCIを施行する患者）"],
        adult_doses={
            "ACS": "60mgローディング→10mg/日（60kg未満または75歳以上は5mg/日）",
        },
        contraindications=["TIA/脳卒中既往（絶対禁忌）", "活動性出血", "重度肝障害"],
        major_interactions=["ワルファリン（出血↑）", "NSAIDs（出血↑）"],
        renal_adjustment="特別な調整不要",
        hepatic_adjustment="重度肝障害では禁忌",
        monitoring=["出血症状", "血小板数"],
        side_effects=["出血（クロピドグレルより高リスク）", "発疹", "高尿酸血症"],
        notes="TIA/脳卒中既往患者には禁忌。クロピドグレルよりも強力な抗血小板効果",
    ),
    "チカグレロル": DrugInfo(
        name_ja="チカグレロル", name_en="Ticagrelor",
        drug_class="抗血小板薬（P2Y12阻害薬）",
        indications=["ACS（DAPT）", "心筋梗塞後高リスク患者"],
        adult_doses={
            "ACS": "180mgローディング→90mg 1日2回",
            "慢性期高リスク": "60mg 1日2回（アスピリン100mgと併用）",
        },
        contraindications=["活動性出血", "重度肝障害", "頭蓋内出血既往", "アスピリン高用量（>100mg/日）との併用"],
        major_interactions=["強力なCYP3A4阻害薬（ケトコナゾール等）", "CYP3A4誘導薬（リファンピシン等→効果↓）", "ジゴキシン（濃度↑）"],
        renal_adjustment="特別な調整不要",
        hepatic_adjustment="重度肝障害では禁忌",
        monitoring=["出血症状", "呼吸困難（アデノシン関連）", "腎機能"],
        side_effects=["出血", "呼吸困難（20%程度）", "徐脈", "尿酸上昇"],
        notes="代謝産物にも活性あり。CYP2C19遺伝子型に影響されない。アスピリン高用量との併用禁忌",
    ),

    # ── 抗凝固薬 ────────────────────────────────────────────────
    "ヘパリン": DrugInfo(
        name_ja="ヘパリン", name_en="Unfractionated Heparin",
        drug_class="抗凝固薬（UFH）",
        indications=["ACS（NSTEMI/UA）", "DVT/PE治療", "AF術前後", "透析"],
        adult_doses={
            "ACS": "60U/kg IVボーラス（最大4000U）→12U/kg/h持続（最大1000U/h）、APTT 60-100s目標",
            "DVT/PE": "80U/kg IVボーラス→18U/kg/h持続",
        },
        contraindications=["ヘパリン誘発血小板減少症（HIT）", "活動性出血", "血小板<100,000"],
        major_interactions=["ワルファリン（相加的出血）", "NSAIDs（出血↑）", "抗血小板薬（出血↑）"],
        renal_adjustment="特別な調整不要（腎排泄が少ない）",
        hepatic_adjustment="重度肝障害では肝臓依存の凝固因子産生低下に注意",
        monitoring=["APTT（6時間ごと、目標60-100秒）", "血小板数（HIT検出）", "抗Xa活性（一部施設）"],
        side_effects=["出血", "HIT（1-3%）", "骨粗鬆症（長期）", "低アルドステロン症"],
        notes="HIT疑い→即ヘパリン中止、非ヘパリン系抗凝固薬に切り替え（アルガトロバン等）",
    ),
    "ワルファリン": DrugInfo(
        name_ja="ワルファリン", name_en="Warfarin",
        drug_class="抗凝固薬（ビタミンK拮抗薬）",
        indications=["非弁膜症性AF", "機械弁", "DVT/PE治療・予防", "抗リン脂質抗体症候群"],
        adult_doses={
            "AF": "2-5mg/日（INR 2.0-3.0目標）",
            "機械弁": "INR 2.5-3.5目標（弁位置による）",
        },
        contraindications=["妊娠（第1・3期）", "活動性出血", "重度肝障害"],
        major_interactions=["多数のCYP2C9阻害/誘導薬（フルコナゾール↑、リファンピシン↓）", "NSAIDs（出血↑）", "アスピリン（出血↑）", "アミオダロン（INR↑）"],
        renal_adjustment="特別な調整不要（腎機能には比較的影響少）",
        hepatic_adjustment="重度肝障害では抗凝固効果増強（凝固因子産生↓）",
        monitoring=["PT-INR（週1-月1回）", "出血症状"],
        side_effects=["出血（最重要）", "皮膚壊死（稀）", "薬物相互作用"],
        notes="ビタミンK過剰摂取（納豆・緑黄色野菜）でINR低下。DOACが使用できる場合はDOACを優先",
    ),
    "アピキサバン": DrugInfo(
        name_ja="アピキサバン", name_en="Apixaban",
        drug_class="抗凝固薬（直接Xa阻害薬）",
        indications=["非弁膜症性AF", "DVT/PE治療・予防", "股関節・膝関節置換後予防"],
        adult_doses={
            "AF": "5mg 1日2回（≥2つの減量基準で2.5mg 1日2回）",
            "DVT/PE治療": "10mg 1日2回×7日→5mg 1日2回",
            "DVT予防": "2.5mg 1日2回",
        },
        contraindications=["重度腎不全（CrCl<15）", "活動性出血", "機械弁"],
        major_interactions=["強力CYP3A4+P-gp阻害薬（リファンピシン等で↓）", "アゾール系抗真菌薬（濃度↑）"],
        renal_adjustment="AF: SCr≥1.5かつ年齢≥80or体重≤60kgで2.5mg 1日2回",
        hepatic_adjustment="重度肝障害（Child-Pugh C）は禁忌",
        monitoring=["出血症状", "腎機能（定期）"],
        side_effects=["出血", "出血性脳卒中（ワルファリンより少）"],
        notes="拮抗薬：アンデキサネットアルファ（保険適用あり）。食事の影響を受けない",
    ),
    "リバーロキサバン": DrugInfo(
        name_ja="リバーロキサバン", name_en="Rivaroxaban",
        drug_class="抗凝固薬（直接Xa阻害薬）",
        indications=["非弁膜症性AF", "DVT/PE治療・予防", "冠動脈疾患低用量"],
        adult_doses={
            "AF": "15mg/日 食後（CrCl 15-49の場合も同様）",
            "DVT/PE治療": "15mg 1日2回×3週→20mg/日 食後",
            "冠動脈疾患": "2.5mg 1日2回（アスピリン100mgと併用）",
        },
        contraindications=["CrCl<15", "活動性出血", "機械弁"],
        major_interactions=["CYP3A4+P-gp阻害薬（アゾール系、HIV薬）", "リファンピシン（効果↓）"],
        renal_adjustment="CrCl<15では禁忌。CrCl 15-49で用量調整",
        hepatic_adjustment="重度肝障害（Child-Pugh C）は禁忌",
        monitoring=["出血症状", "腎機能"],
        side_effects=["出血", "肝酵素上昇"],
        notes="食後服用で吸収改善（特に高用量）。抗Xa測定で薬物濃度評価可",
    ),
    "ダビガトラン": DrugInfo(
        name_ja="ダビガトラン", name_en="Dabigatran",
        drug_class="抗凝固薬（直接トロンビン阻害薬）",
        indications=["非弁膜症性AF", "DVT/PE治療・予防"],
        adult_doses={
            "AF": "150mg 1日2回（75歳以上・高出血リスクは110mg 1日2回）",
            "DVT/PE": "ヘパリン5-10日後→150mg 1日2回",
        },
        contraindications=["重度腎不全（CrCl<30）", "活動性出血", "機械弁"],
        major_interactions=["P-gp阻害薬（アミオダロン、ベラパミル等→濃度↑）", "P-gp誘導薬（リファンピシン→効果↓）"],
        renal_adjustment="CrCl<30では禁忌。CrCl 30-50では110mg推奨（AF）",
        hepatic_adjustment="重度肝障害では禁忌",
        monitoring=["腎機能（定期）", "出血症状", "aPTT/トロンビン時間（参考）"],
        side_effects=["出血", "消化器症状（胃炎様症状・嚥下困難）"],
        notes="拮抗薬：イダルシズマブ（承認済み）。PPI併用で消化器症状軽減",
    ),
    "エドキサバン": DrugInfo(
        name_ja="エドキサバン", name_en="Edoxaban",
        drug_class="抗凝固薬（直接Xa阻害薬）",
        indications=["非弁膜症性AF", "DVT/PE治療"],
        adult_doses={
            "AF": "60mg/日（30mg/日に減量：体重≤60kg、CrCl 15-50、P-gp阻害薬）",
            "DVT/PE": "ヘパリン5-10日後→60mg/日",
        },
        contraindications=["重度腎不全（CrCl<15）", "活動性出血", "機械弁"],
        major_interactions=["P-gp阻害薬（ベラパミル、ドロネダロン等→30mgに減量）"],
        renal_adjustment="CrCl 15-50: 30mg/日",
        hepatic_adjustment="重度肝障害は禁忌",
        monitoring=["出血症状", "腎機能"],
        side_effects=["出血", "肝酵素上昇"],
        notes="CrCl>95では効果低下の可能性があり推奨されない（高腎クリアランス）",
    ),

    # ── 循環器薬 ───────────────────────────────────────────────
    "ニトログリセリン": DrugInfo(
        name_ja="ニトログリセリン", name_en="Nitroglycerin",
        drug_class="硝酸薬（有機硝酸薬）",
        indications=["狭心症発作", "急性心不全（血管拡張）", "高血圧緊急症"],
        adult_doses={
            "狭心症発作": "0.3-0.6mg 舌下（5分ごと、最大3回）",
            "急性心不全": "5-10μg/min IV→200μg/minまで漸増",
            "高血圧緊急症": "5-100μg/min IV（目標DBP 100-110mmHg）",
        },
        contraindications=["PDE5阻害薬（シルデナフィル等）服用中（絶対禁忌）", "重度低血圧（SBP<90）", "閉塞隅角緑内障（点眼用）"],
        major_interactions=["PDE5阻害薬（致死的低血圧）", "降圧薬（相加的低血圧）"],
        renal_adjustment="特別な調整不要",
        hepatic_adjustment="特別な調整不要",
        monitoring=["血圧（5分ごと）", "頭痛症状", "耐性発現"],
        side_effects=["頭痛", "低血圧", "頻脈反射", "耐性（12-14h以上連続投与）"],
        notes="連続投与では8-12h/日の休薬時間を設け耐性を防ぐ。舌下投与は右側臥位で（迷走神経反射防止）",
    ),
    "フロセミド": DrugInfo(
        name_ja="フロセミド", name_en="Furosemide",
        drug_class="ループ利尿薬",
        indications=["急性心不全（肺うっ血）", "慢性心不全", "高血圧", "腎性浮腫"],
        adult_doses={
            "急性心不全": "40-80mg IV（日常内服量の1.5-2.5倍を目安に）",
            "慢性心不全": "20-40mg/日 経口（利尿効果に応じて調整）",
            "高血圧": "20-80mg/日 経口",
        },
        contraindications=["無尿・重度腎不全（GFR<15）", "脱水", "ループ利尿薬過敏症"],
        major_interactions=["アミノグリコシド系（耳毒性・腎毒性↑）", "リチウム（濃度↑）", "NSAIDs（効果↓、腎毒性↑）"],
        renal_adjustment="GFR低下で高用量が必要となることが多い",
        hepatic_adjustment="肝性腹水では過剰利尿による肝性脳症リスク",
        monitoring=["電解質（K/Na/Mg）", "腎機能", "体重・尿量", "血圧"],
        side_effects=["低カリウム血症", "低ナトリウム血症", "低マグネシウム血症", "耳毒性（高用量）"],
        notes="低カリウム血症はジゴキシン中毒リスクを高める。カリウム補充またはスピロノラクトン併用",
    ),
    "スピロノラクトン": DrugInfo(
        name_ja="スピロノラクトン", name_en="Spironolactone",
        drug_class="カリウム保持性利尿薬（アルドステロン拮抗薬）",
        indications=["慢性心不全（EF低下型）", "原発性アルドステロン症", "肝性腹水", "高血圧"],
        adult_doses={
            "慢性心不全": "25-50mg/日（目標：カリウム<5.5mEq/L）",
            "原発性アルドステロン症": "100-400mg/日",
            "肝性腹水": "100-400mg/日",
        },
        contraindications=["高カリウム血症（>5.5）", "重度腎不全（GFR<30）", "アジソン病"],
        major_interactions=["ACE阻害薬/ARB（高K↑↑）", "NSAIDs（高K↑、利尿効果↓）"],
        renal_adjustment="GFR<30では原則禁忌（高K血症リスク）",
        hepatic_adjustment="肝障害で代謝低下→効果増強に注意",
        monitoring=["カリウム（開始後1週・1月・定期）", "腎機能", "血圧"],
        side_effects=["高カリウム血症", "女性化乳房", "月経不順", "めまい"],
        notes="RALES試験・EPHESUS試験で心不全死亡率低下を証明。エプレレノンは選択性高く性ホルモン副作用少",
    ),
    "カルベジロール": DrugInfo(
        name_ja="カルベジロール", name_en="Carvedilol",
        drug_class="α/β遮断薬",
        indications=["慢性心不全（EF低下型）", "高血圧", "狭心症"],
        adult_doses={
            "慢性心不全": "2.5-5mg/日（開始）→25mg 1日2回（目標用量）",
            "高血圧": "5-10mg/日",
        },
        contraindications=["急性非代償性心不全", "重度徐脈（HR<50）", "高度AVブロック（Ⅱ-Ⅲ度）", "気管支喘息"],
        major_interactions=["ジルチアゼム/ベラパミル（高度徐脈・AVブロック）", "インスリン（低血糖症状マスク）"],
        renal_adjustment="特別な調整不要",
        hepatic_adjustment="重度肝障害では慎重（代謝低下）",
        monitoring=["心拍数", "血圧", "心不全症状", "血糖（糖尿病患者）"],
        side_effects=["徐脈", "低血圧", "めまい", "疲労感", "体重増加（一過性）"],
        notes="心不全には少量から開始し2週ごとに漸増。急性増悪期には開始禁忌（安定後に開始）",
    ),
    "ビソプロロール": DrugInfo(
        name_ja="ビソプロロール", name_en="Bisoprolol",
        drug_class="β1選択的β遮断薬",
        indications=["慢性心不全（EF低下型）", "高血圧", "狭心症", "心房細動（レートコントロール）"],
        adult_doses={
            "慢性心不全": "1.25mg/日（開始）→10mg/日（目標用量）",
            "高血圧/狭心症": "5-10mg/日",
            "AF": "2.5-10mg/日（HR 60-80目標）",
        },
        contraindications=["急性非代償性心不全", "重度徐脈", "高度AVブロック", "気管支喘息（相対）"],
        major_interactions=["ジルチアゼム/ベラパミル（徐脈）", "インスリン（低血糖症状マスク）"],
        renal_adjustment="重度腎不全（GFR<20）では慎重（排泄低下）",
        hepatic_adjustment="重度肝障害では慎重",
        monitoring=["心拍数", "血圧", "心不全症状"],
        side_effects=["徐脈", "疲労感", "冷感（末梢血管収縮）", "インポテンス"],
        notes="β1選択性が高く、COPD/軽度喘息にも相対的に安全。CIBIS-II試験で死亡率低下",
    ),
    "エナラプリル": DrugInfo(
        name_ja="エナラプリル", name_en="Enalapril",
        drug_class="ACE阻害薬",
        indications=["慢性心不全（EF低下型）", "高血圧", "糖尿病性腎症"],
        adult_doses={
            "心不全": "2.5mg/日（開始）→20mg/日",
            "高血圧": "5-40mg/日（1-2回分割）",
        },
        contraindications=["妊娠（第2・3期）", "両側腎動脈狭窄", "血管浮腫既往", "高カリウム血症"],
        major_interactions=["ARB（二重遮断→腎障害・高K）", "NSAIDs（腎機能↓）", "アリスキレン（禁忌）", "リチウム（濃度↑）"],
        renal_adjustment="GFR<30では用量半減・慎重投与",
        hepatic_adjustment="プロドラッグ（エナラプリルアト→エナラプリラット）のため重度肝障害で効果低下",
        monitoring=["腎機能・カリウム（開始後1-2週・定期）", "血圧", "咳嗽"],
        side_effects=["空咳（10-20%）", "高カリウム血症", "急性腎障害（腎動脈狭窄患者）", "血管浮腫（稀）"],
        notes="空咳が著明ならARBに変更。妊娠中（第2・3期）は胎児腎毒性のため絶対禁忌",
    ),
    "バルサルタン": DrugInfo(
        name_ja="バルサルタン", name_en="Valsartan",
        drug_class="ARB（アンジオテンシンII受容体拮抗薬）",
        indications=["慢性心不全（EF低下型）", "高血圧", "心筋梗塞後", "糖尿病性腎症"],
        adult_doses={
            "心不全": "40mg 1日2回（開始）→160mg 1日2回（目標）",
            "高血圧": "80-320mg/日",
        },
        contraindications=["妊娠", "両側腎動脈狭窄", "高カリウム血症"],
        major_interactions=["ACE阻害薬（二重遮断禁忌）", "アリスキレン（糖尿病・腎障害で禁忌）", "NSAIDs（腎機能↓）"],
        renal_adjustment="GFR<30では慎重",
        hepatic_adjustment="軽度-中等度肝障害で最大80mg/日（胆汁排泄型）",
        monitoring=["腎機能・カリウム（定期）", "血圧"],
        side_effects=["高カリウム血症", "急性腎障害（腎動脈狭窄）", "低血圧"],
        notes="ACE阻害薬の空咳が忌避される場合の代替薬。Val-HeFT試験で心不全アウトカム改善",
    ),
    "アムロジピン": DrugInfo(
        name_ja="アムロジピン", name_en="Amlodipine",
        drug_class="Ca拮抗薬（ジヒドロピリジン系）",
        indications=["高血圧", "慢性安定狭心症", "冠攣縮性狭心症"],
        adult_doses={
            "高血圧": "2.5-10mg/日",
            "狭心症": "5-10mg/日",
        },
        contraindications=["心原性ショック", "不安定狭心症（相対）"],
        major_interactions=["シクロスポリン（濃度↑）", "シンバスタチン（筋症リスク↑）", "CYP3A4阻害薬（濃度↑）"],
        renal_adjustment="特別な調整不要",
        hepatic_adjustment="重度肝障害では半減期延長→少量から開始",
        monitoring=["血圧", "浮腫", "心拍数"],
        side_effects=["末梢浮腫（最多）", "頭痛", "顔面紅潮", "反射性頻脈（少）"],
        notes="長時間作用型。負の変力・変伝導作用なし。高齢者高血圧に第一選択の一つ",
    ),
    "サクビトリル/バルサルタン": DrugInfo(
        name_ja="サクビトリル/バルサルタン", name_en="Sacubitril/Valsartan (ARNI)",
        drug_class="ARNI（アンジオテンシン受容体ネプリライシン阻害薬）",
        indications=["慢性心不全（EF低下型、NYHA II-IV）"],
        adult_doses={
            "心不全": "49/51mg 1日2回（開始）→97/103mg 1日2回（目標）",
        },
        contraindications=["ACE阻害薬との併用（36h以上間隔が必要）", "血管浮腫既往", "重度肝障害", "妊娠"],
        major_interactions=["ACE阻害薬（血管浮腫のリスク、36h以上間隔必要）", "NSAIDs（腎機能↓）"],
        renal_adjustment="GFR<30では24.5/25.7mgから開始",
        hepatic_adjustment="重度肝障害（Child-Pugh C）は禁忌",
        monitoring=["腎機能・カリウム（定期）", "血圧", "血管浮腫症状"],
        side_effects=["低血圧", "高カリウム血症", "急性腎障害", "血管浮腫"],
        notes="PARADIGM-HF試験でエナラプリルより死亡率低下。ACE阻害薬から切替は36h以上間隔を空ける",
    ),
    "ダパグリフロジン": DrugInfo(
        name_ja="ダパグリフロジン", name_en="Dapagliflozin",
        drug_class="SGLT2阻害薬",
        indications=["2型糖尿病", "慢性心不全（EF低下型・保存型）", "慢性腎臓病"],
        adult_doses={
            "糖尿病": "5-10mg/日",
            "心不全": "10mg/日",
            "CKD": "10mg/日",
        },
        contraindications=["1型糖尿病", "eGFR<25（CKD適応では<45禁忌）"],
        major_interactions=["インスリン・スルホニル尿素薬（低血糖リスク↑）", "ループ利尿薬（脱水リスク）"],
        renal_adjustment="eGFR<25では禁忌（心不全適応はeGFR<25で注意）",
        hepatic_adjustment="重度肝障害では慎重",
        monitoring=["腎機能・電解質", "ケトン体（1型糖尿病疑い）", "尿路感染症状"],
        side_effects=["尿路・性器感染症", "尿量増加", "ケトアシドーシス（1型では禁忌）", "Fournier壊疽（まれ）"],
        notes="DAPA-HF・DAPA-CKD試験で心腎予後改善。糖尿病非合併の心不全・CKDにも適応",
    ),

    # ── 昇圧薬 ─────────────────────────────────────────────────
    "ノルアドレナリン": DrugInfo(
        name_ja="ノルアドレナリン（ノルエピネフリン）", name_en="Norepinephrine",
        drug_class="カテコラミン（α1>β1作用）",
        indications=["敗血症性ショック（第一選択）", "血管拡張性ショック"],
        adult_doses={
            "敗血症性ショック": "0.01-3μg/kg/min IV持続（MAP≥65目標）",
        },
        contraindications=["容量不足の未補正", "閉塞性ショック（相対）"],
        major_interactions=["MAO阻害薬（高血圧クリーゼ）", "三環系抗うつ薬（昇圧効果↑）"],
        renal_adjustment="特別な調整不要",
        hepatic_adjustment="特別な調整不要",
        monitoring=["MAP（連続動脈圧）", "末梢循環（皮膚色・体温）", "乳酸値", "尿量"],
        side_effects=["組織虚血（末梢・腸管）", "不整脈", "頭痛", "過剰昇圧"],
        notes="中心静脈ルートが原則（末梢ルートは短時間のみ可）。MAP65-70が目標（過剰昇圧は臓器虚血）",
    ),
    "アドレナリン": DrugInfo(
        name_ja="アドレナリン（エピネフリン）", name_en="Epinephrine",
        drug_class="カテコラミン（α1+β1+β2作用）",
        indications=["アナフィラキシー（第一選択）", "心停止（CPR中）", "重症喘息"],
        adult_doses={
            "アナフィラキシー": "0.3-0.5mg 筋注（大腿外側部）、5-15分ごとに反復可",
            "心停止": "1mg IV（3-5分ごと）",
            "重症喘息（補助）": "0.3mg 皮下注",
        },
        contraindications=["閉塞隅角緑内障", "高血圧（相対）", "甲状腺機能亢進症（相対）"],
        major_interactions=["β遮断薬（α作用優位→高血圧+徐脈）", "MAO阻害薬（高血圧クリーゼ）"],
        renal_adjustment="特別な調整不要",
        hepatic_adjustment="特別な調整不要",
        monitoring=["血圧・心拍数", "SpO2", "呼吸状態"],
        side_effects=["頻脈・不整脈", "高血圧", "低カリウム血症", "蒼白・振戦"],
        notes="アナフィラキシーでは絶対に迷わず筋注。エピペン（0.15mg/0.3mg）は自己注射用",
    ),
    "ドパミン": DrugInfo(
        name_ja="ドパミン", name_en="Dopamine",
        drug_class="カテコラミン（用量依存性：DA1→β1→α1）",
        indications=["心原性ショック（心収縮力低下）", "敗血症性ショック（ノルアドレナリン代替）"],
        adult_doses={
            "心原性ショック": "5-20μg/kg/min IV持続",
            "低用量（腎保護）": "1-3μg/kg/min（エビデンス不確実）",
        },
        contraindications=["未矯正の心室細動", "褐色細胞腫"],
        major_interactions=["MAO阻害薬（高血圧クリーゼ）", "フェニトイン（低血圧）"],
        renal_adjustment="特別な調整不要",
        hepatic_adjustment="特別な調整不要",
        monitoring=["血圧・心拍数（連続）", "不整脈", "尿量"],
        side_effects=["頻脈・不整脈（高用量）", "高血圧（高用量α効果）", "組織虚血（高用量）"],
        notes="SOAP-II試験でノルアドレナリンと比較して不整脈発生率が高い。現在はノルアドレナリンが第一選択",
    ),
    "ドブタミン": DrugInfo(
        name_ja="ドブタミン", name_en="Dobutamine",
        drug_class="合成カテコラミン（β1>β2作用）",
        indications=["急性非代償性心不全（低心拍出症候群）", "心原性ショック", "心臓負荷試験"],
        adult_doses={
            "急性心不全": "2-20μg/kg/min IV持続",
        },
        contraindications=["閉塞性肥大型心筋症", "重度大動脈弁狭窄"],
        major_interactions=["β遮断薬（心拍出増加効果↓）"],
        renal_adjustment="特別な調整不要",
        hepatic_adjustment="特別な調整不要",
        monitoring=["血圧・心拍数", "心電図（不整脈）", "心拍出量（可能な場合）"],
        side_effects=["頻脈", "不整脈", "頭痛", "低血圧（高用量で血管拡張）"],
        notes="血圧を上げずに心拍出量を増やしたい場合（ウォームショック）に適する。長期使用で耐性",
    ),
    "バソプレシン": DrugInfo(
        name_ja="バソプレシン（抗利尿ホルモン）", name_en="Vasopressin",
        drug_class="抗利尿ホルモン/昇圧薬（V1a/V2受容体）",
        indications=["敗血症性ショック（ノルアドレナリン補助）", "心停止（CPR）", "食道静脈瘤出血"],
        adult_doses={
            "敗血症ショック": "0.03-0.04U/min IV持続（ノルアドレナリンに追加）",
            "心停止": "40U IV（1回のみ）",
            "静脈瘤出血": "0.2-0.4U/min IV",
        },
        contraindications=["冠動脈疾患（相対）"],
        major_interactions=["特記なし"],
        renal_adjustment="特別な調整不要",
        hepatic_adjustment="特別な調整不要",
        monitoring=["血圧", "Na/水分バランス", "心拍数"],
        side_effects=["低Na血症（高用量）", "冠動脈収縮", "腸管虚血"],
        notes="ノルアドレナリン≥0.25μg/kg/minが必要な場合に追加。VASST試験で早期追加の可能性",
    ),

    # ── 抗不整脈薬 ─────────────────────────────────────────────
    "アミオダロン": DrugInfo(
        name_ja="アミオダロン", name_en="Amiodarone",
        drug_class="抗不整脈薬（クラスIII、多チャネル作用）",
        indications=["心室細動/心室頻拍（CPR中）", "持続性VT", "AF（レートコントロール/リズムコントロール）", "WPW症候群"],
        adult_doses={
            "CPR中VF/VT": "300mg IVボーラス（追加150mg）",
            "AF維持療法": "100-400mg/日 経口（最低有効量で）",
        },
        contraindications=["甲状腺機能障害（相対）", "ヨウ素過敏症", "洞房ブロック/AVブロック（ペースメーカーなし）"],
        major_interactions=["ジゴキシン（濃度2倍↑）", "ワルファリン（INR↑）", "多数のQT延長薬（TdPリスク）", "シクロスポリン（濃度↑）"],
        renal_adjustment="特別な調整不要",
        hepatic_adjustment="重度肝障害では慎重（肝毒性リスク）",
        monitoring=["甲状腺機能（TSH/FT3/FT4 6ヶ月ごと）", "胸部X線・肺機能（定期）", "肝機能", "眼科検査（年1）", "QT間隔"],
        side_effects=["甲状腺機能異常（10-20%）", "間質性肺炎（2-5%）", "光線過敏症", "角膜微細沈着物", "肝毒性", "QT延長・TdP"],
        notes="半減期40-55日で薬物動態複雑。多数の臓器毒性があるため最低有効量・短期使用を心がける",
    ),
    "リドカイン": DrugInfo(
        name_ja="リドカイン", name_en="Lidocaine",
        drug_class="抗不整脈薬（クラスIb）/ 局所麻酔薬",
        indications=["心室不整脈（CPR中、アミオダロン代替）", "局所麻酔", "神経因性疼痛"],
        adult_doses={
            "CPR中VF/VT": "1-1.5mg/kg IV→0.5-0.75mg/kg 5-10分ごと（最大3mg/kg）",
            "局所麻酔": "0.5-2%液",
        },
        contraindications=["重度AVブロック", "Adams-Stokes症候群"],
        major_interactions=["β遮断薬（心臓毒性↑）", "抗不整脈薬（相加毒性）"],
        renal_adjustment="代謝産物蓄積に注意",
        hepatic_adjustment="重度肝障害では代謝低下→血中濃度↑→毒性リスク",
        monitoring=["血中濃度（治療域2-5μg/mL）", "ECG", "神経症状"],
        side_effects=["神経毒性（眠気・めまい・けいれん）", "心毒性（高用量）"],
        notes="アミオダロン優先であり、アミオダロン不使用時またはアミオダロン後の2次選択",
    ),
    "アデノシン": DrugInfo(
        name_ja="アデノシン", name_en="Adenosine",
        drug_class="抗不整脈薬（内因性プリン）",
        indications=["発作性上室性頻拍（PSVT）の停止", "WPW症候群のAF以外の上室性頻拍"],
        adult_doses={
            "PSVT": "6mg 急速IV（1-2秒で）→12mgを1-2回まで（1-2分ごと）",
        },
        contraindications=["心房細動/粗動（WPWを介した副路電動の可能性）", "重度AVブロック", "気管支喘息（気管支攣縮リスク）"],
        major_interactions=["テオフィリン（効果拮抗）", "カルバマゼピン（AVブロック↑）", "ジピリダモール（効果増強）"],
        renal_adjustment="特別な調整不要（半減期<10秒）",
        hepatic_adjustment="特別な調整不要",
        monitoring=["ECG（投与中連続モニタリング必須）", "血圧"],
        side_effects=["顔面紅潮", "胸部不快感（一過性）", "短時間のAVブロック", "気管支痙攣（喘息患者）"],
        notes="半減期約10秒。末梢静脈から急速投与し即座にフラッシュ。VTとPSVTの鑑別にも使用可",
    ),
    "ベラパミル": DrugInfo(
        name_ja="ベラパミル", name_en="Verapamil",
        drug_class="Ca拮抗薬（非ジヒドロピリジン系）",
        indications=["PSVT（アデノシン無効時）", "AF/AFL レートコントロール", "肥大型心筋症"],
        adult_doses={
            "PSVT": "5-10mg IV（2分以上かけて）",
            "AF レートコントロール": "5-10mg IV→1-3mg/h持続",
            "経口": "120-480mg/日（3分割）",
        },
        contraindications=["心室細動/頻拍", "WPW症候群（副路電動促進）", "β遮断薬との静注（AVブロック）", "重度心不全（EF<35%）"],
        major_interactions=["β遮断薬（AVブロック・心不全増悪）", "ジゴキシン（濃度↑）", "カルバマゼピン（濃度↑）"],
        renal_adjustment="特別な調整不要",
        hepatic_adjustment="重度肝障害では代謝低下→用量減量",
        monitoring=["ECG（PR間隔）", "血圧", "心不全症状"],
        side_effects=["徐脈・AVブロック", "低血圧", "便秘", "歯肉増殖（長期）"],
        notes="WPW+AFには禁忌（副路電動促進でVFリスク）。心不全EF<35%には禁忌",
    ),
    "ジゴキシン": DrugInfo(
        name_ja="ジゴキシン", name_en="Digoxin",
        drug_class="強心配糖体",
        indications=["慢性心不全（症状緩和）", "AF/AFL レートコントロール（安静時）"],
        adult_doses={
            "心不全": "0.125-0.25mg/日（高齢・腎障害は0.0625-0.125mg）",
            "AF": "0.125-0.25mg/日（安静時HR 60-80目標）",
        },
        contraindications=["WPW症候群（副路電動）", "心室頻拍", "肥大型閉塞性心筋症"],
        major_interactions=["アミオダロン（濃度2倍↑→半減量）", "ベラパミル（濃度↑）", "低カリウム血症（毒性↑）"],
        renal_adjustment="GFRに比例して用量減量（腎排泄90%）",
        hepatic_adjustment="特別な調整不要",
        monitoring=["血中濃度（目標0.5-0.9ng/mL）", "電解質（特にK/Mg）", "腎機能", "ECG"],
        side_effects=["ジゴキシン中毒（徐脈・AV block・悪心・視覚異常）", "低カリウム血症で毒性↑"],
        notes="ジゴキシン中毒はK補充とジゴキシン特異的抗体（Fab）で対処。治療域が狭く頻回モニタリング",
    ),

    # ── 血栓溶解薬 ─────────────────────────────────────────────
    "アルテプラーゼ": DrugInfo(
        name_ja="アルテプラーゼ（tPA）", name_en="Alteplase",
        drug_class="血栓溶解薬（組換え組織型プラスミノゲンアクティベータ）",
        indications=["急性虚血性脳卒中（発症4.5時間以内）", "大量肺塞栓症", "STEMIへの血栓溶解療法"],
        adult_doses={
            "脳卒中": "0.9mg/kg IV（最大90mg）、10%をボーラス、残90%を60分で点滴",
            "PE大量": "100mg IV 2時間で点滴（または体重<65kgは0.6mg/kg）",
            "STEMI": "15mgボーラス→0.75mg/kg 30分→0.5mg/kg 60分（最大100mg）",
        },
        contraindications=["3ヶ月以内の頭蓋内手術・脳卒中・頭部外傷", "活動性出血（月経除く）", "血圧>185/110（治療後も）", "颅内腫瘍・血管奇形", "PT>15s または抗凝固中"],
        major_interactions=["抗凝固薬・抗血小板薬（出血↑）"],
        renal_adjustment="特別な調整不要",
        hepatic_adjustment="特別な調整不要",
        monitoring=["神経症状（30分ごと）", "血圧（15分ごと）", "出血症状", "aPTT/PT"],
        side_effects=["頭蓋内出血（3-7%）", "全身出血", "血管浮腫（まれ）"],
        notes="脳卒中では発症4.5h以内、BP≤185/110に管理後投与。投与後24hは抗凝固薬・抗血小板薬禁忌",
    ),

    # ── 抗菌薬 ─────────────────────────────────────────────────
    "セフトリアキソン": DrugInfo(
        name_ja="セフトリアキソン", name_en="Ceftriaxone",
        drug_class="第3世代セファロスポリン",
        indications=["市中肺炎（入院）", "細菌性髄膜炎", "尿路感染症", "腹腔内感染（キノロン耐性）"],
        adult_doses={
            "市中肺炎": "1-2g IV/IM 1日1回",
            "髄膜炎": "2g IV 12時間ごと",
            "尿路感染症": "1g IV 1日1回",
        },
        contraindications=["セファロスポリン過敏症", "ペニシリン重度過敏症（交差10%）"],
        major_interactions=["カルシウム含有輸液（新生児：沈殿形成）", "ワルファリン（プロトロンビン時間延長）"],
        renal_adjustment="腎機能低下でも一般的に調整不要（胆汁排泄50%）",
        hepatic_adjustment="重度肝・腎両方の障害で用量制限（最大2g/日）",
        monitoring=["腎機能", "アレルギー症状", "偽膜性腸炎症状"],
        side_effects=["下痢", "発疹", "胆嚢内沈殿物（偽胆石症）", "二重感染"],
        notes="1日1回投与で利便性高い。カルシウム含有輸液との同一ルート投与は禁忌（新生児）",
    ),
    "セフェピム": DrugInfo(
        name_ja="セフェピム", name_en="Cefepime",
        drug_class="第4世代セファロスポリン",
        indications=["緑膿菌感染症", "院内肺炎", "発熱性好中球減少症", "複雑性尿路感染症"],
        adult_doses={
            "院内感染": "2g IV 8-12時間ごと（重症は8時間ごと）",
            "発熱性好中球減少症": "2g IV 8時間ごと",
        },
        contraindications=["セファロスポリン過敏症"],
        major_interactions=["アミノグリコシド系（腎毒性↑）"],
        renal_adjustment="CrCl<60で用量調整（CrCl 11-29: 2g 24h、<11: 0.5-1g 24h）",
        hepatic_adjustment="特別な調整不要",
        monitoring=["腎機能", "神経毒性（特に腎不全）", "アレルギー"],
        side_effects=["下痢", "発疹", "神経毒性（脳症・けいれん、特に腎不全）"],
        notes="緑膿菌などGNBに強力。腎不全での神経毒性（脳症・ミオクローヌス）に注意",
    ),
    "メロペネム": DrugInfo(
        name_ja="メロペネム", name_en="Meropenem",
        drug_class="カルバペネム系抗菌薬",
        indications=["重症院内感染症", "多剤耐性菌感染", "細菌性髄膜炎", "発熱性好中球減少症（高リスク）"],
        adult_doses={
            "重症感染症": "1-2g IV 8時間ごと（3-4時間かけて点滴で効果増）",
            "髄膜炎": "2g IV 8時間ごと",
        },
        contraindications=["カルバペネム過敏症"],
        major_interactions=["バルプロ酸（血中濃度著明低下→てんかん発作リスク）"],
        renal_adjustment="GFR 26-50: 1g 12h, GFR 10-25: 500mg 12h, GFR<10: 500mg 24h",
        hepatic_adjustment="特別な調整不要",
        monitoring=["腎機能", "てんかん患者でのバルプロ酸値"],
        side_effects=["下痢（偽膜性腸炎）", "けいれん（高用量、腎不全）", "発疹"],
        notes="バルプロ酸との禁忌的相互作用。ESBL産生菌に有効。最後の切り札として適切使用",
    ),
    "バンコマイシン": DrugInfo(
        name_ja="バンコマイシン", name_en="Vancomycin",
        drug_class="グリコペプチド系抗菌薬",
        indications=["MRSA感染症", "β-ラクタム耐性グラム陽性菌感染", "Clostridioides difficile（経口）"],
        adult_doses={
            "重症MRSA": "25-30mg/kg IVローディング→15-20mg/kg IV 8-12時間ごと（AUC/MIC 400-600目標）",
            "C.diff（経口）": "125mg 経口 6時間ごと×10日",
        },
        contraindications=["バンコマイシン過敏症（Red man症候群は過敏症ではない）"],
        major_interactions=["アミノグリコシド系（腎毒性↑）", "ループ利尿薬（耳毒性↑）"],
        renal_adjustment="TDMによる個別化用量設定が必須（腎機能に応じて大幅調整）",
        hepatic_adjustment="特別な調整不要",
        monitoring=["AUC/MIC（TDM）またはトラフ値（15-20μg/mL）", "腎機能", "耳毒性"],
        side_effects=["腎毒性", "耳毒性（高用量・長期）", "Red man症候群（急速投与で顔面紅潮）"],
        notes="TDM（治療薬物モニタリング）必須。60分以上かけて投与でRed man症候群予防",
    ),
    "レボフロキサシン": DrugInfo(
        name_ja="レボフロキサシン", name_en="Levofloxacin",
        drug_class="ニューキノロン系抗菌薬",
        indications=["市中肺炎（atypical含む）", "副鼻腔炎", "尿路感染症", "皮膚軟部組織感染"],
        adult_doses={
            "肺炎": "750mg IV/経口 1日1回×5日（または500mg×7-14日）",
            "尿路感染症": "500mg 1日1回×3-7日",
        },
        contraindications=["QT延長症候群", "重症筋無力症", "キノロン過敏症", "妊娠（相対）"],
        major_interactions=["多価金属（Ca/Mg/Al/Fe）との同時服用→吸収低下", "ワルファリン（INR↑）", "NSAIDs（けいれん閾値↓）"],
        renal_adjustment="CrCl<50で用量調整（750mg→500mg 1日1回、または750mg 48時間ごと）",
        hepatic_adjustment="特別な調整不要",
        monitoring=["QT間隔（ECG）", "血糖（高血糖・低血糖）", "腱障害症状"],
        side_effects=["腱炎・腱断裂（アキレス腱）", "QT延長", "末梢神経障害", "光線過敏症", "血糖異常"],
        notes="高齢者・ステロイド使用者はアキレス腱断裂リスク高。投与中は過度な運動を控える",
    ),
    "アジスロマイシン": DrugInfo(
        name_ja="アジスロマイシン", name_en="Azithromycin",
        drug_class="マクロライド系抗菌薬",
        indications=["市中肺炎（非定型）", "咽頭炎・扁桃炎", "性感染症（クラミジア）", "マイコプラズマ肺炎"],
        adult_doses={
            "市中肺炎": "500mg/日 IV×2日→250mg 経口×3日（または500mg 経口×3日）",
            "クラミジア": "1g 単回経口",
        },
        contraindications=["QT延長症候群", "重度肝障害", "マクロライド過敏症"],
        major_interactions=["QT延長薬（相加的リスク）", "ワルファリン（INR↑）", "シクロスポリン（濃度↑）"],
        renal_adjustment="特別な調整不要",
        hepatic_adjustment="重度肝障害では禁忌",
        monitoring=["QT間隔", "肝機能（長期）"],
        side_effects=["消化器症状（最多）", "QT延長", "心臓性猝死リスク（わずか）"],
        notes="半減期68時間（組織中はさらに長い）。心血管リスク患者でのQT延長に注意",
    ),
    "ピペラシリン/タゾバクタム": DrugInfo(
        name_ja="ピペラシリン/タゾバクタム", name_en="Piperacillin/Tazobactam",
        drug_class="β-ラクタム/β-ラクタマーゼ阻害薬配合剤",
        indications=["院内肺炎", "複雑性腹腔内感染症", "複雑性尿路感染症", "発熱性好中球減少症"],
        adult_doses={
            "院内感染": "4.5g IV 6-8時間ごと（または3.375g 8時間ごと）",
            "重症": "4.5g IV 8時間ごと（30分以上かけて投与、または延長投与4h）",
        },
        contraindications=["ペニシリン過敏症"],
        major_interactions=["バンコマイシン（腎毒性↑（議論あり））", "メトトレキサート（排泄低下）"],
        renal_adjustment="CrCl<20では8時間ごとを12時間ごとに変更",
        hepatic_adjustment="特別な調整不要",
        monitoring=["腎機能", "アレルギー", "電解質（Na含有量多い）"],
        side_effects=["下痢", "発疹", "低カリウム血症", "神経毒性（高用量）"],
        notes="広域スペクトル（ESBL産生菌には不十分な場合あり）。延長点滴で時間依存性薬効最大化",
    ),
    "アンピシリン": DrugInfo(
        name_ja="アンピシリン", name_en="Ampicillin",
        drug_class="アミノペニシリン系抗菌薬",
        indications=["細菌性髄膜炎（リステリア）", "腸球菌感染症", "B群連鎖球菌感染"],
        adult_doses={
            "髄膜炎（リステリア）": "2g IV 4時間ごと",
            "腸球菌心内膜炎": "2g IV 4時間ごと（ゲンタマイシン併用）",
        },
        contraindications=["ペニシリン過敏症"],
        major_interactions=["アロプリノール（発疹↑）"],
        renal_adjustment="GFR<30では用量調整（6時間ごと→8-12時間ごと）",
        hepatic_adjustment="特別な調整不要",
        monitoring=["腎機能", "アレルギー"],
        side_effects=["発疹（20%、EBV感染者では90%以上）", "下痢"],
        notes="リステリア髄膜炎には必須（第3世代セファロスポリンは無効）",
    ),
    "クリンダマイシン": DrugInfo(
        name_ja="クリンダマイシン", name_en="Clindamycin",
        drug_class="リンコマイシン系抗菌薬",
        indications=["嫌気性菌感染症", "歯科感染症", "皮膚軟部組織感染症（MRSA含む）", "トキシックショック症候群"],
        adult_doses={
            "重症感染症": "600-900mg IV 8時間ごと",
            "皮膚感染症": "300-450mg 経口 8時間ごと",
        },
        contraindications=["重度肝障害（相対）"],
        major_interactions=["神経筋遮断薬（効果増強）"],
        renal_adjustment="特別な調整不要",
        hepatic_adjustment="重度肝障害では慎重（代謝低下）",
        monitoring=["腸炎症状（C.diff）", "肝機能（長期）"],
        side_effects=["C.difficile関連腸炎（リスク高い）", "下痢", "肝酵素上昇"],
        notes="嫌気性菌・グラム陽性球菌に有効。C.diff最大リスク因子の一つ。可能なら短期間使用",
    ),
    "ドキシサイクリン": DrugInfo(
        name_ja="ドキシサイクリン", name_en="Doxycycline",
        drug_class="テトラサイクリン系抗菌薬",
        indications=["マイコプラズマ肺炎", "クラミジア感染症", "ライム病", "マラリア予防", "ブルセラ症（リファンピシン併用）"],
        adult_doses={
            "市中肺炎": "100mg IV/経口 12時間ごと",
            "クラミジア": "100mg 経口 12時間ごと×7日",
            "マラリア予防": "100mg/日（出発1-2日前から帰国後4週まで）",
        },
        contraindications=["妊娠（歯牙黄染・骨格成長障害）", "8歳未満小児（原則）"],
        major_interactions=["多価金属（吸収低下）", "ワルファリン（INR↑）", "レチノイン酸（頭蓋内圧亢進）"],
        renal_adjustment="特別な調整不要（胆汁排泄主体）",
        hepatic_adjustment="重度肝障害では慎重",
        monitoring=["光線過敏症", "食道潰瘍症状"],
        side_effects=["光線過敏症", "消化器症状", "食道潰瘍（就寝前服用・不十分な水分）", "歯牙黄染（小児）"],
        notes="食事と一緒に服用可（吸収は若干低下）。就寝前服用後は横にならない（食道炎予防）",
    ),

    # ── 鎮痛・鎮静薬 ───────────────────────────────────────────
    "モルヒネ": DrugInfo(
        name_ja="モルヒネ", name_en="Morphine",
        drug_class="オピオイド鎮痛薬（μ受容体作動薬）",
        indications=["重症疼痛管理", "急性心不全の呼吸困難", "ACS疼痛（注意が必要）"],
        adult_doses={
            "重症疼痛": "2-4mg IV 15-30分ごと（タイトレーション）",
            "慢性疼痛": "5-30mg 経口 4-6時間ごと",
        },
        contraindications=["重度呼吸抑制", "麻痺性腸閉塞", "急性アルコール中毒"],
        major_interactions=["CNS抑制薬（呼吸抑制↑）", "MAO阻害薬（セロトニン症候群リスク）"],
        renal_adjustment="GFR<30ではモルフィン-6-グルクロニド蓄積→活性代謝物蓄積→呼吸抑制リスク",
        hepatic_adjustment="重度肝障害で代謝低下→少量から開始",
        monitoring=["呼吸数・SpO2", "意識レベル", "疼痛スケール（NRS）", "腸蠕動音"],
        side_effects=["呼吸抑制", "悪心嘔吐", "便秘（制酸剤必須）", "依存性", "掻痒感（ヒスタミン放出）"],
        notes="ACS疼痛での使用は議論あり（消化管虚血や抗血小板薬吸収低下の可能性）。拮抗薬はナロキソン",
    ),
    "フェンタニル": DrugInfo(
        name_ja="フェンタニル", name_en="Fentanyl",
        drug_class="オピオイド鎮痛薬（μ受容体作動薬、高脂溶性）",
        indications=["ICU鎮痛", "急性疼痛（タイトレーション）", "経皮吸収貼付剤（慢性疼痛）"],
        adult_doses={
            "ICU鎮痛": "25-100μg IV ボーラス→25-200μg/h持続",
            "急性疼痛": "25-50μg IV 5-15分ごと（タイトレーション）",
        },
        contraindications=["重度呼吸抑制"],
        major_interactions=["CYP3A4阻害薬（血中濃度↑）", "CNS抑制薬（呼吸抑制↑）"],
        renal_adjustment="腎機能低下でも安全に使用可（活性代謝物蓄積なし）",
        hepatic_adjustment="重度肝障害では半減期延長",
        monitoring=["呼吸数・SpO2", "疼痛スケール", "鎮静レベル（RASS）"],
        side_effects=["呼吸抑制", "胸壁硬直（急速投与）", "悪心嘔吐", "瘙痒感"],
        notes="腎不全でもモルヒネより安全。急速IV投与で胸壁硬直（木の幹症状）リスク。フェンタニルパッチは慢性疼痛専用",
    ),
    "プロポフォール": DrugInfo(
        name_ja="プロポフォール", name_en="Propofol",
        drug_class="静脈麻酔薬/鎮静薬（GABA作動薬）",
        indications=["ICU鎮静", "全身麻酔誘導・維持", "短時間処置の鎮静"],
        adult_doses={
            "ICU鎮静": "5-50μg/kg/min IV持続（RASS -2から0目標）",
            "麻酔誘導": "1.5-2.5mg/kg IV",
        },
        contraindications=["卵・大豆アレルギー（相対）", "18歳未満への集中治療鎮静（プロポフォール症候群）"],
        major_interactions=["CNS抑制薬（鎮静増強）", "オピオイド（相加的呼吸抑制）"],
        renal_adjustment="特別な調整不要",
        hepatic_adjustment="特別な調整不要",
        monitoring=["血中脂質（長期高用量）", "腎機能・CPK（プロポフォール症候群）", "血圧", "鎮静レベル（RASS）"],
        side_effects=["低血圧", "呼吸抑制", "プロポフォール症候群（高用量長期：アシドーシス・横紋筋融解）", "注入部疼痛"],
        notes="油脂成分（1.1kcal/mL）のカロリーを栄養管理に算入。開封後12時間以内使用",
    ),
    "ミダゾラム": DrugInfo(
        name_ja="ミダゾラム", name_en="Midazolam",
        drug_class="ベンゾジアゼピン系鎮静薬",
        indications=["ICU鎮静", "けいれん重積（救急）", "処置前鎮静"],
        adult_doses={
            "ICU鎮静": "1-5mg/h IV持続（RASS -2から0目標）",
            "けいれん重積": "0.1-0.2mg/kg IV/IM/IN",
        },
        contraindications=["重度呼吸不全（相対）", "急性閉塞隅角緑内障"],
        major_interactions=["CYP3A4阻害薬（フルコナゾール等→血中濃度↑）", "CNS抑制薬"],
        renal_adjustment="活性代謝物（1-OH-ミダゾラム）蓄積→長期ICU鎮静では過鎮静リスク",
        hepatic_adjustment="重度肝障害では代謝低下→蓄積",
        monitoring=["鎮静レベル（RASS）", "呼吸状態", "長期では蓄積（週単位）"],
        side_effects=["過鎮静", "呼吸抑制", "低血圧", "健忘（短所ではなく長所の場合も）"],
        notes="拮抗薬：フルマゼニル（半減期短く再鎮静注意）。長期鎮静でプロポフォールより覚醒遅延",
    ),
    "ケタミン": DrugInfo(
        name_ja="ケタミン", name_en="Ketamine",
        drug_class="解離性麻酔薬（NMDA受容体拮抗薬）",
        indications=["気道確保困難患者のRSI", "重症喘息の鎮静", "難治性疼痛"],
        adult_doses={
            "RSI": "1-2mg/kg IV",
            "鎮痛補助": "0.1-0.5mg/kg/h IV持続",
        },
        contraindications=["重度高血圧（未治療）", "甲状腺機能亢進症（相対）", "頭蓋内圧亢進（相対：最近の見直しあり）"],
        major_interactions=["アトロピン（心拍数制御）", "ベンゾジアゼピン（回復せん妄↓）"],
        renal_adjustment="特別な調整不要",
        hepatic_adjustment="重度肝障害では代謝低下",
        monitoring=["血圧・心拍数（カテコラミン放出効果）", "呼吸状態"],
        side_effects=["回復せん妄・幻覚（ベンゾジアゼピンで軽減）", "高血圧・頻脈", "唾液・気道分泌増加"],
        notes="気管支拡張作用があり重症喘息に有用。自発呼吸を維持しやすい（解離麻酔）",
    ),
    "デクスメデトミジン": DrugInfo(
        name_ja="デクスメデトミジン", name_en="Dexmedetomidine",
        drug_class="α2受容体作動薬（鎮静薬）",
        indications=["ICU鎮静（覚醒鎮静）", "アルコール離脱（補助）"],
        adult_doses={
            "ICU鎮静": "0.2-1.5μg/kg/h IV持続（RASS 0から-1目標）",
        },
        contraindications=["重度徐脈", "高度AVブロック"],
        major_interactions=["他の鎮静薬（相加的）", "降圧薬（低血圧↑）"],
        renal_adjustment="特別な調整不要",
        hepatic_adjustment="重度肝障害では半減期延長→低用量から",
        monitoring=["血圧・心拍数", "鎮静レベル（RASS）"],
        side_effects=["低血圧", "徐脈", "口腔乾燥"],
        notes="呼吸抑制が少なく覚醒鎮静が可能。人工呼吸器離脱に適する。MENDS2試験でせん妄・死亡率での優位性が一部示唆",
    ),

    # ── 神経系薬 ───────────────────────────────────────────────
    "フェニトイン": DrugInfo(
        name_ja="フェニトイン", name_en="Phenytoin",
        drug_class="抗てんかん薬（Na+チャネル阻害）",
        indications=["けいれん重積（BZD無効後）", "てんかん（フォーカル発作）"],
        adult_doses={
            "けいれん重積": "20mg/kg IV（最大速度50mg/min）",
            "維持": "5-7mg/kg/日（2分割）",
        },
        contraindications=["Adams-Stokes症候群", "高度AVブロック", "妊娠（催奇形性）"],
        major_interactions=["多数のCYP450誘導（ワルファリン↓、OCP↓、スタチン↓等）", "多数の薬剤と相互作用"],
        renal_adjustment="蛋白結合低下（遊離型↑）に注意（血中濃度解釈）",
        hepatic_adjustment="重度肝障害で代謝低下",
        monitoring=["血中濃度（目標10-20μg/mL）", "ECG（投与中）", "歯肉増殖症", "肝機能"],
        side_effects=["注入部壊死（アルカリ性）", "低血圧・徐脈（急速IV）", "歯肉増殖症", "多毛症", "Stevens-Johnson症候群（まれ）"],
        notes="ホスフェニトイン（プロドラッグ）は筋注・末梢静脈投与が可能で安全性が高い",
    ),
    "バルプロ酸": DrugInfo(
        name_ja="バルプロ酸ナトリウム", name_en="Valproate",
        drug_class="抗てんかん薬（多機序：GABA増強等）",
        indications=["てんかん（各種発作）", "双極性障害", "片頭痛予防"],
        adult_doses={
            "てんかん重積": "30mg/kg IV（5-10分かけて）",
            "てんかん維持": "10-30mg/kg/日（2-3分割）",
            "双極性障害": "750-2000mg/日",
        },
        contraindications=["妊娠（神経管欠損：催奇形性高い）", "重度肝障害", "ミトコンドリア病（Alpers病）"],
        major_interactions=["カルバペネム（バルプロ酸濃度著明低下→てんかん発作）", "ラモトリギン（濃度↑）"],
        renal_adjustment="特別な調整不要",
        hepatic_adjustment="重度肝障害では禁忌",
        monitoring=["血中濃度（目標50-100μg/mL）", "肝機能", "血小板数", "アンモニア"],
        side_effects=["肝毒性（特に2歳未満）", "高アンモニア血症", "血小板減少", "体重増加", "催奇形性"],
        notes="妊娠可能年齢女性への投与は特に慎重に。カルバペネム系抗菌薬との組み合わせでバルプロ酸濃度激減",
    ),
    "レベチラセタム": DrugInfo(
        name_ja="レベチラセタム", name_en="Levetiracetam",
        drug_class="抗てんかん薬（SV2A結合）",
        indications=["てんかん（各種発作）", "けいれん重積（補助）"],
        adult_doses={
            "てんかん重積（補助）": "60mg/kg IV（最大4500mg、15分かけて）",
            "維持": "500-3000mg/日（2分割）",
        },
        contraindications=["特記なし（比較的安全）"],
        major_interactions=["少ない（CYP非依存性）"],
        renal_adjustment="GFR<80で用量調整（GFR<30は最大50%減量）",
        hepatic_adjustment="特別な調整不要",
        monitoring=["腎機能", "行動異常（易怒性・攻撃性）"],
        side_effects=["神経過敏・易怒性", "傾眠", "筋力低下"],
        notes="相互作用が少なく使いやすい。腎機能に応じた用量調整が必要。行動面の副作用が問題になることあり",
    ),
    "マンニトール": DrugInfo(
        name_ja="マンニトール", name_en="Mannitol",
        drug_class="浸透圧利尿薬",
        indications=["頭蓋内圧亢進症", "急性緑内障発作", "急性腎不全予防（エビデンス限定）"],
        adult_doses={
            "頭蓋内圧亢進": "0.5-1.5g/kg IV（20%液、15-30分かけて）、必要に応じて反復",
        },
        contraindications=["心不全（容量負荷）", "高度腎不全（無尿）", "重度脱水"],
        major_interactions=["ループ利尿薬（相加的脱水・電解質異常）"],
        renal_adjustment="無尿・重度腎不全では禁忌（蓄積でARDS・電解質異常）",
        hepatic_adjustment="特別な調整不要",
        monitoring=["血清Na・浸透圧（目標315-320mOsm）", "尿量", "電解質", "神経学的評価"],
        side_effects=["電解質異常", "腎毒性（過剰投与）", "反跳性頭蓋内圧上昇（長期使用）"],
        notes="血清浸透圧>320mOsm/kgになると腎毒性リスク増加。高張食塩水も代替として使用",
    ),
    "デキサメタゾン": DrugInfo(
        name_ja="デキサメタゾン", name_en="Dexamethasone",
        drug_class="副腎皮質ステロイド（強力なグルコルチコイド）",
        indications=["細菌性髄膜炎（抗菌薬前）", "脳浮腫（腫瘍）", "ARDS", "COVID-19重症", "悪心嘔吐（化学療法）"],
        adult_doses={
            "髄膜炎": "0.15mg/kg IV 6時間ごと×4日（抗菌薬15-20分前）",
            "脳腫瘍浮腫": "4-10mg IV 6-8時間ごと",
            "ARDS": "6mg/日 IV×10日（RECOVERY試験）",
        },
        contraindications=["真菌感染症（全身）", "生ワクチン接種（同時禁忌）"],
        major_interactions=["NSAIDs（消化管潰瘍↑）", "糖尿病薬（血糖↑）", "抗菌薬（免疫抑制）"],
        renal_adjustment="特別な調整不要",
        hepatic_adjustment="特別な調整不要",
        monitoring=["血糖（特に糖尿病）", "感染症", "骨密度（長期）"],
        side_effects=["高血糖", "消化管潰瘍（NSAIDs併用で↑）", "免疫抑制", "骨粗鬆症（長期）", "低カリウム血症"],
        notes="細菌性髄膜炎：抗菌薬15-20分前に投与（炎症カスケード抑制が目的）。COVID-19重症でRCT証明",
    ),
    "ニモジピン": DrugInfo(
        name_ja="ニモジピン", name_en="Nimodipine",
        drug_class="Ca拮抗薬（脳血管選択的）",
        indications=["くも膜下出血後の脳血管攣縮予防"],
        adult_doses={
            "SAH後": "60mg 経口 4時間ごと×21日（または2mg/h IV持続、好みによる）",
        },
        contraindications=["重度肝障害", "低血圧"],
        major_interactions=["強力CYP3A4阻害薬（濃度↑）", "降圧薬（低血圧↑）"],
        renal_adjustment="特別な調整不要",
        hepatic_adjustment="重度肝障害では用量半減",
        monitoring=["血圧（4時間ごと）", "神経症状"],
        side_effects=["低血圧", "頭痛", "顔面紅潮"],
        notes="SAH後の脳血管攣縮予防：SAH診断後すぐに開始。経口投与が IV投与より簡便で同等の効果",
    ),

    # ── 代謝・内分泌薬 ─────────────────────────────────────────
    "インスリン（超速効型）": DrugInfo(
        name_ja="インスリン リスプロ/アスパルト/グルリジン（超速効型）", name_en="Insulin Lispro/Aspart/Glulisine",
        drug_class="超速効型インスリン",
        indications=["食後高血糖の補正", "DKA（速効型と同等）", "血糖コントロール"],
        adult_doses={
            "食前": "4-20U 皮下注（食直前）",
            "補正": "（現血糖-目標血糖）/補正係数",
        },
        contraindications=["低血糖"],
        major_interactions=["β遮断薬（低血糖症状マスク）", "サリチル酸（低血糖↑）"],
        renal_adjustment="GFR低下でインスリン必要量↓（腎でのインスリン分解↓）",
        hepatic_adjustment="重度肝障害で低血糖リスク↑",
        monitoring=["血糖（食前後）", "低血糖症状"],
        side_effects=["低血糖", "注射部位脂肪萎縮/肥大"],
        notes="超速効型は食直前（または食直後）に投与。使用前に混濁・凝集がないか確認",
    ),
    "インスリン（持効型）": DrugInfo(
        name_ja="インスリン グラルギン/デテミル/デグルデク（持効型）", name_en="Insulin Glargine/Detemir/Degludec",
        drug_class="持効型インスリン",
        indications=["1型・2型糖尿病の基礎インスリン"],
        adult_doses={
            "基礎": "体重×0.2U/日（開始）、FPG 90-120mg/dLになるよう調整",
        },
        contraindications=["低血糖"],
        major_interactions=["β遮断薬（低血糖症状マスク）"],
        renal_adjustment="GFR低下でインスリン必要量↓",
        hepatic_adjustment="重度肝障害で低血糖リスク↑",
        monitoring=["空腹時血糖", "低血糖症状"],
        side_effects=["低血糖（速効型より少ない）", "注射部位反応"],
        notes="グラルギンとNPHインスリンは混合不可。デグルデクは最長半減期（42h）で注射時間の柔軟性あり",
    ),
    "グルカゴン": DrugInfo(
        name_ja="グルカゴン", name_en="Glucagon",
        drug_class="膵ホルモン",
        indications=["重症低血糖（静脈路確保不能時）", "β遮断薬過量（心停止の補助）"],
        adult_doses={
            "低血糖": "1mg 筋注/皮下注/IV",
            "β遮断薬過量": "3-5mg IV→0.07mg/kg/h持続",
        },
        contraindications=["褐色細胞腫", "インスリノーマ"],
        major_interactions=["ワルファリン（PT延長）"],
        renal_adjustment="特別な調整不要",
        hepatic_adjustment="特別な調整不要",
        monitoring=["血糖（投与後15-30分）", "嘔吐症状"],
        side_effects=["悪心嘔吐（意識障害時は誤嚥リスク）", "頭痛", "血糖上昇"],
        notes="低血糖に対して意識がなく静脈路確保できない場合に筋注。意識回復後は経口摂取を促す",
    ),
    "チアミン（ビタミンB1）": DrugInfo(
        name_ja="チアミン（ビタミンB1）", name_en="Thiamine",
        drug_class="水溶性ビタミン",
        indications=["Wernicke脳症予防・治療", "アルコール依存症", "糖液投与前（アルコール症患者）"],
        adult_doses={
            "Wernicke脳症": "500mg IV 8時間ごと×3日（重症）→250mg/日×5日",
            "予防": "100mg IV/経口 1日1回",
        },
        contraindications=["過敏症（静注は速度管理）"],
        major_interactions=["ループ利尿薬（ビタミンB1欠乏↑）"],
        renal_adjustment="特別な調整不要",
        hepatic_adjustment="特別な調整不要",
        monitoring=["神経症状（眼球運動・失調・意識）"],
        side_effects=["アナフィラキシー（急速IV）"],
        notes="糖液（ブドウ糖）投与前に必ず投与（糖代謝にB1が消費）。疑いがあれば経験的投与",
    ),
    "N-アセチルシステイン": DrugInfo(
        name_ja="N-アセチルシステイン（NAC）", name_en="N-Acetylcysteine",
        drug_class="解毒薬/抗酸化薬",
        indications=["アセトアミノフェン中毒（第一選択）", "造影剤誘発腎症予防（証拠限定的）"],
        adult_doses={
            "アセトアミノフェン中毒": "150mg/kg IV 15分→12.5mg/kg/h 4時間→6.25mg/kg/h 16時間",
            "造影剤予防": "600mg 経口 12時間ごと×2日",
        },
        contraindications=["特記なし（アレルギー様反応あり）"],
        major_interactions=["特記なし"],
        renal_adjustment="特別な調整不要",
        hepatic_adjustment="特別な調整不要",
        monitoring=["アセトアミノフェン血中濃度（Rumack-Matthewノモグラム）", "肝機能", "PT"],
        side_effects=["アナフィラキシー様反応（IVでは3-20%）", "悪心嘔吐"],
        notes="アセトアミノフェン中毒：4時間後の血中濃度をノモグラムに当てはめて治療適応判断。8時間以内投与が最大効果",
    ),
    "フルドロコルチゾン": DrugInfo(
        name_ja="フルドロコルチゾン", name_en="Fludrocortisone",
        drug_class="ミネラルコルチコイド",
        indications=["原発性副腎不全（アジソン病）", "低アルドステロン症", "起立性低血圧（POTS等）"],
        adult_doses={
            "副腎不全": "0.05-0.2mg/日 経口",
            "POTS": "0.05-0.1mg/日",
        },
        contraindications=["うっ血性心不全", "重度高血圧"],
        major_interactions=["NSAIDs（Na貯留↑）", "カリウム利尿薬（低K↑）"],
        renal_adjustment="特別な調整不要",
        hepatic_adjustment="特別な調整不要",
        monitoring=["血圧（高血圧チェック）", "電解質（Na/K）", "浮腫"],
        side_effects=["高血圧", "低カリウム血症", "浮腫"],
        notes="副腎不全の治療ではハイドロコルチゾン（グルコルチコイド）と併用",
    ),
    "ハイドロコルチゾン": DrugInfo(
        name_ja="ハイドロコルチゾン", name_en="Hydrocortisone",
        drug_class="副腎皮質ステロイド（グルコ/ミネラルコルチコイド）",
        indications=["副腎クリーゼ（緊急）", "敗血症性ショック（ステロイド）", "アジソン病補充療法"],
        adult_doses={
            "副腎クリーゼ": "100mg IV ボーラス→200mg/日持続（または50mg 6時間ごと）",
            "敗血症ショック": "200mg/日IV持続（目標MAP達成不良時）",
            "補充療法": "15-20mg/日 経口（朝多め）",
        },
        contraindications=["真菌感染症（全身、相対）"],
        major_interactions=["NSAIDs（消化管潰瘍）", "糖尿病薬（血糖↑）"],
        renal_adjustment="特別な調整不要",
        hepatic_adjustment="特別な調整不要",
        monitoring=["血糖", "電解質", "血圧", "感染症"],
        side_effects=["高血糖", "高血圧", "消化管潰瘍", "免疫抑制"],
        notes="副腎クリーゼ：まず生理食塩水1L急速点滴、次いでハイドロコルチゾン100mg IV。ストレス時は2-3倍量に増量",
    ),
    "レボチロキシン": DrugInfo(
        name_ja="レボチロキシン（T4）", name_en="Levothyroxine",
        drug_class="甲状腺ホルモン製剤",
        indications=["甲状腺機能低下症", "粘液水腫性昏睡（緊急）", "甲状腺癌術後補充"],
        adult_doses={
            "甲状腺機能低下症": "1.6μg/kg/日（開始は25-50μg/日→TSHを見ながら調整）",
            "粘液水腫性昏睡": "300-500μg IVローディング→50-100μg/日IV（T3静注との合わせ技も）",
        },
        contraindications=["未治療の副腎不全（コルチゾール不足下で甲状腺補充は副腎クリーゼリスク）"],
        major_interactions=["ワルファリン（INR↑）", "制酸薬/Ca/鉄剤（吸収↓）", "β遮断薬（心拍数↑を隠す）"],
        renal_adjustment="特別な調整不要",
        hepatic_adjustment="特別な調整不要",
        monitoring=["TSH（6-8週ごとまで安定したら年1回）", "FT4", "心症状（頻脈・動悸）"],
        side_effects=["過量：頻脈・不整脈・体重減少・骨粗鬆症", "過少：症状持続"],
        notes="空腹時服用（朝食30-60分前）が最も吸収良好。TSH正常化に6-8週かかる",
    ),

    # ── 解毒薬 ─────────────────────────────────────────────────
    "フルマゼニル": DrugInfo(
        name_ja="フルマゼニル", name_en="Flumazenil",
        drug_class="ベンゾジアゼピン拮抗薬",
        indications=["ベンゾジアゼピン過量の鑑別・治療", "処置後の鎮静拮抗"],
        adult_doses={
            "BZD過量": "0.2mg IV（30秒かけて）→1分後に0.3mg→0.5mgを繰り返し（最大3mg）",
        },
        contraindications=["BZDによるけいれん抑制患者（けいれん再発）", "三環系抗うつ薬の同時過量（けいれん↑）"],
        major_interactions=["特記なし"],
        renal_adjustment="特別な調整不要",
        hepatic_adjustment="重度肝障害では半減期延長",
        monitoring=["鎮静レベル", "けいれん症状（投与後）", "再鎮静（BZDの半減期が長い場合）"],
        side_effects=["けいれん（BZD依存・三環系過量）", "不安・興奮", "再鎮静（半減期1時間）"],
        notes="半減期が約1時間と短く、BZDより半減期が長ければ再鎮静に注意。監視が必要",
    ),
    "ナロキソン": DrugInfo(
        name_ja="ナロキソン", name_en="Naloxone",
        drug_class="オピオイド拮抗薬",
        indications=["オピオイド過量（呼吸抑制）", "オピオイド誘発便秘（末梢選択的：メチルナルトレキソン）"],
        adult_doses={
            "オピオイド過量": "0.4-2mg IV/IM/SC/IN（2-3分ごとに反復、最大10mg）",
            "慢性オピオイド依存の低用量": "0.1-0.2mg IV（離脱症状軽減）",
        },
        contraindications=["ナロキソン過敏症"],
        major_interactions=["オピオイド（拮抗）"],
        renal_adjustment="特別な調整不要",
        hepatic_adjustment="特別な調整不要",
        monitoring=["呼吸数・SpO2", "意識レベル", "疼痛（オピオイド依存患者では急性疼痛再燃）"],
        side_effects=["急性オピオイド離脱症状（嘔吐・頻脈・高血圧・興奮）", "再鎮静（半減期30-90分）"],
        notes="半減期が短く再鎮静しやすい（モルヒネより半減期が短い）。必要に応じて持続投与。再鎮静モニタリングが必須",
    ),
    "プロタミン": DrugInfo(
        name_ja="プロタミン", name_en="Protamine",
        drug_class="ヘパリン拮抗薬",
        indications=["ヘパリン過量の中和", "体外循環後のヘパリン中和"],
        adult_doses={
            "UFH中和": "1mg プロタミン：100U UFH（最後の3-4時間分のUFH量を考慮）",
        },
        contraindications=["魚アレルギー（相対）", "プロタミン亜鉛インスリン使用者（相対）"],
        major_interactions=["ヘパリン（拮抗）"],
        renal_adjustment="特別な調整不要",
        hepatic_adjustment="特別な調整不要",
        monitoring=["APTT（中和後15分後）", "血圧（低血圧リスク）", "アレルギー症状"],
        side_effects=["低血圧", "徐脈", "アナフィラキシー（魚アレルギー・不妊男性に多い）"],
        notes="急速投与で低血圧リスク（10分以上かけて）。低分子ヘパリンの中和は部分的（約60-75%）",
    ),
    "ビタミンK": DrugInfo(
        name_ja="ビタミンK（フィトナジオン）", name_en="Vitamin K1 (Phytonadione)",
        drug_class="ビタミンK製剤",
        indications=["ワルファリン過量・出血", "ワルファリン効果急速中和（緊急時はPCC優先）", "新生児ビタミンK欠乏予防"],
        adult_doses={
            "ワルファリン過量（出血なし）": "1-5mg 経口（24h後にPT確認）",
            "ワルファリン過量（重篤出血）": "5-10mg IVゆっくり（PCC4因子と併用）",
        },
        contraindications=["血栓塞栓症（大量ビタミンK投与）"],
        major_interactions=["ワルファリン（効果拮抗）"],
        renal_adjustment="特別な調整不要",
        hepatic_adjustment="重度肝障害では効果不十分（凝固因子産生能低下）",
        monitoring=["PT-INR（6-8時間後）", "出血症状"],
        side_effects=["アナフィラキシー（IV急速）", "過量で長期ワルファリン抵抗性"],
        notes="緊急出血にはPCC（4因子プロトロンビン複合体製剤）を優先。ビタミンKはPT正常化に6-8時間",
    ),
    "ダントロレン": DrugInfo(
        name_ja="ダントロレン", name_en="Dantrolene",
        drug_class="筋弛緩薬（筋小胞体Caチャネル阻害）",
        indications=["悪性高熱症（第一選択）", "悪性症候群（補助）"],
        adult_doses={
            "悪性高熱症": "2.5mg/kg IVボーラス→1mg/kg 繰り返し（最大10mg/kg）",
            "悪性症候群": "25mg 経口 2-3回/日→100-600mg/日",
        },
        contraindications=["重度肝障害"],
        major_interactions=["カルシウム拮抗薬（心臓毒性↑）"],
        renal_adjustment="特別な調整不要",
        hepatic_adjustment="重度肝障害では禁忌",
        monitoring=["体温", "CPK", "肝機能", "筋力（過度な弛緩に注意）"],
        side_effects=["肝毒性（長期）", "筋力低下", "眠気"],
        notes="悪性高熱症は致死的緊急症。100mgバイアルを60mLの注射用水で溶解（溶けにくい）。手術室に常備必要",
    ),

    # ── 消化器薬 ───────────────────────────────────────────────
    "オメプラゾール": DrugInfo(
        name_ja="オメプラゾール", name_en="Omeprazole",
        drug_class="プロトンポンプ阻害薬（PPI）",
        indications=["消化性潰瘍", "逆流性食道炎", "H.pylori除菌（3剤療法）", "NSAIDs潰瘍予防"],
        adult_doses={
            "消化性潰瘍": "20-40mg/日 経口（PU治療：20-40mg 4-8週）",
            "GERD": "20mg/日",
            "H.pylori除菌": "20mg 1日2回（7-14日）",
        },
        contraindications=["アタザナビル（抗HIV薬）との併用（吸収低下）"],
        major_interactions=["クロピドグレル（CYP2C19競合→抗血小板効果↓）", "メトトレキサート（排泄低下→毒性↑）"],
        renal_adjustment="特別な調整不要",
        hepatic_adjustment="重度肝障害は20mg/日まで",
        monitoring=["Mg（長期投与）", "骨密度（長期）", "下痢（クロストリジウム）"],
        side_effects=["頭痛", "下痢・便秘", "低Mg血症（長期）", "C.diff感染↑（長期）", "骨折リスク（長期）"],
        notes="長期投与は必要最低限に。PPI依存性胃炎（リバウンド過酸症）に注意。クロピドグレルとの使用はラベプラゾールやパントプラゾールを優先",
    ),
    "オクトレオチド": DrugInfo(
        name_ja="オクトレオチド", name_en="Octreotide",
        drug_class="ソマトスタチンアナログ",
        indications=["食道静脈瘤出血（補助）", "膵外分泌腫瘍（VIPoma等）", "先端巨大症"],
        adult_doses={
            "静脈瘤出血": "50μg IVボーラス→25-50μg/h持続（5日間）",
            "先端巨大症": "100-200μg SC 8時間ごと",
        },
        contraindications=["過敏症"],
        major_interactions=["インスリン・スルホニル尿素薬（低血糖↑ or 高血糖）", "サイクロスポリン（吸収低下）"],
        renal_adjustment="特別な調整不要",
        hepatic_adjustment="重度肝障害は半減期延長→半量",
        monitoring=["血糖", "甲状腺機能", "胆石（長期）"],
        side_effects=["低血糖または高血糖", "消化器症状", "胆石形成（長期）", "徐脈"],
        notes="食道静脈瘤出血：内視鏡的治療と組み合わせる。β遮断薬より迅速に効果発現",
    ),
    "ラクツロース": DrugInfo(
        name_ja="ラクツロース", name_en="Lactulose",
        drug_class="浸透圧性下剤/NH3低減薬",
        indications=["便秘", "肝性脳症（高アンモニア血症）"],
        adult_doses={
            "肝性脳症": "30-45mL 経口 3-4回/日（目標：1日2-4回の軟便）",
            "便秘": "15-30mL/日",
        },
        contraindications=["ガラクトース血症", "腸閉塞"],
        major_interactions=["抗菌薬（腸内細菌叢変化→効果↓）"],
        renal_adjustment="特別な調整不要",
        hepatic_adjustment="肝性脳症の治療薬のため特記なし",
        monitoring=["排便回数・硬さ", "アンモニア値", "電解質（脱水）"],
        side_effects=["腹部膨満感", "下痢（過剰では）", "電解質異常（過剰投与）"],
        notes="肝性脳症：アンモニア産生菌を腸内酸性化で抑制。1日2-4回の軟便が目標。リファキシミン（非吸収性抗菌薬）との併用も有効",
    ),
    "メサラジン": DrugInfo(
        name_ja="メサラジン（5-ASA）", name_en="Mesalazine",
        drug_class="炎症性腸疾患治療薬（5-アミノサリチル酸）",
        indications=["潰瘍性大腸炎（軽症-中等症）", "クローン病（回腸・大腸型の軽症）"],
        adult_doses={
            "UC軽症-中等症": "2.4-4.8g/日 経口（2-3分割）",
            "寛解維持": "1.5-2g/日",
        },
        contraindications=["サリチル酸過敏症", "重度腎障害"],
        major_interactions=["ワルファリン（PT延長）", "免疫抑制薬（相加的免疫抑制）"],
        renal_adjustment="GFR<30では慎重（腎毒性リスク）",
        hepatic_adjustment="特別な調整不要",
        monitoring=["腎機能（6ヶ月ごと）", "肝機能", "腸炎症状"],
        side_effects=["悪心嘔吐", "頭痛", "腎毒性（間質性腎炎）", "心膜炎（まれ）"],
        notes="直腸炎・左側大腸炎には坐剤・浣腸が有効。全大腸型では経口+経直腸の組み合わせが効果的",
    ),
}


def search_drug(query: str, max_results: int = 5) -> list[tuple[str, DrugInfo]]:
    """薬剤名で検索（部分一致・fuzzy match）"""
    results = []
    query_lower = query.lower()

    # 完全一致・部分一致
    for name, info in DRUG_DATABASE.items():
        if query_lower in name.lower() or query_lower in info.name_en.lower():
            results.append((name, info))

    # Fuzzy match（一致がない場合）
    if not results:
        all_names = list(DRUG_DATABASE.keys())
        matches = difflib.get_close_matches(query, all_names, n=max_results, cutoff=0.5)
        for m in matches:
            results.append((m, DRUG_DATABASE[m]))

    return results[:max_results]


def get_drug_info(name: str) -> Optional[DrugInfo]:
    """薬剤名で正確に取得（完全一致優先）"""
    if name in DRUG_DATABASE:
        return DRUG_DATABASE[name]
    # 英語名でも検索
    for drug_name, info in DRUG_DATABASE.items():
        if name.lower() == info.name_en.lower():
            return info
    return None


def check_drug_interactions_from_db(drug_names: list[str]) -> list[dict]:
    """複数薬剤の相互作用を検索"""
    interactions = []
    infos = []

    for name in drug_names:
        info = get_drug_info(name)
        if info:
            infos.append((name, info))

    for i, (name1, info1) in enumerate(infos):
        for j, (name2, info2) in enumerate(infos):
            if i >= j:
                continue
            # info1の相互作用にname2が含まれるか確認
            for interaction_str in info1.major_interactions:
                if name2 in interaction_str or name2.split("（")[0] in interaction_str:
                    interactions.append({
                        "drug1": name1,
                        "drug2": name2,
                        "description": interaction_str,
                        "source": f"{name1}の添付文書より",
                    })

    return interactions


def get_all_drug_classes() -> dict[str, list[str]]:
    """薬剤クラス別に薬剤リストを返す"""
    class_dict: dict[str, list[str]] = {}
    for name, info in DRUG_DATABASE.items():
        cls = info.drug_class.split("（")[0].split("/")[0].strip()
        if cls not in class_dict:
            class_dict[cls] = []
        class_dict[cls].append(name)
    return class_dict
