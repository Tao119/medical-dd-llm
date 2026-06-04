"""
clinical/vitals.py — Vital Sign Parser and Anomaly Detector

バイタルサイン文字列をパースし、異常を検出する。
対応フォーマット例:
  "BP 90/60, HR 110, SpO2 94%, RR 24, 体温 38.5℃"
  "血圧 120/80 mmHg, 脈拍 72, 体温 36.8"
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional


@dataclass
class VitalSigns:
    sbp: float | None = None   # 収縮期血圧 mmHg
    dbp: float | None = None   # 拡張期血圧 mmHg
    hr: float | None = None    # 心拍数 /min
    spo2: float | None = None  # 酸素飽和度 %
    rr: float | None = None    # 呼吸数 /min
    temp: float | None = None  # 体温 °C
    gcs: int | None = None     # Glasgow Coma Scale (3-15)
    raw: str = ""              # 入力元文字列


# ---------------------------------------------------------------------------
# 正規表現パターン群
# ---------------------------------------------------------------------------

_RE_BP = re.compile(
    r"""(?:BP|血圧|収縮期血圧|SBP)\s*[:：]?\s*
        (\d{2,3})\s*/\s*(\d{2,3})""",
    re.VERBOSE | re.IGNORECASE,
)
_RE_HR = re.compile(
    r"""(?:HR|心拍数?|脈拍数?|Pulse|PR)\s*[:：]?\s*(\d{2,3})""",
    re.VERBOSE | re.IGNORECASE,
)
_RE_SPO2 = re.compile(
    r"""(?:SpO2|SaO2|O2\s*sat|酸素飽和度)\s*[:：]?\s*(\d{2,3})\s*%?""",
    re.VERBOSE | re.IGNORECASE,
)
_RE_RR = re.compile(
    r"""(?:RR|呼吸数?|Resp(?:iratory)?\s*Rate?)\s*[:：]?\s*(\d{1,2})""",
    re.VERBOSE | re.IGNORECASE,
)
_RE_TEMP = re.compile(
    r"""(?:体温|BT|Temp(?:erature)?|T)\s*[:：]?\s*(\d{2}(?:\.\d)?)[\s℃°C]?""",
    re.VERBOSE | re.IGNORECASE,
)
_RE_GCS = re.compile(
    r"""(?:GCS|Glasgow)\s*[:：]?\s*(\d{1,2})""",
    re.VERBOSE | re.IGNORECASE,
)


def parse_vitals(text: str) -> VitalSigns:
    """バイタルサイン文字列を VitalSigns dataclass に変換する。

    Parameters
    ----------
    text : str
        フリーテキストのバイタルサイン記述

    Returns
    -------
    VitalSigns
        パース結果 (値が見つからない場合は None)
    """
    vs = VitalSigns(raw=text)

    m = _RE_BP.search(text)
    if m:
        vs.sbp = float(m.group(1))
        vs.dbp = float(m.group(2))

    m = _RE_HR.search(text)
    if m:
        vs.hr = float(m.group(1))

    m = _RE_SPO2.search(text)
    if m:
        vs.spo2 = float(m.group(1))

    m = _RE_RR.search(text)
    if m:
        vs.rr = float(m.group(1))

    m = _RE_TEMP.search(text)
    if m:
        val = float(m.group(1))
        # 体温として非現実的な値は除外 (例: 患者IDと誤検出)
        if 30.0 <= val <= 43.0:
            vs.temp = val

    m = _RE_GCS.search(text)
    if m:
        val = int(m.group(1))
        if 3 <= val <= 15:
            vs.gcs = val

    return vs


# ---------------------------------------------------------------------------
# 閾値定義 (日本の救急医学・集中治療の標準的基準値)
# ---------------------------------------------------------------------------

_THRESHOLDS = {
    "sbp": {
        "critical_low": 80,   # ショック域
        "warning_low": 90,    # 低血圧
        "warning_high": 180,  # 高血圧クリーゼ境界
        "critical_high": 220, # 高血圧緊急症
        "unit": "mmHg",
        "name": "収縮期血圧",
    },
    "dbp": {
        "critical_low": 50,
        "warning_low": 60,
        "warning_high": 110,
        "critical_high": 130,
        "unit": "mmHg",
        "name": "拡張期血圧",
    },
    "hr": {
        "critical_low": 40,   # 高度徐脈
        "warning_low": 50,    # 徐脈
        "warning_high": 120,  # 頻脈
        "critical_high": 150, # 高度頻脈
        "unit": "/min",
        "name": "心拍数",
    },
    "spo2": {
        "critical_low": 90,   # 重篤な低酸素
        "warning_low": 94,    # 低酸素警戒
        "warning_high": 100,  # SpO2 は 100 が上限
        "critical_high": 101, # 実質的に閾値なし
        "unit": "%",
        "name": "酸素飽和度",
    },
    "rr": {
        "critical_low": 6,    # 呼吸抑制
        "warning_low": 10,    # 低呼吸
        "warning_high": 24,   # 頻呼吸
        "critical_high": 30,  # 重篤な頻呼吸
        "unit": "/min",
        "name": "呼吸数",
    },
    "temp": {
        "critical_low": 35.0,  # 低体温
        "warning_low": 36.0,   # 軽度低体温
        "warning_high": 38.0,  # 発熱
        "critical_high": 40.0, # 高体温 (40℃超は生命危機)
        "unit": "℃",
        "name": "体温",
    },
}


def _classify_parameter(name: str, value: float) -> dict:
    """単一バイタルパラメータの重症度を分類する。"""
    th = _THRESHOLDS[name]
    unit = th["unit"]
    display = th["name"]

    if value <= th["critical_low"] or value >= th["critical_high"]:
        severity = "critical"
    elif value <= th["warning_low"] or value >= th["warning_high"]:
        severity = "warning"
    else:
        severity = "normal"

    direction = ""
    if value <= th["critical_low"]:
        direction = "（危機的低値）"
    elif value >= th["critical_high"]:
        direction = "（危機的高値）"
    elif value <= th["warning_low"]:
        direction = "（低値）"
    elif value >= th["warning_high"]:
        direction = "（高値）"

    return {
        "parameter": name,
        "display_name": display,
        "value": value,
        "unit": unit,
        "severity": severity,
        "message": f"{display} {value}{unit}{direction}",
    }


def _compute_shock_index(vs: VitalSigns) -> dict | None:
    """ショック指数 = HR / SBP を計算する。>1.0 でショック疑い。"""
    if vs.hr is None or vs.sbp is None or vs.sbp == 0:
        return None
    si = vs.hr / vs.sbp
    if si >= 1.5:
        severity = "critical"
        msg = f"ショック指数 {si:.2f}（≥1.5: 重篤なショック疑い）"
    elif si >= 1.0:
        severity = "warning"
        msg = f"ショック指数 {si:.2f}（≥1.0: ショック疑い — 輸液・緊急評価を推奨）"
    else:
        severity = "normal"
        msg = f"ショック指数 {si:.2f}（正常範囲）"
    return {"parameter": "shock_index", "display_name": "ショック指数", "value": round(si, 3),
            "unit": "", "severity": severity, "message": msg}


def _compute_qsofa(vs: VitalSigns) -> dict | None:
    """qSOFA スコア（敗血症スクリーニング）を計算する。

    - RR ≥ 22 /min          … 1点
    - 意識変容 (GCS < 15)    … 1点
    - SBP ≤ 100 mmHg        … 1点
    ≥2点: 臓器障害ハイリスク
    """
    score = 0
    components = []

    if vs.rr is not None and vs.rr >= 22:
        score += 1
        components.append(f"呼吸数 {vs.rr}/min ≥22")
    if vs.gcs is not None and vs.gcs < 15:
        score += 1
        components.append(f"GCS {vs.gcs} < 15（意識変容）")
    if vs.sbp is not None and vs.sbp <= 100:
        score += 1
        components.append(f"SBP {vs.sbp}mmHg ≤100")

    # 算出に必要なデータが不十分な場合は None
    available = sum([vs.rr is not None, vs.gcs is not None, vs.sbp is not None])
    if available == 0:
        return None

    severity = "critical" if score >= 2 else ("warning" if score == 1 else "normal")
    comp_str = "、".join(components) if components else "該当なし"
    msg = f"qSOFA {score}点 [{comp_str}]"
    if score >= 2:
        msg += " → 敗血症ハイリスク: 血液培養・乳酸値・ICU評価を至急"

    return {"parameter": "qsofa", "display_name": "qSOFAスコア", "value": score,
            "unit": "点", "severity": severity, "message": msg}


def assess_vitals(vs: VitalSigns) -> dict:
    """バイタルサインの総合評価を行う。

    Parameters
    ----------
    vs : VitalSigns
        parse_vitals() の返り値

    Returns
    -------
    dict
        {
            "flags": [{"parameter": str, "severity": str, "message": str, ...}],
            "severity": "critical" | "warning" | "normal",
            "shock_index": float | None,
            "qsofa": int | None,
            "summary": str,
        }
    """
    flags: list[dict] = []

    for param in ("sbp", "dbp", "hr", "spo2", "rr", "temp"):
        value = getattr(vs, param)
        if value is not None:
            result = _classify_parameter(param, value)
            if result["severity"] != "normal":
                flags.append(result)

    # 派生スコア
    si_result = _compute_shock_index(vs)
    if si_result and si_result["severity"] != "normal":
        flags.append(si_result)

    qsofa_result = _compute_qsofa(vs)
    if qsofa_result and qsofa_result["severity"] != "normal":
        flags.append(qsofa_result)

    # 全体重症度: 1つでも critical があれば critical
    severities = {f["severity"] for f in flags}
    if "critical" in severities:
        overall = "critical"
    elif "warning" in severities:
        overall = "warning"
    else:
        overall = "normal"

    # サマリー文
    if overall == "critical":
        summary = "【緊急】生命徴候に危機的異常あり。即時対応が必要です。"
    elif overall == "warning":
        summary = "【要注意】バイタルサインに異常値あり。早急な評価を推奨します。"
    else:
        summary = "バイタルサインは概ね安定しています。"

    return {
        "flags": flags,
        "severity": overall,
        "shock_index": si_result["value"] if si_result else None,
        "qsofa": qsofa_result["value"] if qsofa_result else None,
        "summary": summary,
    }


# ---------------------------------------------------------------------------
# デモ
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    samples = [
        "BP 90/60, HR 110, SpO2 94%, RR 24, 体温 38.5℃",
        "血圧 80/50 mmHg, 脈拍 130/min, SpO2 88%, RR 28, 体温 39.2℃, GCS 13",
        "BP 130/80, HR 72, SpO2 99%, RR 16, Temp 36.8",
        "血圧 220/120, HR 45, 体温 35.1℃, RR 8",
    ]

    for text in samples:
        print("=" * 60)
        print(f"入力: {text}")
        vs = parse_vitals(text)
        result = assess_vitals(vs)
        print(f"重症度: {result['severity'].upper()}")
        print(f"サマリー: {result['summary']}")
        if result["shock_index"] is not None:
            print(f"ショック指数: {result['shock_index']}")
        if result["qsofa"] is not None:
            print(f"qSOFA: {result['qsofa']}点")
        if result["flags"]:
            print("異常フラグ:")
            for flag in result["flags"]:
                print(f"  [{flag['severity'].upper()}] {flag['message']}")
        print()
