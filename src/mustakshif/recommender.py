from __future__ import annotations

import math
from dataclasses import replace
from datetime import datetime, timezone

from .models import HardwareProfile, ModelCandidate, Recommendation, UserNeeds


PERMISSIVE_LICENSE_MARKERS = ("apache", "mit", "bsd")


def _requested_context_k(needs: UserNeeds, model: ModelCandidate) -> int:
    requested = {"short": 4, "medium": 8, "long": 32}.get(needs.context_size, 8)
    return min(requested, max(1, model.context_k))


def _estimated_memory(model: ModelCandidate, context_k: int) -> float | None:
    if model.runtime == "cloud" or model.size_gb is None:
        return None
    # Reproducible estimate: quantized weights + runtime bookkeeping + KV cache.
    kv_and_runtime = 0.7 + 0.35 * max(1.0, context_k / 8)
    return round(model.size_gb + kv_and_runtime, 2)


def _hardware_mode(
    model: ModelCandidate,
    hardware: HardwareProfile,
    context_k: int,
) -> tuple[str, float | None, bool, list[str]]:
    if model.runtime == "cloud":
        return "cloud", None, True, ["The model runs through Ollama Cloud and requires an internet connection."]

    required = _estimated_memory(model, context_k)
    assert required is not None
    warnings: list[str] = []
    gpu_vram = hardware.best_gpu.vram_gb if hardware.best_gpu else 0.0
    safe_vram = gpu_vram * 0.90
    usable_ram = max(hardware.ram_gb - 4.0, hardware.ram_gb * 0.55)

    if safe_vram >= required:
        return "full_gpu", required, True, warnings
    if gpu_vram >= required:
        warnings.append("The estimated fit is close to total VRAM, so a 10% safety margin classifies it as hybrid.")
    if (
        hardware.best_gpu
        and safe_vram >= max(1.0, (model.size_gb or 0.0) * 0.25)
        and usable_ram >= max(0.0, required - safe_vram)
    ):
        warnings.append("Part of the model may be offloaded to system RAM, so it will be slower than full GPU execution.")
        return "hybrid", required, True, warnings
    if usable_ram >= required:
        if (model.size_gb or 0) > 10:
            warnings.append("The model fits in system RAM but is likely to be slow on the CPU.")
        else:
            warnings.append("Execution will rely mainly on the CPU and will be slower than GPU execution.")
        return "cpu", required, True, warnings
    return "not_fit", required, False, ["Available memory is insufficient after applying runtime safety margins."]


def _capacity_factor(model: ModelCandidate) -> float:
    if model.runtime == "cloud":
        return 1.0
    parameters = model.active_parameter_b or model.parameter_b or 1.0
    return min(1.0, 0.62 + math.log2(parameters + 1.0) * 0.12)


def _language_score(model: ModelCandidate, language: str) -> float:
    base = model.language_scores.get(language, model.language_scores.get("both", 3.0))
    return min(5.0, base * (0.82 + _capacity_factor(model) * 0.18))


def _task_score(model: ModelCandidate, goals: list[str]) -> float:
    values = [model.task_scores.get(goal, 2.5) for goal in goals]
    base = sum(values) / len(values) if values else model.task_scores.get("general", 3.0)
    return min(5.0, base * _capacity_factor(model))


def _speed_score(model: ModelCandidate, mode: str) -> float:
    if mode == "cloud":
        return 4.0
    mode_factor = {"full_gpu": 5.0, "hybrid": 3.1, "cpu": 2.0}.get(mode, 0.0)
    if model.size_gb is None:
        return mode_factor
    size_penalty = min(2.3, math.log2(max(model.size_gb, 1.0)) * 0.45)
    return max(0.5, mode_factor - size_penalty)


def _quality_score(model: ModelCandidate, task_score: float) -> float:
    parameters = model.active_parameter_b or model.parameter_b or 1.0
    scale = min(5.0, 1.4 + math.log2(max(parameters, 0.5) + 1) * 0.88)
    proxy = min(5.0, task_score * 0.58 + scale * 0.42)
    if model.benchmark_score is None:
        return proxy
    benchmark = min(5.0, max(0.0, model.benchmark_score))
    return min(5.0, benchmark * 0.70 + proxy * 0.30)


def _freshness_score(value: str | None) -> float:
    if not value:
        return 2.0
    checked: datetime | None = None
    try:
        checked = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        for pattern in ("%B %d, %Y %I:%M %p UTC", "%b %d, %Y %I:%M %p UTC"):
            try:
                checked = datetime.strptime(value, pattern).replace(tzinfo=timezone.utc)
                break
            except ValueError:
                continue
    if checked is None:
        return 2.0
    if checked.tzinfo is None:
        checked = checked.replace(tzinfo=timezone.utc)
    days = max(0, (datetime.now(timezone.utc) - checked.astimezone(timezone.utc)).days)
    if days <= 30:
        return 5.0
    if days <= 90:
        return 4.5
    if days <= 180:
        return 4.0
    if days <= 365:
        return 3.0
    if days <= 730:
        return 1.5
    return 0.5


def _confidence(model: ModelCandidate) -> str:
    license_known = not model.license_name.startswith("License not indexed")
    if model.benchmark_score is not None and license_known and model.pulls > 0:
        return "High"
    if model.pulls > 0 and model.family_updated_at:
        return "Medium"
    return "Low"


def _category_order(
    recommendations: list[Recommendation],
    metrics: dict[str, dict[str, float]],
    category: str,
) -> list[Recommendation]:
    if category == "best_quality":
        return sorted(
            recommendations,
            key=lambda item: (metrics[item.model.id]["quality"], item.score),
            reverse=True,
        )
    if category == "fastest":
        return sorted(
            recommendations,
            key=lambda item: (metrics[item.model.id]["speed"], item.score),
            reverse=True,
        )
    if category == "lightest":
        return sorted(
            recommendations,
            key=lambda item: (
                item.model.runtime != "local",
                item.estimated_memory_gb if item.estimated_memory_gb is not None else float("inf"),
                -item.score,
            ),
        )
    if category == "most_popular":
        return sorted(
            recommendations,
            key=lambda item: (item.model.pulls, item.score),
            reverse=True,
        )
    return sorted(recommendations, key=lambda item: (item.score, item.model.pulls), reverse=True)


def _diverse_categories(
    recommendations: list[Recommendation],
    metrics: dict[str, dict[str, float]],
    limit: int,
) -> list[Recommendation]:
    selected: list[Recommendation] = []
    used_ids: set[str] = set()
    used_families: set[str] = set()
    categories = ("best_overall", "best_quality", "fastest", "lightest", "most_popular")

    for category in categories[: max(0, limit)]:
        ordered = _category_order(recommendations, metrics, category)
        candidate = next(
            (item for item in ordered if item.model.id not in used_ids and item.model.family not in used_families),
            None,
        )
        if candidate is None:
            candidate = next((item for item in ordered if item.model.id not in used_ids), None)
        if candidate is None:
            continue
        selected.append(replace(candidate, category=category))
        used_ids.add(candidate.model.id)
        used_families.add(candidate.model.family)
    return selected


class RecommendationEngine:
    def recommend(
        self,
        models: list[ModelCandidate],
        hardware: HardwareProfile,
        needs: UserNeeds,
        *,
        limit: int = 5,
    ) -> tuple[list[Recommendation], list[tuple[ModelCandidate, str]]]:
        eligible: list[tuple[ModelCandidate, str, float | None, int, list[str]]] = []
        excluded: list[tuple[ModelCandidate, str]] = []

        for model in models:
            if not model.trusted:
                excluded.append((model, "Untrusted source"))
                continue
            if needs.locality == "local" and model.runtime != "local":
                excluded.append((model, "The user requested local-only execution"))
                continue
            if needs.permissive_license_only and not any(
                marker in model.license_name.lower() for marker in PERMISSIVE_LICENSE_MARKERS
            ):
                excluded.append((model, "The license does not match the selected preference"))
                continue
            if needs.needs_vision and "vision" not in model.capabilities:
                excluded.append((model, "No declared image-understanding support"))
                continue
            if needs.needs_tools and "tools" not in model.capabilities:
                excluded.append((model, "No declared tool-calling support"))
                continue
            if model.runtime == "local" and model.size_gb is not None:
                if hardware.free_disk_gb and hardware.free_disk_gb < model.size_gb + 2.0:
                    excluded.append((model, "Insufficient disk space"))
                    continue

            context_k = _requested_context_k(needs, model)
            mode, memory, fits, warnings = _hardware_mode(model, hardware, context_k)
            if not fits:
                excluded.append((model, warnings[0]))
                continue
            eligible.append((model, mode, memory, context_k, warnings))

        max_pulls = max((model.pulls for model, *_ in eligible), default=0)
        scored: list[Recommendation] = []
        metrics: dict[str, dict[str, float]] = {}
        for model, mode, memory, context_k, original_warnings in eligible:
            warnings = list(original_warnings)
            task = _task_score(model, needs.goals)
            language = _language_score(model, needs.language)
            speed = _speed_score(model, mode)
            quality = _quality_score(model, task)
            freshness = _freshness_score(model.family_updated_at)
            community = (
                math.log10(model.pulls + 1) / math.log10(max_pulls + 1) * 5
                if max_pulls > 0
                else 0.0
            )

            hardware_points = {"full_gpu": 30.0, "hybrid": 22.0, "cpu": 14.0, "cloud": 25.0}[mode]
            task_points = task / 5 * 25
            language_points = language / 5 * 15
            if needs.priority == "speed":
                speed_points = speed / 5 * 15
                quality_points = quality / 5 * 5
            elif needs.priority == "quality":
                speed_points = speed / 5 * 5
                quality_points = quality / 5 * 15
            elif needs.priority == "memory":
                compactness = (
                    3.0
                    if model.runtime == "cloud"
                    else max(0.5, 5.0 - math.log2(max(model.size_gb or 1, 1)) * 0.75)
                )
                speed_points = compactness / 5 * 15
                quality_points = quality / 5 * 5
            else:
                speed_points = speed / 5 * 10
                quality_points = quality / 5 * 10
            freshness_points = freshness
            community_points = community

            breakdown = {
                "hardware": round(hardware_points, 2),
                "task": round(task_points, 2),
                "language": round(language_points, 2),
                "speed": round(speed_points, 2),
                "quality": round(quality_points, 2),
                "community": round(community_points, 2),
                "freshness": round(freshness_points, 2),
            }
            score = round(min(100.0, sum(breakdown.values())), 1)
            if model.license_name.startswith("License not indexed"):
                warnings.append("The official entry does not expose a machine-readable license; verify the model page before use.")
            if model.benchmark_score is None:
                warnings.append("No standardized benchmark score is indexed; quality uses a transparent size-and-capability proxy.")

            pulls_label = f"{model.pulls:,}" if model.pulls else "not published"
            reasons = [
                f"Task fit: {task:.1f}/5 for the selected goals.",
                f"Language fit: {language:.1f}/5.",
                f"Community adoption: {pulls_label} Ollama pulls.",
                f"Freshness: {freshness:.1f}/5 from the official family update date.",
                {
                    "full_gpu": "The model fits inside the GPU after a 10% VRAM safety margin.",
                    "hybrid": "The model can run with weights distributed between GPU and system RAM.",
                    "cpu": "The model can run through system RAM and CPU execution.",
                    "cloud": "The model runs remotely, so local model memory is not required.",
                }[mode],
            ]
            scored.append(
                Recommendation(
                    model=model,
                    score=score,
                    confidence=_confidence(model),
                    hardware_mode=mode,
                    recommended_context_k=context_k,
                    estimated_memory_gb=memory,
                    reasons=reasons,
                    warnings=warnings,
                    score_breakdown=breakdown,
                )
            )
            metrics[model.id] = {"task": task, "language": language, "speed": speed, "quality": quality}

        return _diverse_categories(scored, metrics, limit), excluded
