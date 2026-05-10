#!/usr/bin/env python3
"""
scripts/character_creator.py
Interactive tool to create new characters and add them to characters.json.

Two modes:
  1. Interactive wizard:   python scripts/character_creator.py --interactive
  2. Generate reference:  python scripts/character_creator.py --generate-ref --name aria
  3. Generate all refs:   python scripts/character_creator.py --generate-all-refs
  4. List characters:     python scripts/character_creator.py --list

Creates:
  - Character entry in characters.json
  - Reference image via SDXL (for IP-Adapter consistency)
  - Placeholder voice WAV
"""

import json
import sys
import argparse
import re
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Prompt, Confirm

console = Console()

CHARACTERS_FILE = "characters.json"
THEMES = ["relationships","motivation","mindfulness","horror","finance","fitness","history","kids"]


def load_characters() -> dict:
    with open(CHARACTERS_FILE, encoding="utf-8") as f:
        return json.load(f)


def save_characters(data: dict):
    with open(CHARACTERS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    console.print(f"[green]Saved to {CHARACTERS_FILE}[/]")


# ---------------------------------------------------------------------------
# LIST
# ---------------------------------------------------------------------------

def list_characters():
    data  = load_characters()
    chars = data["characters"]
    table = Table(title=f"Characters ({len(chars)} total)")
    table.add_column("Key",        style="cyan",   width=14)
    table.add_column("Name",       style="white",  width=18)
    table.add_column("Type",       style="yellow", width=10)
    table.add_column("Gender",     style="green",  width=8)
    table.add_column("Best Themes",style="dim",    width=40)
    table.add_column("Ref Image",  style="dim",    width=8)

    for key, c in chars.items():
        ref_exists = "YES" if Path(c.get("reference_image","")).exists() else "no"
        table.add_row(
            key,
            c["display_name"],
            c.get("type","human"),
            c.get("gender","-"),
            ", ".join(c.get("best_themes", [])),
            ref_exists
        )
    console.print(table)


# ---------------------------------------------------------------------------
# INTERACTIVE WIZARD
# ---------------------------------------------------------------------------

def create_character_interactive():
    console.print(Panel(
        "[bold]Character Creator[/]\n"
        "Adds a new character to characters.json.\n"
        "Answer each question -- press Enter for defaults.",
        title="New Character"
    ))

    # Basic info
    key         = Prompt.ask("[cyan]Character key (lowercase, no spaces, e.g. 'maya')")
    key         = re.sub(r"[^a-z0-9_]", "_", key.lower())
    name        = Prompt.ask("[cyan]Display name", default=key.title())
    char_type   = Prompt.ask("[cyan]Type", choices=["human","cartoon"], default="human")
    gender      = Prompt.ask("[cyan]Gender", choices=["female","male","nonbinary"], default="female")

    if char_type == "human":
        age_range   = Prompt.ask("[cyan]Age range", default="25-32")
        ethnicity   = Prompt.ask("[cyan]Ethnicity / appearance (e.g. 'East Asian', 'Black woman', 'Latina')")
        description = Prompt.ask("[cyan]Short physical description (hair, eyes, notable features)")
    else:
        age_range   = "N/A"
        ethnicity   = "cartoon"
        description = Prompt.ask("[cyan]Cartoon character description (shape, colors, features)")

    personality  = Prompt.ask("[cyan]Personality / energy (2-3 words or short phrase)")
    voice_desc   = Prompt.ask("[cyan]Voice description (e.g. 'warm deep male voice, 35 years old')")

    # Themes
    console.print(f"\nAvailable themes: {', '.join(THEMES)}")
    themes_input = Prompt.ask("[cyan]Best themes (comma-separated)", default="relationships,motivation")
    best_themes  = [t.strip() for t in themes_input.split(",") if t.strip() in THEMES]

    # Visual
    sd_prompt    = Prompt.ask(
        "[cyan]SDXL prompt (describe the character for image generation)",
        default=f"{description}, {gender}, {ethnicity if char_type=='human' else 'cartoon character'}"
    )
    neg_prompt   = Prompt.ask(
        "[cyan]Negative prompt",
        default="ugly, deformed, blurry, watermark, text, explicit"
    )

    # TTS speed per selected theme
    tts_speeds = {}
    console.print("\n[dim]Set narration speed per theme (0.75=slow/calm, 1.0=normal, 1.1=fast/energetic)[/]")
    for t in best_themes:
        default_speed = {
            "mindfulness": "0.78", "horror": "0.87", "kids": "0.87",
            "fitness": "1.05", "motivation": "1.03",
        }.get(t, "0.95")
        speed = Prompt.ask(f"  Speed for [yellow]{t}[/]", default=default_speed)
        tts_speeds[t] = float(speed)

    # Generate theme adaptations automatically
    theme_adaptations = {}
    trigger = f"{key}_character" if char_type == "human" else f"{key}_{key}"
    for t in best_themes:
        theme_adaptations[t] = f"{trigger}, {_theme_style_hint(t, gender, char_type)}"

    # Build character dict
    import random
    character = {
        "display_name":    name,
        "type":            char_type,
        "gender":          gender,
        "age_range":       age_range,
        "ethnicity":       ethnicity,
        "description":     description,
        "personality":     personality,
        "best_themes":     best_themes,
        "reference_image": f"assets/characters/{key}_reference.png",
        "seed":            random.randint(100, 9999),
        "lora_path":       f"models/lora/{key}_v1.safetensors",
        "trigger_word":    trigger,
        "ip_adapter_weight": 0.72 if char_type == "human" else 0.88,
        "sd_prompt":       sd_prompt,
        "negative_prompt": neg_prompt,
        "theme_adaptations": theme_adaptations,
        "voice_ref":       f"assets/voice_refs/{key}_reference.wav",
        "voice_description": voice_desc,
        "tts_speed_by_theme": tts_speeds
    }

    # Preview
    console.print()
    console.print(Panel(
        json.dumps(character, indent=2, ensure_ascii=False)[:1200],
        title=f"New character: {key}"
    ))

    if Confirm.ask("Add this character to characters.json?"):
        data = load_characters()
        data["characters"][key] = character
        save_characters(data)
        console.print(f"[bold green]Character '{key}' added![/]")

        # Offer to generate reference image
        if Confirm.ask(f"Generate reference image for {name} now? (requires SDXL on GPU)"):
            generate_reference_image(key)

        # Create placeholder voice WAV
        _make_placeholder_voice(key, gender)
        console.print(f"[yellow]Placeholder voice created: assets/voice_refs/{key}_reference.wav[/]")
        console.print(f"[dim]Replace it with a real 6-second recording for best quality.[/]")

    else:
        console.print("[yellow]Character not saved.[/]")


# ---------------------------------------------------------------------------
# REFERENCE IMAGE GENERATION
# ---------------------------------------------------------------------------

def generate_reference_image(char_key: str):
    """Generate a reference image for IP-Adapter using SDXL."""
    data = load_characters()
    chars = data["characters"]

    if char_key not in chars:
        console.print(f"[red]Character '{char_key}' not found[/]")
        return

    char = chars[char_key]
    out_path = Path(char["reference_image"])
    out_path.parent.mkdir(parents=True, exist_ok=True)

    console.print(f"[blue]Generating reference image for {char['display_name']}...[/]")

    import torch
    from diffusers import StableDiffusionXLPipeline

    device = "cuda" if torch.cuda.is_available() else "cpu"
    dtype  = torch.float16 if device == "cuda" else torch.float32

    console.print(f"[dim]Loading SDXL on {device}...[/]")
    pipe = StableDiffusionXLPipeline.from_pretrained(
        "stabilityai/stable-diffusion-xl-base-1.0",
        torch_dtype=dtype, use_safetensors=True,
        variant="fp16" if dtype == torch.float16 else None,
    ).to(device)

    # Reference images should be:
    # - Front-facing, clear face
    # - Neutral expression (IP-Adapter works better with neutral)
    # - Good lighting
    ref_prompt = (
        f"{char['sd_prompt']}, "
        f"portrait, front facing, looking at camera, neutral expression, "
        f"clear face, good lighting, high quality"
    )
    neg_prompt = char["negative_prompt"] + ", side view, back view, dark, obscured face"

    seed = char.get("seed", 42)
    gen  = torch.Generator(device).manual_seed(seed)

    image = pipe(
        prompt=ref_prompt,
        negative_prompt=neg_prompt,
        width=1024, height=1024,
        num_inference_steps=35,
        guidance_scale=7.5,
        generator=gen,
    ).images[0]

    image.save(str(out_path), quality=97)
    console.print(f"[bold green]Reference image saved: {out_path}[/]")
    console.print("[dim]This image will be used by IP-Adapter for character consistency.[/]")

    del pipe
    if device == "cuda":
        torch.cuda.empty_cache()


def generate_all_references():
    """Generate reference images for all characters missing one."""
    data  = load_characters()
    chars = data["characters"]
    missing = [k for k, v in chars.items() if not Path(v.get("reference_image","")).exists()]

    if not missing:
        console.print("[green]All characters already have reference images.[/]")
        return

    console.print(f"[yellow]Generating references for: {', '.join(missing)}[/]")
    for key in missing:
        generate_reference_image(key)
        console.print()


# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------

def _theme_style_hint(theme: str, gender: str, char_type: str) -> str:
    hints = {
        "relationships":  "casual stylish, warm relatable expression",
        "motivation":     "confident powerful pose, determined energy",
        "mindfulness":    "serene peaceful expression, soft calm",
        "horror":         "frightened tense expression, dark atmospheric",
        "finance":        "professional sharp style, confident",
        "fitness":        "athletic wear, energetic strong",
        "history":        "period-appropriate attire, dignified",
        "kids":           "warm friendly smile, bright colors",
    }
    return hints.get(theme, "natural expression, good lighting")


def _make_placeholder_voice(char_key: str, gender: str):
    """Create a placeholder voice WAV file."""
    import numpy as np
    try:
        import soundfile as sf
    except ImportError:
        console.print("[yellow]soundfile not installed -- skipping voice placeholder[/]")
        return

    Path("assets/voice_refs").mkdir(parents=True, exist_ok=True)
    out = f"assets/voice_refs/{char_key}_reference.wav"
    if Path(out).exists():
        return

    sr   = 22050
    t    = __import__("numpy").linspace(0, 6, sr * 6)
    freq = 180 if gender == "male" else 220
    wave = 0.15 * np.sin(2 * 3.14159 * freq * t) * np.exp(-t * 0.3)
    sf.write(out, wave, sr)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AI Studio Character Manager")
    parser.add_argument("--list",             action="store_true", help="List all characters")
    parser.add_argument("--interactive",      action="store_true", help="Create new character interactively")
    parser.add_argument("--generate-ref",     metavar="NAME",       help="Generate reference image for character")
    parser.add_argument("--generate-all-refs",action="store_true", help="Generate refs for all missing characters")
    args = parser.parse_args()

    if args.list:
        list_characters()
    elif args.interactive:
        create_character_interactive()
    elif args.generate_ref:
        generate_reference_image(args.generate_ref)
    elif args.generate_all_refs:
        generate_all_references()
    else:
        parser.print_help()
        console.print("\n[dim]Quick start:[/]")
        console.print("  python scripts/character_creator.py --list")
        console.print("  python scripts/character_creator.py --interactive")
        console.print("  python scripts/character_creator.py --generate-ref aria")
        console.print("  python scripts/character_creator.py --generate-all-refs")
