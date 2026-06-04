import json
import re
import os
import torch
from pathlib import Path
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

        # LoRA アダプタか通常モデルかを判定
        is_lora = (Path(model_name) / "adapter_config.json").exists()

        if is_lora:
            # adapter_config.json から base_model を読む
            import json as _json
            adapter_cfg = _json.load(open(Path(model_name) / "adapter_config.json"))
            base_model = adapter_cfg.get("base_model_name_or_path", "rinna/japanese-gpt2-medium")
            print(f"Loading LoRA adapter from: {model_name} (base: {base_model}) on {device}")
            self.tokenizer = AutoTokenizer.from_pretrained(base_model)
            base = AutoModelForCausalLM.from_pretrained(
                base_model,
                torch_dtype=torch.float16 if device != "cpu" else torch.float32,
            )
            from peft import PeftModel
            self.model = PeftModel.from_pretrained(base, model_name).to(device).eval()
        else:
            print(f"Loading generator: {model_name} on {device}")
            self.tokenizer = AutoTokenizer.from_pretrained(model_name)
            self.model = AutoModelForCausalLM.from_pretrained(
                model_name, torch_dtype=torch.float16 if device != "cpu" else torch.float32
            ).to(device).eval()

        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token

    def build_prompt(self, case: dict, retrieved_docs: list[dict]) -> str:
        # RAGコンテキストは先頭150文字のみ（GPT-2の1024token制限対策）
        context = ""
        for doc in retrieved_docs[:1]:
            context = f"[参考:{doc['source']}]{doc['text'][:150]}"

        symptoms = ', '.join(case.get('symptoms', [])[:3])
        prompt = (
            f"医師として鑑別診断をJSONで出力してください。\n"
            f"{context}\n\n"
            f"主訴:{case.get('chief_complaint','')}"
            f" 症状:{symptoms}"
            f" バイタル:{case.get('vitals','')}"
            f" 既往:{case.get('history','なし')}"
            f" {case.get('demographics','')}\n\n"
            f"```json\n"
            f'{{"primary":{{"disease":"'
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
        # プロンプトに先頭部分を付加したので完全なJSONを再構築
        full = '{"primary":{"disease":"' + raw_output
        # まず完全なJSONを試みる
        for pattern in [r"```json\s*(.*?)\s*```", r"(\{.*?\})", r"(\{.*)"]:
            m = re.search(pattern, full, re.DOTALL)
            if m:
                try:
                    return json.loads(m.group(1) if "```" in pattern else m.group(1))
                except json.JSONDecodeError:
                    pass
        # 部分的なパース: 最低でも primary.disease を抽出
        partial = {"raw_output": raw_output, "parse_error": True}
        m = re.search(r'"disease"\s*:\s*"([^"]+)"', full)
        if m:
            partial["_extracted_primary"] = m.group(1)
        return partial

    def diagnose(self, case: dict, retrieved_docs: list[dict]) -> dict:
        prompt = self.build_prompt(case, retrieved_docs)
        raw = self.generate(prompt)
        result = self.parse_dd(raw)
        result["_retrieved_sources"] = [d["source"] for d in retrieved_docs]
        return result
