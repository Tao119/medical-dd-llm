import os
import sys
import json
import argparse
import torch
from pathlib import Path
from datasets import Dataset
from transformers import (
    AutoTokenizer, AutoModelForCausalLM,
    TrainingArguments, Trainer, DataCollatorForSeq2Seq
)
from peft import get_peft_model, LoraConfig, TaskType
from config import BASE_MODEL, SYSTEM_PROMPT


def format_prompt(record: dict) -> str:
    return (
        f"{SYSTEM_PROMPT}\n\n"
        f"### 入力\n{record['instruction']}\n\n"
        f"### 鑑別診断\n{record['output']}"
    )


def tokenize(record: dict, tokenizer, max_length: int = 1024) -> dict:
    text = format_prompt(record)
    enc = tokenizer(
        text, truncation=True, max_length=max_length,
        padding=False, return_tensors=None
    )
    enc["labels"] = enc["input_ids"].copy()
    return enc


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data",        default="data/processed/dd_training.json")
    parser.add_argument("--model",       default=BASE_MODEL)
    parser.add_argument("--output",      default="model/dd_finetuned")
    parser.add_argument("--epochs",      type=int,   default=5)
    parser.add_argument("--batch",       type=int,   default=2)
    parser.add_argument("--lr",          type=float, default=2e-4)
    parser.add_argument("--lora_r",      type=int,   default=8)
    parser.add_argument("--lora_alpha",  type=int,   default=16)
    parser.add_argument("--max_length",  type=int,   default=1024)
    args = parser.parse_args()

    device = ("mps" if torch.backends.mps.is_available()
              else "cuda" if torch.cuda.is_available() else "cpu")
    print(f"device: {device}")

    with open(args.data, encoding="utf-8") as f:
        records = json.load(f)
    print(f"Training samples: {len(records)}")

    tokenizer = AutoTokenizer.from_pretrained(args.model)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    model = AutoModelForCausalLM.from_pretrained(
        args.model,
        torch_dtype=torch.float16 if device != "cpu" else torch.float32,
    )

    lora_cfg = LoraConfig(
        task_type=TaskType.CAUSAL_LM,
        r=args.lora_r,
        lora_alpha=args.lora_alpha,
        lora_dropout=0.05,
        bias="none",
        target_modules=["c_attn"] if "gpt2" in args.model else ["q_proj", "v_proj"],
    )
    model = get_peft_model(model, lora_cfg)
    model.print_trainable_parameters()

    dataset = Dataset.from_list(records)
    tokenized = dataset.map(
        lambda x: tokenize(x, tokenizer, args.max_length),
        remove_columns=dataset.column_names
    )

    train_args = TrainingArguments(
        output_dir=args.output,
        num_train_epochs=args.epochs,
        per_device_train_batch_size=args.batch,
        gradient_accumulation_steps=4,
        learning_rate=args.lr,
        lr_scheduler_type="cosine",
        warmup_ratio=0.1,
        fp16=(device == "cuda"),
        logging_steps=5,
        save_strategy="epoch",
        report_to="none",
    )

    trainer = Trainer(
        model=model,
        args=train_args,
        train_dataset=tokenized,
        data_collator=DataCollatorForSeq2Seq(tokenizer, model, padding=True),
    )

    trainer.train()
    model.save_pretrained(args.output)
    tokenizer.save_pretrained(args.output)
    print(f"\nModel saved: {args.output}")


if __name__ == "__main__":
    main()
