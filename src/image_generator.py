"""
src/image_generator.py  - v2.1
SDXL 1.0 + IP-Adapter for character consistency across all themes.
IP-Adapter: reference image of your character injected into every scene.
No LoRA training needed -- just provide reference photos.
"""

import json, time, logging
from pathlib import Path
import torch
from PIL import Image
from diffusers import StableDiffusionXLPipeline, StableDiffusionXLImg2ImgPipeline
from rich.console import Console

console = Console()
logger  = logging.getLogger(__name__)


class ImageGeneratorV2:

    def __init__(self, config: dict, theme: dict, characters: dict):
        self.config     = config
        self.theme      = theme
        self.characters = characters.get("characters", {})
        self.theme_id   = theme["theme_id"]
        self.device     = config["hardware"]["device"]
        self.dtype      = torch.float16 if self.device == "cuda" else torch.float32
        img             = config["models"]["image"]
        self.width      = img["width"]
        self.height     = img["height"]
        self.steps      = img["steps"]
        self.cfg        = img["cfg_scale"]
        self.use_refiner= img["use_refiner"]
        self.refiner_at = img["refiner_switch_at"]
        self.base       = None
        self.refiner    = None
        self.ip_loaded  = False

    def _load(self):
        if self.base: return
        console.print("[blue]Loading SDXL 1.0...[/]")
        # Use theme-specific checkpoint if defined (e.g. Juggernaut XL for mythology)
        checkpoint = (
            self.theme.get("sdxl_checkpoint") or
            self.config["models"]["image"]["base_model"]
        )
        console.print(f"[dim]Checkpoint: {checkpoint}[/]")
        self.base = StableDiffusionXLPipeline.from_pretrained(
            checkpoint,
            torch_dtype=self.dtype, use_safetensors=True,
            variant="fp16" if self.dtype == torch.float16 else None,
        ).to(self.device)
        if self.config["hardware"].get("enable_xformers"):
            try: self.base.enable_xformers_memory_efficient_attention()
            except Exception: pass
        if self.config["hardware"].get("enable_vae_slicing"):
            self.base.enable_vae_slicing()
        if self.use_refiner:
            self.refiner = StableDiffusionXLImg2ImgPipeline.from_pretrained(
                self.config["models"]["image"]["refiner_model"],
                torch_dtype=self.dtype, use_safetensors=True,
                variant="fp16" if self.dtype == torch.float16 else None,
            ).to(self.device)
        console.print("[green]SDXL ready[/]")

    def _load_ip(self):
        if self.ip_loaded: return
        try:
            self.base.load_ip_adapter(
                "h94/IP-Adapter", subfolder="sdxl_models",
                weight_name="ip-adapter_sdxl.bin",
            )
            self.ip_loaded = True
            console.print("[green]IP-Adapter loaded -- character consistency enabled[/]")
        except Exception as e:
            console.print(f"[yellow]IP-Adapter unavailable ({e}) -- prompt-only mode[/]")

    def _char_ref_image(self, char_key: str):
        char = self.characters.get(char_key, {})
        ref  = char.get("reference_image")
        if ref and Path(ref).exists():
            return Image.open(ref).convert("RGB")
        return None

    def generate_scene(self, background_key, character=None, action="",
                       output_path=None, seed=None, scene_id=1):
        self._load()
        style   = self.theme["visual_style"]
        bgs     = self.theme["backgrounds"]
        bg_keys = list(bgs.keys())
        bg      = bgs.get(background_key, bgs[bg_keys[scene_id % len(bg_keys)]])

        char_frag    = ""
        ip_ref       = None
        ip_weight    = 0.0
        if character and character in self.characters:
            cdata      = self.characters[character]
            adaptation = cdata.get("theme_adaptations", {}).get(self.theme_id,
                         cdata.get("sd_prompt", ""))
            char_frag  = adaptation + ", "
            ref        = self._char_ref_image(character)
            if ref:
                self._load_ip()
                if self.ip_loaded:
                    ip_ref    = ref
                    ip_weight = cdata.get("ip_adapter_weight", 0.7)

        positive = f"{char_frag}{action}, {bg}, {style['art_style']}, {style['quality_tags']}"
        negative = style["negative_prompt"]

        if seed is None:
            base_seed = self.characters.get(character, {}).get("seed", 42) if character else 42
            seed = base_seed + scene_id
        gen = torch.Generator(device=self.device).manual_seed(seed)

        ip_tag = " [IP-Adapter]" if ip_ref else ""
        console.print(f"[blue]  Scene {scene_id}: {background_key}{' + ' + character if character else ''}{ip_tag}[/]")
        t = time.time()

        if ip_ref and self.ip_loaded:
            self.base.set_ip_adapter_scale(ip_weight)
            out = self.base(
                prompt=positive, negative_prompt=negative,
                ip_adapter_image=ip_ref,
                width=self.width, height=self.height,
                num_inference_steps=self.steps,
                denoising_end=self.refiner_at if self.use_refiner else 1.0,
                guidance_scale=self.cfg, generator=gen,
                output_type="latent" if self.use_refiner else "pil",
            )
        else:
            out = self.base(
                prompt=positive, negative_prompt=negative,
                width=self.width, height=self.height,
                num_inference_steps=self.steps,
                denoising_end=self.refiner_at if self.use_refiner else 1.0,
                guidance_scale=self.cfg, generator=gen,
                output_type="latent" if self.use_refiner else "pil",
            )

        if self.use_refiner and self.refiner:
            image = self.refiner(
                prompt=positive, negative_prompt=negative,
                image=out.images,
                num_inference_steps=int(self.steps * (1 - self.refiner_at)),
                denoising_start=self.refiner_at,
                guidance_scale=self.cfg, generator=gen,
            ).images[0]
        else:
            image = out.images[0]

        if output_path is None:
            output_path = f"output/images/scene_{scene_id:02d}.png"
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        image.save(output_path, quality=95)
        console.print(f"[green]  Scene {scene_id} done ({time.time()-t:.0f}s)[/]")
        return output_path

    def generate_all_scenes(self, scenes, session_dir):
        console.print(f"\n[bold blue]Generating {len(scenes)} SDXL scenes...[/]")
        paths = []
        mood_to_action = {
            "peaceful":"serene peaceful moment", "emotional":"emotionally resonant",
            "intense":"powerful dramatic moment", "calm":"tranquil calm atmosphere",
            "hopeful":"hopeful uplifting scene", "dark":"dark atmospheric tension",
            "energetic":"dynamic energetic scene", "cheerful":"happy cheerful warm",
        }
        for scene in scenes:
            sid    = scene["scene_id"]
            bg     = scene.get("background", list(self.theme["backgrounds"].keys())[0])
            char   = scene.get("character")
            action = mood_to_action.get(scene.get("mood","default"), "compelling cinematic")
            out    = str(Path(session_dir) / "images" / f"scene_{sid:02d}.png")
            paths.append(self.generate_scene(bg, char, action, out, scene_id=sid))
        console.print(f"[bold green]All {len(paths)} images generated[/]")
        return paths

    def unload(self):
        for a in ["base","refiner"]:
            m = getattr(self, a, None)
            if m: del m; setattr(self, a, None)
        if torch.cuda.is_available(): torch.cuda.empty_cache()
