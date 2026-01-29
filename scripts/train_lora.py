#!/usr/bin/env python3
"""
LoRA fine-tuning script for job matching model (Phase 2).

Supports two backends:
- mlx-lm: For Apple Silicon (M1/M2/M3) - recommended for Mac users
- unsloth: For NVIDIA GPUs - faster training

Usage:
    # Apple Silicon (mlx-lm)
    python scripts/train_lora.py --backend mlx --data data/

    # NVIDIA GPU (unsloth)  
    python scripts/train_lora.py --backend unsloth --data data/

    # Custom parameters
    python scripts/train_lora.py --backend mlx --epochs 5 --lr 2e-4 --batch-size 4
"""

import argparse
import json
import sys
from pathlib import Path
from datetime import datetime


def check_mlx_available():
    """Check if mlx-lm is available."""
    try:
        import mlx.core
        import mlx_lm
        return True
    except ImportError:
        return False


def check_unsloth_available():
    """Check if unsloth is available."""
    try:
        from unsloth import FastLanguageModel
        return True
    except ImportError:
        return False


def train_with_mlx(args):
    """Train with mlx-lm (Apple Silicon)."""
    try:
        from mlx_lm import lora, generate
        import mlx.core as mx
    except ImportError:
        print("❌ mlx-lm not installed. Run: pip install mlx-lm")
        sys.exit(1)
    
    print("🍎 Training with mlx-lm (Apple Silicon)")
    print(f"   Model: {args.model}")
    print(f"   Data: {args.data}")
    print(f"   Output: {args.output}")
    
    # Load training data
    train_file = Path(args.data) / "train.jsonl"
    eval_file = Path(args.data) / "eval.jsonl"
    
    if not train_file.exists():
        print(f"❌ Training file not found: {train_file}")
        sys.exit(1)
    
    # Count examples
    with open(train_file) as f:
        train_count = sum(1 for _ in f)
    print(f"   Training examples: {train_count}")
    
    # Create output directory
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Training configuration
    # Note: mlx-lm uses a YAML config or command-line args
    config = {
        "model": args.model,
        "train": True,
        "data": str(args.data),
        "lora_layers": args.lora_layers,
        "batch_size": args.batch_size,
        "iters": args.epochs * (train_count // args.batch_size),
        "learning_rate": args.lr,
        "adapter_path": str(output_dir / "adapters"),
    }
    
    # Save config
    config_file = output_dir / "train_config.json"
    with open(config_file, "w") as f:
        json.dump(config, f, indent=2)
    print(f"   Config saved: {config_file}")
    
    # Print mlx-lm command (user runs manually for now)
    print(f"\n{'='*60}")
    print("MLX-LM TRAINING COMMAND")
    print(f"{'='*60}")
    print(f"""
Run the following command to start training:

mlx_lm.lora \\
    --model {args.model} \\
    --train \\
    --data {args.data} \\
    --batch-size {args.batch_size} \\
    --lora-layers {args.lora_layers} \\
    --iters {config['iters']} \\
    --learning-rate {args.lr} \\
    --adapter-path {output_dir / 'adapters'}

After training, fuse the adapter:

mlx_lm.fuse \\
    --model {args.model} \\
    --adapter-path {output_dir / 'adapters'} \\
    --save-path {output_dir / 'fused_model'}

Then convert to GGUF (requires llama.cpp):

python convert_hf_to_gguf.py {output_dir / 'fused_model'} \\
    --outtype q4_K_M \\
    --outfile {output_dir / 'job-matcher.gguf'}
""")
    
    return config


def train_with_unsloth(args):
    """Train with unsloth (NVIDIA GPU)."""
    try:
        from unsloth import FastLanguageModel
        from transformers import TrainingArguments
        from trl import SFTTrainer
        from datasets import load_dataset
    except ImportError:
        print("❌ unsloth not installed. Run: pip install unsloth")
        sys.exit(1)
    
    print("🚀 Training with unsloth (NVIDIA GPU)")
    print(f"   Model: {args.model}")
    print(f"   Data: {args.data}")
    print(f"   Output: {args.output}")
    
    # Map model names
    model_map = {
        "gemma3:12b": "unsloth/gemma-2-9b-it-bnb-4bit",
        "gemma3:27b": "unsloth/gemma-2-27b-it-bnb-4bit",
        "llama3:8b": "unsloth/Meta-Llama-3.1-8B-Instruct-bnb-4bit",
    }
    
    hf_model = model_map.get(args.model, args.model)
    print(f"   HuggingFace model: {hf_model}")
    
    # Load model with LoRA
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=hf_model,
        max_seq_length=4096,
        dtype=None,  # Auto-detect
        load_in_4bit=True,
    )
    
    model = FastLanguageModel.get_peft_model(
        model,
        r=args.lora_r,
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj",
                        "gate_proj", "up_proj", "down_proj"],
        lora_alpha=args.lora_alpha,
        lora_dropout=0.0,
        bias="none",
        use_gradient_checkpointing="unsloth",
    )
    
    # Load dataset
    train_file = Path(args.data) / "train.jsonl"
    eval_file = Path(args.data) / "eval.jsonl"
    
    dataset = load_dataset("json", data_files={
        "train": str(train_file),
        "eval": str(eval_file) if eval_file.exists() else None,
    })
    
    # Format function for Alpaca-style data
    def formatting_func(examples):
        texts = []
        for i in range(len(examples["instruction"])):
            text = f"""### Instruction:
{examples['instruction'][i]}

### Response:
{examples['output'][i]}"""
            texts.append(text)
        return {"text": texts}
    
    dataset = dataset.map(formatting_func, batched=True)
    
    # Training arguments
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    training_args = TrainingArguments(
        output_dir=str(output_dir),
        per_device_train_batch_size=args.batch_size,
        gradient_accumulation_steps=4,
        warmup_steps=10,
        num_train_epochs=args.epochs,
        learning_rate=args.lr,
        fp16=True,
        logging_steps=10,
        save_strategy="epoch",
        evaluation_strategy="epoch" if eval_file.exists() else "no",
    )
    
    trainer = SFTTrainer(
        model=model,
        tokenizer=tokenizer,
        train_dataset=dataset["train"],
        eval_dataset=dataset.get("eval"),
        dataset_text_field="text",
        max_seq_length=4096,
        args=training_args,
    )
    
    print(f"\n🏋️ Starting training...")
    trainer.train()
    
    # Save model
    print(f"\n💾 Saving model to {output_dir}")
    model.save_pretrained(output_dir / "lora_adapter")
    tokenizer.save_pretrained(output_dir / "lora_adapter")
    
    # Export to GGUF
    print(f"\n📦 Exporting to GGUF...")
    model.save_pretrained_gguf(
        str(output_dir / "job-matcher"),
        tokenizer,
        quantization_method="q4_k_m"
    )
    
    print(f"\n✅ Training complete!")
    print(f"   Adapter: {output_dir / 'lora_adapter'}")
    print(f"   GGUF: {output_dir / 'job-matcher-unsloth.Q4_K_M.gguf'}")
    
    return {"output_dir": str(output_dir)}


def main():
    parser = argparse.ArgumentParser(description="LoRA fine-tuning for job matching")
    parser.add_argument("--backend", choices=["mlx", "unsloth", "auto"], default="auto",
                        help="Training backend (default: auto-detect)")
    parser.add_argument("--model", type=str, default="gemma3:12b",
                        help="Base model (default: gemma3:12b)")
    parser.add_argument("--data", type=str, default="data/",
                        help="Training data directory (default: data/)")
    parser.add_argument("--output", type=str, default="models/job-matcher-lora",
                        help="Output directory (default: models/job-matcher-lora)")
    parser.add_argument("--epochs", type=int, default=3,
                        help="Number of epochs (default: 3)")
    parser.add_argument("--batch-size", type=int, default=4,
                        help="Batch size (default: 4)")
    parser.add_argument("--lr", type=float, default=2e-4,
                        help="Learning rate (default: 2e-4)")
    parser.add_argument("--lora-r", type=int, default=16,
                        help="LoRA rank (default: 16)")
    parser.add_argument("--lora-alpha", type=int, default=32,
                        help="LoRA alpha (default: 32)")
    parser.add_argument("--lora-layers", type=int, default=16,
                        help="Number of LoRA layers for mlx-lm (default: 16)")
    args = parser.parse_args()

    # Validate data directory
    data_dir = Path(args.data)
    train_file = data_dir / "train.jsonl"
    
    if not train_file.exists():
        print(f"❌ Training data not found: {train_file}")
        print(f"   Run these steps first:")
        print(f"   1. python scripts/export_for_labeling.py")
        print(f"   2. Label the CSV file")
        print(f"   3. python scripts/import_labels.py")
        sys.exit(1)
    
    # Count training examples
    with open(train_file) as f:
        train_count = sum(1 for _ in f)
    
    if train_count < 10:
        print(f"⚠️  Only {train_count} training examples. Recommend at least 50-100 for good results.")
    
    # Auto-detect backend
    if args.backend == "auto":
        if check_mlx_available():
            args.backend = "mlx"
            print("🔍 Auto-detected: mlx-lm (Apple Silicon)")
        elif check_unsloth_available():
            args.backend = "unsloth"
            print("🔍 Auto-detected: unsloth (NVIDIA GPU)")
        else:
            print("❌ No training backend available.")
            print("   Install one of:")
            print("   - pip install mlx-lm  # Apple Silicon")
            print("   - pip install unsloth  # NVIDIA GPU")
            sys.exit(1)
    
    print(f"\n{'='*60}")
    print("TRAINING CONFIGURATION")
    print(f"{'='*60}")
    print(f"Backend: {args.backend}")
    print(f"Model: {args.model}")
    print(f"Data: {args.data}")
    print(f"Output: {args.output}")
    print(f"Epochs: {args.epochs}")
    print(f"Batch size: {args.batch_size}")
    print(f"Learning rate: {args.lr}")
    print(f"LoRA rank (r): {args.lora_r}")
    print(f"LoRA alpha: {args.lora_alpha}")
    print(f"Training examples: {train_count}")
    print(f"{'='*60}\n")
    
    # Run training
    if args.backend == "mlx":
        result = train_with_mlx(args)
    else:
        result = train_with_unsloth(args)
    
    # Save training metadata
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    metadata = {
        "backend": args.backend,
        "model": args.model,
        "epochs": args.epochs,
        "batch_size": args.batch_size,
        "learning_rate": args.lr,
        "lora_r": args.lora_r,
        "lora_alpha": args.lora_alpha,
        "training_examples": train_count,
        "created": datetime.now().isoformat(),
    }
    
    with open(output_dir / "training_metadata.json", "w") as f:
        json.dump(metadata, f, indent=2)
    
    print(f"\n📝 Next steps:")
    print(f"   1. Wait for training to complete")
    print(f"   2. Create Modelfile: see Modelfile.job-matcher")
    print(f"   3. Register with Ollama: ollama create job-matcher -f Modelfile.job-matcher")


if __name__ == "__main__":
    main()
