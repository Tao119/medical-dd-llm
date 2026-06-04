import json
import re
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM
from config import SYSTEM_PROMPT, MAX_NEW_TOKENS, TEMPERATURE


class DDGenerator:
    def __init__(self, model_name: str, device: str = None):
        if device is None:
            if torch.backends.mps.is_available():
                device = "mps"
            elif torch.cuda.is_available():
                device = "cuda"
            else:
                device = "cpu"
        self.device = device
        print(f"Loading generator: {model_name} on {device}")
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModelForCausalLM.from_pretrained(
            model_name, torch_dtype=torch.float16 if device != "cpu" else torch.float32
        ).to(device).eval()
        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token

    def build_prompt(self, case: dict, retrieved_docs: list[dict]) -> str:
        context_parts = []
        for i, doc in enumerate(retrieved_docs, 1):
            context_parts.append(f"[文献{i}: {doc['source']}]\n{doc['text'][:300]}")
        context = "\n\n".join(context_parts)

        case_text = (
            f"患者情報:\n"
            f"  主訴: {case.get('chief_complaint', '不明')}\n"
            f"  症状: {', '.join(case.get('symptoms', []))}\n"
            f"  バイタル: {case.get('vitals', '記載なし')}\n"
            f"  既往歴: {case.get('history', 'なし')}\n"
            f"  年齢・性別: {case.get('demographics', '不明')}"
        )

        prompt = (
            f"{SYSTEM_PROMPT}\n\n"
            f"## 参考文献\n{context}\n\n"
            f"## {case_text}\n\n"
            f"## 鑑別診断 (JSON形式で出力)\n```json\n"
        )
        return prompt

    def generate(self, prompt: str) -> str:
        inputs = self.tokenizer(prompt, return_tensors="pt",
                                truncation=True, max_length=1800)
        inputs = {k: v.to(self.device) for k, v in inputs.items()}
        with torch.no_grad():
            output_ids = self.model.generate(
                **inputs,
                max_new_tokens=MAX_NEW_TOKENS,
                temperature=TEMPERATURE,
                do_sample=TEMPERATURE > 0,
                pad_token_id=self.tokenizer.eos_token_id,
                eos_token_id=self.tokenizer.eos_token_id,
            )
        new_ids = output_ids[0][inputs["input_ids"].shape[1]:]
        return self.tokenizer.decode(new_ids, skip_special_tokens=True)

    def parse_dd(self, raw_output: str) -> dict:
        json_match = re.search(r"```json\s*(.*?)\s*```", raw_output, re.DOTALL)
        if not json_match:
            json_match = re.search(r"(\{.*\})", raw_output, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass
        return {"raw_output": raw_output, "parse_error": True}

    def diagnose(self, case: dict, retrieved_docs: list[dict]) -> dict:
        prompt = self.build_prompt(case, retrieved_docs)
        raw = self.generate(prompt)
        result = self.parse_dd(raw)
        result["_retrieved_sources"] = [d["source"] for d in retrieved_docs]
        return result
