#!/usr/bin/env python3
"""
scripts/download_models.py
Downloads all AI models to the Network Volume (/workspace/models).
Run once after pod setup -- models persist between sessions.

Skips: audiocraft (incompatible with torch 2.4+/2.8+)
Music: handled by local MP3 files in assets/music/
"""

import os
import sys
import shutil
import json
from pathlib import Path

# Cache models to network volume if available
MODELS_DIR = "/workspace/models"
Path(MODELS_DIR).mkdir(parents=True, exist_ok=True)
os.environ["HF_HOME"]              = MODELS_DIR
os.environ["TRANSFORMERS_CACHE"]   = f"{MODELS_DIR}/transformers"
os.environ["DIFFUSERS_CACHE"]      = f"{MODELS_DIR}/diffusers"
os.environ["TORCH_HOME"]           = f"{MODELS_DIR}/torch"

try:
    from rich.console import Console
    from rich.panel import Panel
    console = Console()
    def log(msg):  console.print(f"[green]  OK  {msg}[/]")
    def info(msg): console.print(f"[blue]  >>  {msg}[/]")
    def warn(msg): console.print(f"[yellow]  !!  {msg}[/]")
    def fail(msg): console.print(f"[red]  XX  {msg}[/]"); sys.exit(1)
except ImportError:
    def log(msg):  print(f"  OK: {msg}")
    def info(msg): print(f"  >>: {msg}")
    def warn(msg): print(f"  !!: {msg}")
    def fail(msg): print(f"  XX: {msg}"); sys.exit(1)


def check_disk_space(required_gb: float = 25.0):
    free = shutil.disk_usage(MODELS_DIR).free / (1024 ** 3)
    total = shutil.disk_usage(MODELS_DIR).total / (1024 ** 3)
    info(f"Network Volume: {free:.1f}GB free / {total:.1f}GB total")
    info(f"Required: ~{required_gb}GB")
    if free < required_gb:
        fail(f"Not enough space! Need {required_gb}GB, have {free:.1f}GB")


def download_whisper():
    info("Downloading Whisper large-v3 (~1.5GB)...")
    import whisper
    model = whisper.load_model("large-v3")
    log("Whisper large-v3 ready")
    del model


def download_sdxl():
    info("Downloading SDXL 1.0 Base (~6.9GB) -- grab a coffee...")
    import torch
    from diffusers import StableDiffusionXLPipeline

    dtype = torch.float16 if torch.cuda.is_available() else torch.float32
    pipe = StableDiffusionXLPipeline.from_pretrained(
        "stabilityai/stable-diffusion-xl-base-1.0",
        torch_dtype=dtype,
        use_safetensors=True,
        variant="fp16" if dtype == torch.float16 else None,
        cache_dir=f"{MODELS_DIR}/diffusers",
    )
    log("SDXL 1.0 Base ready")
    del pipe
    if torch.cuda.is_available():
        torch.cuda.empty_cache()


def download_sdxl_refiner():
    info("Downloading SDXL Refiner (~6.1GB)...")
    import torch
    from diffusers import StableDiffusionXLImg2ImgPipeline

    dtype = torch.float16 if torch.cuda.is_available() else torch.float32
    pipe = StableDiffusionXLImg2ImgPipeline.from_pretrained(
        "stabilityai/stable-diffusion-xl-refiner-1.0",
        torch_dtype=dtype,
        use_safetensors=True,
        variant="fp16" if dtype == torch.float16 else None,
        cache_dir=f"{MODELS_DIR}/diffusers",
    )
    log("SDXL Refiner ready")
    del pipe
    if torch.cuda.is_available():
        torch.cuda.empty_cache()


def download_svd():
    info("Downloading SVD-XT (Stable Video Diffusion, ~7GB)...")
    import torch
    from diffusers import StableVideoDiffusionPipeline

    dtype = torch.float16 if torch.cuda.is_available() else torch.float32
    pipe = StableVideoDiffusionPipeline.from_pretrained(
        "stabilityai/stable-video-diffusion-img2vid-xt",
        torch_dtype=dtype,
        variant="fp16" if dtype == torch.float16 else None,
        cache_dir=f"{MODELS_DIR}/diffusers",
    )
    log("SVD-XT ready (image-to-video for horror/relationships themes)")
    del pipe
    if torch.cuda.is_available():
        torch.cuda.empty_cache()


def download_xtts():
    info("Downloading Coqui XTTS v2 (~2.5GB)...")
    os.environ["COQUI_TOS_AGREED"] = "1"
    try:
        from TTS.api import TTS
        tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2")
        log("Coqui XTTS v2 ready")
        del tts
    except ImportError:
        warn("Coqui TTS not installed -- run: pip install TTS==0.22.0")
    except Exception as e:
        warn(f"XTTS download failed: {e}")


def download_animatediff():
    info("Downloading AnimateDiff motion adapter (~1.8GB)...")
    try:
        from diffusers import MotionAdapter
        adapter = MotionAdapter.from_pretrained(
            "guoyww/animatediff-motion-adapter-v1-5-2",
            cache_dir=f"{MODELS_DIR}/diffusers",
        )
        log("AnimateDiff motion adapter ready")
        del adapter
    except Exception as e:
        warn(f"AnimateDiff download failed: {e}")


def check_music():
    info("Checking local music files...")
    music_dir = Path("/workspace/ai-studio-v2/assets/music")
    music_dir.mkdir(parents=True, exist_ok=True)

    files = list(music_dir.glob("*.mp3")) + \
            list(music_dir.glob("*.wav")) + \
            list(music_dir.glob("*.ogg"))

    if files:
        log(f"Music files found: {len(files)} track(s)")
        for f in files:
            print(f"       {f.name}")
    else:
        warn("No music files in assets/music/ -- downloading samples...")
        import subprocess
        tracks = [
            ("ambient_01.mp3",    "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-1.mp3"),
            ("epic_01.mp3",       "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-6.mp3"),
            ("orchestral_01.mp3", "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-9.mp3"),
        ]
        for fname, url in tracks:
            out = music_dir / fname
            subprocess.run(["wget", "-q", url, "-O", str(out)], check=True)
            log(f"Downloaded: {fname}")


def check_voice_refs():
    info("Checking voice reference files...")
    refs_dir = Path("/workspace/ai-studio-v2/assets/voice_refs")
    refs_dir.mkdir(parents=True, exist_ok=True)

    refs = list(refs_dir.glob("*.wav"))
    if refs:
        log(f"Voice refs found: {len(refs)} files")
    else:
        warn("No voice reference WAVs -- creating placeholders...")
        try:
            import numpy as np
            import soundfile as sf
            sr = 22050
            t  = np.linspace(0, 6, sr * 6)
            for name, freq in [
                ("narrator_reference", 180),
                ("aria_reference",     220),
                ("oracle_reference",   170),
                ("marcus_reference",   160),
            ]:
                path = refs_dir / f"{name}.wav"
                wave = 0.15 * np.sin(2 * 3.14159 * freq * t) * np.exp(-t * 0.3)
                sf.write(str(path), wave, sr)
            log("Placeholder voice refs created")
            warn("Replace with real 6-sec recordings for best quality")
        except ImportError:
            warn("soundfile not installed -- skipping voice ref creation")


def main():
    print()
    print("=" * 60)
    print("  AI Studio v2 -- Model Downloader")
    print(f"  Saving to: {MODELS_DIR}")
    print("=" * 60)
    print()

    import torch
    device = "cuda" if torch.cuda.is_available() else "cpu"
    info(f"Device: {device}")
    if device == "cuda":
        info(f"GPU: {torch.cuda.get_device_name(0)}")
        info(f"VRAM: {torch.cuda.get_device_properties(0).total_memory / 1024**3:.1f}GB")

    check_disk_space(25.0)
    print()

    steps = [
        ("Whisper large-v3 (subtitles, ~1.5GB)",        download_whisper),
        ("Coqui XTTS v2 (voice synthesis, ~2.5GB)",     download_xtts),
        ("AnimateDiff (animation adapter, ~1.8GB)",      download_animatediff),
        ("SDXL 1.0 Base (image gen, ~6.9GB)",           download_sdxl),
        ("SDXL Refiner (image quality, ~6.1GB)",        download_sdxl_refiner),
        ("SVD-XT (video animation, ~7.0GB)",            download_svd),
        ("Music files check",                           check_music),
        ("Voice reference files check",                 check_voice_refs),
    ]

    failed = []
    for i, (name, fn) in enumerate(steps, 1):
        print(f"\n[{i}/{len(steps)}] {name}")
        try:
            fn()
        except Exception as e:
            warn(f"Failed: {e}")
            failed.append(name)

    print()
    print("=" * 60)
    if failed:
        warn(f"Some downloads failed: {', '.join(failed)}")
        warn("Run this script again to retry failed downloads")
    else:
        log("All models downloaded successfully!")

    total_used = sum(
        f.stat().st_size for f in Path(MODELS_DIR).rglob("*") if f.is_file()
    ) / (1024 ** 3)
    log(f"Network Volume used: {total_used:.1f}GB")
    print()
    print("  Next step:")
    print("  python pipeline.py --theme mythology --topic 'Medusa was not the monster'")
    print("=" * 60)
    print()


if __name__ == "__main__":
    main()
