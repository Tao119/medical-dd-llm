"""
clinical/nlp_processor.py — Clinical NLP Pipeline

Parses free-text Japanese clinical notes and extracts structured information
using regex + keyword matching (no external NLP library required).

Key functions
-------------
    parse_clinical_note(text: str) -> ClinicalNote
    note_to_case(note: ClinicalNote) -> dict

Usage
-----
    cd medical-dd-llm
    python clinical/nlp_processor.py
"""

from __future__ import annotations

import re
import sys
import os
from dataclasses import dataclass, field

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from model.dd_engine import diagnose


# ---------------------------------------------------------------------------
# Dataclass
# ---------------------------------------------------------------------------

@dataclass
class ClinicalNote:
    raw_text: str
    demographics: dict = field(default_factory=dict)
    medical_history: list[str] = field(default_factory=list)
    chief_complaint: str = ""
    symptoms: list[str] = field(default_factory=list)
    vitals_text: str = ""
    labs_text: str = ""
    findings: list[str] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Demographics
# ---------------------------------------------------------------------------

_RE_AGE = re.compile(r"(\d{1,3})\s*歳")
_RE_SEX = re.compile(r"(男性|女性|男|女)")


def _extract_demographics(text: str) -> dict:
    demographics: dict = {}
    m = _RE_AGE.search(text)
    if m:
        demographics["age"] = int(m.group(1))
    m = _RE_SEX.search(text)
    if m:
        raw = m.group(1)
        demographics["sex"] = "男性" if raw in ("男性", "男") else "女性"
    return demographics


# ---------------------------------------------------------------------------
# Medical history
# ---------------------------------------------------------------------------

_HISTORY_KEYWORDS = [
    "高血圧", "糖尿病", "心不全", "心筋梗塞", "心房細動",
    "脳梗塞", "脳出血", "COPD", "慢性腎不全", "腎不全",
    "肝硬変", "肝炎", "甲状腺機能低下症", "甲状腺機能亢進症",
    "喘息", "アレルギー", "関節リウマチ", "骨粗鬆症", "てんかん",
    "鬱病", "統合失調症", "認知症", "パーキンソン病",
    "悪性腫瘍", "がん", "癌", "手術歴", "輸血歴",
    "アルコール依存", "喫煙歴", "既往",
]

_RE_HISTORY_SECTION = re.compile(
    r"(?:既往|病歴|既往歴|既往症|既往疾患|合併症|基礎疾患)"
    r".{0,100}",
    re.DOTALL,
)


def _extract_medical_history(text: str) -> list[str]:
    found = []
    for kw in _HISTORY_KEYWORDS:
        if kw in text and kw not in found:
            found.append(kw)
    return found


# ---------------------------------------------------------------------------
# Chief complaint
# ---------------------------------------------------------------------------

_CC_PATTERNS = [
    re.compile(r"(?:主訴|主な訴え|訴え)\s*[：:]\s*(.+?)(?:。|\n|$)"),
    re.compile(r"(?:来院理由|受診理由)\s*[：:]\s*(.+?)(?:。|\n|$)"),
    # Sentence containing "から" + "出現" (symptom onset)
    re.compile(r"(?:今朝|本日|昨日|.{1,6}ごろ)(?:から|より).{3,30}(?:出現|発症|来院|受診)"),
]

_CC_KEYWORDS = [
    "胸痛", "胸部圧迫感", "圧迫感", "胸部不快感",
    "呼吸困難", "息切れ", "動悸",
    "腹痛", "腹部痛",
    "頭痛", "めまい",
    "発熱", "悪寒",
    "嘔気", "嘔吐",
    "意識消失", "意識障害",
    "四肢脱力", "麻痺",
    "浮腫", "下腿浮腫",
    "背部痛", "腰痛",
    "倦怠感", "全身倦怠感",
]


def _extract_chief_complaint(text: str) -> str:
    for pat in _CC_PATTERNS:
        m = pat.search(text)
        if m:
            return m.group(0).strip()

    # Fall back: first matched CC keyword
    for kw in _CC_KEYWORDS:
        if kw in text:
            # Try to grab short context around it
            idx = text.index(kw)
            start = max(0, idx - 10)
            end = min(len(text), idx + 30)
            return text[start:end].strip()

    return ""


# ---------------------------------------------------------------------------
# Symptoms
# ---------------------------------------------------------------------------

_SYMPTOM_KEYWORDS = [
    # Cardiovascular
    "胸痛", "圧迫感", "絞扼感", "放散痛", "左肩痛", "左肩への放散痛",
    "動悸", "不整脈", "頻脈", "徐脈",
    # Respiratory
    "呼吸困難", "息切れ", "咳嗽", "喀痰", "喀血", "喘鳴",
    # Neurological
    "頭痛", "めまい", "意識消失", "意識障害", "麻痺", "脱力",
    "痺れ", "構音障害", "視力障害",
    # GI
    "腹痛", "嘔気", "嘔吐", "下痢", "便秘", "黄疸", "血便", "腹部膨満",
    # General
    "発熱", "悪寒", "倦怠感", "食欲不振", "体重減少", "浮腫",
    "冷汗", "発汗", "チアノーゼ",
    # MSK/Derm
    "関節痛", "筋肉痛", "皮疹", "点状出血",
    # Pain
    "背部痛", "腰痛", "肩痛", "下肢痛",
]


def _extract_symptoms(text: str) -> list[str]:
    return [kw for kw in _SYMPTOM_KEYWORDS if kw in text]


# ---------------------------------------------------------------------------
# Vitals
# ---------------------------------------------------------------------------

_VITALS_PATTERN = re.compile(
    r"(?:"
    r"血圧\s*\d+[/／]\d+\s*(?:mmHg)?|"
    r"BP\s*\d+[/／]\d+|"
    r"心拍数?\s*\d+\s*(?:回[/／]分|/min|bpm)?|"
    r"HR\s*\d+|"
    r"SpO2\s*\d+\s*%?|"
    r"体温\s*\d+(?:\.\d)?\s*(?:℃|度)?|"
    r"BT\s*\d+(?:\.\d)?|"
    r"呼吸数?\s*\d+\s*(?:回[/／]分)?|"
    r"RR\s*\d+"
    r")",
    re.IGNORECASE,
)


def _extract_vitals_text(text: str) -> str:
    matches = _VITALS_PATTERN.findall(text)
    return "、".join(matches) if matches else ""


# ---------------------------------------------------------------------------
# Lab values
# ---------------------------------------------------------------------------

_LAB_PATTERN = re.compile(
    r"(?:"
    r"(?:TnI|トロポニン[IT]?)\s*[\d.]+\s*(?:ng/mL|ng/dl|μg/L)?|"
    r"BNP\s*[\d.]+\s*(?:pg/mL)?|"
    r"NT-proBNP\s*[\d.]+\s*(?:pg/mL)?|"
    r"CRP\s*[\d.]+\s*(?:mg/dL)?|"
    r"WBC\s*[\d,]+\s*(?:/μL)?|"
    r"Hb\s*[\d.]+\s*(?:g/dL)?|"
    r"Plt\s*[\d×x]+\s*(?:/μL)?|"
    r"Cr(?:eatinine)?\s*[\d.]+\s*(?:mg/dL)?|"
    r"eGFR\s*[\d.]+|"
    r"Na\s*[\d.]+\s*(?:mEq/L)?|"
    r"K\s*[\d.]+\s*(?:mEq/L)?|"
    r"Cl\s*[\d.]+|"
    r"Glu(?:cose)?\s*[\d.]+\s*(?:mg/dL)?|"
    r"HbA1c\s*[\d.]+\s*%?|"
    r"ALT\s*[\d]+\s*(?:IU/L)?|"
    r"AST\s*[\d]+\s*(?:IU/L)?|"
    r"T-Bil\s*[\d.]+\s*(?:mg/dL)?|"
    r"乳酸\s*[\d.]+\s*(?:mmol/L)?|"
    r"D-dimer\s*[\d.]+\s*(?:μg/mL)?"
    r")",
    re.IGNORECASE,
)


def _extract_labs_text(text: str) -> str:
    matches = _LAB_PATTERN.findall(text)
    return "、".join(matches) if matches else ""


# ---------------------------------------------------------------------------
# Physical exam findings
# ---------------------------------------------------------------------------

_FINDING_KEYWORDS = [
    # Cardiac
    "ST上昇", "ST低下", "T波逆転", "心電図", "新規LBBB",
    "心雑音", "Ⅲ音", "Ⅳ音", "不整脈",
    # Pulmonary
    "ラ音", "湿性ラ音", "乾性ラ音", "喘鳴", "呼吸音低下",
    "胸水", "肺水腫", "浸潤影",
    # Abdominal
    "圧痛", "反跳痛", "筋性防御", "腸蠕動音",
    # Neurological
    "項部硬直", "Kernig徴候", "Brudzinski徴候",
    # General
    "浮腫", "チアノーゼ", "黄疸", "点状出血", "皮疹",
    # Imaging/special
    "縦隔拡大", "心拡大", "バット翼陰影",
]


def _extract_findings(text: str) -> list[str]:
    return [kw for kw in _FINDING_KEYWORDS if kw in text]


# ---------------------------------------------------------------------------
# Keyword summary
# ---------------------------------------------------------------------------

_ALL_CLINICAL_KEYWORDS = (
    _CC_KEYWORDS + _SYMPTOM_KEYWORDS + _FINDING_KEYWORDS + _HISTORY_KEYWORDS
)


def _extract_keywords(text: str) -> list[str]:
    seen = set()
    result = []
    for kw in _ALL_CLINICAL_KEYWORDS:
        if kw in text and kw not in seen:
            seen.add(kw)
            result.append(kw)
    return result


# ---------------------------------------------------------------------------
# Main parse function
# ---------------------------------------------------------------------------

def parse_clinical_note(text: str) -> ClinicalNote:
    """
    Parse a free-text Japanese clinical note into a structured ClinicalNote.

    Parameters
    ----------
    text : str
        Raw clinical note (doctor's progress note or admission note).

    Returns
    -------
    ClinicalNote
        Structured representation of the note.
    """
    return ClinicalNote(
        raw_text=text,
        demographics=_extract_demographics(text),
        medical_history=_extract_medical_history(text),
        chief_complaint=_extract_chief_complaint(text),
        symptoms=_extract_symptoms(text),
        vitals_text=_extract_vitals_text(text),
        labs_text=_extract_labs_text(text),
        findings=_extract_findings(text),
        keywords=_extract_keywords(text),
    )


# ---------------------------------------------------------------------------
# Convert to dd_engine case dict
# ---------------------------------------------------------------------------

def note_to_case(note: ClinicalNote) -> dict:
    """
    Convert a ClinicalNote to the case dict format consumed by
    model.dd_engine.diagnose().

    Parameters
    ----------
    note : ClinicalNote

    Returns
    -------
    dict  matching the expected structure of dd_engine.diagnose()
    """
    demo_str = ""
    if "age" in note.demographics:
        demo_str += f"{note.demographics['age']}歳"
    if "sex" in note.demographics:
        demo_str += note.demographics["sex"]

    return {
        "demographics": demo_str,
        "chief_complaint": note.chief_complaint,
        "symptoms": note.symptoms,
        "history": "、".join(note.medical_history),
        "vitals": note.vitals_text,
        "findings": "、".join(note.findings),
        "keywords": note.keywords,
    }


# ---------------------------------------------------------------------------
# Sample clinical notes
# ---------------------------------------------------------------------------

SAMPLE_NOTES = [
    # Note 1: ACS
    """67歳男性、高血圧・糖尿病の既往あり。本日午前10時頃から前胸部の圧迫感が出現。
冷汗と左肩への放散痛を伴う。血圧90/60mmHg、心拍数112回/分、SpO2 94%。
心電図でST上昇を認める。TnI 0.8 ng/mL、BNP 650 pg/mL。""",

    # Note 2: Heart failure
    """75歳女性、心筋梗塞の既往あり。3日前から両下腿浮腫が悪化し、
起座呼吸が出現した。体重が5kg増加している。呼吸困難・息切れあり。
血圧150/90mmHg、心拍数88回/分、SpO2 90%、呼吸数24回/分。
胸部X線でバット翼陰影を認める。BNP 1200 pg/mL。""",

    # Note 3: Pneumonia
    """55歳男性、喫煙歴30年。3日前から発熱（38.5℃）、咳嗽、喀痰が出現。
全身倦怠感と食欲不振あり。血圧120/75mmHg、心拍数96回/分、
SpO2 95%、呼吸数22回/分。聴診で右下肺野に湿性ラ音を聴取。
WBC 15000/μL、CRP 12.5 mg/dL。""",

    # Note 4: Sepsis
    """42歳女性、尿路感染の既往あり。昨日から高熱（39.2℃）と全身倦怠感。
下腹部痛および頻尿もある。血圧85/55mmHg、心拍数130回/分、
SpO2 96%、呼吸数28回/分。WBC 20000/μL、CRP 18 mg/dL、乳酸 3.2 mmol/L。""",

    # Note 5: Subarachnoid hemorrhage
    """28歳男性、既往歴なし。突然の激しい頭痛（雷鳴頭痛）が出現。
嘔吐を伴う。項部硬直あり。血圧180/100mmHg、心拍数90回/分、SpO2 99%。
意識清明だが羞明を訴えている。""",
]


# ---------------------------------------------------------------------------
# Demo
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("=" * 70)
    print("Clinical NLP Processor Demo")
    print("=" * 70)

    for i, text in enumerate(SAMPLE_NOTES, 1):
        print(f"\n--- Note {i} ---")
        print(f"Raw text: {text[:80].strip()}…")

        note = parse_clinical_note(text)
        print(f"Demographics : {note.demographics}")
        print(f"Hx           : {note.medical_history}")
        print(f"CC           : {note.chief_complaint[:60]}")
        print(f"Symptoms     : {note.symptoms}")
        print(f"Vitals text  : {note.vitals_text}")
        print(f"Labs text    : {note.labs_text}")
        print(f"Findings     : {note.findings}")
        print(f"Keywords     : {note.keywords[:8]}…")

        case = note_to_case(note)
        result = diagnose(case, labs_text=note.labs_text)
        print(f"\n[DD Engine Result]")
        print(f"  Primary   : {result.primary['disease']}  "
              f"(prob={result.primary['probability']:.2f})")
        if result.differentials:
            top3 = result.differentials[:3]
            print(f"  Diff Dx   : {[d['disease'] for d in top3]}")
        print(f"  Urgency   : {result.urgency}")
        if result.red_flags:
            print(f"  Red flags : {result.red_flags[:2]}")

    print("\n" + "=" * 70)
    print("Done.")
