"""
src/pod_manager.py
Control RunPod pods from your laptop.
Auto-start GPU pod before pipeline, auto-stop after.
Saves money by never leaving pod running idle.

Usage:
  from pod_manager import PodManager
  mgr = PodManager()
  mgr.start()
  # ... run your pipeline remotely ...
  mgr.stop()
"""

import os
import time
import json
import logging
from pathlib import Path
from rich.console import Console

console = Console()
logger  = logging.getLogger(__name__)


class PodManager:
    """
    Manages RunPod lifecycle from your local machine.
    Requires: pip install runpod
    API key from: https://www.runpod.io/console/user/settings
    """

    def __init__(self, config_path: str = "config.json"):
        with open(config_path) as f:
            cfg = json.load(f)
        rp = cfg.get("runpod", {})

        self.api_key       = rp.get("api_key") or os.environ.get("RUNPOD_API_KEY")
        self.preferred_gpu = rp.get("preferred_gpu", "NVIDIA GeForce RTX 3090")
        self.template_id   = rp.get("template_id")
        self.volume_id     = rp.get("network_volume_id")
        self.idle_timeout  = rp.get("auto_stop_after_idle_minutes", 30)
        self.active_pod_id = None

        if not self.api_key:
            raise ValueError(
                "RUNPOD_API_KEY not set.\n"
                "Get it from: https://www.runpod.io/console/user/settings\n"
                "Then add to config.json: runpod.api_key OR set env: RUNPOD_API_KEY=..."
            )

    def _client(self):
        import runpod
        runpod.api_key = self.api_key
        return runpod

    def start(self, wait_ready: bool = True) -> str:
        """
        Start a new GPU pod. Returns pod ID.
        Blocks until pod is running if wait_ready=True.
        """
        rp = self._client()

        console.print(f"[blue]Starting RunPod pod ({self.preferred_gpu})...[/]")

        pod_config = {
            "name": "ai-studio-v2-run",
            "image_name": "runpod/pytorch:2.2.0-py3.11-cuda12.1.1-devel-ubuntu22.04",
            "gpu_type_id": self.preferred_gpu,
            "cloud_type": "SECURE",
            "container_disk_in_gb": 30,
            "ports": "8888/http,22/tcp",
            "env": {
                "OLLAMA_NUM_PARALLEL": "1",
                "RUNPOD_STOP_AFTER_IDLE": str(self.idle_timeout * 60),
            }
        }

        # Attach network volume if configured (persists models between runs)
        if self.volume_id:
            pod_config["volume_in_gb"]     = 60
            pod_config["volume_mount_path"] = "/workspace/models"

        if self.template_id:
            pod_config["template_id"] = self.template_id

        try:
            pod = rp.create_pod(**pod_config)
            self.active_pod_id = pod["id"]
            console.print(f"[green]Pod created: {self.active_pod_id}[/]")
        except Exception as e:
            console.print(f"[yellow]Preferred GPU unavailable: {e}[/]")
            console.print("[yellow]Trying community cloud (cheaper)...[/]")
            pod_config["cloud_type"] = "COMMUNITY"
            pod = rp.create_pod(**pod_config)
            self.active_pod_id = pod["id"]

        if wait_ready:
            self._wait_until_running(self.active_pod_id)

        return self.active_pod_id

    def stop(self, pod_id: str = None):
        """Terminate pod. Billing stops immediately."""
        pid = pod_id or self.active_pod_id
        if not pid:
            console.print("[yellow]No active pod to stop[/]")
            return

        rp = self._client()
        rp.terminate_pod(pid)
        self.active_pod_id = None
        console.print(f"[green]Pod {pid} terminated. Billing stopped.[/]")

    def get_status(self, pod_id: str = None) -> dict:
        """Get pod status and connection info."""
        pid = pod_id or self.active_pod_id
        if not pid:
            return {"status": "no_pod"}

        rp   = self._client()
        pods = rp.get_pods()
        for p in pods:
            if p["id"] == pid:
                return p
        return {"status": "not_found"}

    def get_ssh_command(self, pod_id: str = None) -> str:
        """Returns the SSH command to connect to the pod."""
        status = self.get_status(pod_id)
        ports  = status.get("runtime", {}).get("ports", [])
        for port in ports:
            if port.get("privatePort") == 22:
                ip      = port.get("ip")
                pub_port = port.get("publicPort")
                return f"ssh root@{ip} -p {pub_port}"
        return "SSH port not ready yet"

    def _wait_until_running(self, pod_id: str, timeout: int = 300):
        console.print("[yellow]Waiting for pod to be ready...[/]", end="")
        start = time.time()
        while time.time() - start < timeout:
            status = self.get_status(pod_id)
            state  = status.get("desiredStatus") or status.get("runtime", {}).get("uptimeInSeconds", -1)
            if status.get("runtime"):
                console.print(f"\n[green]Pod running! ({int(time.time()-start)}s)[/]")
                ssh = self.get_ssh_command(pod_id)
                console.print(f"[cyan]SSH: {ssh}[/]")
                return
            console.print(".", end="", flush=True)
            time.sleep(5)
        raise TimeoutError(f"Pod {pod_id} did not start within {timeout}s")

    def list_available_gpus(self) -> list:
        """List available GPU types and their prices."""
        rp = self._client()
        gpus = rp.get_gpus()
        results = []
        for g in gpus:
            results.append({
                "id":       g.get("id"),
                "name":     g.get("displayName"),
                "vram_gb":  g.get("memoryInGb"),
                "price_hr": g.get("securePrice") or g.get("communityPrice"),
                "available": g.get("secureCloud") or g.get("communityCloud")
            })
        results.sort(key=lambda x: x.get("price_hr") or 999)
        return results

    def print_gpu_prices(self):
        """Print a table of available GPUs and prices."""
        from rich.table import Table
        gpus  = self.list_available_gpus()
        table = Table(title="RunPod GPU Availability")
        table.add_column("GPU", style="cyan")
        table.add_column("VRAM", style="green")
        table.add_column("$/hr", style="yellow")
        table.add_column("Available", style="white")
        for g in gpus[:15]:
            table.add_row(
                g["name"] or "?",
                f"{g['vram_gb']}GB" if g.get("vram_gb") else "?",
                f"${g['price_hr']:.3f}" if g.get("price_hr") else "?",
                "Yes" if g.get("available") else "No"
            )
        console.print(table)


# ---------------------------------------------------------------------------
# Cost tracker
# ---------------------------------------------------------------------------

class CostTracker:
    """Tracks GPU time and cost per session."""

    def __init__(self, log_path: str = "logs/costs.json"):
        self.log_path = Path(log_path)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self._start_time = None
        self._gpu_price_per_hr = 0.44  # Default RTX 3090

    def start_session(self, session_id: str, gpu_price_per_hr: float = 0.44):
        import time
        self._start_time      = time.time()
        self._session_id      = session_id
        self._gpu_price_per_hr = gpu_price_per_hr
        console.print(f"[dim]Cost tracking started (${gpu_price_per_hr}/hr)[/]")

    def end_session(self) -> dict:
        import time
        if not self._start_time:
            return {}
        elapsed_hr = (time.time() - self._start_time) / 3600
        cost       = elapsed_hr * self._gpu_price_per_hr

        record = {
            "session_id":    self._session_id,
            "duration_min":  round(elapsed_hr * 60, 1),
            "cost_usd":      round(cost, 4),
            "gpu_price_hr":  self._gpu_price_per_hr
        }

        # Append to log
        history = []
        if self.log_path.exists():
            with open(self.log_path) as f:
                history = json.load(f)
        history.append(record)
        with open(self.log_path, "w") as f:
            json.dump(history, f, indent=2)

        console.print(f"[green]Session cost: ${cost:.4f} ({elapsed_hr*60:.1f} min)[/]")
        return record
