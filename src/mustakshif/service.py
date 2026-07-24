from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from .catalog import CatalogService
from .hardware import HardwareInspector
from .models import HardwareProfile, Recommendation, UserNeeds
from .recommender import RecommendationEngine


ProgressCallback = Callable[[str], None]


@dataclass(slots=True)
class DiscoveryResult:
    hardware: HardwareProfile
    needs: UserNeeds
    recommendations: list[Recommendation]
    source_state: str
    checked_at: str | None
    source_errors: list[str]
    discovered_families: int
    verified_families: int
    candidate_count: int


class AdvisorService:
    """Shared application service used by both the desktop and CLI surfaces."""

    def scan_device(self) -> HardwareProfile:
        return HardwareInspector().scan()

    def discover(
        self,
        needs: UserNeeds,
        *,
        hardware: HardwareProfile | None = None,
        offline: bool = False,
        progress: ProgressCallback | None = None,
    ) -> DiscoveryResult:
        device = hardware or self.scan_device()
        catalog = CatalogService()
        models = catalog.load(
            offline=offline,
            force_refresh=False,
            needs=needs,
            hardware=device,
            progress=progress,
        )
        recommendations, _ = RecommendationEngine().recommend(models, device, needs)
        return DiscoveryResult(
            hardware=device,
            needs=needs,
            recommendations=recommendations,
            source_state=catalog.source_state,
            checked_at=catalog.checked_at,
            source_errors=list(catalog.last_errors),
            discovered_families=catalog.discovered_family_count,
            verified_families=catalog.verified_family_count,
            candidate_count=len(models),
        )
