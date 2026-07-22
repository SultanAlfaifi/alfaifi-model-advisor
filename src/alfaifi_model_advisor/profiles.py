from __future__ import annotations

from dataclasses import dataclass

from .models import ModelCandidate


@dataclass(frozen=True, slots=True)
class FamilyProfile:
    family: str
    publisher: str
    display_name: str
    publisher_url: str
    license_name: str
    capabilities: tuple[str, ...]
    task_scores: dict[str, float]
    language_scores: dict[str, float]
    modalities: tuple[str, ...]
    parameter_map: dict[str, tuple[float | None, float | None]]
    notes: tuple[str, ...] = ()


FAMILY_PROFILES: dict[str, FamilyProfile] = {
    "qwen3.5": FamilyProfile(
        family="qwen3.5",
        publisher="Qwen",
        display_name="Qwen 3.5",
        publisher_url="https://huggingface.co/Qwen",
        license_name="Apache-2.0 / verify model card",
        capabilities=("chat", "writing", "coding", "agents", "vision", "documents", "translation", "reasoning", "ui_design", "tools"),
        task_scores={"general": 4.7, "writing": 4.5, "coding": 4.7, "agents": 4.7, "vision": 4.6, "documents": 4.6, "translation": 4.7, "reasoning": 4.7, "ui_design": 4.5},
        language_scores={"ar": 4.8, "en": 4.8, "both": 4.8},
        modalities=("text", "image"),
        parameter_map={"0.8b": (0.8, None), "2b": (2.0, None), "4b": (4.0, None), "9b": (9.0, None), "27b": (27.0, None), "35b": (35.0, 3.0), "122b": (122.0, 10.0)},
    ),
    "qwen3-coder": FamilyProfile(
        family="qwen3-coder",
        publisher="Qwen",
        display_name="Qwen 3 Coder",
        publisher_url="https://huggingface.co/Qwen",
        license_name="Apache-2.0 / verify model card",
        capabilities=("coding", "agents", "reasoning", "ui_design", "tools"),
        task_scores={"general": 4.1, "writing": 3.7, "coding": 5.0, "agents": 5.0, "vision": 2.0, "documents": 4.0, "translation": 3.6, "reasoning": 4.7, "ui_design": 4.7},
        language_scores={"ar": 3.8, "en": 4.9, "both": 4.1},
        modalities=("text",),
        parameter_map={"30b": (30.0, 3.3), "480b-cloud": (480.0, 35.0)},
        notes=("Specialized for coding and agentic workflows.",),
    ),
    "gemma4": FamilyProfile(
        family="gemma4",
        publisher="Google",
        display_name="Gemma 4",
        publisher_url="https://huggingface.co/google",
        license_name="Apache-2.0 / verify model card",
        capabilities=("chat", "writing", "coding", "agents", "vision", "documents", "translation", "reasoning", "ui_design", "tools"),
        task_scores={"general": 4.6, "writing": 4.6, "coding": 4.5, "agents": 4.5, "vision": 4.9, "documents": 4.6, "translation": 4.4, "reasoning": 4.6, "ui_design": 4.7},
        language_scores={"ar": 4.2, "en": 4.8, "both": 4.4},
        modalities=("text", "image"),
        parameter_map={"e2b": (5.0, 2.0), "e4b": (12.0, 4.0), "12b": (12.0, None), "26b": (26.0, 4.0), "31b": (31.0, None)},
    ),
    "kimi-k2.5": FamilyProfile(
        family="kimi-k2.5",
        publisher="Moonshot AI",
        display_name="Kimi K2.5",
        publisher_url="https://huggingface.co/moonshotai",
        license_name="Modified MIT",
        capabilities=("chat", "coding", "agents", "vision", "reasoning", "ui_design", "tools"),
        task_scores={"general": 4.8, "writing": 4.3, "coding": 5.0, "agents": 5.0, "vision": 4.9, "documents": 4.5, "translation": 4.0, "reasoning": 4.9, "ui_design": 5.0},
        language_scores={"ar": 4.0, "en": 4.9, "both": 4.2},
        modalities=("text", "image"),
        parameter_map={"cloud": (1000.0, 32.0)},
        notes=("Available through Ollama Cloud; the complete weights are not practical on a personal computer.",),
    ),
    "kimi-k2.6": FamilyProfile(
        family="kimi-k2.6",
        publisher="Moonshot AI",
        display_name="Kimi K2.6",
        publisher_url="https://huggingface.co/moonshotai/Kimi-K2.6",
        license_name="Modified MIT",
        capabilities=("chat", "coding", "agents", "vision", "reasoning", "ui_design", "tools"),
        task_scores={"general": 4.9, "writing": 4.4, "coding": 5.0, "agents": 5.0, "vision": 5.0, "documents": 4.6, "translation": 4.0, "reasoning": 5.0, "ui_design": 5.0},
        language_scores={"ar": 4.0, "en": 5.0, "both": 4.2},
        modalities=("text", "image"),
        parameter_map={"cloud": (1100.0, None)},
        notes=("Cloud-hosted through Ollama; designed for agents and long-horizon coding.",),
    ),
}


SEED_VARIANTS: tuple[tuple[str, str, float | None, int, str], ...] = (
    ("qwen3.5", "0.8b", 1.0, 256, "local"),
    ("qwen3.5", "2b", 2.7, 256, "local"),
    ("qwen3.5", "4b", 3.4, 256, "local"),
    ("qwen3.5", "9b", 6.6, 256, "local"),
    ("qwen3.5", "27b", 17.0, 256, "local"),
    ("qwen3.5", "35b", 24.0, 256, "local"),
    ("qwen3.5", "122b", 81.0, 256, "local"),
    ("qwen3-coder", "30b", 19.0, 256, "local"),
    ("qwen3-coder", "480b-cloud", None, 256, "cloud"),
    ("gemma4", "e2b", 7.2, 128, "local"),
    ("gemma4", "e4b", 9.6, 128, "local"),
    ("gemma4", "12b", 7.6, 256, "local"),
    ("gemma4", "26b", 18.0, 256, "local"),
    ("gemma4", "31b", 20.0, 256, "local"),
    ("kimi-k2.5", "cloud", None, 256, "cloud"),
    ("kimi-k2.6", "cloud", None, 256, "cloud"),
)


def build_candidate(
    family: str,
    variant: str,
    size_gb: float | None,
    context_k: int,
    runtime: str,
    *,
    source_state: str,
    last_checked: str | None = None,
) -> ModelCandidate:
    profile = FAMILY_PROFILES[family]
    parameters, active_parameters = profile.parameter_map.get(variant, (None, None))
    model_id = f"{family}:{variant}"
    return ModelCandidate(
        id=model_id,
        family=family,
        publisher=profile.publisher,
        display_name=f"{profile.display_name} {variant}",
        variant=variant,
        size_gb=size_gb,
        context_k=context_k,
        parameter_b=parameters,
        active_parameter_b=active_parameters,
        runtime=runtime,
        modalities=list(profile.modalities),
        capabilities=list(profile.capabilities),
        task_scores=dict(profile.task_scores),
        language_scores=dict(profile.language_scores),
        license_name=profile.license_name,
        official_url=f"https://ollama.com/library/{model_id}",
        publisher_url=profile.publisher_url,
        install_command=f"ollama pull {model_id}",
        trusted=True,
        source_state=source_state,
        last_checked=last_checked,
        notes=list(profile.notes),
    )


def seed_catalog() -> list[ModelCandidate]:
    return [
        build_candidate(family, variant, size, context, runtime, source_state="seed")
        for family, variant, size, context, runtime in SEED_VARIANTS
    ]
