#!/bin/bash
# Convert MLX LoRA adapter to GGUF for Ollama
#
# This script fuses the LoRA adapter with the base model and converts to GGUF format.
#
# Prerequisites:
#   pip install mlx-lm
#   brew install llama.cpp  (or build from source)
#
# Usage:
#   ./scripts/convert_to_gguf.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

BASE_MODEL="mlx-community/gemma-2-9b-it-4bit"
ADAPTER_PATH="models/job-matcher-lora/adapters"
FUSED_OUTPUT="models/job-matcher-fused"
GGUF_OUTPUT="models/job-matcher.gguf"

echo "=============================================="
echo "Step 1: Fuse LoRA adapter with base model"
echo "=============================================="
echo ""
echo "This merges the adapter weights into the base model."
echo ""

# Check if adapter exists
if [ ! -d "$ADAPTER_PATH" ]; then
    echo "❌ Adapter not found at: $ADAPTER_PATH"
    exit 1
fi

echo "Running: mlx_lm.fuse --model $BASE_MODEL --adapter-path $ADAPTER_PATH --save-path $FUSED_OUTPUT"
echo ""

mlx_lm.fuse \
    --model "$BASE_MODEL" \
    --adapter-path "$ADAPTER_PATH" \
    --save-path "$FUSED_OUTPUT"

echo ""
echo "✅ Fused model saved to: $FUSED_OUTPUT"
echo ""

echo "=============================================="
echo "Step 2: Convert to GGUF format"
echo "=============================================="
echo ""
echo "Note: This step requires llama.cpp's convert script."
echo ""

# Check for llama.cpp convert script
CONVERT_SCRIPT=""
if command -v convert-hf-to-gguf.py &> /dev/null; then
    CONVERT_SCRIPT="convert-hf-to-gguf.py"
elif [ -f "$HOME/llama.cpp/convert-hf-to-gguf.py" ]; then
    CONVERT_SCRIPT="python $HOME/llama.cpp/convert-hf-to-gguf.py"
elif [ -f "/opt/homebrew/share/llama.cpp/convert-hf-to-gguf.py" ]; then
    CONVERT_SCRIPT="python /opt/homebrew/share/llama.cpp/convert-hf-to-gguf.py"
fi

if [ -z "$CONVERT_SCRIPT" ]; then
    echo "⚠️  llama.cpp convert script not found automatically."
    echo ""
    echo "To convert to GGUF, you need to:"
    echo ""
    echo "Option A: Install llama.cpp via Homebrew"
    echo "  brew install llama.cpp"
    echo ""
    echo "Option B: Clone and use llama.cpp manually"
    echo "  git clone https://github.com/ggerganov/llama.cpp"
    echo "  pip install -r llama.cpp/requirements.txt"
    echo "  python llama.cpp/convert-hf-to-gguf.py $FUSED_OUTPUT --outfile $GGUF_OUTPUT --outtype q8_0"
    echo ""
    echo "The fused model is ready at: $FUSED_OUTPUT"
    exit 0
fi

echo "Running: $CONVERT_SCRIPT $FUSED_OUTPUT --outfile $GGUF_OUTPUT --outtype q8_0"
echo ""

$CONVERT_SCRIPT "$FUSED_OUTPUT" --outfile "$GGUF_OUTPUT" --outtype q8_0

echo ""
echo "✅ GGUF model saved to: $GGUF_OUTPUT"
echo ""

echo "=============================================="
echo "Step 3: Create Ollama model"
echo "=============================================="
echo ""
echo "Run the following command to create the Ollama model:"
echo ""
echo "  ollama create job-matcher -f Modelfile.job-matcher"
echo ""
echo "Then update Modelfile.job-matcher to point to: $GGUF_OUTPUT"
echo ""
