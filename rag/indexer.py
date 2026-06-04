import os
import json
import pickle
import re
import numpy as np
import torch
from pathlib import Path
from transformers import AutoTokenizer, AutoModel


def mean_pool(hidden, mask):
    mask = mask.unsqueeze(-1).float()
    return (hidden * mask).sum(1) / mask.sum(1).clamp(min=1e-9)


class MedicalIndexer:
    def __init__(self, embed_model: str, device: str = None):
        if device is None:
            if torch.backends.mps.is_available():
                device = "mps"
            elif torch.cuda.is_available():
                device = "cuda"
            else:
                device = "cpu"
        self.device = device
        self.tokenizer = AutoTokenizer.from_pretrained(embed_model)
        self.model = AutoModel.from_pretrained(embed_model).to(device).eval()
        self.chunks: list[dict] = []
        self.embeddings: np.ndarray | None = None

    def load_documents(self, raw_dir: str, chunk_size: int = 400, overlap: int = 80):
        raw_dir = Path(raw_dir)
        docs = list(raw_dir.glob("*.txt")) + list(raw_dir.glob("*.md"))
        print(f"Loading {len(docs)} documents...")
        for doc_path in docs:
            text = doc_path.read_text(encoding="utf-8", errors="ignore")
            source = doc_path.stem
            for chunk in self._chunk_text(text, chunk_size, overlap):
                self.chunks.append({"text": chunk, "source": source})
        print(f"Total chunks: {len(self.chunks)}")

    def load_pdf_texts(self, pdf_dir: str, chunk_size: int = 400, overlap: int = 80):
        try:
            import pdfplumber
        except ImportError:
            print("pdfplumber not installed. Run: pip install pdfplumber")
            return
        pdf_dir = Path(pdf_dir)
        for pdf_path in pdf_dir.glob("*.pdf"):
            with pdfplumber.open(pdf_path) as pdf:
                text = "\n".join(p.extract_text() or "" for p in pdf.pages)
            source = pdf_path.stem
            for chunk in self._chunk_text(text, chunk_size, overlap):
                self.chunks.append({"text": chunk, "source": source})
        print(f"PDF chunks loaded: {len(self.chunks)}")

    def _chunk_text(self, text: str, size: int, overlap: int) -> list[str]:
        text = re.sub(r"\s+", " ", text).strip()
        # 日本語対応: 文字数ベースでチャンク化
        char_size = size * 2  # 1単語≒2文字と仮定
        char_overlap = overlap * 2
        chunks = []
        i = 0
        while i < len(text):
            chunk = text[i : i + char_size]
            if chunk.strip():
                chunks.append(chunk)
            i += char_size - char_overlap
        return chunks

    def build_index(self, batch_size: int = 16):
        print(f"Embedding {len(self.chunks)} chunks on {self.device}...")
        all_emb = []
        for i in range(0, len(self.chunks), batch_size):
            batch = [c["text"] for c in self.chunks[i : i + batch_size]]
            enc = self.tokenizer(batch, padding=True, truncation=True,
                                 max_length=256, return_tensors="pt")
            enc = {k: v.to(self.device) for k, v in enc.items()}
            with torch.no_grad():
                out = self.model(**enc)
            emb = mean_pool(out.last_hidden_state, enc["attention_mask"])
            emb = emb / emb.norm(dim=-1, keepdim=True)
            all_emb.append(emb.cpu().numpy())
            if (i // batch_size) % 10 == 0:
                print(f"  {i}/{len(self.chunks)}")
        self.embeddings = np.vstack(all_emb).astype(np.float32)
        print(f"Index built: shape={self.embeddings.shape}")

    def save(self, index_dir: str):
        index_dir = Path(index_dir)
        index_dir.mkdir(parents=True, exist_ok=True)
        np.save(index_dir / "embeddings.npy", self.embeddings)
        with open(index_dir / "chunks.json", "w", encoding="utf-8") as f:
            json.dump(self.chunks, f, ensure_ascii=False, indent=2)
        print(f"Saved to {index_dir}")

    def load(self, index_dir: str):
        index_dir = Path(index_dir)
        self.embeddings = np.load(index_dir / "embeddings.npy")
        with open(index_dir / "chunks.json", encoding="utf-8") as f:
            self.chunks = json.load(f)
        print(f"Loaded {len(self.chunks)} chunks, embeddings={self.embeddings.shape}")

    def retrieve(self, query: str, top_k: int = 5) -> list[dict]:
        enc = self.tokenizer(query, return_tensors="pt",
                             max_length=128, truncation=True)
        enc = {k: v.to(self.device) for k, v in enc.items()}
        with torch.no_grad():
            out = self.model(**enc)
        q_emb = mean_pool(out.last_hidden_state, enc["attention_mask"])
        q_emb = (q_emb / q_emb.norm(dim=-1, keepdim=True)).cpu().numpy()
        scores = (self.embeddings @ q_emb.T).squeeze()
        top_idx = scores.argsort()[::-1][:top_k]
        results = []
        for idx in top_idx:
            results.append({
                "text": self.chunks[idx]["text"],
                "source": self.chunks[idx]["source"],
                "score": float(scores[idx]),
            })
        return results


if __name__ == "__main__":
    import sys
    from config import EMBED_MODEL

    raw_dir = sys.argv[1] if len(sys.argv) > 1 else "data/raw"
    index_dir = sys.argv[2] if len(sys.argv) > 2 else "data/index"

    indexer = MedicalIndexer(EMBED_MODEL)
    indexer.load_documents(raw_dir)
    indexer.load_pdf_texts(raw_dir)
    if indexer.chunks:
        indexer.build_index()
        indexer.save(index_dir)
    else:
        print("No documents found. Place .txt or .pdf files in", raw_dir)
