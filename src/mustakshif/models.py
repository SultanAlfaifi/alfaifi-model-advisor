from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(slots=True)
class GpuInfo:
    name: str
    vram_gb: float = 0.0
    free_vram_gb: float | None = None
    vendor: str = "unknown"
    source: str = "system"
    discrete: bool = False


@dataclass(slots=True)
class OllamaInfo:
    installed: bool
    path: str | None = None
    version: str | None = None


@dataclass(slots=True)
class HardwareProfile:
    os_name: str
    machine: str
    cpu: str
    physical_cores: int
    logical_cores: int
    ram_gb: float
    free_ram_gb: float
    gpus: list[GpuInfo]
    best_gpu: GpuInfo | None
    free_disk_gb: float
    model_path: str
    ollama: OllamaInfo

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ModelCandidate:
    id: str
    family: str
    publisher: str
    display_name: str
    variant: str
    size_gb: float | None
    context_k: int
    parameter_b: float | None
    active_parameter_b: float | None
    runtime: str
    modalities: list[str]
    capabilities: list[str]
    task_scores: dict[str, float]
    language_scores: dict[str, float]
    license_name: str
    official_url: str
    publisher_url: str
    install_command: str | None
    description: str = ""
    pulls: int = 0
    tag_count: int = 0
    family_updated_at: str | None = None
    benchmark_score: float | None = None
    benchmark_source: str | None = None
    trusted: bool = True
    source_state: str = "seed"
    last_checked: str | None = None
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "ModelCandidate":
        allowed = {item.name for item in cls.__dataclass_fields__.values()}
        return cls(**{key: item for key, item in value.items() if key in allowed})


@dataclass(slots=True)
class UserNeeds:
    experience: str
    goals: list[str]
    language: str
    priority: str
    locality: str
    needs_vision: bool
    needs_tools: bool
    context_size: str
    permissive_license_only: bool = False


@dataclass(slots=True)
class Recommendation:
    model: ModelCandidate
    score: float
    confidence: str
    hardware_mode: str
    recommended_context_k: int
    estimated_memory_gb: float | None
    reasons: list[str]
    warnings: list[str]
    category: str = "best_overall"
    score_breakdown: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["model"] = self.model.to_dict()
        return result
