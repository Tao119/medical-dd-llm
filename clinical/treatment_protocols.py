"""
clinical/treatment_protocols.py — Evidence-Based Treatment Protocols

主要疾患の時系列治療プロトコル（構造化データ）。

対応疾患 (12+):
  1.  STEMI
  2.  急性心不全
  3.  DKA (糖尿病性ケトアシドーシス)
  4.  アナフィラキシー
  5.  敗血症性ショック (SEP-1 バンドル)
  6.  痙攣重積状態
  7.  脳卒中 / tPA プロトコル
  8.  肺塞栓症
  9.  急性大動脈解離
  10. 高血圧性緊急症
  11. 急性喘息
  12. 上部消化管出血
"""

from __future__ import annotations

import difflib
from dataclasses import dataclass, field


# ===========================================================================
# データモデル
# ===========================================================================

@dataclass
class TreatmentStep:
    timing: str           # "0-10min", "10-30min", "30-60min", "ongoing"
    action: str
    dose: str | None = None
    condition: str | None = None
    priority: int = 2     # 1=immediate, 2=urgent, 3=soon


@dataclass
class TreatmentProtocol:
    diagnosis: str
    icd10: str
    key_principle: str
    steps: list[TreatmentStep]
    monitoring: list[str]
    goals: dict           # {"BP": "100-120 mmHg", "HR": "<60"} etc.
    pitfalls: list[str]


# ===========================================================================
# 12 疾患のプロトコル定義
# ===========================================================================

_PROTOCOLS: list[TreatmentProtocol] = [

    # ------------------------------------------------------------------
    # 1. STEMI
    # ------------------------------------------------------------------
    TreatmentProtocol(
        diagnosis="STEMI (ST上昇型心筋梗塞)",
        icd10="I21.0",
        key_principle="Door-to-Balloon ≤90 分。再灌流が最優先。遅延は心筋壊死を拡大させる。",
        steps=[
            TreatmentStep(
                timing="0-10min", priority=1,
                action="12 誘導心電図取得・心筋梗塞確認",
                dose=None,
                condition="STE ≥2mm (男性) / ≥1.5mm (女性) in V2-V3、または他誘導 ≥1mm",
            ),
            TreatmentStep(
                timing="0-10min", priority=1,
                action="アスピリン 負荷投与",
                dose="アスピリン 200-300 mg 咀嚼投与（アスピリン未使用の場合）",
            ),
            TreatmentStep(
                timing="0-10min", priority=1,
                action="P2Y12 阻害薬 負荷投与",
                dose="チカグレロル 180 mg PO または クロピドグレル 600 mg PO",
                condition="出血リスク・ CABG 予定なければ",
            ),
            TreatmentStep(
                timing="0-10min", priority=1,
                action="ヘパリン 初回投与",
                dose="UFH 60-70 IU/kg IV ボーラス (最大 5000 IU)、その後 12-15 IU/kg/h 持続",
            ),
            TreatmentStep(
                timing="0-10min", priority=1,
                action="静脈路確保・血液検査",
                dose="心筋逸脱酵素 (TnI/TnT, CK-MB)・CBC・BMP・凝固・血型",
            ),
            TreatmentStep(
                timing="0-10min", priority=1,
                action="酸素投与",
                dose="SpO2 <90% の場合のみ投与（過剰酸素は梗塞巣を拡大する可能性）",
            ),
            TreatmentStep(
                timing="0-30min", priority=1,
                action="緊急心臓カテーテル室へ転送",
                dose=None,
                condition="Primary PCI 施設なければ fibrinolysis または転送を直ちに決定",
            ),
            TreatmentStep(
                timing="10-30min", priority=2,
                action="モルヒネ 鎮痛（強い疼痛の場合）",
                dose="モルヒネ 2-4 mg IV、5 分ごとに滴定（低血圧・嘔気注意）",
                condition="NRS ≥7 かつ収縮期血圧 >90 mmHg",
            ),
            TreatmentStep(
                timing="10-30min", priority=2,
                action="ニトログリセリン 舌下（胸痛持続時）",
                dose="ニトログリセリン 0.3 mg 舌下、5 分ごと × 3 回",
                condition="SBP >90 mmHg、PDE5 阻害薬未使用",
            ),
            TreatmentStep(
                timing="0-90min", priority=1,
                action="Primary PCI — Balloon 拡張 (DtB ≤90 分)",
                dose="必要に応じてステント留置",
            ),
            TreatmentStep(
                timing="ongoing", priority=2,
                action="β遮断薬 経口開始（安定化後）",
                dose="メトプロロール 25-50 mg PO BID（心不全・徐脈・低血圧がなければ）",
            ),
            TreatmentStep(
                timing="ongoing", priority=2,
                action="ACE 阻害薬/ARB 開始",
                dose="ラミプリル 2.5 mg PO から開始（LV 機能低下・DM・高血圧に特に適応）",
            ),
            TreatmentStep(
                timing="ongoing", priority=2,
                action="高強度スタチン",
                dose="アトルバスタチン 40-80 mg PO qd（LDL <70 mg/dL を目標）",
            ),
        ],
        monitoring=[
            "持続心電図モニタリング（再灌流不整脈・再閉塞の検知）",
            "1 時間ごとの心筋逸脱酵素 (peak TnI/TnT 確認)",
            "血行動態: BP・HR 30 分ごと（安定するまで）",
            "尿量モニタリング (≥0.5 mL/kg/h 目標)",
            "心エコー: LV 機能・合併症評価（24 時間以内）",
        ],
        goals={
            "DtB": "≤90 分",
            "TIMI flow": "3 (完全再灌流)",
            "SBP": "90-140 mmHg",
            "HR": "50-70 bpm",
            "SpO2": "≥95%",
            "LDL": "<70 mg/dL",
        },
        pitfalls=[
            "SpO2 正常例への過剰酸素投与 → 梗塞巣拡大",
            "P2Y12 阻害薬の遅延 → ステント血栓症リスク",
            "低血圧患者へのニトログリセリン投与 → 血圧さらに低下",
            "PDE5 阻害薬内服中へのニトログリセリン → 致死的低血圧",
            "右室梗塞を見逃す → V3R/V4R 誘導確認を忘れない（右冠動脈 STEMI 例）",
            "fibrinolysis 後 PCI 施設への搬送遅延 → facilitated PCI の概念",
        ],
    ),

    # ------------------------------------------------------------------
    # 2. 急性心不全
    # ------------------------------------------------------------------
    TreatmentProtocol(
        diagnosis="急性心不全 (急性非代償性心不全)",
        icd10="I50.9",
        key_principle="LMNOP: Lasix・Morphine・Nitrates・O2・Position。うっ血除去と後負荷軽減が主軸。",
        steps=[
            TreatmentStep(
                timing="0-10min", priority=1,
                action="起坐位または 45 度以上の頭部挙上",
                dose=None,
            ),
            TreatmentStep(
                timing="0-10min", priority=1,
                action="酸素投与 / NIV",
                dose="SpO2 <94% → 高流量酸素。呼吸困難・頻呼吸 → CPAP/BiPAP 開始",
            ),
            TreatmentStep(
                timing="0-10min", priority=1,
                action="静脈路確保・心電図・CXR・採血",
                dose="BNP/NT-proBNP・TnI/TnT・BMP・CBC・CXR",
            ),
            TreatmentStep(
                timing="0-30min", priority=1,
                action="フロセミド IV 利尿",
                dose="フロセミド 40-80 mg IV ボーラス（利尿薬未使用の場合）。既投与中は 2.5 倍量を目安に。",
                condition="うっ血所見（湿性ラ音・浮腫・静脈怒張）がある場合",
            ),
            TreatmentStep(
                timing="0-30min", priority=1,
                action="ニトログリセリン IV（後負荷軽減）",
                dose="ニトログリセリン 5-10 μg/min から開始、5-10 μg/min ずつ増量 (SBP >100 mmHg 目標)",
                condition="SBP >110 mmHg、PDE5 阻害薬未使用",
            ),
            TreatmentStep(
                timing="0-30min", priority=2,
                action="モルヒネ（重篤な呼吸困難・疼痛）",
                dose="モルヒネ 2-4 mg IV、5 分ごとに滴定",
                condition="重篤な呼吸困難・不穏・肺水腫。ルーチン使用は回避（予後悪化の報告）",
            ),
            TreatmentStep(
                timing="30-60min", priority=2,
                action="原因検索・治療（STEMI・AF・高血圧クリーゼ等）",
                dose=None,
            ),
            TreatmentStep(
                timing="30-60min", priority=2,
                action="心原性ショック → 強心薬",
                dose="ドパミン 5-10 μg/kg/min または ドブタミン 2.5-10 μg/kg/min IV",
                condition="SBP <90 mmHg かつ低灌流所見",
            ),
            TreatmentStep(
                timing="ongoing", priority=3,
                action="利尿効果評価 (目標: 0.5-1 mL/kg/h)",
                dose="6 時間後に反応不十分 → フロセミド持続投与 5-10 mg/h または増量",
            ),
            TreatmentStep(
                timing="ongoing", priority=3,
                action="ACE 阻害薬/ARB・β遮断薬・MRA の導入（安定化後）",
                dose="入院中または退院前に HFrEF 治療の 4 本柱を開始",
                condition="EF <40%（HFrEF）",
            ),
        ],
        monitoring=[
            "SpO2・呼吸数 連続モニタリング",
            "BP・HR 30 分ごと（利尿薬投与後）",
            "尿量（カテーテル留置推奨、目標 ≥0.5 mL/kg/h）",
            "電解質（K・Mg）— 利尿薬による低 K 血症に注意",
            "BUN/Cr — AKI を早期検出",
            "BNP/NT-proBNP（トレンドで効果評価）",
        ],
        goals={
            "SBP": "90-140 mmHg",
            "SpO2": "≥94%",
            "尿量": "≥0.5 mL/kg/h",
            "BNP": "トレンド改善",
            "K": "3.5-5.0 mEq/L",
        },
        pitfalls=[
            "低血圧患者へのニトログリセリン/利尿薬過多 → 前負荷過剰低下",
            "うっ血を過小評価して退院 → 再入院",
            "AKI リスクを無視した過剰利尿",
            "STEMI・AF 等の基礎原因を見逃す",
            "HFpEF で強心薬を使用 → 有害な可能性",
        ],
    ),

    # ------------------------------------------------------------------
    # 3. DKA
    # ------------------------------------------------------------------
    TreatmentProtocol(
        diagnosis="DKA (糖尿病性ケトアシドーシス)",
        icd10="E10.1",
        key_principle="輸液→インスリン→カリウム補充の順序を守る。インスリン先行は致死的低 K 血症を招く。",
        steps=[
            TreatmentStep(
                timing="0-10min", priority=1,
                action="診断確認と静脈路確保",
                dose="血糖・血ガス・電解質・BUN/Cr・β-ヒドロキシ酪酸・尿ケトン・CBC・UA",
            ),
            TreatmentStep(
                timing="0-60min", priority=1,
                action="輸液蘇生 — 0.9% 生食",
                dose="0.9% NaCl 1000-2000 mL を最初の 1 時間で IV (ショック: 500 mL ×2 ボーラス)",
                condition="脱水・ショック状態に応じて調整",
            ),
            TreatmentStep(
                timing="0-60min", priority=1,
                action="カリウム確認・補充",
                dose="K <3.3 mEq/L → インスリン保留。KCl 20-40 mEq/h 補充後に再評価。K 3.3-5.0: KCl 20-30 mEq/L を輸液に追加",
                condition="K が正常/低値に是正されるまでインスリン開始禁止",
            ),
            TreatmentStep(
                timing="60min", priority=1,
                action="インスリン持続投与開始",
                dose="レギュラーインスリン 0.1 U/kg/h IV 持続（初回ボーラス: 0.1 U/kg IV、省略可）",
                condition="K ≥3.3 mEq/L を確認後に開始",
            ),
            TreatmentStep(
                timing="1-4h", priority=2,
                action="輸液切替 — 0.45% NaCl",
                dose="0.9% → 0.45% NaCl 250-500 mL/h（Na 補正後）",
                condition="Na 正常化後",
            ),
            TreatmentStep(
                timing="ongoing", priority=2,
                action="血糖 250 mg/dL 到達時に 5% ブドウ糖追加",
                dose="5% ブドウ糖 + 0.45% NaCl に切替、インスリン継続",
                condition="血糖 ≤250 mg/dL になったとき（アニオンギャップはまだ開大の場合が多い）",
            ),
            TreatmentStep(
                timing="ongoing", priority=2,
                action="重炭酸ナトリウム（限定的適応）",
                dose="pH <6.9 かつ循環破綻: NaHCO3 100 mEq を 400 mL 精製水に溶かし 2 時間で投与",
                condition="pH ≥6.9 ではルーチン投与非推奨（paradoxical CNS acidosis・低 K 悪化）",
            ),
            TreatmentStep(
                timing="ongoing", priority=3,
                action="誘因の検索・治療",
                dose="感染症（抗生物質）・インスリン中断・新規発症 DM など",
            ),
            TreatmentStep(
                timing="8-24h", priority=2,
                action="皮下インスリンへの切替",
                dose="AG 正常化・pH ≥7.3・重炭酸 ≥15・経口摂取可能 → 皮下インスリン導入後 2-4 時間で IV 中止",
            ),
        ],
        monitoring=[
            "血糖 1 時間ごと（インスリン投与中）",
            "電解質・BGA 2-4 時間ごと",
            "尿量 1 時間ごと（カテーテル留置）",
            "アニオンギャップ追跡 (AG = Na - (Cl + HCO3)、正常 8-12)",
            "β-ヒドロキシ酪酸（解消を直接確認）",
            "心電図（高/低 K 所見の確認）",
        ],
        goals={
            "血糖低下速度": "50-75 mg/dL/h",
            "目標血糖": "150-200 mg/dL (初期解消まで)",
            "pH": "≥7.30",
            "HCO3": "≥15 mEq/L",
            "AG": "正常化 (≤12)",
            "K": "3.5-5.0 mEq/L",
        },
        pitfalls=[
            "低 K 血症状態でインスリン先行投与 → 致死的低 K 血症",
            "血糖のみを指標にした早期インスリン中止 → アニオンギャップが開大のままで DKA 継続",
            "脳浮腫（小児 DKA で特に注意）→ 補液速度の過剰は禁物",
            "HHS（高浸透圧高血糖症候群）との鑑別忘れ",
            "肺水腫リスクを無視した過剰補液",
            "ルーチンの重炭酸ナトリウム投与 → 低 K・脳内アシドーシス悪化",
        ],
    ),

    # ------------------------------------------------------------------
    # 4. アナフィラキシー
    # ------------------------------------------------------------------
    TreatmentProtocol(
        diagnosis="アナフィラキシー",
        icd10="T78.2",
        key_principle="エピネフリン筋注が第一選択。抗ヒスタミン薬はエピネフリンの代替にならない。",
        steps=[
            TreatmentStep(
                timing="0-10min", priority=1,
                action="エピネフリン 筋注（第一選択）",
                dose="エピネフリン 0.3-0.5 mg IM（大腿外側）。エピペン 0.3 mg も可。小児: 0.01 mg/kg",
            ),
            TreatmentStep(
                timing="0-10min", priority=1,
                action="仰臥位・下肢挙上（ショック時）",
                dose=None,
                condition="起立不能・低血圧 → 仰臥位。嘔気・呼吸困難 → 快適な姿勢",
            ),
            TreatmentStep(
                timing="0-10min", priority=1,
                action="酸素投与",
                dose="高流量酸素 10-15 L/min マスク（SpO2 ≥95% 目標）",
            ),
            TreatmentStep(
                timing="0-10min", priority=1,
                action="静脈路確保",
                dose="太径カテーテル（16-18G）× 2 本",
            ),
            TreatmentStep(
                timing="0-10min", priority=2,
                action="エピネフリン効果不十分 → 5-15 分後に再投与",
                dose="エピネフリン 0.3-0.5 mg IM 反復（最大 3 回）",
            ),
            TreatmentStep(
                timing="0-30min", priority=1,
                action="輸液蘇生（低血圧・ショック）",
                dose="生食 1-2 L IV 急速投与（小児: 20 mL/kg ボーラス）",
                condition="低血圧・ショックを伴う場合",
            ),
            TreatmentStep(
                timing="10-30min", priority=2,
                action="抗ヒスタミン薬（補助）",
                dose="ジフェンヒドラミン 25-50 mg IV または PO（皮膚症状の緩和）",
                condition="エピネフリン投与後の補助。エピネフリンの代替ではない",
            ),
            TreatmentStep(
                timing="10-30min", priority=2,
                action="コルチコステロイド（遅発相予防）",
                dose="メチルプレドニゾロン 125 mg IV（または等価量）",
                condition="遅発相（8-12 時間後）の症状抑制を目的",
            ),
            TreatmentStep(
                timing="ongoing", priority=2,
                action="エピネフリン持続投与（難治性）",
                dose="エピネフリン 0.1-0.5 μg/kg/min IV 持続",
                condition="IM 投与 3 回後も低血圧持続",
            ),
            TreatmentStep(
                timing="ongoing", priority=2,
                action="気管挿管・外科的気道確保",
                dose=None,
                condition="上気道閉塞（喉頭浮腫）で気道確保不能の場合",
            ),
            TreatmentStep(
                timing="ongoing", priority=3,
                action="観察 4-8 時間（双相反応の監視）",
                dose=None,
            ),
        ],
        monitoring=[
            "BP・HR・SpO2 連続モニタリング",
            "エピネフリン投与後 5-15 分で効果確認",
            "4-8 時間の院内観察（双相性アナフィラキシー）",
            "喉頭浮腫の進行（嗄声・喘鳴）",
        ],
        goals={
            "SBP": "≥90 mmHg",
            "SpO2": "≥95%",
            "皮膚": "紅潮・蕁麻疹の改善",
        },
        pitfalls=[
            "エピネフリンを投与せず抗ヒスタミン薬で代替 → 致死的",
            "静脈路確保を優先しエピネフリン筋注を遅らせる",
            "β遮断薬内服中は効果が減弱 → グルカゴン 1-2 mg IV を追加考慮",
            "早期退院 → 双相性反応（8-12 時間後）を見逃す",
            "エピペン処方・患者教育を怠る",
        ],
    ),

    # ------------------------------------------------------------------
    # 5. 敗血症性ショック (SEP-1 バンドル)
    # ------------------------------------------------------------------
    TreatmentProtocol(
        diagnosis="敗血症性ショック (Septic Shock)",
        icd10="A41.9",
        key_principle="Hour-1 バンドル: 採血→乳酸→広域抗生物質→輸液→昇圧薬。1 時間以内の抗生物質投与が予後規定。",
        steps=[
            TreatmentStep(
                timing="0-10min", priority=1,
                action="血液培養 2 セット採取（抗菌薬投与前）",
                dose="好気 + 嫌気 × 2 セット（異なる部位から）",
            ),
            TreatmentStep(
                timing="0-10min", priority=1,
                action="乳酸値測定",
                dose="静脈血乳酸 ≥2 mmol/L で敗血症、≥4 mmol/L で重篤",
            ),
            TreatmentStep(
                timing="0-60min", priority=1,
                action="広域抗菌薬 投与開始（診断後 1 時間以内）",
                dose="ピペラシリン-タゾバクタム 4.5 g IV q6h + バンコマイシン 25 mg/kg IV（MRSA 疑い時）",
                condition="感染源・地域の耐性菌パターンにより調整",
            ),
            TreatmentStep(
                timing="0-60min", priority=1,
                action="晶質液 急速輸液",
                dose="生食または乳酸リンゲル液 30 mL/kg IV 3 時間以内に投与",
                condition="低血圧（MAP <65 mmHg）または乳酸 ≥4 mmol/L",
            ),
            TreatmentStep(
                timing="0-60min", priority=1,
                action="昇圧薬 開始（輸液反応不十分時）",
                dose="ノルエピネフリン 0.01-3.0 μg/kg/min IV 持続（MAP 65 mmHg 目標）",
                condition="MAP <65 mmHg かつ輸液 30 mL/kg 投与後",
            ),
            TreatmentStep(
                timing="30-60min", priority=2,
                action="感染源同定・ドレナージ",
                dose=None,
                condition="膿瘍・胆嚢炎・虫垂炎等 → 外科的 / インターベンション的ドレナージを検討",
            ),
            TreatmentStep(
                timing="1-6h", priority=2,
                action="輸液反応性評価（無駄な過剰輸液回避）",
                dose="POCUS・受動的下肢挙上・脈圧変動で輸液反応性を確認",
            ),
            TreatmentStep(
                timing="6h", priority=2,
                action="目標達成確認（6 時間バンドル）",
                dose="乳酸 ≥2 mmol/L → 2 時間後に再測定。MAP ≥65 mmHg。尿量 ≥0.5 mL/kg/h",
            ),
            TreatmentStep(
                timing="ongoing", priority=2,
                action="コルチコステロイド（難治性ショック）",
                dose="ヒドロコルチゾン 200 mg/日 持続 IV（ノルエピネフリン ≥0.25 μg/kg/min 必要な場合）",
            ),
            TreatmentStep(
                timing="ongoing", priority=3,
                action="抗菌薬 de-escalation（培養結果後）",
                dose="72 時間後に培養結果でスペクトルを絞り込む",
            ),
        ],
        monitoring=[
            "MAP 連続モニタリング（動脈ライン推奨）",
            "乳酸 2 時間ごと（解消まで）",
            "尿量 1 時間ごと（カテーテル留置）",
            "輸液バランス 6 時間ごと",
            "ScvO2（中心静脈酸素飽和度）≥70% を目標",
            "血糖 1-2 時間ごと（140-180 mg/dL 目標）",
        ],
        goals={
            "MAP": "≥65 mmHg",
            "乳酸": "解消 (<2 mmol/L) または 2 時間で 10% 以上低下",
            "尿量": "≥0.5 mL/kg/h",
            "ScvO2": "≥70%",
            "血糖": "140-180 mg/dL",
        },
        pitfalls=[
            "培養採取前に抗菌薬投与 → 診断情報の喪失",
            "抗菌薬開始の遅延 → 1 時間遅延ごとに生存率低下",
            "過剰輸液 → 肺水腫・腹部コンパートメント症候群",
            "ルーチンのコルチコステロイド（難治性ショックでなければ不要）",
            "感染源ドレナージの遅延",
            "血糖コントロール不良（低血糖も有害）",
        ],
    ),

    # ------------------------------------------------------------------
    # 6. 痙攣重積状態
    # ------------------------------------------------------------------
    TreatmentProtocol(
        diagnosis="痙攣重積状態 (Status Epilepticus)",
        icd10="G41.9",
        key_principle="5 分以上の痙攣は重積として即時介入。時間経過とともに治療反応性が低下する。段階的薬物療法を実施。",
        steps=[
            TreatmentStep(
                timing="0-5min", priority=1,
                action="ABCs 確認・気道保護",
                dose="酸素投与 10-15 L/min。吸引準備。挿管セット用意",
            ),
            TreatmentStep(
                timing="0-5min", priority=1,
                action="血糖測定",
                dose="血糖 <60 mg/dL → チアミン 100 mg IV 後にブドウ糖 50 mL (D50W) IV",
            ),
            TreatmentStep(
                timing="5-20min", priority=1,
                action="第一選択: ベンゾジアゼピン（BZD）",
                dose="ロラゼパム 0.1 mg/kg IV（最大 4 mg）または ジアゼパム 0.15 mg/kg IV（最大 10 mg）。5-10 分後に繰り返し可",
                condition="IV ルートあり",
            ),
            TreatmentStep(
                timing="5-20min", priority=1,
                action="IV なし → ミダゾラム 筋注/鼻腔内",
                dose="ミダゾラム 10 mg IM（または 0.2 mg/kg、最大 10 mg）",
                condition="静脈路未確保の場合",
            ),
            TreatmentStep(
                timing="20-40min", priority=1,
                action="第二選択: 抗てんかん薬（BZD 無効時）",
                dose="レベチラセタム 60 mg/kg IV 15 分で（最大 4500 mg） または フェノバルビタール 20 mg/kg IV ≤100 mg/min",
                condition="BZD 2 回投与後も発作持続（難治性 SE）",
            ),
            TreatmentStep(
                timing="20-40min", priority=2,
                action="フェニトイン（代替）",
                dose="ホスフェニトイン 20 mg PE/kg IV ≤150 mg PE/min（心電図モニタリング必須）",
                condition="レベチラセタム使用不可の場合",
            ),
            TreatmentStep(
                timing="40-60min", priority=1,
                action="超難治性 SE → 麻酔薬導入",
                dose="プロポフォール 1-2 mg/kg IV ボーラス → 1-5 mg/kg/h 持続 または ミダゾラム 0.2 mg/kg → 0.05-0.5 mg/kg/h",
                condition="第二選択薬 2 種無効（超難治性 SE）",
            ),
            TreatmentStep(
                timing="ongoing", priority=2,
                action="連続脳波モニタリング (cEEG)",
                dose=None,
                condition="意識障害が遷延する場合（non-convulsive SE を除外）",
            ),
            TreatmentStep(
                timing="ongoing", priority=2,
                action="原因検索",
                dose="電解質・血糖・薬物スクリーニング・頭部 CT/MRI・腰椎穿刺（発熱・髄膜刺激症状）",
            ),
        ],
        monitoring=[
            "連続心電図（フェニトイン使用時は必須）",
            "SpO2・呼吸数 連続モニタリング",
            "血糖 30 分ごと（BZD・麻酔薬投与中）",
            "連続脳波（cEEG）による発作消失確認",
            "動脈血ガス（チアノーゼ・呼吸抑制）",
        ],
        goals={
            "発作消失": "5 分以内の薬物介入開始",
            "第一選択": "5-20 分以内",
            "第二選択": "20-40 分以内",
            "超難治性 SE": "40-60 分以内に麻酔",
        },
        pitfalls=[
            "BZD 投与の遅れ（静脈路確保を優先しすぎ）",
            "低血糖・代謝異常の見落とし",
            "Non-convulsive SE を見逃す（意識障害 + EEG なしで診断できない）",
            "フェニトインを速く投与 → 不整脈・低血圧",
            "麻酔薬導入後の気道管理不十分",
            "発作消失後に維持療法を怠る",
        ],
    ),

    # ------------------------------------------------------------------
    # 7. 脳卒中 / tPA プロトコル
    # ------------------------------------------------------------------
    TreatmentProtocol(
        diagnosis="急性虚血性脳卒中 (tPA プロトコル)",
        icd10="I63.9",
        key_principle="Time is Brain。発症から 4.5 時間以内の tPA（アルテプラーゼ）投与、かつ Door-to-Needle ≤60 分。絶対禁忌を厳格に確認。",
        steps=[
            TreatmentStep(
                timing="0-10min", priority=1,
                action="NIHSS 評価・発症時刻確認",
                dose="最終正常時刻（LKW）を確認。不明は wake-up stroke として扱う",
            ),
            TreatmentStep(
                timing="0-25min", priority=1,
                action="頭部 CT（出血除外）",
                dose="造影不要 CT。ASPECTS スコア評価（≥6 が tPA 適応の目安）",
            ),
            TreatmentStep(
                timing="0-25min", priority=1,
                action="採血（PT/APTT・血小板・血糖・電解質）",
                dose=None,
            ),
            TreatmentStep(
                timing="0-45min", priority=1,
                action="tPA 絶対禁忌チェック",
                dose=None,
                condition="出血性脳卒中・3 ヶ月以内頭蓋内手術・INR >1.7・血小板 <100,000・血糖 <50 mg/dL・SBP >185 mmHg（降圧が前提）",
            ),
            TreatmentStep(
                timing="0-60min", priority=1,
                action="アルテプラーゼ 投与（DtN ≤60 分）",
                dose="アルテプラーゼ 0.9 mg/kg（最大 90 mg）: 総量の 10% を 1 分で IV ボーラス → 残り 90% を 60 分で持続 IV",
                condition="LKW から 4.5 時間以内 かつ 禁忌なし",
            ),
            TreatmentStep(
                timing="0-60min", priority=2,
                action="血圧管理（tPA 投与前）",
                dose="SBP >185 mmHg → ラベタロール 10-20 mg IV または ニカルジピン 5-15 mg/h IV で SBP <185 mmHg に",
            ),
            TreatmentStep(
                timing="30-60min", priority=1,
                action="血管内治療の評価（機械的血栓回収）",
                dose=None,
                condition="大血管閉塞（LVO: ICA/M1/Basilar）→ tPA 併用または血管内治療単独（LKW 24h 以内で適応拡大）",
            ),
            TreatmentStep(
                timing="ongoing", priority=2,
                action="tPA 投与中・後の血圧管理",
                dose="tPA 中: SBP <180 mmHg、DBP <105 mmHg を維持。24 時間は抗凝固・抗血小板禁止",
            ),
            TreatmentStep(
                timing="ongoing", priority=2,
                action="神経学的悪化 → 症候性頭蓋内出血（SICH）を疑い CT",
                dose="tPA 中止・クリオプレシピテート・血液内科コンサルト",
                condition="NIHSS 4 点以上の悪化",
            ),
            TreatmentStep(
                timing="24h", priority=3,
                action="抗血小板薬 開始",
                dose="アスピリン 160-300 mg PO 開始（CT で出血除外後）",
            ),
        ],
        monitoring=[
            "神経学的評価（NIHSS）: 投与中 15 分ごと → 24 時間 1 時間ごと",
            "BP: 投与中 15 分ごと × 2 時間 → 30 分ごと × 6 時間 → 1 時間ごと × 16 時間",
            "24 時間後 MRI/CT（SICH 除外と再灌流確認）",
            "嚥下評価（誤嚥性肺炎予防）",
        ],
        goals={
            "DtN": "≤60 分（理想 ≤45 分）",
            "tPA 投与窓": "LKW から 4.5 時間以内",
            "BP（tPA 投与中）": "SBP <180 mmHg",
            "血糖": "140-180 mg/dL",
        },
        pitfalls=[
            "発症時刻の不正確な確認 → LKW を最終目撃時刻に統一",
            "禁忌確認の省略（抗凝固薬内服・最近の手術等）",
            "DtN 遅延（画像診断・採血の逐次処理）→ 並列処理で短縮",
            "tPA 後の過剰降圧 → 梗塞周辺部への血流低下",
            "tPA 後 24 時間の抗凝固・抗血小板禁止を忘れる",
            "LVO の見落とし → 血管内治療の機会逸失",
        ],
    ),

    # ------------------------------------------------------------------
    # 8. 肺塞栓症
    # ------------------------------------------------------------------
    TreatmentProtocol(
        diagnosis="肺塞栓症 (Pulmonary Embolism)",
        icd10="I26.9",
        key_principle="大量 PE（循環虚脱）は溶栓療法が第一選択。中等量 PE は早期抗凝固。リスク層別化（PESI スコア）が管理を規定する。",
        steps=[
            TreatmentStep(
                timing="0-10min", priority=1,
                action="PE 疑い → 安定化・酸素投与",
                dose="高流量酸素。大量 PE では積極的輸液は回避（右室過負荷悪化）",
            ),
            TreatmentStep(
                timing="0-30min", priority=1,
                action="診断確認（CT 肺動脈造影）",
                dose="CTPA が第一選択。不安定 → エコーで右室拡大を確認しながら経験的治療",
            ),
            TreatmentStep(
                timing="0-30min", priority=1,
                action="抗凝固療法 開始（非大量 PE）",
                dose="ヘパリン 80 IU/kg IV ボーラス → 18 IU/kg/h 持続 または リバーロキサバン 15 mg PO BID × 21 日",
                condition="大量 PE（循環虚脱）でない場合",
            ),
            TreatmentStep(
                timing="0-60min", priority=1,
                action="全身溶栓療法（大量 PE）",
                dose="アルテプラーゼ 100 mg IV 2 時間で投与（50 mg ボーラス可）",
                condition="大量 PE: 循環虚脱（SBP <90 mmHg）または心停止 → 絶対適応",
            ),
            TreatmentStep(
                timing="30-60min", priority=2,
                action="外科的肺動脈血栓摘除術 / カテーテル血栓破砕",
                dose=None,
                condition="溶栓禁忌の大量 PE または溶栓失敗例",
            ),
            TreatmentStep(
                timing="ongoing", priority=2,
                action="昇圧薬（大量 PE + 低血圧）",
                dose="ノルエピネフリン 0.01-3.0 μg/kg/min。ドブタミン（右室不全）2.5-10 μg/kg/min",
            ),
            TreatmentStep(
                timing="ongoing", priority=3,
                action="経口抗凝固薬への移行（安定後）",
                dose="DOAC（アピキサバン・リバーロキサバン）推奨。最低 3 ヶ月間（再発・癌合併では長期）",
            ),
            TreatmentStep(
                timing="ongoing", priority=3,
                action="誘因検索",
                dose="DVT・悪性腫瘍（隠蔽癌）・血栓性素因スクリーニング（初発・若年・再発例）",
            ),
        ],
        monitoring=[
            "BP・HR・SpO2 連続モニタリング",
            "心エコー（右室拡大・McConnell サイン・D-shape）",
            "BNP/TnI（中等量 PE のリスク評価）",
            "APTT（ヘパリン調整、1.5-2.5 × 正常値）",
            "溶栓後 2-3 時間で臨床効果評価",
        ],
        goals={
            "SBP": "≥90 mmHg",
            "SpO2": "≥95%",
            "APTT（ヘパリン）": "60-80 秒（1.5-2.5 × 正常値）",
        },
        pitfalls=[
            "非大量 PE に対する過剰輸液 → 右室拡大悪化",
            "溶栓禁忌の確認不足（最近の手術・出血性素因）",
            "Wells スコア・PERC ルールによる適切なリスク評価の省略",
            "慢性肺塞栓性肺高血圧症（CTEPH）のフォロー不足",
        ],
    ),

    # ------------------------------------------------------------------
    # 9. 急性大動脈解離
    # ------------------------------------------------------------------
    TreatmentProtocol(
        diagnosis="急性大動脈解離",
        icd10="I71.0",
        key_principle="Stanford A 型（上行大動脈）は緊急外科手術。B 型は医療管理（BP/HR コントロール）が基本。鎮痛と降圧が最優先。",
        steps=[
            TreatmentStep(
                timing="0-10min", priority=1,
                action="安静・IV 路確保（太径 2 本）",
                dose="安静臥床。不必要な体動を避ける",
            ),
            TreatmentStep(
                timing="0-30min", priority=1,
                action="心拍数コントロール（第一目標）",
                dose="エスモロール 500 μg/kg IV ボーラス → 50-200 μg/kg/min 持続 （目標 HR <60 bpm）",
            ),
            TreatmentStep(
                timing="0-30min", priority=1,
                action="血圧コントロール（HR 目標達成後）",
                dose="ニカルジピン 5-15 mg/h IV（SBP 目標 100-120 mmHg）または ニトロプルシド 0.3-10 μg/kg/min",
                condition="HR コントロール後に血圧が目標未達の場合（β遮断薬のみで先行）",
            ),
            TreatmentStep(
                timing="0-30min", priority=1,
                action="CT 大動脈造影（診断確定）",
                dose="造影 CT: Stanford 分類・解離範囲・合併症評価",
            ),
            TreatmentStep(
                timing="0-60min", priority=1,
                action="Stanford A 型 → 緊急心臓外科コンサルト・手術準備",
                dose=None,
                condition="Stanford A 型（上行大動脈解離）",
            ),
            TreatmentStep(
                timing="ongoing", priority=2,
                action="鎮痛（疼痛コントロール）",
                dose="モルヒネ 2-4 mg IV 滴定（疼痛は血圧上昇を招く）",
            ),
            TreatmentStep(
                timing="ongoing", priority=2,
                action="Stanford B 型の合併症管理",
                dose=None,
                condition="臓器虚血（腸間膜・腎・脊髄）→ TEVAR（血管内ステントグラフト）を検討",
            ),
            TreatmentStep(
                timing="ongoing", priority=3,
                action="長期血圧管理（退院後）",
                dose="SBP <130 mmHg 目標。β遮断薬を第一選択。定期的 CT フォロー",
            ),
        ],
        monitoring=[
            "動脈ライン（橈骨または大腿）による連続 BP モニタリング",
            "HR 連続モニタリング（目標 <60 bpm）",
            "両腕 BP 差（>20 mmHg → 上行大動脈解離示唆）",
            "尿量（腎動脈解離）",
            "神経学的評価（脊髄・脳虚血）",
        ],
        goals={
            "HR": "<60 bpm",
            "SBP": "100-120 mmHg",
            "尿量": "≥0.5 mL/kg/h",
        },
        pitfalls=[
            "HR コントロール前に血管拡張薬のみ投与 → 反射性頻脈で剪断力増大",
            "Stanford A 型を誤って保存的治療 → 致死的",
            "腸間膜・腎・脊髄虚血の見落とし",
            "造影剤使用による腎機能悪化のリスク管理",
            "疼痛管理不十分による血圧上昇",
        ],
    ),

    # ------------------------------------------------------------------
    # 10. 高血圧性緊急症
    # ------------------------------------------------------------------
    TreatmentProtocol(
        diagnosis="高血圧性緊急症 (Hypertensive Emergency)",
        icd10="I10",
        key_principle="最初の 1 時間で MAP を 25% 低下させる。過剰降圧は臓器虚血（脳・心・腎）を招く。標的臓器障害の種類で薬剤を選択する。",
        steps=[
            TreatmentStep(
                timing="0-30min", priority=1,
                action="静脈路確保・標的臓器障害評価",
                dose="眼底・神経（脳症）・心（ACS・AHF）・腎（AKI）・大動脈（解離）を評価",
            ),
            TreatmentStep(
                timing="0-60min", priority=1,
                action="IV 降圧薬 開始",
                dose="ラベタロール 20 mg IV ボーラス → 2 mg/min 持続 または ニカルジピン 5-15 mg/h IV",
                condition="ルーチン。大動脈解離にはβ遮断薬を先行",
            ),
            TreatmentStep(
                timing="0-60min", priority=1,
                action="目標: 最初の 1 時間で MAP を 25% 低下",
                dose=None,
            ),
            TreatmentStep(
                timing="1-6h", priority=2,
                action="その後 160/100 mmHg 程度まで段階的に",
                dose="急激な正常化は禁止（脳血流自動調節能の障害）",
            ),
            TreatmentStep(
                timing="ongoing", priority=2,
                action="高血圧性脳症 / PRES → ニカルジピン",
                dose="ニカルジピン 5-15 mg/h IV（脳症では MgSO4 も有効）",
                condition="頭痛・視力障害・痙攣・意識障害",
            ),
            TreatmentStep(
                timing="ongoing", priority=2,
                action="ACS 合併 → ニトログリセリン + β遮断薬",
                dose="ニトログリセリン 5-200 μg/min IV + メトプロロール 5 mg IV q5min × 3",
            ),
            TreatmentStep(
                timing="ongoing", priority=2,
                action="経口薬への移行（安定化後）",
                dose="ACE 阻害薬/ARB + Ca チャネル拮抗薬 + 利尿薬の組み合わせ",
            ),
        ],
        monitoring=[
            "動脈ライン推奨（連続 BP モニタリング）",
            "神経学的評価 30 分ごと",
            "尿量 1 時間ごと",
            "BUN/Cr（AKI 評価）",
            "12 誘導心電図（ACS・LVH 評価）",
        ],
        goals={
            "最初の 1 時間": "MAP を ≤25% 低下",
            "2-6 時間": "160/100 mmHg 程度",
            "24-48 時間": "135/85 mmHg 程度",
        },
        pitfalls=[
            "過剰急速降圧 → 脳梗塞・心筋梗塞",
            "舌下ニフェジピン → 制御不能な急速降圧（禁忌）",
            "高血圧緊急症 vs 切迫症の混同（切迫症は外来管理可）",
            "標的臓器によって推奨薬が異なることを忘れる",
        ],
    ),

    # ------------------------------------------------------------------
    # 11. 急性喘息
    # ------------------------------------------------------------------
    TreatmentProtocol(
        diagnosis="急性喘息発作",
        icd10="J45.901",
        key_principle="SABA 吸入が第一選択。重症発作は MgSO4 IV・NIV を追加。挿管は最終手段（高リスク）。",
        steps=[
            TreatmentStep(
                timing="0-10min", priority=1,
                action="SABA 吸入（サルブタモール）",
                dose="サルブタモール 2.5-5 mg ネブライザー または MDI 4-8 puff（スペーサー使用）",
            ),
            TreatmentStep(
                timing="0-10min", priority=1,
                action="酸素投与",
                dose="SpO2 ≥94% を目標。過剰酸素は高 CO2 血症の患者では注意",
            ),
            TreatmentStep(
                timing="0-20min", priority=1,
                action="全身性コルチコステロイド",
                dose="プレドニゾロン 40-50 mg PO または メチルプレドニゾロン 80-125 mg IV（重症）",
            ),
            TreatmentStep(
                timing="0-20min", priority=2,
                action="イプラトロピウム 吸入（重症時追加）",
                dose="イプラトロピウム 0.5 mg ネブライザー（最初の 3 回まで SABA と混合）",
                condition="重症発作または SABA 単独で不十分",
            ),
            TreatmentStep(
                timing="20-60min", priority=1,
                action="SABA 反復（20 分ごと × 3 回）",
                dose="サルブタモール 2.5-5 mg ネブライザー 20 分ごと（重症: 持続ネブライザー 10-15 mg/h）",
            ),
            TreatmentStep(
                timing="30-60min", priority=2,
                action="硫酸マグネシウム IV（重症・SABA 反応不良）",
                dose="MgSO4 2 g IV 20 分かけて投与（低 Mg 不要、気管支拡張効果）",
                condition="重症発作 (FEV1 <40%、SpO2 <92%) でSABA 3 回後も不十分",
            ),
            TreatmentStep(
                timing="30-60min", priority=2,
                action="ヘリオックス（軽減療法）",
                dose="Heliox (70% He / 30% O2) 吸入",
                condition="重症・難治性（SpO2 が許容される範囲で）",
            ),
            TreatmentStep(
                timing="ongoing", priority=2,
                action="NIV（NPPV: BiPAP）",
                dose="IPAP 10-15 cmH2O / EPAP 5-8 cmH2O",
                condition="重症で挿管を避けたい場合（意識清明・協力可能）",
            ),
            TreatmentStep(
                timing="ongoing", priority=3,
                action="挿管（最終手段）",
                dose="RSI: ケタミン 1-2 mg/kg IV（気管支拡張作用あり）+ ロクロニウム 1.2 mg/kg IV",
                condition="心停止切迫・意識障害・完全疲弊",
            ),
        ],
        monitoring=[
            "SpO2 連続モニタリング",
            "呼吸数・補助筋使用・奇脈（重症度評価）",
            "PEFR または FEV1（可能であれば）",
            "動脈血ガス（重症・CO2 貯留を疑う場合）",
            "β2 作動薬による低 K 血症（長期使用時）",
        ],
        goals={
            "SpO2": "≥94%",
            "PEF": "≥70% 予測値",
            "症状": "会話可能・起座位不要",
        },
        pitfalls=[
            "コルチコステロイドの遅延 → 炎症相への作用が遅れる（早期投与が重要）",
            "挿管後の高原圧・auto-PEEP → 動的過膨張",
            "SpO2 正常で「軽症」と誤判断 → 動脈血ガスで CO2 確認",
            "β遮断薬内服患者への SABA → 効果が減弱（原則避けるか高用量）",
            "低 K 血症（SABA + コルチコステロイド）の見落とし",
        ],
    ),

    # ------------------------------------------------------------------
    # 12. 上部消化管出血
    # ------------------------------------------------------------------
    TreatmentProtocol(
        diagnosis="上部消化管出血 (Upper GI Bleeding)",
        icd10="K92.2",
        key_principle="蘇生→リスク評価（Glasgow-Blatchford / Rockall）→早期内視鏡（24 時間以内、高リスクは 12 時間以内）→止血。",
        steps=[
            TreatmentStep(
                timing="0-10min", priority=1,
                action="2 本の太径静脈路確保（18G 以上）",
                dose="生食または乳酸リンゲル液 急速輸液（低血圧の場合）",
            ),
            TreatmentStep(
                timing="0-10min", priority=1,
                action="輸血準備・交差適合試験",
                dose="目標 Hb ≥7 g/dL（心疾患・高齢 ≥8 g/dL）。濃厚赤血球 2-4 単位準備",
            ),
            TreatmentStep(
                timing="0-30min", priority=1,
                action="PPI 高用量 投与",
                dose="エソメプラゾール 80 mg IV ボーラス → 8 mg/h 持続 IV",
                condition="消化性潰瘍出血が疑われる場合（即時開始）",
            ),
            TreatmentStep(
                timing="0-30min", priority=2,
                action="胃管挿入（必要に応じ）",
                dose=None,
                condition="意識障害・大量出血で誤嚥リスク高い場合に検討（ルーチンは不要）",
            ),
            TreatmentStep(
                timing="0-30min", priority=2,
                action="オクトレオチド（食道静脈瘤出血が疑われる場合）",
                dose="オクトレオチド 50 μg IV ボーラス → 50 μg/h 持続 IV（3-5 日間）",
                condition="肝硬変・静脈瘤出血が疑われる場合",
            ),
            TreatmentStep(
                timing="0-30min", priority=2,
                action="気道保護（大量出血・意識障害）",
                dose="気管挿管を考慮（誤嚥リスク）",
                condition="意識障害 GCS <9 または大量出血",
            ),
            TreatmentStep(
                timing="0-12h", priority=1,
                action="上部内視鏡（EGD）緊急施行",
                dose=None,
                condition="高リスク（GBS ≥7、出血継続、心血管合併症）: 12 時間以内",
            ),
            TreatmentStep(
                timing="0-24h", priority=2,
                action="上部内視鏡（一般リスク）",
                dose=None,
                condition="安定例: 24 時間以内に施行",
            ),
            TreatmentStep(
                timing="ongoing", priority=2,
                action="静脈瘤出血 → TIPS・外科的シャント（内視鏡止血失敗時）",
                dose=None,
                condition="内視鏡的硬化療法・結紮（EVL）失敗例",
            ),
            TreatmentStep(
                timing="ongoing", priority=3,
                action="H. pylori 検査・除菌（消化性潰瘍）",
                dose="CLO テストまたは迅速尿素呼気試験 → 陽性: 3 剤除菌療法",
            ),
        ],
        monitoring=[
            "BP・HR 15-30 分ごと（バイタル安定するまで）",
            "Hb 6-8 時間ごと（出血量評価）",
            "尿量（臓器灌流評価）",
            "BUN/Cr（血液の腸管分解で BUN 上昇 → 活動性出血の指標）",
            "PT/INR・血小板（凝固障害の評価）",
        ],
        goals={
            "Hb": "≥7 g/dL (≥8 g/dL 心疾患)",
            "SBP": "≥90 mmHg",
            "内視鏡": "高リスク: ≤12h / 一般: ≤24h",
        },
        pitfalls=[
            "静脈瘤出血でオクトレオチドを投与しない",
            "輸血の過剰 → 門脈圧上昇で静脈瘤出血悪化",
            "PPI の遅延（即時開始が内視鏡所見と予後を改善）",
            "抗凝固・抗血小板薬中止のタイミング判断（血栓リスクと出血リスクのバランス）",
            "NSAID・アスピリン関連潰瘍の見落とし → 再出血予防に PPI 長期投与",
        ],
    ),
]


# ===========================================================================
# アクセス関数
# ===========================================================================

def get_protocol(diagnosis: str) -> TreatmentProtocol | None:
    """
    疾患名からプロトコルを取得する（ファジーマッチング対応）。

    Parameters
    ----------
    diagnosis : str
        疾患名（英語・日本語、部分一致可）

    Returns
    -------
    TreatmentProtocol | None
    """
    d = diagnosis.lower().strip()

    # 完全・部分一致
    for p in _PROTOCOLS:
        if d in p.diagnosis.lower() or p.diagnosis.lower() in d:
            return p

    # ICD-10 コード一致
    for p in _PROTOCOLS:
        if d.upper() == p.icd10.upper():
            return p

    # 日本語キーワードマッピング
    keyword_map = {
        "stemi": "STEMI",
        "heart failure": "急性心不全",
        "dka": "DKA",
        "anaphylaxis": "アナフィラキシー",
        "sepsis": "敗血症",
        "septic shock": "敗血症",
        "epilepsy": "痙攣",
        "seizure": "痙攣",
        "stroke": "脳卒中",
        "tpa": "脳卒中",
        "pe": "肺塞栓",
        "pulmonary embolism": "肺塞栓",
        "aortic dissection": "大動脈解離",
        "hypertensive": "高血圧",
        "asthma": "喘息",
        "gi bleed": "消化管出血",
        "ugib": "消化管出血",
        "心筋梗塞": "STEMI",
        "心不全": "急性心不全",
        "糖尿病性ケトアシドーシス": "DKA",
        "敗血症性": "敗血症",
        "痙攣重積": "痙攣重積",
        "虚血性脳卒中": "脳卒中",
        "肺塞栓": "肺塞栓",
        "大動脈解離": "大動脈解離",
        "高血圧性緊急症": "高血圧",
        "喘息発作": "急性喘息",
        "消化管出血": "消化管出血",
    }

    for kw, target in keyword_map.items():
        if kw in d:
            for p in _PROTOCOLS:
                if target in p.diagnosis:
                    return p

    # difflib ファジーマッチング
    names = [p.diagnosis.lower() for p in _PROTOCOLS]
    matches = difflib.get_close_matches(d, names, n=1, cutoff=0.35)
    if matches:
        idx = names.index(matches[0])
        return _PROTOCOLS[idx]

    return None


def list_protocols() -> list[dict]:
    """登録されている全プロトコルの一覧を返す。"""
    return [
        {
            "diagnosis": p.diagnosis,
            "icd10": p.icd10,
            "steps_count": len(p.steps),
            "key_principle": p.key_principle[:60] + "...",
        }
        for p in _PROTOCOLS
    ]


def format_protocol_text(protocol: TreatmentProtocol) -> str:
    """
    プロトコルを臨床サマリーテキストに変換する。

    Parameters
    ----------
    protocol : TreatmentProtocol
        プロトコルオブジェクト

    Returns
    -------
    str
        フォーマット済みテキスト
    """
    lines: list[str] = []
    lines.append("=" * 68)
    lines.append(f"  治療プロトコル: {protocol.diagnosis}")
    lines.append(f"  ICD-10: {protocol.icd10}")
    lines.append("=" * 68)
    lines.append(f"\n[原則]\n  {protocol.key_principle}\n")

    # ゴール
    lines.append("[治療目標]")
    for k, v in protocol.goals.items():
        lines.append(f"  {k}: {v}")
    lines.append("")

    # ステップ（優先度でグループ化）
    lines.append("[治療ステップ]")
    priority_labels = {1: "即時", 2: "緊急", 3: "準緊急"}
    prev_timing = ""
    for step in sorted(protocol.steps, key=lambda s: (s.timing, s.priority)):
        if step.timing != prev_timing:
            lines.append(f"\n  ▸ {step.timing}")
            prev_timing = step.timing
        pri = priority_labels.get(step.priority, "")
        line = f"    [{pri}] {step.action}"
        if step.dose:
            line += f"\n          用量: {step.dose}"
        if step.condition:
            line += f"\n          条件: {step.condition}"
        lines.append(line)

    # モニタリング
    lines.append("\n[モニタリング]")
    for m in protocol.monitoring:
        lines.append(f"  • {m}")

    # 落とし穴
    lines.append("\n[注意点・よくある誤り]")
    for i, pit in enumerate(protocol.pitfalls, 1):
        lines.append(f"  {i}. {pit}")

    lines.append("\n" + "=" * 68)
    return "\n".join(lines)


# ===========================================================================
# デモ
# ===========================================================================

if __name__ == "__main__":
    print("=" * 68)
    print("  Evidence-Based Treatment Protocols — デモ")
    print("=" * 68)

    # 登録一覧
    print("\n--- 登録プロトコル一覧 ---")
    for entry in list_protocols():
        print(f"  [{entry['icd10']}] {entry['diagnosis']} ({entry['steps_count']} ステップ)")

    # STEMI プロトコル全文表示
    print("\n--- STEMI プロトコル ---")
    p = get_protocol("STEMI")
    if p:
        print(format_protocol_text(p))

    # ファジーマッチングテスト
    print("\n--- ファジーマッチングテスト ---")
    queries = ["心筋梗塞", "septic shock", "anaphylaxis", "DKA", "status epilepticus", "UGIB", "tPA"]
    for q in queries:
        found = get_protocol(q)
        print(f"  '{q}' → {found.diagnosis if found else 'Not found'}")

    # DKA プロトコル
    print("\n--- DKA プロトコル（サマリー） ---")
    dka = get_protocol("DKA")
    if dka:
        print(f"原則: {dka.key_principle}")
        print("\n即時ステップ:")
        for s in [step for step in dka.steps if step.priority == 1]:
            print(f"  [{s.timing}] {s.action}")
            if s.dose:
                print(f"          {s.dose}")
        print("\n注意点:")
        for pit in dka.pitfalls[:3]:
            print(f"  - {pit}")
