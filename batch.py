#!/usr/bin/env python3
"""
batch.py - Batch Video Generation
Generates multiple videos in one session.

RunPod: start pod once, generate 10 videos, stop pod.
       Cost drops from $0.28/video to ~$0.20/video (amortized startup).

Windows CPU: queue runs overnight, one after another.

Usage:
  # Run a queue file:
  python batch.py --queue batch_queue.json

  # Quick batch from command line (same theme):
  python batch.py --theme mythology --topics "Medusa was not the monster,Why Prometheus stole fire,The fall of Icarus"

  # Multi-theme batch:
  python batch.py --queue batch_queue.json --stop-after 3

  # Dry run (show plan without generating):
  python batch.py --queue batch_queue.json --dry-run

  # Resume failed batch:
  python batch.py --queue batch_queue.json --resume batch_results_20250510.json
"""

import json
import sys
import time
import uuid
import argparse
import logging
from pathlib import Path
from datetime import datetime, timedelta
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn

console = Console()
Path("logs").mkdir(exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler("logs/batch.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("batch")


# ---------------------------------------------------------------------------
# BATCH QUEUE FORMAT
# ---------------------------------------------------------------------------

EXAMPLE_QUEUE = {
    "_comment": "Batch queue file for AI Content Studio. Run with: python batch.py --queue batch_queue.json",
    "_version": "1.0",
    "settings": {
        "stop_on_error": False,
        "delay_between_videos_seconds": 10,
        "notify_on_complete": True
    },
    "videos": [
        {
            "theme": "mythology",
            "topic": "Medusa was not the monster",
            "format": "epic_tale",
            "enabled": True
        },
        {
            "theme": "mythology",
            "topic": "Why Prometheus stole fire from the gods",
            "format": "god_profile",
            "enabled": True
        },
        {
            "theme": "relationships",
            "topic": "Why you keep attracting the wrong people",
            "format": "story_lesson",
            "enabled": True
        },
        {
            "theme": "finance",
            "topic": "How compound interest actually works",
            "format": "explainer",
            "enabled": True
        },
        {
            "theme": "horror",
            "topic": "The man who lived in my walls for three years",
            "format": "full_story",
            "enabled": True
        },
        {
            "theme": "motivation",
            "topic": "Stop waiting for the right moment",
            "format": "story_lesson",
            "enabled": True
        },
        {
            "theme": "history",
            "topic": "The Roman emperor who declared war on the ocean",
            "format": "narrative",
            "enabled": True
        },
        {
            "theme": "sports",
            "topic": "The night Leicester City won the Premier League",
            "format": "legendary_moment",
            "enabled": True
        }
    ]
}


# ---------------------------------------------------------------------------
# BATCH RUNNER
# ---------------------------------------------------------------------------

class BatchRunner:

    def __init__(self, queue: list, settings: dict = None):
        self.queue    = [v for v in queue if v.get("enabled", True)]
        self.settings = settings or {}
        self.results  = []
        self.batch_id = str(uuid.uuid4())[:8]
        self.start_time = None

    def _estimate_time(self) -> str:
        """Rough estimate of total batch time."""
        # CPU: ~75 min/video average | GPU: ~28 min/video average
        is_gpu = self._check_gpu()
        mins_each = 28 if is_gpu else 75
        total_mins = len(self.queue) * mins_each
        h = total_mins // 60
        m = total_mins % 60
        return f"~{h}h {m}m" if h > 0 else f"~{m} min"

    def _check_gpu(self) -> bool:
        try:
            import torch
            return torch.cuda.is_available()
        except Exception:
            return False

    def _estimate_cost(self) -> str:
        """Estimate RunPod cost for this batch."""
        try:
            import torch
            if not torch.cuda.is_available():
                return "N/A (CPU)"
        except Exception:
            return "N/A (CPU)"

        gpu_price = float(__import__("os").environ.get("GPU_PRICE_PER_HR", "0.64"))
        mins_each = 28
        total_hrs = (len(self.queue) * mins_each) / 60
        cost = total_hrs * gpu_price
        return f"~${cost:.2f}"

    def print_plan(self):
        """Display the batch plan before running."""
        table = Table(title=f"Batch Plan - {len(self.queue)} videos")
        table.add_column("#",       style="dim",    width=4)
        table.add_column("Theme",   style="cyan",   width=14)
        table.add_column("Format",  style="yellow", width=18)
        table.add_column("Topic",   style="white",  width=50)

        for i, v in enumerate(self.queue, 1):
            table.add_row(
                str(i),
                v.get("theme", "?"),
                v.get("format", "default"),
                v.get("topic", "auto")[:50]
            )
        console.print(table)
        console.print(f"  Estimated time:  [yellow]{self._estimate_time()}[/]")
        console.print(f"  Estimated cost:  [yellow]{self._estimate_cost()}[/]")
        console.print(f"  Batch ID:        [dim]{self.batch_id}[/]")

    def run(self, dry_run: bool = False, stop_after: int = None) -> dict:
        """Run the full batch."""
        self.start_time = time.time()
        queue = self.queue[:stop_after] if stop_after else self.queue

        self.print_plan()

        if dry_run:
            console.print("\n[yellow]Dry run -- no videos generated.[/]")
            return {"batch_id": self.batch_id, "videos": [], "status": "dry_run"}

        console.print(f"\n[bold green]Starting batch {self.batch_id} - {len(queue)} videos[/]")
        console.print("[dim]Videos saved to output/final/ as they complete.[/]\n")

        delay = self.settings.get("delay_between_videos_seconds", 10)
        stop_on_error = self.settings.get("stop_on_error", False)

        for i, video_spec in enumerate(queue, 1):
            theme    = video_spec.get("theme", "kids")
            topic    = video_spec.get("topic", "auto")
            fmt      = video_spec.get("format")
            label    = f"[{i}/{len(queue)}] {theme}: {topic[:40]}"

            console.rule(f"Video {i}/{len(queue)}")
            console.print(f"[bold cyan]{label}[/]")
            console.print(f"[dim]Started: {datetime.now().strftime('%H:%M:%S')}[/]\n")

            result = {
                "index":       i,
                "theme":       theme,
                "topic":       topic,
                "format":      fmt,
                "started_at":  datetime.now().isoformat(),
                "status":      "pending",
                "session_id":  None,
                "youtube_path":None,
                "tiktok_path": None,
                "duration_min":None,
                "error":       None
            }

            t_video = time.time()

            try:
                sys.path.insert(0, "src")
                # Import pipeline run function
                from pipeline import run_pipeline

                state = run_pipeline(
                    theme_id   = theme,
                    topic      = topic,
                    format_key = fmt,
                )

                elapsed_min = (time.time() - t_video) / 60
                result.update({
                    "status":       "done",
                    "session_id":   state["session_id"],
                    "youtube_path": state.get("stages", {}).get("assembly", {}).get("youtube"),
                    "tiktok_path":  state.get("stages", {}).get("assembly", {}).get("tiktok"),
                    "duration_min": round(elapsed_min, 1),
                })

                console.print(f"\n[bold green]Video {i} done in {elapsed_min:.1f} min[/]")

            except Exception as e:
                elapsed_min = (time.time() - t_video) / 60
                result.update({
                    "status":       "failed",
                    "error":        str(e),
                    "duration_min": round(elapsed_min, 1),
                })
                logger.error(f"Video {i} failed: {e}", exc_info=True)
                console.print(f"\n[bold red]Video {i} FAILED: {e}[/]")

                if stop_on_error:
                    console.print("[red]stop_on_error=true -- halting batch[/]")
                    self.results.append(result)
                    break

            self.results.append(result)

            # Save progress after each video
            self._save_results()

            # Delay between videos (GPU cool-down + cache clear)
            if i < len(queue):
                console.print(f"[dim]Waiting {delay}s before next video...[/]")
                self._clear_gpu_cache()
                time.sleep(delay)

        return self._finalize()

    def _clear_gpu_cache(self):
        try:
            import torch, gc
            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                console.print("[dim]GPU cache cleared[/]")
        except Exception:
            pass

    def _save_results(self):
        """Save batch results JSON after each video completes."""
        date_str   = datetime.now().strftime("%Y%m%d")
        results_path = Path(f"output/batch_results_{date_str}_{self.batch_id}.json")
        results_path.parent.mkdir(exist_ok=True)

        summary = {
            "batch_id":    self.batch_id,
            "started_at":  datetime.fromtimestamp(self.start_time).isoformat(),
            "saved_at":    datetime.now().isoformat(),
            "total":       len(self.queue),
            "completed":   sum(1 for r in self.results if r["status"] == "done"),
            "failed":      sum(1 for r in self.results if r["status"] == "failed"),
            "videos":      self.results
        }
        with open(results_path, "w") as f:
            json.dump(summary, f, indent=2)
        return results_path

    def _finalize(self) -> dict:
        """Print final summary and return results."""
        total_elapsed = (time.time() - self.start_time) / 60
        done   = [r for r in self.results if r["status"] == "done"]
        failed = [r for r in self.results if r["status"] == "failed"]

        results_path = self._save_results()

        # Summary table
        table = Table(title=f"Batch Complete - {self.batch_id}")
        table.add_column("#",       style="dim",    width=4)
        table.add_column("Theme",   style="cyan",   width=14)
        table.add_column("Status",  style="white",  width=8)
        table.add_column("Time",    style="yellow", width=8)
        table.add_column("Output",  style="dim",    width=45)

        for r in self.results:
            status_str = "[green]DONE[/]"   if r["status"] == "done" \
                    else "[red]FAILED[/]"   if r["status"] == "failed" \
                    else "[yellow]SKIP[/]"
            out = r.get("youtube_path") or r.get("error", "")[:40] or "-"
            if out and len(out) > 45:
                out = "..." + out[-42:]
            table.add_row(
                str(r["index"]),
                r["theme"],
                status_str,
                f"{r.get('duration_min','?')}m",
                out
            )

        console.print(table)
        console.print(Panel(
            f"[bold green]Batch {self.batch_id} finished![/]\n\n"
            f"Total time:  [yellow]{total_elapsed:.1f} min[/]\n"
            f"Completed:   [green]{len(done)}/{len(self.results)}[/]\n"
            f"Failed:      [red]{len(failed)}/{len(self.results)}[/]\n"
            f"Results:     [dim]{results_path}[/]\n\n"
            f"[white]All finished videos are in: output/final/[/]\n"
            f"[dim]Next: review each video, record hooks, upload[/]",
            title="Batch Summary"
        ))

        return {
            "batch_id":  self.batch_id,
            "total":     len(self.results),
            "completed": len(done),
            "failed":    len(failed),
            "total_min": round(total_elapsed, 1),
            "videos":    self.results
        }


# ---------------------------------------------------------------------------
# QUEUE FILE HELPERS
# ---------------------------------------------------------------------------

def load_queue_file(path: str) -> tuple:
    """Load and validate a batch queue JSON file."""
    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    videos   = data.get("videos", data if isinstance(data, list) else [])
    settings = data.get("settings", {})

    if not videos:
        raise ValueError(f"No videos found in queue file: {path}")

    # Validate each entry
    valid = []
    for i, v in enumerate(videos):
        if not isinstance(v, dict):
            logger.warning(f"Skipping invalid entry {i}: {v}")
            continue
        if not v.get("enabled", True):
            console.print(f"[dim]Skipping disabled: {v.get('topic','?')}[/]")
            continue
        if "theme" not in v:
            logger.warning(f"Entry {i} missing 'theme', defaulting to 'kids'")
            v["theme"] = "kids"
        valid.append(v)

    return valid, settings


def create_example_queue(output_path: str = "batch_queue.json"):
    """Write an example queue file."""
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(EXAMPLE_QUEUE, f, indent=2, ensure_ascii=False)
    console.print(f"[green]Example queue created: {output_path}[/]")
    console.print("[dim]Edit it, then run: python batch.py --queue batch_queue.json[/]")


def create_themed_queue(theme: str, topics: list, fmt: str = None) -> list:
    """Build a queue from a list of topics all with the same theme."""
    return [{"theme": theme, "topic": t.strip(), "format": fmt, "enabled": True}
            for t in topics if t.strip()]


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="AI Content Studio - Batch Generator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python batch.py --create-queue                     # create example queue file
  python batch.py --queue batch_queue.json           # run full queue
  python batch.py --queue batch_queue.json --dry-run # preview without generating
  python batch.py --queue batch_queue.json --stop-after 3
  python batch.py --theme mythology --topics "Medusa,Icarus,Prometheus"
  python batch.py --theme motivation --topics "Stop overthinking,Wake up early" --format story_lesson
        """
    )

    parser.add_argument("--queue",        help="Path to batch queue JSON file")
    parser.add_argument("--theme",        help="Single theme for all videos (with --topics)")
    parser.add_argument("--topics",       help="Comma-separated topics (with --theme)")
    parser.add_argument("--format",       help="Format key for all videos")
    parser.add_argument("--stop-after",   type=int, help="Stop after N videos")
    parser.add_argument("--dry-run",      action="store_true", help="Show plan without generating")
    parser.add_argument("--create-queue", action="store_true", help="Create example batch_queue.json")
    parser.add_argument("--resume",       help="Resume from a previous results JSON")

    args = parser.parse_args()

    # Create example queue
    if args.create_queue:
        create_example_queue()
        sys.exit(0)

    # Build queue
    queue    = []
    settings = {}

    if args.queue:
        queue, settings = load_queue_file(args.queue)

    elif args.theme and args.topics:
        topics = args.topics.split(",")
        queue  = create_themed_queue(args.theme, topics, args.format)

    elif args.resume:
        with open(args.resume) as f:
            prev = json.load(f)
        # Re-queue failed videos only
        failed = [v for v in prev["videos"] if v["status"] == "failed"]
        queue  = [{"theme": v["theme"], "topic": v["topic"],
                   "format": v.get("format"), "enabled": True}
                  for v in failed]
        console.print(f"[yellow]Resuming {len(queue)} failed videos from previous batch[/]")

    else:
        parser.print_help()
        console.print("\n[yellow]Tip: run with --create-queue to generate an example file[/]")
        sys.exit(1)

    if not queue:
        console.print("[red]No videos to generate. Check your queue file.[/]")
        sys.exit(1)

    runner = BatchRunner(queue, settings)
    runner.run(dry_run=args.dry_run, stop_after=args.stop_after)
