
 AI Content Studio v2 - RunPod Edition
 GPU-accelerated, multi-theme, high-quality video generation
 Themes: Kids, Relationships, Motivation, Mindfulness, Horror Stories, Finance, Fitness

==============================================================
  HARDWARE REQUIREMENTS
==============================================================

  Minimum:  RTX 3080 10GB  ($0.34/hr on RunPod)
  Good:     RTX 3090 24GB  ($0.44/hr on RunPod)
  Best:     RTX 4090 24GB  ($0.74/hr on RunPod)
  Overkill: A100  40GB     ($1.10/hr on RunPod)

  Recommended: RTX 3090 -- best VRAM/price ratio
  VRAM needed: 16GB minimum for SDXL + AnimateDiff together

==============================================================
  V2 UPGRADES OVER V1
==============================================================

  Images:    SD 1.5 (768px)  -->  SDXL 1.0 (1024px) + Refiner
  Animation: Ken Burns only  -->  AnimateDiff (real motion)
  Voice:     XTTS v2 (CPU)   -->  XTTS v2 (GPU, 10x faster)
  Music:     Local MP3 files -->  MusicGen-Medium (GPU, richer)
  Themes:    Kids only        -->  8 themes, all configurable
  Quality:   Draft            -->  Production ready
  Speed:     80 min (CPU)     -->  18 min (RTX 3090)

==============================================================
  QUICK START - RUNPOD (20 MINUTES TO FIRST VIDEO)
==============================================================

Step 1: Create RunPod account
  https://runpod.io

Step 2: Add credit ($10 minimum - lasts ~22 videos on RTX 3090)

Step 3: Create Network Volume (persistent storage for models)
  RunPod Dashboard -> Storage -> New Network Volume
  Name: ai-studio-models
  Size: 60 GB
  Region: EU-RO-1 or US-TX-3 (cheapest)

Step 4: Deploy Pod
  Pods -> Deploy -> Community Cloud
  GPU: RTX 3090 (or 3080 if unavailable)
  Template: runpod/pytorch:2.2.0-py3.11-cuda12.1.1-devel-ubuntu22.04
  Volume: attach ai-studio-models at /workspace/models
  Disk: 30 GB container disk
  Ports: 8888/http (Jupyter), 7860/http (optional Gradio)

Step 5: Connect -> Open Terminal -> run:
  curl -fsSL https://raw.githubusercontent.com/YOU/ai-studio-v2/main/scripts/setup_runpod.sh | bash

Step 6: Generate your first video:
  cd /workspace/ai-studio-v2
  python pipeline.py --theme relationships --topic "How to stop overthinking"

==============================================================
  PROJECT STRUCTURE
==============================================================

  ai-studio-v2/
  |-- README.md
  |-- pipeline.py              Master orchestrator
  |-- config.json              Global settings
  |-- requirements_gpu.txt     GPU Python packages
  |-- Dockerfile               RunPod custom template
  |-- themes/
  |   |-- kids.json            Kids / bedtime stories
  |   |-- relationships.json   Love, dating, self-worth
  |   |-- motivation.json      Success, mindset, hustle
  |   |-- mindfulness.json     Meditation, calm, sleep
  |   |-- horror.json          Scary bedtime stories (teens)
  |   |-- finance.json         Money tips, investing basics
  |   |-- fitness.json         Workout motivation, health
  |   |-- history.json         Historical facts, stories
  |-- src/
  |   |-- trend_scanner.py     Google Trends + YouTube API
  |   |-- script_generator.py  Ollama LLM scripting
  |   |-- voice_generator.py   XTTS v2 GPU voice cloning
  |   |-- music_generator.py   MusicGen-Medium GPU music
  |   |-- image_generator.py   SDXL 1.0 + Refiner
  |   |-- animator.py          AnimateDiff motion
  |   |-- lipsync.py           Wav2Lip / LatentSync
  |   |-- subtitle_generator.py Whisper Large-v3
  |   |-- assembler.py         FFmpeg final assembly
  |   |-- hook_generator.py    Hook options for human
  |   |-- uploader.py          YouTube + TikTok publish
  |   |-- pod_manager.py       RunPod auto start/stop
  |-- scripts/
  |   |-- setup_runpod.sh      One-shot RunPod bootstrap
  |   |-- download_models.py   Model downloader
  |   |-- train_lora.py        Character LoRA trainer
  |   |-- cost_tracker.py      Track RunPod spend
  |-- assets/
      |-- voice_refs/          6-sec reference WAV files
      |-- music/               Royalty-free background tracks
      |-- intro/               Studio intro clips per theme
      |-- outro/               Studio outro clips per theme

==============================================================
  ESTIMATED COSTS (RTX 3090 at $0.44/hr)
==============================================================

  Per video breakdown:
    SDXL + Refiner (8 scenes):   6 min  = $0.044
    AnimateDiff (8 clips):        8 min  = $0.059
    XTTS v2 voice (8 scenes):    3 min  = $0.022
    MusicGen-Medium (60s):        4 min  = $0.029
    Wav2Lip (optional):           3 min  = $0.022
    FFmpeg assembly:              2 min  = $0.015
    Total per video:             ~26 min = $0.19

  Monthly (3 videos/day, 22 days):
    GPU time:  ~$12.50
    Storage:   ~$2.00 (Network Volume)
    Total:     ~$14.50/month

  $10 starter credit = ~52 videos to test
