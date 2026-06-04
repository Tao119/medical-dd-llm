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


# ── 追加エンドポイント ─────────────────────────────────────────

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
