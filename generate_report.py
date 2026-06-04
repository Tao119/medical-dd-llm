"""
generate_report.py — Clinical Case Report Generator

Usage:
  from generate_report import generate_case_report, batch_report

  text_report = generate_case_report(case, diagnosis_result, format="text")
  html_report = generate_case_report(case, diagnosis_result, format="html")
  json_report = generate_case_report(case, diagnosis_result, format="json")

Run batch_report() to generate 10 sample reports saved to reports/ directory.
"""

from __future__ import annotations

import os
import sys
import json
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from model.dd_engine import diagnose, DiagnosisResult
from clinical.treatment_protocols import get_protocol
from clinical.vitals import parse_vitals, assess_vitals

REPORTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "reports")
os.makedirs(REPORTS_DIR, exist_ok=True)

JST = timezone(timedelta(hours=9))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now_jst() -> str:
    return datetime.now(JST).strftime("%Y-%m-%d %H:%M")


def _urgency_label(urgency: str) -> str:
    return {
        "immediate": "🔴 即時対応",
        "urgent":    "🟡 緊急",
        "routine":   "🟢 通常",
    }.get(urgency, urgency)


def _severity_label(severity: str) -> str:
    return {
        "critical": "CRITICAL",
        "warning":  "WARNING",
        "normal":   "NORMAL",
    }.get(severity, severity)


def _lab_badge(status: str) -> str:
    return {
        "critical": "[CRITICAL]",
        "high":     "[HIGH]",
        "low":      "[LOW]",
        "normal":   "[NORMAL]",
    }.get(status.lower(), f"[{status.upper()}]")


# ---------------------------------------------------------------------------
# TEXT report
# ---------------------------------------------------------------------------

def _render_text(case: dict, result: DiagnosisResult) -> str:
    lines = []
    a = lines.append

    a("=== 臨床症例報告 ===")
    a(f"日時: {_now_jst()}")
    a(f"患者情報: {case.get('demographics', '不明')}")
    a(f"主訴: {case.get('chief_complaint', '不明')}")

    # --- Vital signs ---
    a("")
    a("【バイタルサイン評価】")
    va = result.vital_assessment
    if va:
        a(f"重症度: {_severity_label(va.get('severity', 'normal'))}")
        for flag in va.get("flags", []):
            a(f"  ⚠ {flag.get('message', '')}")
        if not va.get("flags"):
            a("  → 異常なし")
    else:
        vitals_str = case.get("vitals", "")
        if vitals_str:
            a(f"  {vitals_str}")
        else:
            a("  バイタルサイン情報なし")

    # --- Differential diagnosis ---
    a("")
    a("【鑑別診断】")
    primary = result.primary
    icd = result.icd10
    icd_str = f" [ICD-10: {icd['code']}]" if icd and icd.get("code") else ""
    prob_pct = int(primary.get("probability", 0) * 100)
    a(f"第一診断: {primary.get('disease', '不明')} (ACS) — 確率 {prob_pct}%{icd_str}")
    basis = primary.get("basis", "")
    if basis:
        a(f"根拠: {basis}")
    for rank, diff in enumerate(result.differentials[:3], start=2):
        diff_prob = int(diff.get("probability", 0) * 100)
        a(f"  {rank}位: {diff.get('disease', '')} ({diff_prob}%)")

    # --- Risk scores ---
    a("")
    a("【リスクスコア】")
    if result.risk_scores:
        for score_name, score_data in result.risk_scores.items():
            if isinstance(score_data, dict):
                score_val = score_data.get("score", "N/A")
                category  = score_data.get("category", "")
                mace_risk = score_data.get("mace_risk", None)
                interp    = score_data.get("interpretation", "")
                if mace_risk:
                    a(f"  {score_name}: {score_val} → {category} (MACE {mace_risk}%)")
                elif interp:
                    a(f"  {score_name}: {score_val} → {interp}")
                elif category:
                    a(f"  {score_name}: {score_val} → {category}")
                else:
                    a(f"  {score_name}: {score_val}")
    else:
        a("  スコア情報なし")

    # --- Lab values ---
    a("")
    a("【検査値】")
    if result.lab_flags:
        for flag in result.lab_flags:
            badge = _lab_badge(flag.get("status", "normal"))
            name  = flag.get("name", "")
            val   = flag.get("value", "")
            unit  = flag.get("unit", "")
            a(f"  {badge} {name}: {val} {unit}".rstrip())
    else:
        lab_text = case.get("labs", "")
        if lab_text:
            a(f"  {lab_text}")
        else:
            a("  検査値情報なし")

    # --- Recommendations ---
    a("")
    a("【推奨事項】")
    if result.red_flags:
        a("Red Flags:")
        for rf in result.red_flags:
            a(f"  ⚠ {rf}")
    if result.next_steps:
        a("Next Steps:")
        for ns in result.next_steps:
            a(f"  ✓ {ns}")
    a(f"緊急度: {_urgency_label(result.urgency)}")

    # --- Treatment protocol ---
    a("")
    protocol = get_protocol(primary.get("disease", ""))
    if protocol:
        a(f"【治療プロトコル】（{protocol.diagnosis}標準）")
        for step in protocol.steps[:6]:
            dose_str = f" {step.dose}" if step.dose else ""
            a(f"  [{step.timing}] {step.action}{dose_str}")
        if protocol.monitoring:
            a("  モニタリング: " + "、".join(protocol.monitoring[:3]))
    else:
        a("【治療プロトコル】")
        a("  標準プロトコルを参照のこと")

    a("")
    a("=== レポート終 ===")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# JSON report
# ---------------------------------------------------------------------------

def _render_json(case: dict, result: DiagnosisResult) -> str:
    protocol = get_protocol(result.primary.get("disease", ""))
    protocol_steps = []
    if protocol:
        for step in protocol.steps:
            protocol_steps.append({
                "timing":  step.timing,
                "action":  step.action,
                "dose":    step.dose,
                "priority": step.priority,
            })

    data = {
        "generated_at":    _now_jst(),
        "patient":         case.get("demographics", ""),
        "chief_complaint": case.get("chief_complaint", ""),
        "vitals_raw":      case.get("vitals", ""),
        "vital_assessment": result.vital_assessment,
        "primary_diagnosis": {
            "disease":     result.primary.get("disease", ""),
            "probability": result.primary.get("probability", 0),
            "basis":       result.primary.get("basis", ""),
            "icd10":       result.icd10,
        },
        "differentials": result.differentials,
        "risk_scores":   result.risk_scores,
        "lab_flags":     result.lab_flags,
        "red_flags":     result.red_flags,
        "next_steps":    result.next_steps,
        "urgency":       result.urgency,
        "protocol_steps": protocol_steps,
    }
    return json.dumps(data, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# HTML report
# ---------------------------------------------------------------------------

_HTML_STYLE = """
body { font-family: 'Segoe UI', Arial, sans-serif; max-width: 860px;
       margin: 30px auto; padding: 20px; background: #f7f9fc; color: #2c3e50; }
h1   { background: #2c3e50; color: white; padding: 12px 20px;
       border-radius: 6px; font-size: 1.3em; margin: 0 0 20px; }
h2   { border-left: 4px solid #3498db; padding-left: 10px;
       color: #2c3e50; font-size: 1.0em; margin: 20px 0 8px; }
.meta     { color: #7f8c8d; font-size: 0.88em; margin-bottom: 18px; }
.critical { background: #fdecea; border: 1px solid #e74c3c; border-radius: 4px;
            padding: 6px 12px; margin: 4px 0; font-size: 0.9em; }
.warning  { background: #fef9e7; border: 1px solid #f39c12; border-radius: 4px;
            padding: 6px 12px; margin: 4px 0; font-size: 0.9em; }
.normal   { background: #eafaf1; border: 1px solid #27ae60; border-radius: 4px;
            padding: 6px 12px; margin: 4px 0; font-size: 0.9em; }
.diagnosis-primary { background: #ebf5fb; border: 1px solid #3498db;
                     border-radius: 4px; padding: 10px 14px; margin: 6px 0; }
.diagnosis-diff    { padding: 4px 14px; color: #555; font-size: 0.9em; }
.next-step { background: #eafaf1; padding: 5px 12px; margin: 3px 0;
             border-radius: 3px; font-size: 0.9em; }
.protocol-step { display: flex; gap: 12px; padding: 5px 0;
                 border-bottom: 1px solid #eee; font-size: 0.9em; }
.timing { background: #3498db; color: white; padding: 2px 8px;
          border-radius: 10px; font-size: 0.8em; white-space: nowrap;
          align-self: center; }
.badge-critical { color: #e74c3c; font-weight: bold; }
.badge-high     { color: #e67e22; font-weight: bold; }
.badge-low      { color: #3498db; font-weight: bold; }
.badge-normal   { color: #27ae60; }
.urgency        { display: inline-block; padding: 6px 14px; border-radius: 4px;
                  font-weight: bold; font-size: 1.0em; }
.urgency-immediate { background: #fdecea; color: #e74c3c; }
.urgency-urgent    { background: #fef9e7; color: #e67e22; }
.urgency-routine   { background: #eafaf1; color: #27ae60; }
.score-box { background: white; border: 1px solid #ddd; border-radius: 4px;
             padding: 8px 14px; display: inline-block; margin: 4px; min-width: 160px; }
.score-name  { font-size: 0.8em; color: #7f8c8d; }
.score-value { font-size: 1.2em; font-weight: bold; color: #2c3e50; }
"""


def _html_vital_badge(flag: dict) -> str:
    msg = flag.get("message", "")
    return f'<div class="critical">⚠ {msg}</div>'


def _render_html(case: dict, result: DiagnosisResult) -> str:
    primary  = result.primary
    icd      = result.icd10
    icd_str  = f" [{icd['code']}]" if icd and icd.get("code") else ""
    prob_pct = int(primary.get("probability", 0) * 100)
    va       = result.vital_assessment or {}
    severity = va.get("severity", "normal")
    protocol = get_protocol(primary.get("disease", ""))

    urgency_class_map = {
        "immediate": "urgency-immediate",
        "urgent":    "urgency-urgent",
        "routine":   "urgency-routine",
    }
    urg_class = urgency_class_map.get(result.urgency, "urgency-routine")
    urg_label = _urgency_label(result.urgency)

    vital_flags_html = ""
    if va.get("flags"):
        vital_flags_html = "\n".join(_html_vital_badge(f) for f in va["flags"])
    else:
        vital_flags_html = '<div class="normal">バイタル異常なし</div>'

    diff_html = ""
    for rank, diff in enumerate(result.differentials[:3], start=2):
        dp = int(diff.get("probability", 0) * 100)
        diff_html += f'<div class="diagnosis-diff">{rank}位: {diff.get("disease", "")} ({dp}%)</div>\n'

    scores_html = ""
    if result.risk_scores:
        for sname, sdata in result.risk_scores.items():
            if isinstance(sdata, dict):
                sv  = sdata.get("score", "N/A")
                cat = sdata.get("category", sdata.get("interpretation", ""))
                scores_html += (
                    f'<div class="score-box">'
                    f'<div class="score-name">{sname}</div>'
                    f'<div class="score-value">{sv}</div>'
                    f'<div style="font-size:0.8em;color:#555">{cat}</div>'
                    f'</div>'
                )
    else:
        scores_html = "<p style='color:#999'>スコア情報なし</p>"

    labs_html = ""
    if result.lab_flags:
        for flag in result.lab_flags:
            status    = flag.get("status", "normal").lower()
            badge_cls = f"badge-{status}" if status in ("critical", "high", "low") else "badge-normal"
            name  = flag.get("name", "")
            val   = flag.get("value", "")
            unit  = flag.get("unit", "")
            badge = _lab_badge(status)
            labs_html += (
                f'<div style="padding:3px 0">'
                f'<span class="{badge_cls}">{badge}</span> {name}: {val} {unit}'
                f'</div>'
            )
    else:
        labs_html = "<p style='color:#999'>検査値情報なし</p>"

    redflag_html = ""
    if result.red_flags:
        redflag_html = "\n".join(
            f'<div class="critical">⚠ {rf}</div>' for rf in result.red_flags
        )

    steps_html = ""
    if result.next_steps:
        steps_html = "\n".join(
            f'<div class="next-step">✓ {ns}</div>' for ns in result.next_steps
        )

    protocol_html = ""
    if protocol:
        protocol_html = f"<h2>治療プロトコル（{protocol.diagnosis}標準）</h2>\n"
        for step in protocol.steps[:6]:
            dose_str = f"<br><small style='color:#777'>{step.dose}</small>" if step.dose else ""
            protocol_html += (
                f'<div class="protocol-step">'
                f'<span class="timing">{step.timing}</span>'
                f'<span>{step.action}{dose_str}</span>'
                f'</div>\n'
            )
    else:
        protocol_html = "<h2>治療プロトコル</h2><p>標準プロトコルを参照のこと</p>"

    html = f"""<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>臨床症例報告</title>
  <style>{_HTML_STYLE}</style>
</head>
<body>
<h1>臨床症例報告</h1>
<div class="meta">
  生成日時: {_now_jst()} &nbsp;|&nbsp;
  患者: {case.get('demographics', '不明')} &nbsp;|&nbsp;
  主訴: {case.get('chief_complaint', '不明')}
</div>

<h2>バイタルサイン評価</h2>
<div class="{severity}">重症度: <strong>{_severity_label(severity)}</strong></div>
{vital_flags_html}

<h2>鑑別診断</h2>
<div class="diagnosis-primary">
  <strong>第一診断: {primary.get('disease', '不明')}</strong>{icd_str} &mdash; 確率 {prob_pct}%
  <br><small style="color:#555">根拠: {primary.get('basis', '')}</small>
</div>
{diff_html}

<h2>リスクスコア</h2>
{scores_html}

<h2>検査値</h2>
{labs_html}

<h2>推奨事項</h2>
{redflag_html}
{steps_html}
<p style="margin-top:10px">緊急度: <span class="urgency {urg_class}">{urg_label}</span></p>

{protocol_html}

<hr style="border:none;border-top:1px solid #ddd;margin-top:30px">
<p style="color:#aaa;font-size:0.8em;text-align:center">
  本レポートは診断支援AIによる参考情報です。最終診断は医師が行ってください。
</p>
</body>
</html>"""
    return html


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_case_report(
    case: dict,
    diagnosis_result: DiagnosisResult,
    format: str = "text",
) -> str:
    """
    Generate a clinical case report in the specified format.

    Parameters
    ----------
    case : dict
        Patient case with keys: chief_complaint, demographics, symptoms,
        vitals, labs, history.
    diagnosis_result : DiagnosisResult
        Output from model.dd_engine.diagnose().
    format : str
        "text" | "json" | "html"

    Returns
    -------
    str  — formatted report content
    """
    if format == "json":
        return _render_json(case, diagnosis_result)
    elif format == "html":
        return _render_html(case, diagnosis_result)
    else:
        return _render_text(case, diagnosis_result)


# ---------------------------------------------------------------------------
# Batch report runner
# ---------------------------------------------------------------------------

BATCH_CASES = [
    {
        "id": "case_01",
        "demographics": "65歳男性",
        "chief_complaint": "胸痛・冷汗",
        "symptoms": ["前胸部圧迫感", "冷汗", "左肩放散痛", "呼吸困難"],
        "vitals": "BP 90/60, HR 110, SpO2 94%, RR 22, 体温 36.8",
        "labs": "トロポニンI 0.8 ng/mL, BNP 650 pg/mL, CRP 3.5 mg/dL",
        "history": "高血圧・喫煙歴あり。急性冠症候群疑い。",
    },
    {
        "id": "case_02",
        "demographics": "72歳女性",
        "chief_complaint": "呼吸困難・発熱",
        "symptoms": ["咳嗽", "発熱38.5℃", "酸素飽和度低下", "意識混濁"],
        "vitals": "BP 100/65, HR 105, SpO2 88%, RR 28, 体温 38.5",
        "labs": "WBC 18000, CRP 12.0, PCT 2.8",
        "history": "3日前から咳と発熱。糖尿病既往あり。市中肺炎疑い。",
    },
    {
        "id": "case_03",
        "demographics": "45歳男性",
        "chief_complaint": "突然の激烈な頭痛",
        "symptoms": ["雷鳴頭痛", "嘔吐", "項部硬直", "光過敏"],
        "vitals": "BP 170/100, HR 85, SpO2 98%, RR 16, 体温 37.2",
        "labs": "CT: 脳槽高吸収域",
        "history": "突然発症の最悪頭痛。くも膜下出血疑い。",
    },
    {
        "id": "case_04",
        "demographics": "28歳女性",
        "chief_complaint": "蜂刺され後の全身発疹・息苦しさ",
        "symptoms": ["蕁麻疹", "顔面浮腫", "喘鳴", "低血圧"],
        "vitals": "BP 80/50, HR 130, SpO2 90%, RR 30, 体温 36.5",
        "labs": "なし（即時対応中）",
        "history": "蜂刺傷5分後に発症。アナフィラキシーショック。",
    },
    {
        "id": "case_05",
        "demographics": "58歳男性",
        "chief_complaint": "右片麻痺・構音障害",
        "symptoms": ["右上下肢脱力", "構音障害", "顔面神経麻痺", "発症後2時間"],
        "vitals": "BP 185/105, HR 78, SpO2 97%, RR 14, 体温 36.6",
        "labs": "血糖 130, Cr 0.9",
        "history": "2時間前突然発症。脳卒中疑い（虚血性）。",
    },
    {
        "id": "case_06",
        "demographics": "55歳男性",
        "chief_complaint": "発熱・意識障害・低血圧",
        "symptoms": ["高熱39.5℃", "意識障害", "低血圧", "頻脈", "冷汗"],
        "vitals": "BP 85/55, HR 120, SpO2 92%, RR 26, 体温 39.5",
        "labs": "WBC 22000, Lac 4.2, PCT 15.0, Cr 2.3",
        "history": "尿路感染症から進展した敗血症性ショック疑い。",
    },
    {
        "id": "case_07",
        "demographics": "62歳女性",
        "chief_complaint": "急性腹痛・嘔吐",
        "symptoms": ["上腹部痛", "嘔吐", "発熱38.2℃", "背部への放散痛"],
        "vitals": "BP 120/75, HR 95, SpO2 97%, RR 18, 体温 38.2",
        "labs": "アミラーゼ 850 U/L, リパーゼ 1200 U/L, WBC 14000",
        "history": "飲酒後に発症。急性膵炎疑い。",
    },
    {
        "id": "case_08",
        "demographics": "38歳男性",
        "chief_complaint": "突然の胸痛・呼吸困難",
        "symptoms": ["胸膜性胸痛", "呼吸困難", "頻脈", "発症安静時"],
        "vitals": "BP 125/80, HR 115, SpO2 91%, RR 24, 体温 36.9",
        "labs": "D-ダイマー 3.8 μg/mL",
        "history": "長期臥床後に発症。肺塞栓症疑い。",
    },
    {
        "id": "case_09",
        "demographics": "70歳男性",
        "chief_complaint": "背部裂けるような痛み",
        "symptoms": ["引き裂かれるような背部痛", "上肢血圧左右差", "冷汗"],
        "vitals": "BP(R) 180/100 BP(L) 140/85, HR 95, SpO2 96%, RR 20",
        "labs": "CT: 大動脈内フラップ確認",
        "history": "突然発症の激痛。大動脈解離（Stanford A型）疑い。",
    },
    {
        "id": "case_10",
        "demographics": "19歳男性",
        "chief_complaint": "運動後の高血糖・嘔吐・意識混濁",
        "symptoms": ["口渇", "多尿", "嘔吐", "腹痛", "Kussmaul呼吸"],
        "vitals": "BP 100/70, HR 108, SpO2 97%, RR 28（深大呼吸）, 体温 37.1",
        "labs": "血糖 480 mg/dL, pH 7.18, HCO3 8, ケトン体強陽性",
        "history": "1型糖尿病既往。インスリン中断後に発症。DKA疑い。",
    },
]


def batch_report(output_dir: str = REPORTS_DIR):
    """Generate reports for all 10 sample cases and save to output_dir."""
    os.makedirs(output_dir, exist_ok=True)
    summary = []

    for case in BATCH_CASES:
        case_id = case["id"]
        labs_text = case.get("labs", "")

        result = diagnose(case, labs_text=labs_text)

        # Text
        text_content = generate_case_report(case, result, format="text")
        text_path = os.path.join(output_dir, f"{case_id}.txt")
        with open(text_path, "w", encoding="utf-8") as f:
            f.write(text_content)

        # HTML
        html_content = generate_case_report(case, result, format="html")
        html_path = os.path.join(output_dir, f"{case_id}.html")
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html_content)

        # JSON
        json_content = generate_case_report(case, result, format="json")
        json_path = os.path.join(output_dir, f"{case_id}.json")
        with open(json_path, "w", encoding="utf-8") as f:
            f.write(json_content)

        summary.append({
            "case_id":       case_id,
            "patient":       case.get("demographics", ""),
            "chief_complaint": case.get("chief_complaint", ""),
            "primary_dx":    result.primary.get("disease", ""),
            "probability":   result.primary.get("probability", 0),
            "urgency":       result.urgency,
            "text_file":     text_path,
            "html_file":     html_path,
            "json_file":     json_path,
        })

        print(f"  [{case_id}] {case.get('chief_complaint', '')} → "
              f"{result.primary.get('disease', '')} "
              f"({int(result.primary.get('probability', 0) * 100)}%)  "
              f"[{result.urgency}]")

    # Save batch summary
    summary_path = os.path.join(output_dir, "batch_summary.json")
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print(f"\nBatch summary saved to {summary_path}")
    return summary


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("=" * 60)
    print("Clinical Case Report Generator")
    print(f"Output directory: {REPORTS_DIR}")
    print("=" * 60)
    print("\nGenerating reports for 10 sample cases...\n")

    results = batch_report()

    print("\n" + "=" * 60)
    print("SAMPLE REPORT (case_01 — text format)")
    print("=" * 60)
    # Print the first case report to stdout as a demo
    case = BATCH_CASES[0]
    dr = diagnose(case, labs_text=case.get("labs", ""))
    print(generate_case_report(case, dr, format="text"))

    print(f"\nAll reports saved to: {REPORTS_DIR}/")
    print(f"  - {len(results)} × .txt  (text reports)")
    print(f"  - {len(results)} × .html (HTML reports)")
    print(f"  - {len(results)} × .json (JSON reports)")
    print(f"  - batch_summary.json")
