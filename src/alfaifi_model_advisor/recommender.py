from __future__ import annotations

import math

from .models import HardwareProfile, ModelCandidate, Recommendation, UserNeeds


PERMISSIVE_LICENSE_MARKERS = ("apache", "mit", "bsd")


def _requested_context_k(needs: UserNeeds, model: ModelCandidate) -> int:
    requested = {"short": 4, "medium": 8, "long": 32}.get(needs.context_size, 8)
    return min(requested, max(1, model.context_k))


def _estimated_memory(model: ModelCandidate, context_k: int) -> float | None:
    if model.runtime == "cloud" or model.size_gb is None:
        return None
    # Conservative practical estimate: weights + runtime bookkeeping + KV cache.
    kv_and_runtime = 0.7 + 0.35 * max(1.0, context_k / 8)
    # Preserve two decimals for fit decisions; the UI may display fewer digits.
    return round(model.size_gb + kv_and_runtime, 2)


def _hardware_mode(
    model: ModelCandidate,
    hardware: HardwareProfile,
    context_k: int,
) -> tuple[str, float | None, bool, list[str]]:
    if model.runtime == "cloud":
        return "cloud", None, True, ["Runs through a cloud service and does not store the model weights in local VRAM."]

    required = _estimated_memory(model, context_k)
    assert required is not None
    warnings: list[str] = []
    gpu_vram = hardware.best_gpu.vram_gb if hardware.best_gpu else 0.0
    # Keep an OS reserve without making 8 GB computers appear unusable.
    usable_ram = max(hardware.ram_gb - 4.0, hardware.ram_gb * 0.55)

    if gpu_vram >= required:
        return "full_gpu", required, True, warnings
    if hardware.best_gpu and gpu_vram >= max(1.0, model.size_gb * 0.45) and usable_ram >= required - gpu_vram:
        warnings.append("Part of the model will be offloaded to system RAM, so it will be slower than full GPU execution.")
        return "hybrid", required, True, warnings
    if usable_ram >= required:
        if model.size_gb > 10:
            warnings.append("The model fits in system RAM but may be very slow on the CPU.")
        else:
            warnings.append("Execution will rely mainly on the CPU and will be slower than GPU execution.")
        return "cpu", required, True, warnings
    return "not_fit", required, False, ["Available memory is insufficient after applying a safe runtime margin."]


def _language_score(model: ModelCandidate, language: str) -> float:
    base = model.language_scores.get(language, model.language_scores.get("both", 3.0))
    return base * (0.8 + _capacity_factor(model) * 0.2)


def _task_score(model: ModelCandidate, goals: list[str]) -> float:
    values = [model.task_scores.get(goal, 2.5) for goal in goals]
    base = sum(values) / len(values) if values else model.task_scores.get("general", 3.0)
    return base * _capacity_factor(model)


def _capacity_factor(model: ModelCandidate) -> float:
    """Scale family-level capability claims by the selected model size."""
    if model.runtime == "cloud":
        return 1.0
    parameters = model.parameter_b or 1.0
    return min(1.0, 0.62 + math.log2(parameters + 1.0) * 0.12)


def _speed_score(model: ModelCandidate, mode: str) -> float:
    if mode == "cloud":
        return 4.0
    mode_factor = {"full_gpu": 5.0, "hybrid": 3.2, "cpu": 2.2}.get(mode, 0.0)
    if model.size_gb is None:
        return mode_factor
    size_penalty = min(2.2, math.log2(max(model.size_gb, 1.0)) * 0.45)
    return max(0.5, mode_factor - size_penalty)


def _quality_score(model: ModelCandidate, task_score: float) -> float:
    parameters = model.active_parameter_b or model.parameter_b or 1.0
    scale = min(5.0, 1.5 + math.log2(max(parameters, 0.8) + 1) * 0.85)
    return min(5.0, task_score * 0.65 + scale * 0.35)


class RecommendationEngine:
    def recommend(
        self,
        models: list[ModelCandidate],
        hardware: HardwareProfile,
        needs: UserNeeds,
        *,
        limit: int = 3,
    ) -> tuple[list[Recommendation], list[tuple[ModelCandidate, str]]]:
        recommendations: list[Recommendation] = []
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
                required_disk = model.size_gb + 2.0
                if hardware.free_disk_gb and hardware.free_disk_gb < required_disk:
                    excluded.append((model, "Insufficient disk space"))
                    continue

            context_k = _requested_context_k(needs, model)
            mode, memory, fits, warnings = _hardware_mode(model, hardware, context_k)
            if not fits:
                excluded.append((model, warnings[0]))
                continue

            dynamically_discovered = any(
                note.startswith("Discovered dynamically") for note in model.notes
            )
            license_unverified = model.license_name.startswith("License not indexed")
            if license_unverified:
                warnings.append(
                    "The official Ollama entry does not expose a machine-readable license; review the model page before use."
                )

            task = _task_score(model, needs.goals)
            language = _language_score(model, needs.language)
            speed = _speed_score(model, mode)
            quality = _quality_score(model, task)
            hardware_points = {"full_gpu": 30, "hybrid": 23, "cpu": 16, "cloud": 27}[mode]
            task_points = task / 5 * 25
            language_points = language / 5 * 15

            if needs.priority == "speed":
                performance_points = speed / 5 * 15
                quality_points = quality / 5 * 5
            elif needs.priority == "quality":
                performance_points = speed / 5 * 5
                quality_points = quality / 5 * 15
            elif needs.priority == "memory":
                compactness = 5.0 if model.runtime == "cloud" else max(0.5, 5.0 - math.log2(max(model.size_gb or 1, 1)) * 0.75)
                performance_points = compactness / 5 * 15
                quality_points = quality / 5 * 5
            else:
                performance_points = speed / 5 * 10
                quality_points = quality / 5 * 10

            trust_points = 3.0
            if model.source_state == "live":
                trust_points += 2.0
            elif model.source_state == "cache":
                trust_points += 1.2
            else:
                trust_points += 0.6

            score = round(
                hardware_points
                + task_points
                + language_points
                + performance_points
                + quality_points
                + trust_points,
                1,
            )
            if dynamically_discovered:
                score = round(score - 2.0, 1)
            if license_unverified:
                score = round(score - 1.5, 1)
            reasons = [
                f"Task fit: {task:.1f}/5 for the selected goals.",
                f"Language fit: {language:.1f}/5.",
                {
                    "full_gpu": "The model should fit fully in VRAM at the recommended starting context.",
                    "hybrid": "The model can run with weights distributed between GPU and system RAM.",
                    "cpu": "The model can run through system RAM and CPU execution.",
                    "cloud": "Performance does not depend on local hardware, but an internet connection is required.",
                }[mode],
            ]
            if dynamically_discovered or license_unverified:
                reasons.append("The family was discovered from the live official Ollama catalog and ranked conservatively.")
            confidence = (
                "High"
                if model.source_state == "live"
                and not dynamically_discovered
                and not license_unverified
                and (mode == "cloud" or hardware.best_gpu)
                else "Medium"
            )
            recommendations.append(
                Recommendation(
                    model=model,
                    score=score,
                    confidence=confidence,
                    hardware_mode=mode,
                    recommended_context_k=context_k,
                    estimated_memory_gb=memory,
                    reasons=reasons,
                    warnings=warnings,
                )
            )

        recommendations.sort(key=lambda item: (item.score, item.model.parameter_b or 0), reverse=True)
        return recommendations[:limit], excluded
