"""
clinical/icd10.py — ICD-10 Mapper (日本標準対応)

疾患名 → ICD-10 コードのマッピングと曖昧検索。

get_icd10(disease_name) → {"code": "I21.9", "name_ja": "急性心筋梗塞", "name_en": "Acute MI"}
suggest_icd10(partial_name) → [{"code": ..., "name_ja": ..., "name_en": ...}, ...]
"""

from __future__ import annotations

import re
import unicodedata
from difflib import SequenceMatcher


# ===========================================================================
# ICD-10 マスターデータ
# ===========================================================================
# 形式: {"code": str, "name_ja": str, "name_en": str, "aliases": [str, ...]}

_ICD10_MASTER: list[dict] = [
    # =========================================================
    # I — 循環器疾患 (Cardiovascular)
    # =========================================================
    {
        "code": "I21.9",
        "name_ja": "急性心筋梗塞",
        "name_en": "Acute myocardial infarction, unspecified",
        "aliases": ["AMI", "心筋梗塞", "STEMI", "NSTEMI", "ACS", "急性冠症候群"],
    },
    {
        "code": "I21.0",
        "name_ja": "前壁STEMIを伴う急性心筋梗塞",
        "name_en": "Acute transmural MI of anterior wall",
        "aliases": ["前壁梗塞", "前壁ST上昇型心筋梗塞", "前壁STEMI"],
    },
    {
        "code": "I21.1",
        "name_ja": "下壁STEMIを伴う急性心筋梗塞",
        "name_en": "Acute transmural MI of inferior wall",
        "aliases": ["下壁梗塞", "下壁STEMI", "下壁心筋梗塞"],
    },
    {
        "code": "I20.0",
        "name_ja": "不安定狭心症",
        "name_en": "Unstable angina",
        "aliases": ["不安定狭心症", "UA"],
    },
    {
        "code": "I20.9",
        "name_ja": "狭心症",
        "name_en": "Angina pectoris, unspecified",
        "aliases": ["狭心症", "AP", "労作性狭心症"],
    },
    {
        "code": "I50.9",
        "name_ja": "心不全",
        "name_en": "Heart failure, unspecified",
        "aliases": ["心不全", "CHF", "うっ血性心不全", "急性心不全", "慢性心不全"],
    },
    {
        "code": "I50.1",
        "name_ja": "左室収縮不全",
        "name_en": "Left ventricular failure",
        "aliases": ["左心不全", "左室不全", "LVF"],
    },
    {
        "code": "I26.9",
        "name_ja": "肺塞栓症",
        "name_en": "Pulmonary embolism without mention of acute cor pulmonale",
        "aliases": ["PE", "肺血栓塞栓症", "PTE", "肺梗塞"],
    },
    {
        "code": "I71.0",
        "name_ja": "大動脈解離",
        "name_en": "Dissection of aorta",
        "aliases": ["大動脈解離", "Stanford A型解離", "Stanford B型解離",
                    "aortic dissection", "AD"],
    },
    {
        "code": "I71.4",
        "name_ja": "腹部大動脈瘤",
        "name_en": "Abdominal aortic aneurysm",
        "aliases": ["AAA", "腹部大動脈瘤", "大動脈瘤"],
    },
    {
        "code": "I48.9",
        "name_ja": "心房細動",
        "name_en": "Atrial fibrillation and flutter, unspecified",
        "aliases": ["心房細動", "AF", "Af", "発作性AF", "持続性AF"],
    },
    {
        "code": "I47.2",
        "name_ja": "心室頻拍",
        "name_en": "Ventricular tachycardia",
        "aliases": ["VT", "心室頻拍", "持続性VT"],
    },
    {
        "code": "I49.0",
        "name_ja": "心室細動",
        "name_en": "Ventricular fibrillation",
        "aliases": ["VF", "心室細動", "心室粗動"],
    },
    {
        "code": "I44.2",
        "name_ja": "完全房室ブロック",
        "name_en": "Atrioventricular block, complete",
        "aliases": ["完全AVブロック", "3度AVブロック", "完全房室ブロック"],
    },
    {
        "code": "I10",
        "name_ja": "本態性高血圧",
        "name_en": "Essential (primary) hypertension",
        "aliases": ["高血圧", "HT", "EH", "本態性高血圧"],
    },
    {
        "code": "I16.0",
        "name_ja": "高血圧緊急症",
        "name_en": "Hypertensive crisis",
        "aliases": ["高血圧緊急症", "高血圧クリーゼ", "hypertensive emergency"],
    },
    {
        "code": "I80.2",
        "name_ja": "深部静脈血栓症",
        "name_en": "Deep vein thrombosis",
        "aliases": ["DVT", "深部静脈血栓症", "下肢DVT"],
    },
    {
        "code": "I25.1",
        "name_ja": "冠動脈疾患",
        "name_en": "Atherosclerotic heart disease",
        "aliases": ["CAD", "冠動脈疾患", "IHD", "虚血性心疾患"],
    },
    {
        "code": "I33.0",
        "name_ja": "感染性心内膜炎",
        "name_en": "Acute and subacute infective endocarditis",
        "aliases": ["IE", "心内膜炎", "感染性心内膜炎"],
    },
    # =========================================================
    # I60-I69 — 脳血管疾患 (Cerebrovascular)
    # =========================================================
    {
        "code": "I63.9",
        "name_ja": "脳梗塞",
        "name_en": "Cerebral infarction, unspecified",
        "aliases": ["脳梗塞", "虚血性脳卒中", "cerebral infarction", "CI",
                    "ischemic stroke"],
    },
    {
        "code": "I63.0",
        "name_ja": "椎骨脳底動脈系血栓症による脳梗塞",
        "name_en": "Cerebral infarction due to thrombosis of vertebral artery",
        "aliases": ["脳底動脈梗塞", "椎骨脳底動脈梗塞", "後方循環梗塞"],
    },
    {
        "code": "I61.9",
        "name_ja": "脳内出血",
        "name_en": "Intracerebral haemorrhage, unspecified",
        "aliases": ["脳出血", "脳内出血", "ICH", "intracerebral hemorrhage"],
    },
    {
        "code": "I60.9",
        "name_ja": "くも膜下出血",
        "name_en": "Subarachnoid haemorrhage, unspecified",
        "aliases": ["SAH", "くも膜下出血", "subarachnoid hemorrhage"],
    },
    {
        "code": "G45.9",
        "name_ja": "一過性脳虚血発作",
        "name_en": "Transient cerebral ischaemic attack, unspecified",
        "aliases": ["TIA", "一過性脳虚血発作", "transient ischemic attack"],
    },
    # =========================================================
    # G — 神経疾患 (Neurological)
    # =========================================================
    {
        "code": "G00.9",
        "name_ja": "細菌性髄膜炎",
        "name_en": "Bacterial meningitis, unspecified",
        "aliases": ["髄膜炎", "細菌性髄膜炎", "化膿性髄膜炎", "bacterial meningitis"],
    },
    {
        "code": "G03.9",
        "name_ja": "髄膜炎",
        "name_en": "Meningitis, unspecified",
        "aliases": ["無菌性髄膜炎", "ウイルス性髄膜炎", "aseptic meningitis"],
    },
    {
        "code": "G04.0",
        "name_ja": "急性散在性脳脊髄炎",
        "name_en": "Acute disseminated encephalomyelitis",
        "aliases": ["ADEM", "急性散在性脳脊髄炎"],
    },
    {
        "code": "G40.9",
        "name_ja": "てんかん",
        "name_en": "Epilepsy, unspecified",
        "aliases": ["てんかん", "痙攣発作", "epilepsy", "seizure"],
    },
    {
        "code": "G41.9",
        "name_ja": "てんかん重積状態",
        "name_en": "Status epilepticus, unspecified",
        "aliases": ["てんかん重積", "status epilepticus", "SE", "重積状態"],
    },
    {
        "code": "G35",
        "name_ja": "多発性硬化症",
        "name_en": "Multiple sclerosis",
        "aliases": ["MS", "多発性硬化症"],
    },
    {
        "code": "G61.0",
        "name_ja": "ギラン・バレー症候群",
        "name_en": "Guillain-Barré syndrome",
        "aliases": ["GBS", "ギランバレー症候群", "ギラン・バレー"],
    },
    {
        "code": "G43.9",
        "name_ja": "片頭痛",
        "name_en": "Migraine, unspecified",
        "aliases": ["片頭痛", "migraine"],
    },
    # =========================================================
    # J — 呼吸器疾患 (Respiratory)
    # =========================================================
    {
        "code": "J18.9",
        "name_ja": "肺炎",
        "name_en": "Pneumonia, unspecified",
        "aliases": ["肺炎", "CAP", "市中肺炎", "pneumonia"],
    },
    {
        "code": "J18.0",
        "name_ja": "気管支肺炎",
        "name_en": "Bronchopneumonia, unspecified",
        "aliases": ["気管支肺炎", "bronchopneumonia"],
    },
    {
        "code": "J15.9",
        "name_ja": "細菌性肺炎",
        "name_en": "Unspecified bacterial pneumonia",
        "aliases": ["細菌性肺炎", "bacterial pneumonia"],
    },
    {
        "code": "J12.9",
        "name_ja": "ウイルス性肺炎",
        "name_en": "Viral pneumonia, unspecified",
        "aliases": ["ウイルス性肺炎", "viral pneumonia"],
    },
    {
        "code": "J80",
        "name_ja": "急性呼吸窮迫症候群",
        "name_en": "Acute respiratory distress syndrome",
        "aliases": ["ARDS", "急性呼吸窮迫症候群", "急性呼吸促迫症候群"],
    },
    {
        "code": "J44.1",
        "name_ja": "COPD増悪",
        "name_en": "Chronic obstructive pulmonary disease with acute exacerbation",
        "aliases": ["COPD増悪", "AECOPD", "慢性閉塞性肺疾患急性増悪"],
    },
    {
        "code": "J44.0",
        "name_ja": "慢性閉塞性肺疾患",
        "name_en": "COPD with acute lower respiratory infection",
        "aliases": ["COPD", "慢性閉塞性肺疾患"],
    },
    {
        "code": "J45.9",
        "name_ja": "喘息",
        "name_en": "Asthma, unspecified",
        "aliases": ["喘息", "気管支喘息", "asthma", "bronchial asthma"],
    },
    {
        "code": "J45.0",
        "name_ja": "重篤な喘息発作",
        "name_en": "Predominantly allergic asthma",
        "aliases": ["重篤な喘息", "status asthmaticus", "喘息重積状態"],
    },
    {
        "code": "A15.0",
        "name_ja": "肺結核",
        "name_en": "Tuberculosis of lung",
        "aliases": ["肺結核", "TB", "結核", "tuberculosis"],
    },
    {
        "code": "J93.9",
        "name_ja": "気胸",
        "name_en": "Pneumothorax, unspecified",
        "aliases": ["気胸", "pneumothorax", "自然気胸", "緊張性気胸"],
    },
    {
        "code": "J90",
        "name_ja": "胸水貯留",
        "name_en": "Pleural effusion",
        "aliases": ["胸水", "胸水貯留", "pleural effusion"],
    },
    {
        "code": "J96.0",
        "name_ja": "急性呼吸不全",
        "name_en": "Acute respiratory failure",
        "aliases": ["急性呼吸不全", "ARF", "acute respiratory failure"],
    },
    # =========================================================
    # K — 消化器・肝臓疾患 (GI / Hepatic)
    # =========================================================
    {
        "code": "K37",
        "name_ja": "虫垂炎",
        "name_en": "Unspecified appendicitis",
        "aliases": ["虫垂炎", "急性虫垂炎", "appendicitis"],
    },
    {
        "code": "K83.0",
        "name_ja": "胆管炎",
        "name_en": "Cholangitis",
        "aliases": ["胆管炎", "急性胆管炎", "cholangitis", "ERCP"],
    },
    {
        "code": "K81.0",
        "name_ja": "急性胆嚢炎",
        "name_en": "Acute cholecystitis",
        "aliases": ["胆嚢炎", "急性胆嚢炎", "cholecystitis"],
    },
    {
        "code": "K85.9",
        "name_ja": "急性膵炎",
        "name_en": "Acute pancreatitis, unspecified",
        "aliases": ["急性膵炎", "pancreatitis", "AP"],
    },
    {
        "code": "K86.1",
        "name_ja": "慢性膵炎",
        "name_en": "Other chronic pancreatitis",
        "aliases": ["慢性膵炎", "chronic pancreatitis"],
    },
    {
        "code": "K92.0",
        "name_ja": "吐血",
        "name_en": "Haematemesis",
        "aliases": ["吐血", "上部消化管出血", "GIB", "消化管出血", "hematemesis"],
    },
    {
        "code": "K92.1",
        "name_ja": "血便",
        "name_en": "Melaena",
        "aliases": ["血便", "下部消化管出血", "melaena", "melena"],
    },
    {
        "code": "K92.2",
        "name_ja": "消化管出血",
        "name_en": "Gastrointestinal haemorrhage, unspecified",
        "aliases": ["消化管出血", "GI bleeding", "UGIB", "LGIB"],
    },
    {
        "code": "K70.3",
        "name_ja": "アルコール性肝硬変",
        "name_en": "Alcoholic cirrhosis of liver",
        "aliases": ["肝硬変", "alcoholic cirrhosis", "アルコール性肝硬変"],
    },
    {
        "code": "K72.0",
        "name_ja": "急性肝不全",
        "name_en": "Acute and subacute hepatic failure",
        "aliases": ["急性肝不全", "fulminant hepatitis", "劇症肝炎", "急性肝炎"],
    },
    {
        "code": "K56.6",
        "name_ja": "腸閉塞",
        "name_en": "Other and unspecified intestinal obstruction",
        "aliases": ["腸閉塞", "イレウス", "intestinal obstruction", "ileus"],
    },
    {
        "code": "K25.0",
        "name_ja": "胃潰瘍穿孔",
        "name_en": "Gastric ulcer, acute with haemorrhage",
        "aliases": ["胃潰瘍", "消化性潰瘍", "PUD", "gastric ulcer"],
    },
    {
        "code": "K55.0",
        "name_ja": "急性腸管虚血",
        "name_en": "Acute vascular disorders of intestine",
        "aliases": ["腸管虚血", "急性腸虚血", "mesenteric ischemia", "腸管壊死"],
    },
    # =========================================================
    # E — 内分泌・代謝疾患 (Endocrine / Metabolic)
    # =========================================================
    {
        "code": "E10.1",
        "name_ja": "1型糖尿病性ケトアシドーシス",
        "name_en": "Type 1 DM with ketoacidosis",
        "aliases": ["DKA", "糖尿病性ケトアシドーシス", "ケトアシドーシス",
                    "diabetic ketoacidosis"],
    },
    {
        "code": "E11.0",
        "name_ja": "2型糖尿病性高浸透圧性昏睡",
        "name_en": "Type 2 DM with hyperosmolar coma",
        "aliases": ["HHS", "高浸透圧高血糖症候群", "高浸透圧性昏睡",
                    "hyperosmolar hyperglycemic state", "HONK"],
    },
    {
        "code": "E16.0",
        "name_ja": "低血糖",
        "name_en": "Drug-induced hypoglycaemia without coma",
        "aliases": ["低血糖", "hypoglycemia", "低血糖発作", "インスリン低血糖"],
    },
    {
        "code": "E11.9",
        "name_ja": "2型糖尿病",
        "name_en": "Type 2 diabetes mellitus without complications",
        "aliases": ["2型糖尿病", "T2DM", "type 2 diabetes"],
    },
    {
        "code": "E10.9",
        "name_ja": "1型糖尿病",
        "name_en": "Type 1 diabetes mellitus without complications",
        "aliases": ["1型糖尿病", "T1DM", "type 1 diabetes"],
    },
    {
        "code": "E05.0",
        "name_ja": "甲状腺クリーゼ",
        "name_en": "Thyrotoxicosis with diffuse goitre",
        "aliases": ["甲状腺クリーゼ", "バセドウ病クリーゼ", "thyroid storm",
                    "thyrotoxic crisis"],
    },
    {
        "code": "E03.5",
        "name_ja": "粘液水腫性昏睡",
        "name_en": "Myxoedema coma",
        "aliases": ["粘液水腫性昏睡", "myxedema coma", "甲状腺機能低下症昏睡"],
    },
    {
        "code": "E27.1",
        "name_ja": "原発性副腎不全 (副腎クリーゼ)",
        "name_en": "Primary adrenocortical insufficiency",
        "aliases": ["副腎クリーゼ", "アジソン病", "adrenal crisis",
                    "Addisonian crisis"],
    },
    {
        "code": "E22.0",
        "name_ja": "先端巨大症",
        "name_en": "Acromegaly and pituitary gigantism",
        "aliases": ["先端巨大症", "acromegaly"],
    },
    {
        "code": "E83.5",
        "name_ja": "高カルシウム血症",
        "name_en": "Disorders of calcium metabolism",
        "aliases": ["高カルシウム血症", "hypercalcemia"],
    },
    # =========================================================
    # A / B — 感染症 (Infectious)
    # =========================================================
    {
        "code": "A41.9",
        "name_ja": "敗血症",
        "name_en": "Sepsis, unspecified",
        "aliases": ["敗血症", "sepsis", "SIRS", "敗血症ショック"],
    },
    {
        "code": "A41.0",
        "name_ja": "黄色ブドウ球菌敗血症",
        "name_en": "Sepsis due to Staphylococcus aureus",
        "aliases": ["MRSA敗血症", "黄色ブドウ球菌敗血症", "staph sepsis"],
    },
    {
        "code": "A39.9",
        "name_ja": "髄膜炎菌感染症",
        "name_en": "Meningococcal infection, unspecified",
        "aliases": ["髄膜炎菌感染症", "meningococcemia", "Nm感染症"],
    },
    {
        "code": "A39.0",
        "name_ja": "髄膜炎菌性髄膜炎",
        "name_en": "Meningococcal meningitis",
        "aliases": ["髄膜炎菌性髄膜炎"],
    },
    {
        "code": "A48.3",
        "name_ja": "毒素性ショック症候群",
        "name_en": "Toxic shock syndrome",
        "aliases": ["TSS", "毒素性ショック症候群", "toxic shock syndrome"],
    },
    {
        "code": "B34.9",
        "name_ja": "ウイルス感染症",
        "name_en": "Viral infection, unspecified",
        "aliases": ["ウイルス感染", "viral infection"],
    },
    {
        "code": "A90",
        "name_ja": "デング熱",
        "name_en": "Dengue fever",
        "aliases": ["デング熱", "dengue fever"],
    },
    {
        "code": "B20",
        "name_ja": "HIV感染症",
        "name_en": "HIV disease",
        "aliases": ["HIV", "AIDS", "HIV感染症", "エイズ"],
    },
    {
        "code": "A02.0",
        "name_ja": "サルモネラ腸炎",
        "name_en": "Salmonella enteritis",
        "aliases": ["サルモネラ腸炎", "salmonellosis"],
    },
    {
        "code": "A09",
        "name_ja": "感染性腸炎",
        "name_en": "Infectious gastroenteritis and colitis",
        "aliases": ["感染性腸炎", "gastroenteritis", "食中毒"],
    },
    # =========================================================
    # N — 泌尿生殖器疾患
    # =========================================================
    {
        "code": "N39.0",
        "name_ja": "尿路感染症",
        "name_en": "Urinary tract infection, site not specified",
        "aliases": ["UTI", "尿路感染症", "膀胱炎", "腎盂腎炎"],
    },
    {
        "code": "N10",
        "name_ja": "急性腎盂腎炎",
        "name_en": "Acute tubulo-interstitial nephritis",
        "aliases": ["腎盂腎炎", "急性腎盂腎炎", "pyelonephritis"],
    },
    {
        "code": "N17.9",
        "name_ja": "急性腎不全",
        "name_en": "Acute kidney failure, unspecified",
        "aliases": ["AKI", "急性腎不全", "急性腎障害", "acute kidney injury"],
    },
    {
        "code": "N18.5",
        "name_ja": "慢性腎臓病ステージ5 (末期腎不全)",
        "name_en": "Chronic kidney disease, stage 5",
        "aliases": ["ESKD", "末期腎不全", "CKD5", "透析"],
    },
    {
        "code": "N20.0",
        "name_ja": "腎結石",
        "name_en": "Calculus of kidney",
        "aliases": ["腎結石", "尿管結石", "ureterolithiasis", "腎石灰化"],
    },
    # =========================================================
    # M — 筋骨格・結合組織疾患
    # =========================================================
    {
        "code": "M32.9",
        "name_ja": "全身性エリテマトーデス",
        "name_en": "Systemic lupus erythematosus, unspecified",
        "aliases": ["SLE", "全身性エリテマトーデス", "ループス"],
    },
    {
        "code": "M06.9",
        "name_ja": "関節リウマチ",
        "name_en": "Rheumatoid arthritis, unspecified",
        "aliases": ["RA", "関節リウマチ", "rheumatoid arthritis"],
    },
    {
        "code": "M31.3",
        "name_ja": "川崎病",
        "name_en": "Wegener's granulomatosis",  # NOTE: M30.3 が川崎病、暫定 M31.3
        "aliases": ["川崎病", "Kawasaki disease"],
    },
    # =========================================================
    # S / T — 外傷・中毒
    # =========================================================
    {
        "code": "T78.2",
        "name_ja": "アナフィラキシー",
        "name_en": "Anaphylactic shock, unspecified",
        "aliases": ["アナフィラキシー", "アナフィラキシーショック", "anaphylaxis",
                    "anaphylactic shock"],
    },
    {
        "code": "T39.1",
        "name_ja": "解熱鎮痛薬中毒",
        "name_en": "Poisoning by 4-Aminophenol derivatives",
        "aliases": ["アセトアミノフェン中毒", "APAP中毒", "パラセタモール中毒"],
    },
    {
        "code": "T36.0",
        "name_ja": "薬物中毒",
        "name_en": "Poisoning by penicillins",
        "aliases": ["薬物中毒", "overdose"],
    },
    {
        "code": "T71",
        "name_ja": "窒息",
        "name_en": "Asphyxiation",
        "aliases": ["窒息", "asphyxia", "窒息死"],
    },
    {
        "code": "S06.9",
        "name_ja": "頭部外傷",
        "name_en": "Intracranial injury, unspecified",
        "aliases": ["頭部外傷", "TBI", "外傷性脳損傷", "頭蓋内損傷"],
    },
    # =========================================================
    # C — 悪性腫瘍
    # =========================================================
    {
        "code": "C34.9",
        "name_ja": "肺悪性腫瘍",
        "name_en": "Malignant neoplasm of bronchus and lung, unspecified",
        "aliases": ["肺がん", "肺癌", "lung cancer", "肺腫瘍"],
    },
    {
        "code": "C25.9",
        "name_ja": "膵臓悪性腫瘍",
        "name_en": "Malignant neoplasm of pancreas, unspecified",
        "aliases": ["膵癌", "膵臓癌", "pancreatic cancer"],
    },
    {
        "code": "C18.9",
        "name_ja": "結腸悪性腫瘍",
        "name_en": "Malignant neoplasm of colon, unspecified",
        "aliases": ["大腸がん", "結腸癌", "colon cancer"],
    },
    # =========================================================
    # R — 症状・徴候
    # =========================================================
    {
        "code": "R55",
        "name_ja": "失神",
        "name_en": "Syncope and collapse",
        "aliases": ["失神", "syncope", "意識消失", "失神発作"],
    },
    {
        "code": "R57.9",
        "name_ja": "ショック",
        "name_en": "Shock, unspecified",
        "aliases": ["ショック", "shock", "循環不全"],
    },
    {
        "code": "R57.0",
        "name_ja": "心原性ショック",
        "name_en": "Cardiogenic shock",
        "aliases": ["心原性ショック", "cardiogenic shock"],
    },
    {
        "code": "R57.1",
        "name_ja": "低容量ショック",
        "name_en": "Hypovolaemic shock",
        "aliases": ["低容量ショック", "出血性ショック", "hypovolemic shock"],
    },
    {
        "code": "R41.3",
        "name_ja": "意識障害",
        "name_en": "Other amnesia",
        "aliases": ["意識障害", "意識混濁", "昏睡", "LOC"],
    },
]


# ===========================================================================
# インデックス構築
# ===========================================================================

def _build_index() -> dict[str, dict]:
    """すべてのエイリアスをキーとする高速参照辞書を構築する。"""
    idx: dict[str, dict] = {}
    for entry in _ICD10_MASTER:
        item = {
            "code": entry["code"],
            "name_ja": entry["name_ja"],
            "name_en": entry["name_en"],
        }
        # 正式名称と全エイリアスを登録
        for alias in [entry["name_ja"], entry["name_en"]] + entry.get("aliases", []):
            key = alias.strip().lower()
            idx[key] = item
    return idx


_INDEX: dict[str, dict] = _build_index()


def _normalize(text: str) -> str:
    """検索用に正規化: 小文字・全角→半角・スペース除去。"""
    text = unicodedata.normalize("NFKC", text).strip().lower()
    text = re.sub(r"\s+", " ", text)
    return text


# ===========================================================================
# 公開 API
# ===========================================================================

def get_icd10(disease_name: str) -> dict | None:
    """疾患名から ICD-10 コードを取得する。

    Parameters
    ----------
    disease_name : str
        疾患名 (日本語・英語・略語 いずれも可)

    Returns
    -------
    dict | None
        {"code": str, "name_ja": str, "name_en": str}
        一致なしの場合は None
    """
    key = _normalize(disease_name)
    # 完全一致
    if key in _INDEX:
        return dict(_INDEX[key])

    # コード直接指定 (例: "I21.9")
    code_upper = disease_name.strip().upper()
    for entry in _ICD10_MASTER:
        if entry["code"].upper() == code_upper:
            return {"code": entry["code"], "name_ja": entry["name_ja"],
                    "name_en": entry["name_en"]}

    # 前方一致 / 部分一致
    for alias, item in _INDEX.items():
        if key in alias or alias in key:
            return dict(item)

    return None


def suggest_icd10(
    partial_name: str,
    max_results: int = 5,
    threshold: float = 0.3,
) -> list[dict]:
    """部分的な疾患名から候補を検索する (ファジー検索)。

    Parameters
    ----------
    partial_name : str
        検索クエリ (部分的な疾患名)
    max_results : int
        最大返却件数 (デフォルト: 5)
    threshold : float
        類似度の最低閾値 0〜1 (デフォルト: 0.3)

    Returns
    -------
    list[dict]
        [{"code": str, "name_ja": str, "name_en": str, "score": float}, ...]
        類似度スコアの降順
    """
    query = _normalize(partial_name)
    scored: list[tuple[float, dict]] = []
    seen_codes: set[str] = set()

    for alias, item in _INDEX.items():
        if item["code"] in seen_codes:
            # 同コードの別エイリアスで既に高スコアが登録済みなら更新のみ
            existing = next((s for s in scored if s[1]["code"] == item["code"]), None)
            if existing is None:
                continue

        # 完全一致 / 部分一致ボーナス
        if query == alias:
            sim = 1.0
        elif query in alias or alias in query:
            sim = 0.85
        else:
            sim = SequenceMatcher(None, query, alias).ratio()

        if sim >= threshold:
            result = {**item, "score": round(sim, 4)}
            # 同コードなら最高スコアで更新
            existing_idx = next(
                (i for i, (_, d) in enumerate(scored) if d["code"] == item["code"]),
                None,
            )
            if existing_idx is not None:
                if sim > scored[existing_idx][0]:
                    scored[existing_idx] = (sim, result)
            else:
                scored.append((sim, result))
                seen_codes.add(item["code"])

    scored.sort(key=lambda x: x[0], reverse=True)
    return [item for _, item in scored[:max_results]]


def list_icd10_by_chapter(chapter_prefix: str) -> list[dict]:
    """ICD-10 コードのプレフィックスで絞り込む。

    Parameters
    ----------
    chapter_prefix : str
        例: "I" (循環器), "J" (呼吸器), "K" (消化器)

    Returns
    -------
    list[dict]
        該当する全エントリ
    """
    prefix = chapter_prefix.strip().upper()
    return [
        {"code": e["code"], "name_ja": e["name_ja"], "name_en": e["name_en"]}
        for e in _ICD10_MASTER
        if e["code"].upper().startswith(prefix)
    ]


# ===========================================================================
# デモ
# ===========================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("【完全一致検索】")
    queries = [
        "急性心筋梗塞", "AMI", "肺炎", "DKA", "aortic dissection",
        "敗血症", "アナフィラキシー", "くも膜下出血", "I26.9",
    ]
    for q in queries:
        result = get_icd10(q)
        if result:
            print(f"  '{q}' → {result['code']}  {result['name_ja']}  [{result['name_en']}]")
        else:
            print(f"  '{q}' → 見つかりません")

    print()
    print("=" * 60)
    print("【ファジー検索】")
    fuzzy_queries = ["心筋", "脳卒中", "pneumo", "敗血", "肺血栓"]
    for q in fuzzy_queries:
        suggestions = suggest_icd10(q, max_results=3)
        print(f"\n  '{q}' の候補:")
        for s in suggestions:
            print(f"    [{s['score']:.2f}] {s['code']}  {s['name_ja']}")

    print()
    print("=" * 60)
    print("【チャプター別一覧 (循環器: I)】")
    cardio = list_icd10_by_chapter("I")
    for item in cardio[:8]:
        print(f"  {item['code']:10s} {item['name_ja']}")
    print(f"  ... 合計 {len(cardio)} 件")
