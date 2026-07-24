from __future__ import annotations

import re
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
    description: str = ""
    pulls: int = 0
    tag_count: int = 0
    updated_at: str | None = None
    benchmark_score: float | None = None
    benchmark_source: str | None = None
    notes: tuple[str, ...] = ()


PUBLISHER_HINTS: tuple[tuple[tuple[str, ...], str, str], ...] = (
    (("qwen",), "Qwen", "https://huggingface.co/Qwen"),
    (("gemma", "google"), "Google", "https://huggingface.co/google"),
    (("llama", "meta"), "Meta", "https://huggingface.co/meta-llama"),
    (("deepseek",), "DeepSeek", "https://huggingface.co/deepseek-ai"),
    (("mistral", "mixtral", "ministral", "devstral"), "Mistral AI", "https://huggingface.co/mistralai"),
    (("phi", "microsoft"), "Microsoft", "https://huggingface.co/microsoft"),
    (("granite", "ibm"), "IBM", "https://huggingface.co/ibm-granite"),
    (("nemotron", "nvidia"), "NVIDIA", "https://huggingface.co/nvidia"),
    (("olmo", "tulu"), "Ai2", "https://huggingface.co/allenai"),
    (("kimi", "moonshot"), "Moonshot AI", "https://huggingface.co/moonshotai"),
    (("glm", "z.ai"), "Z.ai", "https://huggingface.co/zai-org"),
    (("minicpm", "openbmb"), "OpenBMB", "https://huggingface.co/openbmb"),
    (("gpt-oss", "openai"), "OpenAI", "https://huggingface.co/openai"),
    (("cohere", "command-r", "aya"), "Cohere", "https://huggingface.co/CohereForAI"),
    (("falcon",), "TII", "https://huggingface.co/tiiuae"),
)


def _parameter_values(variant: str) -> tuple[float | None, float | None]:
    """Read total and active parameter counts from an Ollama size badge."""
    value = variant.lower().strip()
    match = re.fullmatch(r"e([0-9]+(?:\.[0-9]+)?)b", value)
    if match:
        effective = float(match.group(1))
        return effective, effective
    match = re.fullmatch(r"([0-9]+(?:\.[0-9]+)?)m", value)
    if match:
        return round(float(match.group(1)) / 1000, 3), None
    match = re.fullmatch(r"([0-9]+(?:\.[0-9]+)?)b", value)
    if match:
        return float(match.group(1)), None
    match = re.fullmatch(r"([0-9]+(?:\.[0-9]+)?)x([0-9]+(?:\.[0-9]+)?)b", value)
    if match:
        experts, expert_size = map(float, match.groups())
        return experts * expert_size, expert_size
    match = re.fullmatch(r"([0-9]+(?:\.[0-9]+)?)b-a([0-9]+(?:\.[0-9]+)?)b", value)
    if match:
        total, active = map(float, match.groups())
        return total, active
    return None, None


def _uniform_capability_scores(searchable: str, badges: set[str]) -> tuple[set[str], set[str], dict[str, float]]:
    """Apply the same metadata rules to every publisher and family."""
    capabilities = {"chat", "writing", "documents"}
    modalities = {"text"}
    scores = {
        "general": 3.5,
        "writing": 3.4,
        "coding": 2.8,
        "agents": 2.7,
        "vision": 1.0,
        "documents": 3.2,
        "translation": 2.8,
        "reasoning": 3.0,
        "ui_design": 2.6,
    }

    if "tools" in badges or any(word in searchable for word in ("tool use", "tool-use", "function calling")):
        capabilities.update(("tools", "agents"))
        scores["agents"] = 4.2
        scores["coding"] = max(scores["coding"], 3.7)
    if "thinking" in badges or any(word in searchable for word in ("reasoning", "reasoner", "thinking", "math")):
        capabilities.add("reasoning")
        scores["reasoning"] = 4.4
        scores["general"] = max(scores["general"], 3.8)
    if "vision" in badges or any(word in searchable for word in ("multimodal", "image understanding", "visual")):
        capabilities.update(("vision", "ui_design"))
        modalities.add("image")
        scores.update({"vision": 4.3, "documents": 4.0, "ui_design": 4.0})
    if "audio" in badges:
        modalities.add("audio")
    if any(word in searchable for word in ("code", "coding", "software", "developer", "programming")):
        capabilities.add("coding")
        scores.update({"coding": 4.5, "agents": max(scores["agents"], 4.0), "ui_design": max(scores["ui_design"], 3.7)})
    if any(word in searchable for word in ("agentic", "agent ", "agents ", "autonomous")):
        capabilities.update(("agents", "tools"))
        scores["agents"] = 4.5
        scores["coding"] = max(scores["coding"], 3.9)
    if any(word in searchable for word in ("translate", "translation", "multilingual", "languages", "dialects")):
        capabilities.add("translation")
        scores["translation"] = 4.4
    if any(word in searchable for word in ("document", "pdf", "ocr", "retrieval", "rag")):
        capabilities.add("documents")
        scores["documents"] = 4.4
    if any(word in searchable for word in ("writing", "story", "creative", "summarization")):
        scores["writing"] = 4.3

    return capabilities, modalities, scores


def _uniform_language_scores(searchable: str) -> dict[str, float]:
    if any(word in searchable for word in ("arabic", "العربية", "arab culture", "middle east")):
        return {"ar": 4.8, "en": 3.8, "both": 4.3}
    if any(word in searchable for word in ("multilingual", "languages", "dialects", "translation")):
        return {"ar": 3.8, "en": 4.2, "both": 4.2}
    if any(word in searchable for word in ("chinese only", "korean only", "japanese only")):
        return {"ar": 2.0, "en": 3.0, "both": 2.5}
    return {"ar": 3.0, "en": 3.8, "both": 3.3}


def discovered_profile(
    family: str,
    description: str,
    badges: set[str],
    *,
    pulls: int = 0,
    tag_count: int = 0,
    updated_at: str | None = None,
) -> FamilyProfile | None:
    parameter_map = {
        badge: _parameter_values(badge)
        for badge in badges
        if _parameter_values(badge)[0] is not None
    }
    if "cloud" in badges:
        parameter_map["cloud"] = (None, None)
    if not parameter_map or ("embedding" in badges and not badges.intersection({"vision", "tools", "thinking"})):
        return None

    searchable = f"{family} {description}".lower()
    publisher = "Official Ollama library"
    publisher_url = f"https://ollama.com/library/{family}"
    for hints, name, url in PUBLISHER_HINTS:
        if any(hint in searchable for hint in hints):
            publisher, publisher_url = name, url
            break

    capabilities, modalities, scores = _uniform_capability_scores(searchable, badges)
    title = family.replace("-", " ").replace("_", " ").title()
    return FamilyProfile(
        family=family,
        publisher=publisher,
        display_name=title,
        publisher_url=publisher_url,
        license_name="License not indexed — verify official model page",
        capabilities=tuple(sorted(capabilities)),
        task_scores=scores,
        language_scores=_uniform_language_scores(searchable),
        modalities=tuple(sorted(modalities)),
        parameter_map=parameter_map,
        description=description,
        pulls=max(0, pulls),
        tag_count=max(0, tag_count),
        updated_at=updated_at,
        notes=("Capability estimates were derived uniformly from official Ollama metadata.",),
    )


def build_candidate_from_profile(
    profile: FamilyProfile,
    variant: str,
    size_gb: float | None,
    context_k: int,
    runtime: str,
    *,
    source_state: str,
    last_checked: str | None = None,
) -> ModelCandidate:
    family = profile.family
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
        description=profile.description,
        pulls=profile.pulls,
        tag_count=profile.tag_count,
        family_updated_at=profile.updated_at,
        benchmark_score=profile.benchmark_score,
        benchmark_source=profile.benchmark_source,
        trusted=True,
        source_state=source_state,
        last_checked=last_checked,
        notes=list(profile.notes),
    )


SEED_FAMILIES: tuple[dict[str, object], ...] = (
    {
        "family": "qwen3.5",
        "description": "An open-source multimodal model family with tools, thinking, and broad language support.",
        "badges": {"vision", "tools", "thinking", "cloud", "0.8b", "2b", "4b", "9b", "27b"},
        "pulls": 16_100_000,
        "variants": (("0.8b", 1.0, 256, "local"), ("2b", 2.7, 256, "local"), ("4b", 3.4, 256, "local"), ("9b", 6.6, 256, "local"), ("27b", 17.0, 256, "local")),
    },
    {
        "family": "gemma4",
        "description": "A multilingual multimodal family for reasoning, agentic workflows, coding, and document understanding.",
        "badges": {"vision", "tools", "thinking", "audio", "e2b", "e4b", "12b", "26b", "31b"},
        "pulls": 19_300_000,
        "variants": (("e2b", 7.2, 128, "local"), ("e4b", 9.6, 128, "local"), ("12b", 7.6, 256, "local")),
    },
    {
        "family": "granite4.1",
        "description": "An Apache-2.0 multilingual model family for coding, retrieval, tools, and structured output.",
        "badges": {"tools", "thinking", "3b", "8b", "30b"},
        "pulls": 275_000,
        "variants": (("3b", 2.4, 128, "local"), ("8b", 5.3, 128, "local")),
    },
    {
        "family": "deepseek-r1",
        "description": "An open reasoning model family for math, coding, and general problem solving.",
        "badges": {"thinking", "1.5b", "7b", "8b", "14b"},
        "pulls": 48_600_000,
        "variants": (("1.5b", 1.1, 128, "local"), ("7b", 4.7, 128, "local"), ("8b", 5.2, 128, "local")),
    },
    {
        "family": "llama3.2",
        "description": "A compact multilingual model family for local chat and tool use.",
        "badges": {"tools", "1b", "3b"},
        "pulls": 77_400_000,
        "variants": (("1b", 1.3, 128, "local"), ("3b", 2.0, 128, "local")),
    },
    {
        "family": "kimi-k2.6",
        "description": "A multilingual cloud model for multimodal agentic coding and autonomous tools.",
        "badges": {"vision", "tools", "thinking", "cloud"},
        "pulls": 395_000,
        "variants": (("cloud", None, 256, "cloud"),),
    },
)


def seed_catalog() -> list[ModelCandidate]:
    models: list[ModelCandidate] = []
    for item in SEED_FAMILIES:
        profile = discovered_profile(
            str(item["family"]),
            str(item["description"]),
            set(item["badges"]),
            pulls=int(item["pulls"]),
        )
        if not profile:
            continue
        for variant, size, context, runtime in item["variants"]:
            models.append(
                build_candidate_from_profile(
                    profile,
                    str(variant),
                    size,
                    int(context),
                    str(runtime),
                    source_state="seed",
                )
            )
    return models
