"""
symptom_checker.py — Interactive Symptom Checker

Step-by-step symptom checker with branching logic.
No UI required — pure Python class-based API.

Implements 3 complete symptom trees:
  1. Chest pain
  2. Dyspnea (shortness of breath)
  3. Fever + headache

Usage:
  checker = SymptomChecker()
  print(checker.start())
  print(checker.answer("胸痛"))
  # ... continues until DiagnosisResult is returned
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Union


# ─────────────────────────────────────────────────────────────
# Data Types
# ─────────────────────────────────────────────────────────────

@dataclass
class DiagnosisResult:
    """Terminal node: differential diagnosis + urgency + next steps."""
    differentials: list[str]
    urgency: str          # "immediate" | "urgent" | "semi-urgent" | "outpatient"
    urgency_jp: str       # Japanese label
    next_steps: list[str]
    red_flags: list[str]
    path_summary: str

    def __str__(self) -> str:
        lines = [
            "",
            "=" * 52,
            "【診断結果】",
            "=" * 52,
            f"緊急度: {self.urgency_jp}",
            "",
            "鑑別診断:",
        ]
        for i, d in enumerate(self.differentials, 1):
            lines.append(f"  {i}. {d}")
        if self.red_flags:
            lines.append("")
            lines.append("Red flags:")
            for r in self.red_flags:
                lines.append(f"  ⚠ {r}")
        lines.append("")
        lines.append("次のステップ:")
        for s in self.next_steps:
            lines.append(f"  → {s}")
        lines.append("=" * 52)
        return "\n".join(lines)


# ─────────────────────────────────────────────────────────────
# Decision Node
# ─────────────────────────────────────────────────────────────

@dataclass
class DecisionNode:
    """A question node in the decision tree."""
    question: str
    options: dict[str, "DecisionNode | DiagnosisResult"]
    default: "DecisionNode | DiagnosisResult | None" = None

    def match(self, response: str) -> "DecisionNode | DiagnosisResult":
        """Match response to an option (case-insensitive partial match)."""
        resp_lower = response.strip().lower()
        for key, node in self.options.items():
            if resp_lower in key.lower() or key.lower() in resp_lower:
                return node
        if self.default is not None:
            return self.default
        # Return first option as fallback
        return next(iter(self.options.values()))


# ─────────────────────────────────────────────────────────────
# Tree Builders
# ─────────────────────────────────────────────────────────────

def build_chest_pain_tree() -> DecisionNode:
    """6-level chest pain decision tree."""

    # Terminal nodes
    stemi = DiagnosisResult(
        differentials=["STEMI (ST上昇型心筋梗塞)"],
        urgency="immediate",
        urgency_jp="即時対応 (Immediate)",
        next_steps=["12誘導心電図確認", "循環器緊急コール", "PCI室準備 (door-to-balloon <90min)",
                    "アスピリン300mg + クロピドグレル600mg", "UFH投与"],
        red_flags=["ST上昇", "急激な胸痛", "ショック徴候"],
        path_summary="STEMI経路",
    )

    nstemi_high = DiagnosisResult(
        differentials=["NSTEMI (高リスク)", "不安定狭心症"],
        urgency="urgent",
        urgency_jp="緊急 (24h以内PCI)",
        next_steps=["入院・心電図モニタリング", "連続TnI測定 (0/3/6h)", "PCI 24h以内",
                    "DAPT + 抗凝固療法", "心エコー"],
        red_flags=["TnI陽性", "TIMI/GRACEスコア高値"],
        path_summary="NSTEMI高リスク経路",
    )

    nstemi_low = DiagnosisResult(
        differentials=["NSTEMI (低リスク)", "筋骨格性胸痛"],
        urgency="semi-urgent",
        urgency_jp="準緊急 (入院観察)",
        next_steps=["入院・6h後TnI再測定", "負荷心電図または冠動脈CT",
                    "DAPT開始 (TnI陽性なら)", "カルジオロジーコンサルト"],
        red_flags=[],
        path_summary="NSTEMI低リスク経路",
    )

    aortic_dissection = DiagnosisResult(
        differentials=["大動脈解離 (Type A/B)"],
        urgency="immediate",
        urgency_jp="即時対応 (Immediate)",
        next_steps=["造影CT緊急施行", "心臓血管外科緊急コール",
                    "血圧コントロール (目標SBP<120)", "疼痛管理 (モルヒネ)",
                    "手術/カテーテル介入準備"],
        red_flags=["血圧左右差 >20mmHg", "胸背部への放散痛", "縦隔拡大"],
        path_summary="大動脈解離経路",
    )

    pe = DiagnosisResult(
        differentials=["肺塞栓症 (PE)", "深部静脈血栓症 (DVT)"],
        urgency="urgent",
        urgency_jp="緊急",
        next_steps=["CTPA (確定診断)", "D-dimer測定", "UFH投与開始 (疑い強ければ先行)",
                    "心エコー (右心負荷評価)", "Wells scoreスコアリング"],
        red_flags=["突然発症の呼吸困難", "片側下腿腫脹", "長期臥床/手術後"],
        path_summary="肺塞栓症経路",
    )

    musculoskeletal = DiagnosisResult(
        differentials=["筋骨格性胸痛", "肋間神経痛", "肋骨骨折"],
        urgency="outpatient",
        urgency_jp="外来対応",
        next_steps=["NSAID投与", "安静", "胸部X線 (骨折除外)", "2週間後再診"],
        red_flags=[],
        path_summary="筋骨格性経路",
    )

    # Level 4: HEART score branch
    heart_q = DecisionNode(
        question="HEART score を計算してください。\n"
                 "  H: 病歴 (0–2点)\n"
                 "  E: 心電図 (0–2点)\n"
                 "  A: 年齢 (0–2点)\n"
                 "  R: 危険因子 (0–2点)\n"
                 "  T: TnI (0–2点)\n"
                 "合計スコアは何点ですか？ (例: '7', '5', '3')",
        options={
            "7": nstemi_high, "8": nstemi_high, "9": nstemi_high, "10": nstemi_high,
            "high": nstemi_high, "高": nstemi_high,
            "4": nstemi_low, "5": nstemi_low, "6": nstemi_low,
            "mid": nstemi_low, "中": nstemi_low,
            "0": musculoskeletal, "1": musculoskeletal, "2": musculoskeletal,
            "3": musculoskeletal, "low": musculoskeletal, "低": musculoskeletal,
        },
        default=nstemi_low,
    )

    # Level 3: TnI elevated?
    tni_q = DecisionNode(
        question="TnI (トロポニンI) / TnT は上昇していますか？ (はい/いいえ)",
        options={
            "はい": nstemi_high,
            "yes": nstemi_high,
            "陽性": nstemi_high,
            "いいえ": heart_q,
            "no": heart_q,
            "陰性": heart_q,
        },
        default=heart_q,
    )

    # Level 2: ST elevation?
    st_q = DecisionNode(
        question="12誘導心電図でST上昇 (≥2mm) を認めますか？ (はい/いいえ)",
        options={
            "はい": stemi,
            "yes": stemi,
            "あり": stemi,
            "いいえ": tni_q,
            "no": tni_q,
            "なし": tni_q,
        },
        default=tni_q,
    )

    # Level 2b: Dissection screening
    dissection_q = DecisionNode(
        question="胸背部への放散痛、または血圧左右差 >20mmHg はありますか？ (はい/いいえ)",
        options={
            "はい": aortic_dissection,
            "yes": aortic_dissection,
            "あり": aortic_dissection,
            "いいえ": st_q,
            "no": st_q,
            "なし": st_q,
        },
        default=st_q,
    )

    # Level 2c: PE screening
    pe_q = DecisionNode(
        question="突然発症の胸痛 + 呼吸困難、または片側下腿腫脹がありますか？ (はい/いいえ)",
        options={
            "はい": pe,
            "yes": pe,
            "あり": pe,
            "いいえ": dissection_q,
            "no": dissection_q,
            "なし": dissection_q,
        },
        default=dissection_q,
    )

    # Level 1: Pain character
    root = DecisionNode(
        question="胸痛の性状を教えてください。\n"
                 "  a) 押しつぶされるような圧迫感・放散痛\n"
                 "  b) 刺すような / 体位・呼吸で変化\n"
                 "  c) 引き裂かれるような激痛 (突然最大)",
        options={
            "a": pe_q, "a)": pe_q, "圧迫": pe_q, "放散": pe_q, "締め付け": pe_q,
            "b": musculoskeletal, "b)": musculoskeletal, "刺す": musculoskeletal,
            "体位": musculoskeletal,
            "c": aortic_dissection, "c)": aortic_dissection,
            "引き裂き": aortic_dissection, "激痛": aortic_dissection,
        },
        default=pe_q,
    )

    return root


def build_dyspnea_tree() -> DecisionNode:
    """4-level dyspnea workup tree."""

    # Terminal nodes
    immediate_airway = DiagnosisResult(
        differentials=["急性呼吸不全", "緊張性気胸", "重症肺炎"],
        urgency="immediate",
        urgency_jp="即時対応",
        next_steps=["気道確保・酸素投与", "HFNC/NIV/挿管考慮", "SpO2モニタリング",
                    "胸部X線緊急", "動脈血ガス分析"],
        red_flags=["SpO2<90%", "呼吸窮迫"],
        path_summary="重症呼吸不全経路",
    )

    chf = DiagnosisResult(
        differentials=["うっ血性心不全 (CHF)", "急性肺水腫"],
        urgency="urgent",
        urgency_jp="緊急",
        next_steps=["BNP/NT-proBNP測定", "心エコー (EF評価)", "ループ利尿薬 (フロセミド 40mg IV)",
                    "酸素投与 (目標SpO2≥94%)", "心電図・モニター"],
        red_flags=["起座呼吸", "夜間発作性呼吸困難", "両下腿浮腫"],
        path_summary="CHF経路",
    )

    copd_exacerbation = DiagnosisResult(
        differentials=["COPD増悪", "急性気管支炎"],
        urgency="urgent",
        urgency_jp="緊急",
        next_steps=["気管支拡張薬 (SABA+SAMA 吸入)", "全身ステロイド (プレドニゾロン 40mg)",
                    "動脈血ガス (CO2ナルコーシス評価)", "NIV適応評価",
                    "抗菌薬 (感染増悪なら)"],
        red_flags=["PaCO2上昇", "意識障害", "呼吸筋疲労"],
        path_summary="COPD増悪経路",
    )

    pneumonia = DiagnosisResult(
        differentials=["市中肺炎 (CAP)", "誤嚥性肺炎", "COVID-19"],
        urgency="urgent",
        urgency_jp="緊急",
        next_steps=["胸部X線/CT", "血液培養×2 (抗菌薬前)", "PSI/CURB-65スコア",
                    "抗菌薬 (β-ラクタム ± マクロライド)", "酸素投与"],
        red_flags=["SpO2低下", "敗血症徴候", "免疫抑制"],
        path_summary="肺炎経路",
    )

    pe_dyspnea = DiagnosisResult(
        differentials=["肺塞栓症 (PE)", "深部静脈血栓症"],
        urgency="urgent",
        urgency_jp="緊急",
        next_steps=["Wells scoreスコアリング", "D-dimer測定", "CTPA",
                    "UFH開始 (高疑いなら先行)", "下肢静脈エコー"],
        red_flags=["突然発症", "胸痛合併", "長期臥床/術後"],
        path_summary="PE経路",
    )

    asthma = DiagnosisResult(
        differentials=["気管支喘息発作", "アレルギー反応"],
        urgency="urgent",
        urgency_jp="緊急",
        next_steps=["SABA吸入 (サルブタモール)", "全身ステロイド", "SpO2モニタリング",
                    "トリガー除去", "重症なら静脈ステロイド"],
        red_flags=["無呼吸発作", "会話不能", "チアノーゼ"],
        path_summary="喘息経路",
    )

    # Wheeze branch
    wheeze_q = DecisionNode(
        question="喘鳴 (wheezing) の既往はありますか？\n  a) 喘息の既往あり\n  b) COPD/喫煙歴あり\n  c) 新規発症",
        options={
            "a": asthma, "a)": asthma, "喘息": asthma,
            "b": copd_exacerbation, "b)": copd_exacerbation, "copd": copd_exacerbation,
            "喫煙": copd_exacerbation,
            "c": asthma, "c)": asthma, "新規": asthma,
        },
        default=asthma,
    )

    # Signs branch
    signs_q = DecisionNode(
        question="身体所見はどれですか？\n"
                 "  a) 両側湿性ラ音 (肺底部)\n"
                 "  b) 喘鳴 (吸気/呼気)\n"
                 "  c) 片側呼吸音低下\n"
                 "  d) 所見なし / 軽度のみ",
        options={
            "a": chf, "a)": chf, "湿性": chf, "ラ音": chf,
            "b": wheeze_q, "b)": wheeze_q, "喘鳴": wheeze_q,
            "c": pneumonia, "c)": pneumonia, "片側": pneumonia, "低下": pneumonia,
            "d": pe_dyspnea, "d)": pe_dyspnea, "なし": pe_dyspnea,
        },
        default=chf,
    )

    # Onset branch
    onset_q = DecisionNode(
        question="発症は突然ですか、緩徐ですか？\n  a) 突然発症 (数分以内)\n  b) 緩徐 (数時間〜数日)",
        options={
            "a": pe_dyspnea, "a)": pe_dyspnea, "突然": pe_dyspnea,
            "b": signs_q, "b)": signs_q, "緩徐": signs_q,
        },
        default=signs_q,
    )

    # Root: SpO2
    root = DecisionNode(
        question="現在のSpO2 (室内気) はどのくらいですか？\n  a) <90%\n  b) 90–94%\n  c) ≥95%",
        options={
            "a": immediate_airway, "a)": immediate_airway, "<90": immediate_airway,
            "90": immediate_airway,
            "b": onset_q, "b)": onset_q, "90-94": onset_q, "90–94": onset_q,
            "c": onset_q, "c)": onset_q, "95": onset_q, "96": onset_q,
            "97": onset_q, "98": onset_q, "99": onset_q,
        },
        default=onset_q,
    )

    return root


def build_fever_headache_tree() -> DecisionNode:
    """Fever + headache differential tree."""

    # Terminal nodes
    meningitis = DiagnosisResult(
        differentials=["細菌性髄膜炎", "ウイルス性髄膜炎 (ヘルペス脳炎含む)"],
        urgency="immediate",
        urgency_jp="即時対応",
        next_steps=["腰椎穿刺 (CT後、禁忌なし確認)", "セフトリアキソン 2g IV緊急投与",
                    "デキサメタゾン 0.15mg/kg × 4日", "アシクロビル (ヘルペス疑いなら)",
                    "神経内科/感染症科コール"],
        red_flags=["項部硬直", "ケルニッヒ徴候", "意識障害", "点状出血斑"],
        path_summary="髄膜炎経路",
    )

    subarachnoid = DiagnosisResult(
        differentials=["くも膜下出血 (SAH)", "頭蓋内出血"],
        urgency="immediate",
        urgency_jp="即時対応",
        next_steps=["頭部CT緊急 (造影なし)", "脳神経外科緊急コール",
                    "腰椎穿刺 (CT陰性でもSAH疑いなら)", "血圧管理 (SBP<160目標)",
                    "絶対安静"],
        red_flags=["雷鳴頭痛 (thunderclap)", "意識消失", "頸部痛"],
        path_summary="SAH経路",
    )

    encephalitis = DiagnosisResult(
        differentials=["脳炎 (ヘルペス/日本脳炎)", "自己免疫性脳炎"],
        urgency="immediate",
        urgency_jp="即時対応",
        next_steps=["頭部MRI (FLAIR/DWI)", "脳波 (EEG)", "髄液検査",
                    "アシクロビル 10mg/kg q8h 開始", "神経内科コール"],
        red_flags=["意識障害", "痙攣", "精神症状"],
        path_summary="脳炎経路",
    )

    influenza = DiagnosisResult(
        differentials=["インフルエンザ", "COVID-19", "ウイルス性上気道炎"],
        urgency="outpatient",
        urgency_jp="外来対応",
        next_steps=["迅速抗原検査 (インフル/COVID)", "オセルタミビル (発症48h以内)",
                    "解熱鎮痛薬", "水分補給・安静", "重症化リスク評価"],
        red_flags=["呼吸困難", "意識障害", "5日以上継続"],
        path_summary="インフルエンザ経路",
    )

    sinusitis = DiagnosisResult(
        differentials=["急性副鼻腔炎", "緊張型頭痛"],
        urgency="outpatient",
        urgency_jp="外来対応",
        next_steps=["鼻腔所見確認", "AMOXICILLIN (細菌性なら)", "NSAIDs",
                    "副鼻腔CT (重症・再発例)", "7〜10日後再診"],
        red_flags=[],
        path_summary="副鼻腔炎経路",
    )

    # Mental status branch
    mental_q = DecisionNode(
        question="意識障害、痙攣、または精神症状はありますか？ (はい/いいえ)",
        options={
            "はい": encephalitis,
            "yes": encephalitis,
            "あり": encephalitis,
            "いいえ": meningitis,
            "no": meningitis,
            "なし": meningitis,
        },
        default=meningitis,
    )

    # Meningism branch
    meningism_q = DecisionNode(
        question="項部硬直 (首を前に曲げると抵抗) はありますか？ (はい/いいえ)",
        options={
            "はい": mental_q,
            "yes": mental_q,
            "あり": mental_q,
            "いいえ": influenza,
            "no": influenza,
            "なし": influenza,
        },
        default=influenza,
    )

    # Onset branch
    onset_q = DecisionNode(
        question="頭痛はどのように始まりましたか？\n"
                 "  a) 雷鳴頭痛 (突然の激烈な頭痛、人生最悪レベル)\n"
                 "  b) 徐々に悪化\n"
                 "  c) 普通の頭痛",
        options={
            "a": subarachnoid, "a)": subarachnoid, "雷鳴": subarachnoid,
            "突然": subarachnoid, "最悪": subarachnoid,
            "b": meningism_q, "b)": meningism_q, "徐々": meningism_q, "悪化": meningism_q,
            "c": sinusitis, "c)": sinusitis, "普通": sinusitis,
        },
        default=meningism_q,
    )

    # Root: Fever level
    root = DecisionNode(
        question="発熱の程度と頭痛の組み合わせを教えてください。\n"
                 "  a) 高熱 (≥38.5℃) + 激しい頭痛\n"
                 "  b) 高熱 + 軽〜中等度頭痛\n"
                 "  c) 微熱 (37–38℃) + 頭痛",
        options={
            "a": onset_q, "a)": onset_q, "高熱": onset_q, "激し": onset_q,
            "b": meningism_q, "b)": meningism_q,
            "c": sinusitis, "c)": sinusitis, "微熱": sinusitis,
        },
        default=meningism_q,
    )

    return root


# ─────────────────────────────────────────────────────────────
# SymptomChecker Class
# ─────────────────────────────────────────────────────────────

class SymptomChecker:
    """
    Interactive symptom checker with branching question logic.

    Implements 3 complete symptom trees:
      - chest_pain: 胸痛
      - dyspnea:    呼吸困難
      - fever_headache: 発熱+頭痛
    """

    CHIEF_COMPLAINTS = {
        "胸痛": "chest_pain",
        "chest": "chest_pain",
        "chest_pain": "chest_pain",
        "呼吸困難": "dyspnea",
        "dyspnea": "dyspnea",
        "息切れ": "dyspnea",
        "shortness": "dyspnea",
        "発熱": "fever_headache",
        "fever": "fever_headache",
        "頭痛": "fever_headache",
        "headache": "fever_headache",
        "発熱+頭痛": "fever_headache",
        "腹痛": None,  # not implemented
        "腹": None,
    }

    _TREES = {
        "chest_pain": build_chest_pain_tree,
        "dyspnea": build_dyspnea_tree,
        "fever_headache": build_fever_headache_tree,
    }

    _INITIAL_QUESTION = (
        "主症状は何ですか？\n"
        "  a) 胸痛 (chest pain)\n"
        "  b) 呼吸困難 (dyspnea / 息切れ)\n"
        "  c) 発熱 + 頭痛 (fever + headache)\n"
        "  d) 腹痛 (abdominal pain) ※未実装"
    )

    def __init__(self):
        self._current_node: DecisionNode | DiagnosisResult | None = None
        self._path: list[str] = []
        self._started: bool = False

    def start(self) -> str:
        """Returns the first question."""
        self._current_node = None
        self._path = []
        self._started = True
        return self._INITIAL_QUESTION

    def answer(self, response: str) -> Union[str, DiagnosisResult]:
        """
        Process the user's response.

        Returns the next question (str) or a DiagnosisResult when done.
        """
        if not self._started:
            raise RuntimeError("Call start() first.")

        self._path.append(response)

        # Initial symptom selection
        if self._current_node is None:
            resp_lower = response.strip().lower()
            tree_key = None
            for keyword, key in self.CHIEF_COMPLAINTS.items():
                if keyword.lower() in resp_lower or resp_lower in keyword.lower():
                    tree_key = key
                    break

            if tree_key is None:
                return ("申し訳ありませんが、その症状には対応していません。\n"
                        "胸痛 / 呼吸困難 / 発熱+頭痛 のいずれかを選択してください。")

            self._current_node = self._TREES[tree_key]()
            return self._current_node.question

        # Navigate tree
        if isinstance(self._current_node, DiagnosisResult):
            return "診断が既に確定しています。reset() を呼び出して再開してください。"

        next_node = self._current_node.match(response)
        self._current_node = next_node

        if isinstance(next_node, DiagnosisResult):
            result = next_node
            result.path_summary = " → ".join(self._path)
            return result
        else:
            return next_node.question

    def reset(self) -> None:
        """Reset the checker to initial state."""
        self._current_node = None
        self._path = []
        self._started = False

    def get_path(self) -> list[str]:
        """Returns the diagnostic path taken so far."""
        return list(self._path)


# ─────────────────────────────────────────────────────────────
# Demo: Run 3 example cases
# ─────────────────────────────────────────────────────────────

def run_demo_case(checker: SymptomChecker, answers: list[str], title: str) -> None:
    """Run a single demo case through the checker."""
    print(f"\n{'='*60}")
    print(f"  CASE: {title}")
    print(f"{'='*60}")

    question = checker.start()
    print(f"\nQ: {question}")

    for ans in answers:
        print(f"\nA: {ans}")
        result = checker.answer(ans)

        if isinstance(result, DiagnosisResult):
            print(result)
            print(f"\n診断経路: {' → '.join(checker.get_path())}")
            checker.reset()
            return
        else:
            print(f"\nQ: {result}")

    print("(デモ終了前に答えが尽きました)")
    checker.reset()


if __name__ == '__main__':
    checker = SymptomChecker()

    # Case 1: STEMI
    run_demo_case(
        checker,
        answers=["胸痛", "圧迫感・放散痛", "いいえ(PE)", "いいえ(解離)", "はい(ST上昇)"],
        title="Case 1: 急性心筋梗塞 (STEMI) — 60歳男性, 胸部圧迫感15分",
    )

    # Case 2: PE
    run_demo_case(
        checker,
        answers=["呼吸困難", "95", "突然", "なし"],
        title="Case 2: 肺塞栓症 (PE) — 45歳女性, 長距離フライト後の突然の息切れ",
    )

    # Case 3: 細菌性髄膜炎
    run_demo_case(
        checker,
        answers=["発熱+頭痛", "高熱+激しい頭痛", "徐々に悪化", "はい(項部硬直)", "いいえ(意識清明)"],
        title="Case 3: 細菌性髄膜炎 — 22歳女性, 発熱38.9℃+激しい頭痛+項部硬直",
    )

    print(f"\n{'='*60}")
    print("Demo complete. SymptomChecker supports 3 symptom trees:")
    print("  - chest_pain (胸痛)")
    print("  - dyspnea    (呼吸困難)")
    print("  - fever_headache (発熱+頭痛)")
    print(f"{'='*60}")
