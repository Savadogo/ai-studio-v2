#!/bin/bash
# =============================================================================
# AI Studio v2 - RunPod Bootstrap Script
# Run once after pod spin-up:
#   curl -fsSL https://YOUR_REPO/setup_runpod.sh | bash
# Or manually:
#   bash scripts/setup_runpod.sh
# =============================================================================

set -e

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'
log()  { echo -e "${GREEN}[OK]${NC} $1"; }
info() { echo -e "${CYAN}[>>]${NC} $1"; }
warn() { echo -e "${YELLOW}[!!]${NC} $1"; }

echo ""
echo "=============================================="
echo "  AI Studio v2 - RunPod Bootstrap"
echo "  GPU: $(nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null || echo 'detecting...')"
echo "=============================================="
echo ""

# -- 1. System packages -------------------------------------------------------
info "Installing system packages..."
apt-get update -qq
apt-get install -y -qq \
    ffmpeg git curl wget unzip \
    libsndfile1 libportaudio2 espeak-ng \
    build-essential cmake pkg-config \
    python3-dev
log "System packages ready"

# -- 2. Python packages -------------------------------------------------------
info "Upgrading pip + setuptools (force-reinstall fixes pkg_resources)..."
pip install --upgrade pip -q
pip install "setuptools>=69.0" --force-reinstall -q
pip install wheel --upgrade -q
log "pip + setuptools upgraded"

info "Installing PyTorch (already in RunPod template, verifying CUDA)..."
python -c "import torch; print(f'  PyTorch {torch.__version__} | CUDA: {torch.cuda.is_available()} | GPU: {torch.cuda.get_device_name(0) if torch.cuda.is_available() else None}')"

info "Installing openai-whisper (needs --no-build-isolation)..."
pip install openai-whisper --no-build-isolation -q
log "whisper installed"

info "Installing av binary (no compilation)..."
pip install "av>=12.0,<13" --only-binary=:all: -q || \
    warn "av binary not found -- audiocraft will use local music fallback"

info "Installing core studio packages..."
pip install \
    diffusers==0.29.2 transformers>=4.40.0 accelerate>=0.30.0 \
    safetensors>=0.4.3 Pillow>=10.0.0 \
    soundfile librosa scipy tqdm rich python-dotenv \
    ollama pytrends requests \
    fastapi uvicorn pydantic jinja2 aiofiles \
    google-api-python-client google-auth-oauthlib \
    runpod typer -q
log "Core packages installed"

info "Installing Coqui TTS v2 (voice synthesis)..."
pip install TTS==0.22.0 -q && log "Coqui TTS installed" || \
    warn "Coqui TTS failed -- check Python version (needs 3.11)"

info "Downloading local music fallback tracks..."
mkdir -p /workspace/ai-studio-v2/assets/music
[ ! -f /workspace/ai-studio-v2/assets/music/ambient_01.mp3 ] && \
    wget -q "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-1.mp3" \
         -O /workspace/ai-studio-v2/assets/music/ambient_01.mp3 && log "ambient track downloaded"
[ ! -f /workspace/ai-studio-v2/assets/music/epic_01.mp3 ] && \
    wget -q "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-6.mp3" \
         -O /workspace/ai-studio-v2/assets/music/epic_01.mp3 && log "epic track downloaded"
[ ! -f /workspace/ai-studio-v2/assets/music/orchestral_01.mp3 ] && \
    wget -q "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-9.mp3" \
         -O /workspace/ai-studio-v2/assets/music/orchestral_01.mp3 && log "orchestral track downloaded"
log "Python packages and music assets ready"

# -- 3. Ollama ----------------------------------------------------------------
info "Installing Ollama..."
if ! command -v ollama &>/dev/null; then
    curl -fsSL https://ollama.ai/install.sh | sh
    log "Ollama installed"
else
    log "Ollama already installed"
fi

# Start Ollama in background
ollama serve &>/dev/null &
sleep 4

info "Pulling Llama 3.1 8B..."
ollama pull llama3.1:8b
log "Llama 3.1 8B ready"

# -- 4. Download models to Network Volume (/workspace/models) -----------------
info "Downloading AI models to Network Volume..."
info "(Models persist between pod restarts - only downloads once)"
python /workspace/ai-studio-v2/scripts/download_models.py
log "All models ready"

# -- 5. Create .env from template ---------------------------------------------
if [ ! -f "/workspace/ai-studio-v2/.env" ]; then
    cp /workspace/ai-studio-v2/.env.example /workspace/ai-studio-v2/.env
    warn "Edit .env with your API keys: nano /workspace/ai-studio-v2/.env"
fi

# -- 6. Verify GPU access from Python ----------------------------------------
info "Verifying GPU access..."
python -c "
import torch
print(f'  CUDA available: {torch.cuda.is_available()}')
print(f'  GPU: {torch.cuda.get_device_name(0)}')
print(f'  VRAM: {torch.cuda.get_device_properties(0).total_memory / 1024**3:.1f} GB')
"

# -- 7. Quick smoke test ------------------------------------------------------
info "Running quick smoke test (SDXL prompt test)..."
python -c "
import torch
from diffusers import StableDiffusionXLPipeline
pipe = StableDiffusionXLPipeline.from_pretrained(
    'stabilityai/stable-diffusion-xl-base-1.0',
    torch_dtype=torch.float16,
    use_safetensors=True,
    variant='fp16',
).to('cuda')
print('  SDXL loaded on GPU successfully')
del pipe
torch.cuda.empty_cache()
"
log "GPU smoke test passed"

# -- Done ---------------------------------------------------------------------
echo ""
echo "=============================================="
echo "  Bootstrap complete! Ready to generate."
echo "=============================================="
echo ""
echo "  Generate your first video:"
echo "  cd /workspace/ai-studio-v2"
echo "  python pipeline.py --theme relationships --topic 'How to stop overthinking'"
echo ""
echo "  Available themes:"
echo "  kids | relationships | motivation | mindfulness | horror | finance | fitness | history"
echo ""
