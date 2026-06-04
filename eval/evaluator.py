import json
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def disease_match(pred: str, gold: str, threshold: float = 0.6) -> float:
    pred_words = set(pred.lower().split())
    gold_words = set(gold.lower().split())
    if not gold_words:
        return 0.0
    overlap = len(pred_words & gold_words) / len(gold_words)
    return overlap


def evaluate_dd(pred: dict, gold: dict) -> dict:
    scores = {}

    if "primary" in pred and "primary" in gold:
        scores["primary_match"] = disease_match(
            pred["primary"].get("disease", ""),
            gold["primary"].get("disease", "")
        )
        p_prob = pred["primary"].get("probability", 0)
        g_prob = gold["primary"].get("probability", 0)
        scores["primary_prob_error"] = abs(p_prob - g_prob)
    else:
        scores["primary_match"] = 0.0
        scores["primary_prob_error"] = 1.0

    if "differentials" in pred and "differentials" in gold:
        pred_diseases = {d.get("disease", "") for d in pred["differentials"]}
        gold_diseases = {d.get("disease", "") for d in gold["differentials"]}
        matched = sum(
            any(disease_match(p, g) > 0.5 for p in pred_diseases)
            for g in gold_diseases
        )
        scores["differential_recall"] = matched / max(len(gold_diseases), 1)
    else:
        scores["differential_recall"] = 0.0

    if "red_flags" in pred and "red_flags" in gold:
        pred_flags = " ".join(pred["red_flags"])
        gold_flags = " ".join(gold["red_flags"])
        scores["red_flag_recall"] = disease_match(pred_flags, gold_flags)
    else:
        scores["red_flag_recall"] = 0.0

    pred_urgency = pred.get("urgency", "")
    gold_urgency = gold.get("urgency", "")
    scores["urgency_match"] = float(pred_urgency == gold_urgency)

    scores["overall"] = (
        scores["primary_match"] * 0.35
        + (1 - scores["primary_prob_error"]) * 0.15
        + scores["differential_recall"] * 0.25
        + scores["red_flag_recall"] * 0.15
        + scores["urgency_match"] * 0.10
    )
    return scores


def batch_evaluate(results_path: str, gold_path: str) -> dict:
    with open(results_path, encoding="utf-8") as f:
        results = json.load(f)
    with open(gold_path, encoding="utf-8") as f:
        golds = json.load(f)

    all_scores = []
    for pred_item, gold_item in zip(results, golds):
        pred = pred_item.get("prediction", {})
        gold = gold_item.get("answer", {})
        if isinstance(gold, str):
            try:
                gold = json.loads(gold)
            except Exception:
                continue
        scores = evaluate_dd(pred, gold)
        all_scores.append(scores)

    if not all_scores:
        return {}

    avg = {k: sum(s[k] for s in all_scores) / len(all_scores) for k in all_scores[0]}
    print("\n=== 評価結果 ===")
    print(f"サンプル数: {len(all_scores)}")
    print(f"第一診断一致率: {avg['primary_match']:.3f}")
    print(f"鑑別診断再現率: {avg['differential_recall']:.3f}")
    print(f"Red Flag再現率: {avg['red_flag_recall']:.3f}")
    print(f"緊急度一致率:   {avg['urgency_match']:.3f}")
    print(f"総合スコア:     {avg['overall']:.3f}")
    return avg


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--results", required=True)
    parser.add_argument("--gold",    required=True)
    args = parser.parse_args()
    batch_evaluate(args.results, args.gold)
