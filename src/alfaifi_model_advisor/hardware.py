from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
from pathlib import Path

import psutil

from .models import GpuInfo, HardwareProfile, OllamaInfo


CREATE_NO_WINDOW = 0x08000000 if os.name == "nt" else 0


def _run(command: list[str], timeout: int = 8) -> subprocess.CompletedProcess[str] | None:
    try:
        return subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
            creationflags=CREATE_NO_WINDOW,
        )
    except (OSError, subprocess.SubprocessError):
        return None


def _nvidia_gpus() -> list[GpuInfo]:
    executable = shutil.which("nvidia-smi")
    if not executable:
        return []
    result = _run(
        [
            executable,
            "--query-gpu=name,memory.total,memory.free",
            "--format=csv,noheader,nounits",
        ]
    )
    if not result or result.returncode != 0:
        return []

    found: list[GpuInfo] = []
    for row in result.stdout.splitlines():
        parts = [part.strip() for part in row.split(",")]
        if len(parts) < 3:
            continue
        try:
            total = round(float(parts[1]) / 1024, 1)
            free = round(float(parts[2]) / 1024, 1)
        except ValueError:
            continue
        found.append(
            GpuInfo(
                name=parts[0],
                vram_gb=total,
                free_vram_gb=free,
                vendor="NVIDIA",
                source="nvidia-smi",
                discrete=True,
            )
        )
    return found


def _windows_gpu_fallback() -> list[GpuInfo]:
    if os.name != "nt":
        return []
    script = (
        "Get-CimInstance Win32_VideoController | "
        "Select-Object Name,AdapterRAM | ConvertTo-Json -Compress"
    )
    result = _run(["powershell", "-NoProfile", "-Command", script])
    if not result or result.returncode != 0 or not result.stdout.strip():
        return []
    try:
        values = json.loads(result.stdout)
    except json.JSONDecodeError:
        return []
    if isinstance(values, dict):
        values = [values]

    found: list[GpuInfo] = []
    for value in values:
        name = str(value.get("Name") or "Unknown GPU")
        lower = name.lower()
        if any(item in lower for item in ("virtual", "remote", "basic display", "displaylink", "easy&light")):
            continue
        adapter_ram = value.get("AdapterRAM") or 0
        try:
            vram = round(float(adapter_ram) / (1024**3), 1)
        except (TypeError, ValueError):
            vram = 0.0
        integrated = "intel" in lower and any(item in lower for item in ("uhd", "iris", "graphics"))
        vendor = "AMD" if any(item in lower for item in ("amd", "radeon")) else "Intel" if "intel" in lower else "unknown"
        found.append(
            GpuInfo(
                name=name,
                vram_gb=vram,
                vendor=vendor,
                source="Windows CIM (VRAM may be approximate)",
                discrete=not integrated and vram >= 1,
            )
        )
    return found


def _cpu_name() -> str:
    if os.name == "nt":
        result = _run(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                "(Get-CimInstance Win32_Processor | Select-Object -ExpandProperty Name) -join ' | '",
            ]
        )
        if result and result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    return platform.processor() or platform.machine() or "Unknown CPU"


def _ollama_info() -> OllamaInfo:
    path = shutil.which("ollama")
    if not path and os.name == "nt":
        local_app_data = os.getenv("LOCALAPPDATA")
        program_files = os.getenv("ProgramFiles")
        candidates = [
            Path(local_app_data) / "Programs" / "Ollama" / "ollama.exe"
            if local_app_data
            else None,
            Path(program_files) / "Ollama" / "ollama.exe"
            if program_files
            else None,
        ]
        path = next((str(candidate) for candidate in candidates if candidate and candidate.is_file()), None)
    if not path:
        return OllamaInfo(installed=False)
    result = _run([path, "--version"], timeout=5)
    version = result.stdout.strip() if result and result.returncode == 0 else None
    return OllamaInfo(installed=True, path=path, version=version)


class HardwareInspector:
    def scan(self) -> HardwareProfile:
        memory = psutil.virtual_memory()
        ram_gb = round(memory.total / (1024**3), 1)
        free_ram_gb = round(memory.available / (1024**3), 1)

        nvidia = _nvidia_gpus()
        fallback = _windows_gpu_fallback()
        if nvidia:
            fallback = [gpu for gpu in fallback if "nvidia" not in gpu.name.lower()]
        gpus = nvidia + fallback
        discrete = [gpu for gpu in gpus if gpu.discrete]
        best_gpu = max(discrete, key=lambda item: item.vram_gb, default=None)

        model_path = Path(os.getenv("OLLAMA_MODELS") or Path.home() / ".ollama" / "models")
        probe = model_path
        while not probe.exists() and probe.parent != probe:
            probe = probe.parent
        try:
            disk = psutil.disk_usage(str(probe))
            free_disk_gb = round(disk.free / (1024**3), 1)
        except OSError:
            free_disk_gb = 0.0

        return HardwareProfile(
            os_name=f"{platform.system()} {platform.release()}",
            machine=platform.machine(),
            cpu=_cpu_name(),
            physical_cores=psutil.cpu_count(logical=False) or 0,
            logical_cores=psutil.cpu_count(logical=True) or 0,
            ram_gb=ram_gb,
            free_ram_gb=free_ram_gb,
            gpus=gpus,
            best_gpu=best_gpu,
            free_disk_gb=free_disk_gb,
            model_path=str(model_path),
            ollama=_ollama_info(),
        )
