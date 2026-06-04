from dataclasses import dataclass
from typing import Optional


@dataclass
class Interaction:
    drug1: str
    drug2: str
    severity: str   # "contraindicated" | "major" | "moderate" | "minor"
    mechanism: str
    clinical_effect: str
    management: str


INTERACTIONS: list[dict] = [
    # Contraindicated
    {"drugs": ["ワルファリン", "アスピリン"],        "severity": "major",
     "mechanism": "血小板阻害+抗凝固の相加効果",
     "effect": "重篤な出血リスク上昇",
     "management": "併用注意。出血リスク評価必須。PPI追加を検討"},
    {"drugs": ["MAO阻害薬", "SSR"], "severity": "contraindicated",
     "mechanism": "セロトニン産生増加の相加効果",
     "effect": "セロトニン症候群（興奮・発熱・筋強剛）",
     "management": "併用禁忌。MAO阻害薬中止後2週間は間隔を置く"},
    {"drugs": ["MAO阻害薬", "SNRI"], "severity": "contraindicated",
     "mechanism": "セロトニン・ノルアドレナリン増加",
     "effect": "セロトニン症候群・高血圧クリーゼ",
     "management": "併用禁忌"},
    {"drugs": ["QT延長薬", "アミオダロン"], "severity": "major",
     "mechanism": "QT延長の相加効果",
     "effect": "トルサード・ドポワント（TdP）・心室細動",
     "management": "QT 500ms以上→中止。電解質モニタリング（K/Mg）"},
    {"drugs": ["フルコナゾール", "ワルファリン"], "severity": "major",
     "mechanism": "CYP2C9阻害→ワルファリン代謝低下",
     "effect": "PT-INR著明上昇→出血",
     "management": "ワルファリン用量50%減量+PT-INR頻回モニタリング"},
    {"drugs": ["シルデナフィル", "硝酸薬"],         "severity": "contraindicated",
     "mechanism": "NO経路相加による血管拡張",
     "effect": "重篤な低血圧（致死的）",
     "management": "絶対禁忌。最後の硝酸薬服用から24時間（タダラフィルは48時間）空ける"},
    {"drugs": ["ACE阻害薬", "ARB"],                 "severity": "major",
     "mechanism": "RAS抑制の二重遮断",
     "effect": "高カリウム血症・急性腎障害",
     "management": "原則併用禁忌（糸球体腎炎等の特殊例を除く）"},
    {"drugs": ["スタチン", "クラリスロマイシン"],    "severity": "major",
     "mechanism": "CYP3A4阻害→スタチン血中濃度上昇",
     "effect": "横紋筋融解症（CK著明上昇・腎不全）",
     "management": "短期間なら一時的スタチン休薬またはスタチン用量半減"},
    {"drugs": ["メトホルミン", "造影剤"],            "severity": "major",
     "mechanism": "造影剤誘発腎障害→メトホルミン蓄積→乳酸アシドーシス",
     "effect": "重篤な乳酸アシドーシス",
     "management": "造影剤投与前後48時間はメトホルミン休薬"},
    {"drugs": ["ジゴキシン", "アミオダロン"],        "severity": "major",
     "mechanism": "P糖蛋白阻害+腎排泄低下→ジゴキシン濃度上昇",
     "effect": "ジゴキシン中毒（徐脈・AV block・嘔気・視覚異常）",
     "management": "ジゴキシン用量50%削減+血中濃度モニタリング"},
    {"drugs": ["リチウム", "NSAIDs"],               "severity": "major",
     "mechanism": "プロスタグランジン抑制→腎リチウム再吸収増加",
     "effect": "リチウム中毒（振戦・混乱・腎不全）",
     "management": "NSAIDs回避→アセトアミノフェン代用。Li濃度モニタリング"},
    {"drugs": ["カルバマゼピン", "OCP"],             "severity": "major",
     "mechanism": "CYP3A4誘導→経口避妊薬代謝促進",
     "effect": "避妊失敗",
     "management": "バリア避妊法の追加。または代替抗てんかん薬"},
    {"drugs": ["ワーファリン", "ビタミンK"],         "severity": "major",
     "mechanism": "ビタミンKがワルファリンの作用に拮抗",
     "effect": "PT-INR低下→抗凝固効果消失→血栓リスク",
     "management": "緑黄色野菜摂取を一定に保つ。PT-INR変動に注意"},
    {"drugs": ["ジゴキシン", "ベラパミル"],          "severity": "major",
     "mechanism": "P糖蛋白阻害+腎排泄低下",
     "effect": "ジゴキシン中毒",
     "management": "ジゴキシン用量削減+血中濃度モニタリング"},
    {"drugs": ["シプロフロキサシン", "テオフィリン"], "severity": "major",
     "mechanism": "CYP1A2阻害→テオフィリン代謝低下",
     "effect": "テオフィリン中毒（悪心・頻脈・痙攣）",
     "management": "テオフィリン用量50%削減+血中濃度モニタリング"},
    {"drugs": ["フルコナゾール", "ピモジド"],        "severity": "contraindicated",
     "mechanism": "CYP3A4阻害→ピモジド蓄積→QT延長",
     "effect": "致死的不整脈（TdP）",
     "management": "絶対禁忌"},
    {"drugs": ["クロピドグレル", "PPI（オメプラゾール）"], "severity": "moderate",
     "mechanism": "CYP2C19阻害→クロピドグレル活性化低下",
     "effect": "抗血小板効果減弱→ステント血栓症リスク",
     "management": "パントプラゾール/ランソプラゾールへ変更（相互作用少）"},
    {"drugs": ["DOAC", "リファンピシン"],            "severity": "major",
     "mechanism": "P糖蛋白誘導→DOAC排泄促進",
     "effect": "DOAC血中濃度著明低下→抗凝固効果消失",
     "management": "ワルファリンへ切替推奨（DOAC+リファンピシン原則禁忌）"},
    {"drugs": ["タクロリムス", "アゾール系抗真菌薬"], "severity": "major",
     "mechanism": "CYP3A4阻害→タクロリムス代謝低下",
     "effect": "タクロリムス中毒（腎毒性・神経毒性）",
     "management": "タクロリムス用量大幅削減+血中濃度頻回測定"},
    {"drugs": ["スタチン", "ゲムフィブロジル"],      "severity": "major",
     "mechanism": "スタチン代謝阻害（OATP1B1阻害）",
     "effect": "横紋筋融解症リスク著明上昇",
     "management": "ゲムフィブロジルとスタチン併用を可能な限り回避。フェノフィブラートへ変更"},
]


def check_interactions(drug_list: list[str]) -> list[dict]:
    found = []
    normalized = [d.strip().lower() for d in drug_list]
    for inter in INTERACTIONS:
        d1, d2 = inter["drugs"]
        match1 = any(d1 in drug or drug in d1 for drug in normalized)
        match2 = any(d2 in drug or drug in d2 for drug in normalized)
        if match1 and match2:
            found.append({
                "drug1": inter["drugs"][0],
                "drug2": inter["drugs"][1],
                "severity": inter["severity"],
                "mechanism": inter["mechanism"],
                "clinical_effect": inter["effect"],
                "management": inter["management"],
            })
    return found


def check_contraindications(diagnosis: str, drug_list: list[str]) -> list[dict]:
    CONTRAINDICATIONS = {
        "大動脈解離": [("ニトロプルシド", "A型解離では血圧変動が大きい→禁忌")],
        "くも膜下出血": [("NSAIDs", "脳血管れん縮悪化リスク")],
        "高カリウム血症": [("ACE阻害薬", "K上昇"), ("ARB", "K上昇"), ("スピロノラクトン", "K上昇")],
        "急性腎障害": [("メトホルミン", "乳酸アシドーシスリスク"), ("NSAIDs", "腎血流低下"), ("造影剤", "AKI悪化")],
        "QT延長": [("アミオダロン", "QT延長相加"), ("モキシフロキサシン", "QT延長相加"), ("ハロペリドール", "QT延長相加")],
        "血小板減少": [("ヘパリン", "HIT疑いがある場合は禁忌")],
        "ブルガダ症候群": [("アジマリン", "ブルガダパターン顕性化"), ("プロカインアミド", "禁忌"), ("フレカイニド", "禁忌")],
        "気管支喘息": [("β遮断薬", "気管支攣縮誘発"), ("アスピリン", "アスピリン喘息")],
        "妊婦": [("ACE阻害薬", "胎児腎毒性"), ("ARB", "胎児奇形"), ("ワルファリン", "胎児奇形/出血"), ("テトラサイクリン", "骨・歯への影響")],
    }
    found = []
    normalized_dx = diagnosis.lower()
    for condition, drug_contraindications in CONTRAINDICATIONS.items():
        if condition in normalized_dx or normalized_dx in condition:
            for drug, reason in drug_contraindications:
                for user_drug in drug_list:
                    if drug in user_drug or user_drug in drug:
                        found.append({
                            "diagnosis": condition,
                            "drug": drug,
                            "reason": reason,
                            "severity": "contraindicated",
                        })
    return found


if __name__ == "__main__":
    test_drugs = ["ワルファリン", "アスピリン", "メトホルミン", "オメプラゾール", "クロピドグレル"]
    print(f"薬剤リスト: {test_drugs}")
    interactions = check_interactions(test_drugs)
    print(f"\n相互作用 ({len(interactions)}件):")
    for i in interactions:
        print(f"  [{i['severity']}] {i['drug1']} × {i['drug2']}")
        print(f"    → {i['clinical_effect']}")
        print(f"    管理: {i['management']}")

    contraindications = check_contraindications("急性腎障害", test_drugs)
    print(f"\n禁忌 ({len(contraindications)}件):")
    for c in contraindications:
        print(f"  [{c['severity']}] {c['drug']} in {c['diagnosis']}: {c['reason']}")
