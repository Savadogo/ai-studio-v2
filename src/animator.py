"""
src/animator.py  - v2.1
Per-theme animation strategy selector.

Strategy per theme:
  kids, mindfulness, finance, history  --> Ken Burns (CPU, free, safe)
  horror, relationships                --> SVD-XT (image-to-video, ~40s/clip)
  motivation, fitness                  --> CogVideoX-5B (dynamic, ~90s/clip)

All GPU strategies take your SDXL image as INPUT.
Characters stay visually consistent across every clip.
"""

import json
import subprocess
import time
import logging
from pathlib import Path
from enum import Enum
import torch
from rich.console import Console

console = Console()
logger  = logging.getLogger(__name__)


class AnimationStrategy(str, Enum):
    KEN_BURNS = "ken_burns"
    SVD       = "svd"
    COGVIDEO  = "cogvideo"


THEME_STRATEGY: dict[str, AnimationStrategy] = {
    "kids":          AnimationStrategy.KEN_BURNS,
    "mindfulness":   AnimationStrategy.KEN_BURNS,
    "finance":       AnimationStrategy.KEN_BURNS,
    "history":       AnimationStrategy.KEN_BURNS,
    "horror":        AnimationStrategy.SVD,
    "relationships": AnimationStrategy.SVD,
    "motivation":    AnimationStrategy.COGVIDEO,
    "fitness":       AnimationStrategy.COGVIDEO,
    "sports":        AnimationStrategy.COGVIDEO,
    "mythology":     AnimationStrategy.SVD,
}

KEN_BURNS_SETTINGS: dict[str, dict] = {
    "kids":        {"max_zoom": 1.06, "speed": "normal"},
    "mindfulness": {"max_zoom": 1.03, "speed": "ultra_slow"},
    "finance":     {"max_zoom": 1.05, "speed": "slow"},
    "history":     {"max_zoom": 1.07, "speed": "slow"},
    "default":     {"max_zoom": 1.08, "speed": "normal"},
}

SVD_MOTION_BUCKET: dict[str, dict] = {
    "horror":        {"dark": 55, "tense": 70, "default": 65},
    "relationships": {"emotional": 110, "peaceful": 85, "hopeful": 115, "default": 100},
    "sports":        {"intense": 130, "energetic": 140, "default": 120},
    "mythology":     {"divine": 75, "cursed": 65, "epic_war": 120, "dark": 60, "default": 80},
    "default":       {"default": 100},
}

COGVIDEO_PROMPTS: dict[str, dict] = {
    "motivation": {
        "intense":   "powerful dynamic camera movement, dramatic lighting, cinematic energy, inspiring",
        "energetic": "fast determined motion, strong visual momentum, motivational",
        "default":   "confident purposeful movement, cinematic, motivational energy",
    },
    "fitness": {
        "energetic": "athletic dynamic movement, training energy, powerful camera",
        "intense":   "high intensity motion, gym atmosphere, strong determination",
        "default":   "active movement, fitness motivation, strong athletic",
    },
    "sports": {
        "intense":   "dynamic fast camera movement, stadium energy, sports broadcast style, crowd roaring",
        "energetic": "explosive motion, athletic power, cinematic sports camera, high octane",
        "default":   "cinematic sports broadcast movement, dramatic stadium atmosphere",
    },
    "default": {
        "default":   "smooth cinematic camera movement, natural atmospheric motion",
    },
}

MOTION_CYCLE = ["zoom_in", "pan_right", "zoom_out", "pan_left", "diagonal"]


class ThemeAnimator:

    def __init__(self, config: dict, theme: dict):
        self.config   = config
        self.theme_id = theme.get("theme_id", "default")
        self.device   = config["hardware"]["device"]
        self.dtype    = torch.float16
        self.strategy = THEME_STRATEGY.get(self.theme_id, AnimationStrategy.KEN_BURNS)
        self._svd_pipe = None
        self._cog_pipe = None

        console.print(
            f"[blue]Animation: [bold]{self.strategy.value}[/] for theme '{self.theme_id}'[/]"
        )

    def animate_all_scenes(
        self,
        image_paths: list,
        scenes: list,
        session_dir: str,
    ) -> list:
        console.print(f"\n[bold]Animating {len(image_paths)} scenes...[/]")
        clips = []
        for i, (img, scene) in enumerate(zip(image_paths, scenes)):
            sid      = scene["scene_id"]
            mood     = scene.get("mood", "default")
            duration = float(scene.get("duration_seconds", 20))
            out      = str(Path(session_dir) / "clips" / f"clip_{sid:02d}.mp4")
            clip     = self._animate_one(img, mood, duration, out, sid)
            clips.append(clip)
        console.print(f"[bold green]All {len(clips)} clips ready[/]")
        return clips

    def _animate_one(self, image_path, mood, duration, output_path, scene_id):
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        if self.strategy == AnimationStrategy.SVD:
            try:
                return self._svd(image_path, mood, duration, output_path, scene_id)
            except Exception as e:
                console.print(f"[yellow]SVD failed: {e} -- falling back to Ken Burns[/]")
        elif self.strategy == AnimationStrategy.COGVIDEO:
            try:
                return self._cogvideo(image_path, mood, duration, output_path, scene_id)
            except Exception as e:
                console.print(f"[yellow]CogVideo failed: {e} -- falling back to SVD[/]")
                try:
                    return self._svd(image_path, mood, duration, output_path, scene_id)
                except Exception as e2:
                    console.print(f"[yellow]SVD also failed: {e2} -- using Ken Burns[/]")
        return self._ken_burns(image_path, mood, duration, output_path, scene_id)

    # ------------------------------------------------------------------
    # KEN BURNS
    # ------------------------------------------------------------------
    def _ken_burns(self, image_path, mood, duration, output_path, scene_id):
        settings  = KEN_BURNS_SETTINGS.get(self.theme_id, KEN_BURNS_SETTINGS["default"])
        max_zoom  = settings["max_zoom"]
        motion    = MOTION_CYCLE[scene_id % len(MOTION_CYCLE)]
        W, H, fps = 1920, 1080, 24
        frames    = int(duration * fps)
        step      = (max_zoom - 1.0) / frames

        filters = {
            "zoom_in":   (
                f"scale=iw*{max_zoom}:ih*{max_zoom},"
                f"zoompan=z='min(zoom+{step:.6f},{max_zoom})':"
                f"d={frames}:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={W}x{H}:fps={fps}"
            ),
            "zoom_out":  (
                f"scale=iw*{max_zoom}:ih*{max_zoom},"
                f"zoompan=z='if(lte(zoom,1.0),{max_zoom},max(1.0,zoom-{step:.6f}))':"
                f"d={frames}:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={W}x{H}:fps={fps}"
            ),
            "pan_right": (
                f"scale=iw*1.06:ih*1.06,"
                f"zoompan=z='1.06':d={frames}:"
                f"x='min(iw*(on/{frames})*0.05,iw*0.05)':y='ih/2-(ih/zoom/2)':s={W}x{H}:fps={fps}"
            ),
            "pan_left":  (
                f"scale=iw*1.06:ih*1.06,"
                f"zoompan=z='1.06':d={frames}:"
                f"x='max(0,iw*0.05-iw*(on/{frames})*0.05)':y='ih/2-(ih/zoom/2)':s={W}x{H}:fps={fps}"
            ),
            "diagonal":  (
                f"scale=iw*1.07:ih*1.07,"
                f"zoompan=z='1.07':d={frames}:"
                f"x='min(iw*(on/{frames})*0.03,iw*0.03)':y='min(ih*(on/{frames})*0.03,ih*0.03)':s={W}x{H}:fps={fps}"
            ),
        }

        result = subprocess.run([
            "ffmpeg", "-y", "-loop", "1", "-i", image_path,
            "-vf", filters.get(motion, filters["zoom_in"]),
            "-t", str(duration), "-r", str(fps),
            "-c:v", "libx264", "-preset", "ultrafast", "-crf", "20",
            "-pix_fmt", "yuv420p", output_path
        ], capture_output=True)

        if result.returncode != 0:
            raise RuntimeError(f"Ken Burns failed: {result.stderr[-150:]}")

        console.print(f"[green]  [{self.theme_id}] Scene {scene_id}: {motion} ({duration:.0f}s)[/]")
        return output_path

    # ------------------------------------------------------------------
    # SVD-XT  -- image-to-video, character consistent
    # ------------------------------------------------------------------
    def _load_svd(self):
        if self._svd_pipe:
            return
        console.print("[blue]Loading SVD-XT (image-to-video)...[/]")
        from diffusers import StableVideoDiffusionPipeline
        from diffusers.utils import load_image
        self._svd_pipe = StableVideoDiffusionPipeline.from_pretrained(
            "stabilityai/stable-video-diffusion-img2vid-xt",
            torch_dtype=self.dtype, variant="fp16",
        ).to(self.device)
        self._svd_pipe.enable_model_cpu_offload()
        self._load_image_fn = load_image
        console.print("[green]SVD-XT ready -- takes your SDXL image as input[/]")

    def _svd(self, image_path, mood, duration, output_path, scene_id):
        self._load_svd()
        buckets = SVD_MOTION_BUCKET.get(self.theme_id, SVD_MOTION_BUCKET["default"])
        motion_bucket = buckets.get(mood, buckets.get("default", 100))

        image = self._load_image_fn(image_path).resize((1024, 576))

        console.print(f"[blue]  SVD scene {scene_id} (motion={motion_bucket}, mood={mood})...[/]")
        t = time.time()

        frames = self._svd_pipe(
            image,
            num_frames=25,
            num_inference_steps=25,
            decode_chunk_size=8,
            motion_bucket_id=motion_bucket,
            noise_aug_strength=0.02,
            generator=torch.Generator(self.device).manual_seed(scene_id * 7),
        ).frames[0]

        frames_dir = Path(output_path).parent / f"_svd_{scene_id}"
        frames_dir.mkdir(exist_ok=True)
        for fi, frame in enumerate(frames):
            frame.save(str(frames_dir / f"f{fi:04d}.png"))

        fps = max(1.0, len(frames) / duration)
        subprocess.run([
            "ffmpeg", "-y", "-r", f"{fps:.2f}",
            "-i", str(frames_dir / "f%04d.png"),
            "-c:v", "libx264", "-preset", "fast", "-crf", "18",
            "-pix_fmt", "yuv420p", output_path
        ], check=True, capture_output=True)

        import shutil; shutil.rmtree(str(frames_dir), ignore_errors=True)
        console.print(f"[green]  SVD scene {scene_id} done in {time.time()-t:.0f}s[/]")
        return output_path

    # ------------------------------------------------------------------
    # CogVideoX-5B  -- image+text-to-video, dynamic motion
    # ------------------------------------------------------------------
    def _load_cogvideo(self):
        if self._cog_pipe:
            return
        console.print("[blue]Loading CogVideoX-5B (image+text-to-video)...[/]")
        from diffusers import CogVideoXImageToVideoPipeline
        self._cog_pipe = CogVideoXImageToVideoPipeline.from_pretrained(
            "THUDM/CogVideoX-5b-I2V", torch_dtype=torch.bfloat16,
        ).to(self.device)
        self._cog_pipe.enable_model_cpu_offload()
        self._cog_pipe.vae.enable_tiling()
        console.print("[green]CogVideoX-5B ready[/]")

    def _cogvideo(self, image_path, mood, duration, output_path, scene_id):
        self._load_cogvideo()
        from diffusers.utils import load_image, export_to_video
        prompts = COGVIDEO_PROMPTS.get(self.theme_id, COGVIDEO_PROMPTS["default"])
        prompt  = prompts.get(mood, prompts.get("default", "smooth cinematic movement"))

        image = load_image(image_path).resize((720, 480))
        console.print(f"[blue]  CogVideoX scene {scene_id}: {mood}...[/]")
        t = time.time()

        video = self._cog_pipe(
            prompt=prompt, image=image,
            num_videos_per_prompt=1,
            num_inference_steps=25,
            num_frames=49,
            guidance_scale=6.0,
            generator=torch.Generator(self.device).manual_seed(scene_id * 13),
        ).frames[0]

        fps = max(1.0, len(video) / duration)
        tmp = output_path.replace(".mp4", "_tmp.mp4")
        export_to_video(video, tmp, fps=fps)
        subprocess.run([
            "ffmpeg", "-y", "-i", tmp,
            "-c:v", "libx264", "-preset", "fast", "-crf", "18",
            "-pix_fmt", "yuv420p", output_path
        ], check=True, capture_output=True)
        Path(tmp).unlink(missing_ok=True)

        console.print(f"[green]  CogVideoX scene {scene_id} done in {time.time()-t:.0f}s[/]")
        return output_path

    def unload(self):
        for attr in ["_svd_pipe", "_cog_pipe"]:
            pipe = getattr(self, attr, None)
            if pipe:
                del pipe
                setattr(self, attr, None)
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        console.print("[dim]Animator unloaded from GPU[/]")
