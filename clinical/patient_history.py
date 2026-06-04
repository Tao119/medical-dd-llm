"""
clinical/patient_history.py — Longitudinal Patient Tracker
──────────────────────────────────────────────────────────
Track patient encounters over time, detect clinical trends,
and identify signs of deterioration.

Key classes
───────────
  Encounter      : a single clinical visit (case + diagnosis + labs + notes)
  PatientHistory : ordered collection of encounters with trend analysis

Deterioration detection criteria
─────────────────────────────────
  - SpO2 trending downward over 3+ consecutive encounters
  - Urgency escalating (routine → urgent → immediate)
  - New red flags appearing
  - Lab values worsening: Cr rising, WBC consistently elevated
"""

from __future__ import annotations

import os
import sys
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from clinical.vitals import parse_vitals


# ─────────────────────────────────────────────────────────────────────────────
#  Data model
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class Encounter:
    encounter_id: str
    timestamp: str          # ISO-8601 format: "YYYY-MM-DDTHH:MM:SS"
    case: dict              # same structure as dd_engine input
    diagnosis: dict         # result from diagnose().to_dict()
    labs_text: str          # free-text lab string, e.g. "WBC 14000, Cr 2.1"
    notes: str = ""


# ─────────────────────────────────────────────────────────────────────────────
#  Lab value extractor (lightweight; does not depend on lab_interpreter)
# ─────────────────────────────────────────────────────────────────────────────

_LAB_PATTERNS: dict[str, re.Pattern] = {
    "WBC":   re.compile(r"WBC\s*[:：]?\s*([\d.]+)", re.IGNORECASE),
    "Cr":    re.compile(r"(?:Cr|Creatinine|クレアチニン)\s*[:：]?\s*([\d.]+)", re.IGNORECASE),
    "CRP":   re.compile(r"CRP\s*[:：]?\s*([\d.]+)", re.IGNORECASE),
    "TnI":   re.compile(r"(?:TnI|Troponin[ -]?I?)\s*[:：]?\s*([\d.]+)", re.IGNORECASE),
    "BNP":   re.compile(r"BNP\s*[:：]?\s*([\d.]+)", re.IGNORECASE),
    "Hb":    re.compile(r"Hb\s*[:：]?\s*([\d.]+)", re.IGNORECASE),
    "Plt":   re.compile(r"Plt\s*[:：]?\s*([\d.]+)", re.IGNORECASE),
    "Lac":   re.compile(r"(?:Lac|Lactate)\s*[:：]?\s*([\d.]+)", re.IGNORECASE),
    "Na":    re.compile(r"Na\s*[:：]?\s*([\d.]+)", re.IGNORECASE),
    "K":     re.compile(r"K\s*[:：]?\s*([\d.]+)", re.IGNORECASE),
    "Glu":   re.compile(r"(?:Glu|Glucose)\s*[:：]?\s*([\d.]+)", re.IGNORECASE),
    "HbA1c": re.compile(r"HbA1c\s*[:：]?\s*([\d.]+)", re.IGNORECASE),
}


def _extract_labs(labs_text: str) -> dict[str, float]:
    """Parse known lab values from a free-text string."""
    result = {}
    for name, pattern in _LAB_PATTERNS.items():
        m = pattern.search(labs_text)
        if m:
            try:
                result[name] = float(m.group(1))
            except ValueError:
                pass
    return result


def _extract_spo2_from_vitals(case: dict) -> Optional[float]:
    """Try to extract SpO2 from the case vitals string."""
    vitals_raw = case.get("vitals", "")
    if not vitals_raw:
        return None
    vs = parse_vitals(vitals_raw)
    return vs.spo2


def _urgency_level(urgency: str) -> int:
    """Convert urgency string to numeric level (higher = more urgent)."""
    return {"routine": 0, "urgent": 1, "immediate": 2}.get(urgency.lower(), -1)


# ─────────────────────────────────────────────────────────────────────────────
#  PatientHistory
# ─────────────────────────────────────────────────────────────────────────────

class PatientHistory:
    """
    Longitudinal record of a single patient's clinical encounters.

    Parameters
    ----------
    patient_id : unique patient identifier string
    """

    def __init__(self, patient_id: str):
        self.patient_id: str = patient_id
        self._encounters: list[Encounter] = []

    # ── Core interface ────────────────────────────────────────────────────────

    def add_encounter(self, encounter: Encounter) -> None:
        """Append an encounter, maintaining chronological order."""
        self._encounters.append(encounter)
        self._encounters.sort(key=lambda e: e.timestamp)

    @property
    def encounters(self) -> list[Encounter]:
        return list(self._encounters)

    # ── Trend extraction ──────────────────────────────────────────────────────

    def get_trend(self, metric: str) -> list:
        """
        Return per-encounter values for a named metric.

        Supported metrics
        ─────────────────
        "primary_diagnosis" — primary diagnosis name from each encounter
        "urgency"           — urgency string from each encounter
        "vital_sbp"         — systolic blood pressure
        "vital_hr"          — heart rate
        "vital_spo2"        — SpO2
        "vital_rr"          — respiratory rate
        "vital_temp"        — temperature
        "lab_<NAME>"        — lab value, e.g. "lab_Cr", "lab_WBC"

        Returns
        -------
        list of (timestamp, value) tuples.  Value is None when not available.
        """
        results = []
        for enc in self._encounters:
            ts = enc.timestamp
            if metric == "primary_diagnosis":
                val = (enc.diagnosis.get("primary") or {}).get("name")
            elif metric == "urgency":
                val = enc.diagnosis.get("urgency")
            elif metric.startswith("vital_"):
                field_name = metric[len("vital_"):]  # e.g. "sbp"
                vs = parse_vitals(enc.case.get("vitals", ""))
                val = getattr(vs, field_name, None)
            elif metric.startswith("lab_"):
                lab_name = metric[len("lab_"):]
                parsed = _extract_labs(enc.labs_text)
                val = parsed.get(lab_name)
            else:
                val = None
            results.append((ts, val))
        return results

    # ── Deterioration detection ───────────────────────────────────────────────

    def detect_deterioration(self) -> dict:
        """
        Analyse the encounter history for signs of clinical deterioration.

        Returns a dict with:
          deteriorating (bool)
          signals (list[str])  — human-readable descriptions of each signal found
          severity ("none" | "mild" | "moderate" | "severe")
        """
        signals: list[str] = []

        # 1. SpO2 trending downward over 3+ encounters
        spo2_trend = [(ts, v) for ts, v in self.get_trend("vital_spo2") if v is not None]
        if len(spo2_trend) >= 3:
            spo2_vals = [v for _, v in spo2_trend]
            # Check if monotonically decreasing over last 3 values
            for i in range(len(spo2_vals) - 2):
                window = spo2_vals[i:i + 3]
                if window[0] > window[1] > window[2]:
                    drop = window[0] - window[2]
                    signals.append(
                        f"SpO2 trending downward over 3 encounters "
                        f"({window[0]:.0f}% → {window[2]:.0f}%, drop {drop:.1f}%)"
                    )
                    break

        # 2. Urgency escalating
        urgency_trend = [v for _, v in self.get_trend("urgency") if v is not None]
        if len(urgency_trend) >= 2:
            levels = [_urgency_level(u) for u in urgency_trend]
            # Any two consecutive increases
            if any(levels[i + 1] > levels[i] for i in range(len(levels) - 1)):
                last_two = [urgency_trend[i] for i in [-2, -1] if i < len(urgency_trend)]
                signals.append(
                    f"Urgency escalating: {' → '.join(last_two)}"
                )
            # If last encounter is immediate, flag strongly
            if urgency_trend and _urgency_level(urgency_trend[-1]) == 2:
                signals.append("Current urgency level: IMMEDIATE")

        # 3. New red flags appearing
        if len(self._encounters) >= 2:
            prev_flags: set[str] = set()
            for enc in self._encounters[:-1]:
                prev_flags.update(enc.diagnosis.get("red_flags", []))
            current_flags: set[str] = set(self._encounters[-1].diagnosis.get("red_flags", []))
            new_flags = current_flags - prev_flags
            if new_flags:
                signals.append(
                    f"New red flags: {', '.join(sorted(new_flags))}"
                )

        # 4a. Creatinine (Cr) rising
        cr_trend = [(ts, v) for ts, v in self.get_trend("lab_Cr") if v is not None]
        if len(cr_trend) >= 2:
            cr_vals = [v for _, v in cr_trend]
            if cr_vals[-1] > cr_vals[0] * 1.5:
                signals.append(
                    f"Cr rising: {cr_vals[0]:.2f} → {cr_vals[-1]:.2f} mg/dL "
                    f"(+{(cr_vals[-1]/cr_vals[0] - 1)*100:.0f}%)"
                )
            elif all(cr_vals[i + 1] >= cr_vals[i] for i in range(len(cr_vals) - 1)):
                signals.append(
                    f"Cr consistently rising: {cr_vals[0]:.2f} → {cr_vals[-1]:.2f} mg/dL"
                )

        # 4b. WBC consistently elevated (>= 11000 in last 3 measurements)
        wbc_trend = [(ts, v) for ts, v in self.get_trend("lab_WBC") if v is not None]
        if len(wbc_trend) >= 3:
            wbc_vals = [v for _, v in wbc_trend[-3:]]
            if all(v >= 11000 for v in wbc_vals):
                signals.append(
                    f"WBC persistently elevated over 3 encounters "
                    f"({wbc_vals[0]:.0f} → {wbc_vals[-1]:.0f} /μL)"
                )

        # Severity categorisation
        n = len(signals)
        if n == 0:
            severity = "none"
        elif n == 1:
            severity = "mild"
        elif n == 2:
            severity = "moderate"
        else:
            severity = "severe"

        return {
            "deteriorating": n > 0,
            "signals": signals,
            "severity": severity,
        }

    # ── Convenience methods ───────────────────────────────────────────────────

    def summarize(self) -> str:
        """Return a plain-text summary of all encounters."""
        if not self._encounters:
            return f"Patient {self.patient_id}: no encounters recorded."
        lines = [f"Patient: {self.patient_id}  ({len(self._encounters)} encounters)"]
        lines.append("-" * 60)
        for enc in self._encounters:
            prim = (enc.diagnosis.get("primary") or {}).get("name", "unknown")
            urgency = enc.diagnosis.get("urgency", "?")
            red_flags = enc.diagnosis.get("red_flags", [])
            flag_str = ", ".join(red_flags) if red_flags else "none"
            lines.append(
                f"  [{enc.timestamp[:10]}]  ID={enc.encounter_id}\n"
                f"    Diagnosis : {prim}  (urgency: {urgency})\n"
                f"    Red flags : {flag_str}\n"
                f"    Labs      : {enc.labs_text or 'n/a'}\n"
                f"    Notes     : {enc.notes or 'n/a'}"
            )
        det = self.detect_deterioration()
        lines.append("-" * 60)
        lines.append(f"Deterioration: {det['severity'].upper()}")
        for s in det["signals"]:
            lines.append(f"  • {s}")
        return "\n".join(lines)

    def get_recurring_diagnoses(self) -> list[dict]:
        """
        Return diagnoses that appear in more than one encounter.

        Returns a list of dicts: {"name": str, "count": int, "encounters": list[str]}
        sorted by count descending.
        """
        counter: dict[str, list[str]] = {}
        for enc in self._encounters:
            prim = (enc.diagnosis.get("primary") or {}).get("name")
            if prim:
                counter.setdefault(prim, []).append(enc.encounter_id)
        result = [
            {"name": name, "count": len(ids), "encounters": ids}
            for name, ids in counter.items()
            if len(ids) > 1
        ]
        return sorted(result, key=lambda x: -x["count"])

    def drug_timeline(self, drug: str) -> list[tuple[str, str]]:
        """
        Find encounters where a specific drug appears in notes or next_steps.

        Parameters
        ----------
        drug : drug name (case-insensitive substring match)

        Returns
        -------
        list of (timestamp, source_text) tuples
        """
        matches = []
        pattern = re.compile(re.escape(drug), re.IGNORECASE)
        for enc in self._encounters:
            sources = []
            if pattern.search(enc.notes or ""):
                sources.append(enc.notes)
            for step in enc.diagnosis.get("next_steps", []):
                if pattern.search(step):
                    sources.append(step)
            if sources:
                matches.append((enc.timestamp, " | ".join(sources)))
        return matches


# ─────────────────────────────────────────────────────────────────────────────
#  Demo helpers
# ─────────────────────────────────────────────────────────────────────────────

def _make_encounter(
    enc_id: str,
    date: str,
    primary_name: str,
    urgency: str,
    red_flags: list[str],
    next_steps: list[str],
    vitals_str: str,
    labs_str: str,
    notes: str = "",
) -> Encounter:
    case = {"vitals": vitals_str, "text": primary_name}
    diagnosis = {
        "primary": {"name": primary_name, "probability": 0.7},
        "differentials": [],
        "red_flags": red_flags,
        "next_steps": next_steps,
        "urgency": urgency,
        "risk_scores": {},
        "lab_flags": [],
    }
    return Encounter(
        encounter_id=enc_id,
        timestamp=f"{date}T09:00:00",
        case=case,
        diagnosis=diagnosis,
        labs_text=labs_str,
        notes=notes,
    )


def create_deteriorating_patient() -> PatientHistory:
    """
    Construct a PatientHistory with 5 encounters showing gradual deterioration.

    Clinical narrative
    ──────────────────
    A 68-year-old male admitted with suspected pneumonia.
    Over the course of 5 encounters he develops worsening respiratory
    function, rising creatinine (acute kidney injury), persistent
    leukocytosis, and eventual septic shock.
    """
    ph = PatientHistory("PT-7845")

    ph.add_encounter(_make_encounter(
        "E1", "2026-06-01",
        primary_name="Community-acquired pneumonia",
        urgency="urgent",
        red_flags=[],
        next_steps=["chest X-ray", "sputum culture", "start amoxicillin"],
        vitals_str="BP 130/80, HR 88, SpO2 96%, RR 18, 体温 37.8℃",
        labs_str="WBC 12000, CRP 3.2, Cr 1.1",
        notes="Day 1: amoxicillin 500 mg TID started. Mild cough.",
    ))

    ph.add_encounter(_make_encounter(
        "E2", "2026-06-02",
        primary_name="Community-acquired pneumonia",
        urgency="urgent",
        red_flags=["発熱"],
        next_steps=["upgrade antibiotics", "repeat chest X-ray", "IV fluid"],
        vitals_str="BP 122/75, HR 98, SpO2 94%, RR 22, 体温 38.6℃",
        labs_str="WBC 15000, CRP 8.1, Cr 1.3",
        notes="Day 2: worsening fever. Switched to LVFX 500 mg IV. Started 500 mL NS.",
    ))

    ph.add_encounter(_make_encounter(
        "E3", "2026-06-03",
        primary_name="Pneumonia with sepsis",
        urgency="urgent",
        red_flags=["発熱", "呼吸困難"],
        next_steps=["blood culture ×2", "broad-spectrum antibiotics", "ICU consult"],
        vitals_str="BP 108/68, HR 112, SpO2 91%, RR 26, 体温 39.2℃",
        labs_str="WBC 18000, CRP 15.4, Cr 1.7, Lac 2.1",
        notes="Day 3: oxygen 4 L via nasal cannula. ICU consult requested.",
    ))

    ph.add_encounter(_make_encounter(
        "E4", "2026-06-04",
        primary_name="Septic shock (pneumonia source)",
        urgency="immediate",
        red_flags=["発熱", "呼吸困難", "ショック"],
        next_steps=["transfer to ICU", "vasopressors", "intubation standby", "CRRT consideration"],
        vitals_str="BP 88/54, HR 128, SpO2 87%, RR 30, 体温 39.8℃",
        labs_str="WBC 21000, CRP 22.0, Cr 2.4, Lac 4.5, BNP 780",
        notes="Day 4: vasopressors started. Noradrenalin 0.1 mcg/kg/min.",
    ))

    ph.add_encounter(_make_encounter(
        "E5", "2026-06-05",
        primary_name="Septic shock with multi-organ dysfunction",
        urgency="immediate",
        red_flags=["発熱", "呼吸困難", "ショック", "意識障害"],
        next_steps=["CRRT", "increase vasopressors", "prone positioning", "family meeting"],
        vitals_str="BP 72/42, HR 140, SpO2 84%, RR 35, 体温 40.1℃",
        labs_str="WBC 23000, CRP 30.0, Cr 3.8, Lac 7.2, BNP 1200",
        notes="Day 5: intubated. CRRT initiated. Family informed of critical status.",
    ))

    return ph


# ─────────────────────────────────────────────────────────────────────────────
#  Main
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 65)
    print("PatientHistory — Longitudinal Tracker Demo")
    print("=" * 65)

    ph = create_deteriorating_patient()

    # Full summary
    print(ph.summarize())

    # Trend queries
    print("\n--- SpO2 trend ---")
    for ts, v in ph.get_trend("vital_spo2"):
        print(f"  {ts[:10]} : {v}%")

    print("\n--- Urgency trend ---")
    for ts, v in ph.get_trend("urgency"):
        print(f"  {ts[:10]} : {v}")

    print("\n--- Creatinine trend ---")
    for ts, v in ph.get_trend("lab_Cr"):
        print(f"  {ts[:10]} : {v} mg/dL")

    print("\n--- WBC trend ---")
    for ts, v in ph.get_trend("lab_WBC"):
        print(f"  {ts[:10]} : {v} /μL")

    print("\n--- Primary diagnosis trend ---")
    for ts, v in ph.get_trend("primary_diagnosis"):
        print(f"  {ts[:10]} : {v}")

    # Deterioration report
    print("\n--- Deterioration Detection ---")
    det = ph.detect_deterioration()
    print(f"Deteriorating: {det['deteriorating']}  severity: {det['severity'].upper()}")
    for sig in det["signals"]:
        print(f"  • {sig}")

    # Recurring diagnoses
    print("\n--- Recurring Diagnoses ---")
    for rec in ph.get_recurring_diagnoses():
        print(f"  {rec['name']} × {rec['count']}: encounters {rec['encounters']}")

    # Drug timeline
    print("\n--- Drug timeline: 'vasopressor' ---")
    for ts, txt in ph.drug_timeline("vasopressor"):
        print(f"  {ts[:10]} : {txt[:80]}")

    print("\n--- Drug timeline: 'amoxicillin' ---")
    for ts, txt in ph.drug_timeline("amoxicillin"):
        print(f"  {ts[:10]} : {txt[:80]}")
