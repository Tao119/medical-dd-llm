import json
import sys
from pathlib import Path


def download_apollocorpus(out_dir: str = "data/processed", max_samples: int = 5000):
    try:
        from datasets import load_dataset
    except ImportError:
        print("pip install datasets")
        return

    print("Downloading ApolloCorpus-ja (525K medical QA)...")
    ds = load_dataset("kunishou/ApolloCorpus-ja", split="train")
    print(f"Total: {len(ds)} samples")

    records = []
    for item in ds.select(range(min(max_samples, len(ds)))):
        records.append({
            "instruction": item.get("instruction", "") or item.get("input", ""),
            "input": "",
            "output": item.get("output", "") or item.get("response", ""),
        })

    out_path = Path(out_dir) / "apollocorpus_sample.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)
    print(f"Saved {len(records)} samples → {out_path}")


def download_igakuqa(out_dir: str = "data/eval"):
    try:
        from datasets import load_dataset
    except ImportError:
        print("pip install datasets")
        return

    print("Downloading IgakuQA (医師国家試験)...")
    try:
        ds = load_dataset("stardust-coder/IgakuQA", split="test")
        out_path = Path(out_dir) / "igakuqa_test.json"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        records = [dict(item) for item in ds]
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(records, f, ensure_ascii=False, indent=2)
        print(f"Saved {len(records)} samples → {out_path}")
    except Exception as e:
        print(f"IgakuQA load failed: {e}")
        print("Try: pip install datasets && huggingface-cli login")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--apollo",   action="store_true", help="Download ApolloCorpus-ja")
    parser.add_argument("--igakuqa", action="store_true", help="Download IgakuQA")
    parser.add_argument("--all",     action="store_true", help="Download all")
    parser.add_argument("--max",     type=int, default=5000)
    args = parser.parse_args()

    if args.all or args.apollo:
        download_apollocorpus(max_samples=args.max)
    if args.all or args.igakuqa:
        download_igakuqa()
    if not (args.all or args.apollo or args.igakuqa):
        print("Usage: python3 download_training_data.py --all")
        print("       python3 download_training_data.py --apollo --max 10000")
