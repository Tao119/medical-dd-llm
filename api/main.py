import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, List
import json

from model.dd_engine import diagnose
from clinical.vitals import parse_vitals, assess_vitals
from clinical.lab_interpreter import interpret_labs
from clinical.risk_scores import calc_curb65, calc_qsofa
from clinical.icd10 import suggest_icd10
from clinical.drug_interactions import check_interactions, check_contraindications

app = FastAPI(
    title="Medical DD-LLM API",
    description="構造化鑑別診断 API: RAG + 臨床推論エンジン",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# RAG indexer (lazy init)
_indexer = None

def get_indexer():
    global _indexer
    if _indexer is None:
        index_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data/index")
        if os.path.exists(index_dir):
            from rag.indexer import MedicalIndexer
            from config import EMBED_MODEL
            _indexer = MedicalIndexer(EMBED_MODEL)
            _indexer.load(index_dir)
    return _indexer


class CaseInput(BaseModel):
    chief_complaint: str = Field(..., example="胸痛・冷汗")
    symptoms: List[str] = Field(..., example=["前胸部圧迫感", "左肩放散痛", "冷汗"])
    vitals: str = Field("", example="BP 90/60, HR 110, SpO2 94%, RR 24")
    history: str = Field("なし", example="高血圧・糖尿病・喫煙歴15年")
    demographics: str = Field("", example="65歳男性")
    labs: str = Field("", example="WBC 14000, CRP 8.5, TnI 0.8, BNP 450")


class VitalsInput(BaseModel):
    vitals_text: str = Field(..., example="BP 90/60, HR 120, SpO2 93%, RR 28")


class LabsInput(BaseModel):
    labs_text: str = Field(..., example="WBC 18000, CRP 15.0, TnI 1.2, BNP 800, Cr 2.5, K 6.1")


@app.get("/")
def root():
    return {
        "service": "Medical DD-LLM API v2.0",
        "endpoints": ["/diagnose", "/vitals", "/labs", "/icd10/search", "/health"],
    }


@app.get("/health")
def health():
    indexer = get_indexer()
    return {
        "status": "ok",
        "rag_ready": indexer is not None,
        "rag_chunks": len(indexer.chunks) if indexer else 0,
    }


@app.post("/diagnose")
def diagnose_endpoint(case_input: CaseInput):
    case = {
        "chief_complaint": case_input.chief_complaint,
        "symptoms": case_input.symptoms,
        "vitals": case_input.vitals,
        "history": case_input.history,
        "demographics": case_input.demographics,
    }
    indexer = get_indexer()
    docs = []
    if indexer:
        query = f"{case_input.chief_complaint} {' '.join(case_input.symptoms[:3])}"
        docs = indexer.retrieve(query, top_k=3)

    result = diagnose(case, retrieved_docs=docs, labs_text=case_input.labs)
    return result.to_dict()


@app.post("/vitals")
def vitals_endpoint(inp: VitalsInput):
    try:
        vs = parse_vitals(inp.vitals_text)
        av = assess_vitals(vs)
        return {
            "parsed": {
                "sbp": vs.sbp, "dbp": vs.dbp, "hr": vs.hr,
                "spo2": vs.spo2, "rr": vs.rr, "temp": vs.temp, "gcs": vs.gcs,
            },
            "assessment": av,
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/labs")
def labs_endpoint(inp: LabsInput):
    try:
        result = interpret_labs(inp.labs_text)
        return {
            "summary": result.summary,
            "flags": [
                {"name": f.name, "value": f.value, "status": f.status,
                 "unit": f.unit, "message": f.message}
                for f in result.flags
            ],
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/icd10/search")
def icd10_search(q: str, limit: int = 5):
    results = suggest_icd10(q)
    return {"results": results[:limit]}


@app.post("/risk/curb65")
def curb65_endpoint(
    rr: float = 20, sbp: float = 120, dbp: float = 80,
    age: int = 60, bun_mg_dl: Optional[float] = None,
    altered_consciousness: bool = False
):
    result = calc_curb65(rr=rr, sbp=sbp, dbp=dbp, age=age,
                         bun_mg_dl=bun_mg_dl, altered_consciousness=altered_consciousness)
    return {"score": result.score, "category": result.category,
            "recommendation": result.recommendation,
            "interpretation": result.interpretation}


@app.post("/risk/qsofa")
def qsofa_endpoint(rr: float = 20, sbp: float = 120, altered_consciousness: bool = False):
    result = calc_qsofa(rr=rr, sbp=sbp, altered_consciousness=altered_consciousness)
    return {"score": result.score, "components": result.components,
            "interpretation": result.interpretation}


class DrugCheckInput(BaseModel):
    drugs: List[str] = Field(..., example=["ワルファリン", "アスピリン", "メトホルミン"])
    diagnosis: str = Field("", example="急性腎障害")


@app.post("/drugs/check")
def drug_check_endpoint(inp: DrugCheckInput):
    interactions = check_interactions(inp.drugs)
    contraindications = check_contraindications(inp.diagnosis, inp.drugs) if inp.diagnosis else []
    severity_order = {"contraindicated": 0, "major": 1, "moderate": 2, "minor": 3}
    interactions.sort(key=lambda x: severity_order.get(x["severity"], 9))
    return {
        "drug_count": len(inp.drugs),
        "interaction_count": len(interactions),
        "contraindication_count": len(contraindications),
        "interactions": interactions,
        "contraindications": contraindications,
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8765)


# ── 既存追加エンドポイント ─────────────────────────────────────────

from clinical.pediatric import PediatricVitals, assess_pediatric_vitals, pediatric_drug_dose, holliday_segar
from clinical.treatment_protocols import get_protocol, format_protocol_text
from clinical.triage import triage as triage_fn
from clinical.drug_dosing import calc_dose, format_dose_result


class PedVitalsInput(BaseModel):
    age_months: int
    weight_kg: Optional[float] = None
    sbp: Optional[float] = None
    hr: Optional[float] = None
    rr: Optional[float] = None
    spo2: Optional[float] = None
    temp: Optional[float] = None

@app.post("/pediatric/vitals")
def ped_vitals(inp: PedVitalsInput):
    pv = PediatricVitals(**inp.model_dump())
    return assess_pediatric_vitals(pv)

@app.post("/pediatric/dose")
def ped_dose(drug: str, age_months: int, weight_kg: float):
    result = pediatric_drug_dose(drug, age_months=age_months, weight_kg=weight_kg)
    return {
        "drug": result.drug, "dose": result.calculated_dose,
        "route": result.route, "frequency": result.frequency,
        "max_dose": result.max_dose, "notes": result.notes
    }

@app.post("/pediatric/fluid")
def ped_fluid(weight_kg: float):
    f = holliday_segar(weight_kg)
    return {"daily_mL": f.daily_ml, "hourly_mL_h": f.hourly_rate_ml_h,
            "detail": f.calculation_detail}

@app.get("/protocol/{diagnosis}")
def get_treatment_protocol(diagnosis: str):
    proto = get_protocol(diagnosis)
    if not proto:
        raise HTTPException(status_code=404, detail=f"Protocol not found: {diagnosis}")
    return {
        "diagnosis": proto.diagnosis, "icd10": proto.icd10,
        "key_principle": proto.key_principle,
        "steps": [{"timing": s.timing, "action": s.action, "dose": s.dose,
                   "priority": s.priority} for s in proto.steps],
        "monitoring": proto.monitoring, "goals": proto.goals,
        "pitfalls": proto.pitfalls,
        "formatted": format_protocol_text(proto),
    }

class TriageInput(BaseModel):
    chief_complaint: str
    symptoms: List[str] = []
    vitals: str = ""
    pain_score: int = 0

@app.post("/triage")
def triage_endpoint(inp: TriageInput):
    case = {"chief_complaint": inp.chief_complaint, "symptoms": inp.symptoms}
    result = triage_fn(case, vitals_str=inp.vitals, pain_score=inp.pain_score)
    return {"level": result.level, "color": result.color, "name_ja": result.name_ja,
            "max_wait_minutes": result.max_wait_minutes, "reasoning": result.reasoning}

@app.post("/dose")
def dose_endpoint(drug: str, indication: str = "", weight_kg: float = 70,
                  crcl: float = 100, hepatic: bool = False):
    result = calc_dose(drug, indication=indication, weight_kg=weight_kg,
                       crcl=crcl, hepatic_impairment=hepatic)
    return {"drug": result.drug, "dose_text": result.dose_text,
            "total_daily": result.total_daily, "route": result.route,
            "adjustment_notes": result.adjustment_notes,
            "monitoring": result.monitoring, "max_dose": result.max_dose,
            "formatted": format_dose_result(result)}


# ── 専門科・ICU・症状チェッカー追加エンドポイント ─────────────────────────

from clinical.cardiology_specialist import (
    interpret_ecg, calc_cha2ds2vasc, classify_shock
)
from clinical.pulmonology_specialist import interpret_spirometry, calc_pe_probability
from clinical.neurology_specialist import calc_nihss, check_tpa_eligibility
from clinical.icu_scoring import calc_news2, calc_sofa
from viz.decision_tree import get_decision_tree, SUPPORTED_CONDITIONS
from viz.symptom_checker import SymptomChecker


# ── Cardiology ────────────────────────────────────────────────────────────

class ECGInput(BaseModel):
    ecg_text: str = Field(..., example="ST上昇 V1-V4, LBBB, QTc 500ms")


@app.post("/specialist/cardiology/ecg")
def ecg_endpoint(inp: ECGInput):
    """ECG interpretation with urgent flag detection."""
    result = interpret_ecg(inp.ecg_text)
    return {
        "findings": result.findings,
        "urgent_flags": result.urgent_flags,
        "interpretation": result.interpretation,
        "recommended_actions": result.recommended_actions,
    }


class CHA2DS2Input(BaseModel):
    age: int = Field(..., example=72)
    sex: str = Field(..., example="男")
    chf: bool = False
    hypertension: bool = False
    stroke: bool = False
    vascular: bool = False
    diabetes: bool = False


@app.post("/specialist/cardiology/chadsvasc")
def chadsvasc_endpoint(inp: CHA2DS2Input):
    """CHA2DS2-VASc score for AF stroke risk."""
    result = calc_cha2ds2vasc(
        age=inp.age, sex=inp.sex, chf=inp.chf,
        hypertension=inp.hypertension, stroke=inp.stroke,
        vascular=inp.vascular, diabetes=inp.diabetes,
    )
    return result


class ShockInput(BaseModel):
    sbp: float = Field(..., example=75.0)
    hr: float = Field(..., example=130.0)
    symptoms: List[str] = Field(default=[], example=["心筋梗塞", "肺水腫"])
    history: List[str] = Field(default=[], example=["冠動脈疾患"])


@app.post("/specialist/cardiology/shock")
def shock_endpoint(inp: ShockInput):
    """Shock classification and management."""
    result = classify_shock(sbp=inp.sbp, hr=inp.hr,
                            symptoms=inp.symptoms, history=inp.history)
    return result


# ── Pulmonology ───────────────────────────────────────────────────────────

class SpirometryInput(BaseModel):
    fev1_pct: float = Field(..., example=45.0, description="FEV1 % predicted")
    fvc_pct: float = Field(..., example=85.0, description="FVC % predicted")
    fev1_fvc: float = Field(..., example=0.55, description="FEV1/FVC ratio")


@app.post("/specialist/pulmonology/spirometry")
def spirometry_endpoint(inp: SpirometryInput):
    """Spirometry pattern interpretation (obstructive/restrictive/mixed/normal)."""
    result = interpret_spirometry(
        fev1_pct=inp.fev1_pct,
        fvc_pct=inp.fvc_pct,
        fev1_fvc=inp.fev1_fvc,
    )
    return {
        "pattern": result.pattern,
        "severity": result.severity,
        "gold_stage": result.gold_stage,
        "interpretation": result.interpretation,
    }


class PEWellsInput(BaseModel):
    hr: int = Field(..., example=115)
    dvt_signs: bool = False
    pe_more_likely: bool = False
    immobilization: bool = False
    prior_dvt_pe: bool = False
    hemoptysis: bool = False
    cancer: bool = False
    spo2: float = Field(default=96.0)
    age: int = Field(default=50)


@app.post("/specialist/pulmonology/pe_wells")
def pe_wells_endpoint(inp: PEWellsInput):
    """PE probability calculation using modified Wells score."""
    result = calc_pe_probability(
        hr=inp.hr,
        dvt_signs=inp.dvt_signs,
        pe_more_likely=inp.pe_more_likely,
        immobilization=inp.immobilization,
        prior_dvt_pe=inp.prior_dvt_pe,
        hemoptysis=inp.hemoptysis,
        cancer=inp.cancer,
        spo2=inp.spo2,
        age=inp.age,
    )
    return result


# ── Neurology ─────────────────────────────────────────────────────────────

class NIHSSInput(BaseModel):
    consciousness: int = Field(default=0, ge=0, le=3)
    orientation: int = Field(default=0, ge=0, le=2)
    commands: int = Field(default=0, ge=0, le=2)
    gaze: int = Field(default=0, ge=0, le=2)
    visual: int = Field(default=0, ge=0, le=3)
    facial: int = Field(default=0, ge=0, le=3)
    motor_arm_left: int = Field(default=0, ge=0, le=4)
    motor_arm_right: int = Field(default=0, ge=0, le=4)
    motor_leg_left: int = Field(default=0, ge=0, le=4)
    motor_leg_right: int = Field(default=0, ge=0, le=4)
    ataxia: int = Field(default=0, ge=0, le=2)
    sensory: int = Field(default=0, ge=0, le=2)
    language: int = Field(default=0, ge=0, le=3)
    dysarthria: int = Field(default=0, ge=0, le=2)
    extinction: int = Field(default=0, ge=0, le=2)


@app.post("/specialist/neurology/nihss")
def nihss_endpoint(inp: NIHSSInput):
    """NIHSS stroke severity calculation."""
    result = calc_nihss(**inp.model_dump())
    return {
        "total_score": result.total_score,
        "severity": result.severity,
        "mrs_predicted": result.mrs_predicted,
        "mrs_interpretation": result.mrs_interpretation,
        "component_scores": result.component_scores,
        "recommendations": result.recommendations,
    }


class TpaInput(BaseModel):
    ischemic_stroke: bool = True
    nihss: int = Field(default=0, ge=0)
    onset_hours: float = Field(default=0.0, ge=0.0)
    age: int = Field(default=18, ge=0)
    weight_kg: float = Field(default=70.0, gt=0)
    hemorrhage_on_ct: bool = False
    inr: float = Field(default=1.0, ge=0)
    platelets_k: float = Field(default=200.0, ge=0)
    recent_major_surgery_days: int = Field(default=9999, ge=0)
    recent_intracranial_surgery: bool = False
    sbp: float = Field(default=140.0)
    dbp: float = Field(default=80.0)
    glucose: float = Field(default=100.0)
    on_anticoagulant: bool = False
    on_doac: bool = False
    prior_stroke_diabetes: bool = False


@app.post("/specialist/neurology/tpa")
def tpa_endpoint(inp: TpaInput):
    """tPA eligibility assessment for ischemic stroke (AHA 2023)."""
    result = check_tpa_eligibility(**inp.model_dump())
    return {
        "eligible": result.eligible,
        "dose_mg": result.dose_mg,
        "absolute_exclusions": result.absolute_exclusions,
        "relative_exclusions": result.relative_exclusions,
        "notes": result.notes,
    }


# ── ICU Scoring ───────────────────────────────────────────────────────────

class NEWS2Input(BaseModel):
    rr: float = Field(default=16.0)
    spo2_pct: float = Field(default=97.0)
    on_supplemental_o2: bool = False
    sbp_mmhg: float = Field(default=120.0)
    hr: float = Field(default=75.0)
    consciousness: str = Field(default="A", description="A/C/V/P/U (ACVPU scale)")
    temperature_c: float = Field(default=36.5)
    hypercapnic_respiratory_failure: bool = False


@app.post("/icu/news2")
def news2_endpoint(inp: NEWS2Input):
    """NEWS2 Early Warning Score calculation."""
    result = calc_news2(**inp.model_dump())
    return {
        "score": result.score,
        "risk_category": result.risk_category,
        "component_scores": result.component_scores,
        "escalation_required": result.escalation_required,
        "recommended_response": result.recommended_response,
        "monitoring_frequency": result.monitoring_frequency,
    }


class SOFAInput(BaseModel):
    pao2_fio2: float = Field(default=400.0, description="PaO2/FiO2 ratio")
    on_respiratory_support: bool = False
    platelets_k: float = Field(default=200.0, description="platelets ×10³/μL")
    bilirubin_mg_dl: float = Field(default=0.8)
    map_mmhg: float = Field(default=75.0)
    vasopressor: str = Field(default="none",
                              description="none/map_low/dopa_low/dopa_mid/epi/norepi")
    gcs: int = Field(default=15, ge=3, le=15)
    cr_mg_dl: float = Field(default=0.9)
    urine_output_ml_day: Optional[float] = None


@app.post("/icu/sofa")
def sofa_endpoint(inp: SOFAInput):
    """SOFA (Sequential Organ Failure Assessment) score."""
    result = calc_sofa(**inp.model_dump())
    return {
        "score": result.score,
        "organ_scores": result.organ_scores,
        "interpretation": result.interpretation,
        "mortality_estimate": result.mortality_estimate,
        "recommendations": result.recommendations,
    }


# ── Decision Tree ─────────────────────────────────────────────────────────

@app.post("/decision_tree/{condition}")
def decision_tree_endpoint(condition: str):
    """ASCII clinical decision tree for chest_pain, sepsis, or dyspnea."""
    try:
        tree_text = get_decision_tree(condition)
        return {
            "condition": condition,
            "ascii_tree": tree_text,
            "supported_conditions": SUPPORTED_CONDITIONS,
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ── Symptom Checker ───────────────────────────────────────────────────────

# In-memory session store (single-process, demo only)
_checkers: dict[str, SymptomChecker] = {}


class SymptomCheckInput(BaseModel):
    session_id: str = Field(default="default", description="Session identifier")
    action: str = Field(..., description="'start' to begin, 'answer' to respond")
    response: Optional[str] = Field(default=None, description="Answer text (when action='answer')")


@app.post("/symptom_check")
def symptom_check_endpoint(inp: SymptomCheckInput):
    """Interactive symptom checker. Start with action='start', then action='answer'."""
    sid = inp.session_id
    if sid not in _checkers:
        _checkers[sid] = SymptomChecker()
    checker = _checkers[sid]

    if inp.action == "start":
        question = checker.start()
        return {"type": "question", "content": question, "session_id": sid}

    elif inp.action == "answer":
        if not inp.response:
            raise HTTPException(status_code=400, detail="response field required for action='answer'")
        result = checker.answer(inp.response)
        if isinstance(result, str):
            return {"type": "question", "content": result, "session_id": sid}
        else:
            # DiagnosisResult
            return {
                "type": "result",
                "session_id": sid,
                "differentials": result.differentials,
                "urgency": result.urgency,
                "urgency_jp": result.urgency_jp,
                "next_steps": result.next_steps,
                "red_flags": result.red_flags,
                "path_summary": result.path_summary,
            }
    else:
        raise HTTPException(status_code=400, detail=f"Unknown action: {inp.action}. Use 'start' or 'answer'.")


# ── 薬剤データベース エンドポイント ────────────────────────────────

from clinical.drug_database import (
    DRUG_DATABASE, get_drug_info, search_drug,
    check_drug_interactions_from_db, get_all_drug_classes
)


@app.get("/drugs/{name}")
def drug_info_endpoint(name: str):
    """薬剤名で詳細情報を取得（完全一致 / 部分一致 / Fuzzy match）"""
    info = get_drug_info(name)
    if info:
        return {
            "name_ja": info.name_ja,
            "name_en": info.name_en,
            "drug_class": info.drug_class,
            "indications": info.indications,
            "adult_doses": info.adult_doses,
            "contraindications": info.contraindications,
            "major_interactions": info.major_interactions,
            "renal_adjustment": info.renal_adjustment,
            "hepatic_adjustment": info.hepatic_adjustment,
            "monitoring": info.monitoring,
            "side_effects": info.side_effects,
            "notes": info.notes,
        }
    # Try fuzzy search
    results = search_drug(name, max_results=5)
    if results:
        return {
            "message": f"Exact match not found. Suggestions: {[r[0] for r in results]}",
            "suggestions": [
                {"name": r[0], "drug_class": r[1].drug_class, "name_en": r[1].name_en}
                for r in results
            ],
        }
    raise HTTPException(status_code=404, detail=f"Drug not found: {name}")


@app.get("/drugs/search/{query}")
def drug_search_endpoint(query: str, limit: int = 5):
    """薬剤名・英語名で検索"""
    results = search_drug(query, max_results=limit)
    if not results:
        return {"query": query, "results": [], "message": "No drugs found"}
    return {
        "query": query,
        "results": [
            {
                "name_ja": r[1].name_ja,
                "name_en": r[1].name_en,
                "drug_class": r[1].drug_class,
                "indications": r[1].indications[:3],
            }
            for r in results
        ],
    }


class DrugInteractionDBInput(BaseModel):
    drugs: List[str] = Field(..., example=["ワルファリン", "アスピリン", "アミオダロン"])


@app.post("/drugs/interactions_db")
def drug_interactions_db_endpoint(inp: DrugInteractionDBInput):
    """薬剤データベースを使った相互作用チェック（詳細版）"""
    interactions = check_drug_interactions_from_db(inp.drugs)
    # Find drugs not in DB
    not_found = [d for d in inp.drugs if get_drug_info(d) is None]
    return {
        "drugs_checked": inp.drugs,
        "drugs_not_in_db": not_found,
        "interaction_count": len(interactions),
        "interactions": interactions,
        "recommendation": "相互作用が見つかった場合は薬剤師・医師に相談してください",
    }


@app.get("/drugs/classes/all")
def drug_classes_endpoint():
    """薬剤クラス別一覧を返す"""
    classes = get_all_drug_classes()
    return {
        "total_drugs": len(DRUG_DATABASE),
        "total_classes": len(classes),
        "classes": {cls: sorted(drugs) for cls, drugs in sorted(classes.items())},
    }


@app.get("/drugs/list/all")
def drug_list_all_endpoint():
    """全薬剤リストを返す"""
    return {
        "total": len(DRUG_DATABASE),
        "drugs": sorted(DRUG_DATABASE.keys()),
    }
