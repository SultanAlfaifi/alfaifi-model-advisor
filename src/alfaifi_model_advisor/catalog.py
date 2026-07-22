from __future__ import annotations

import html as html_module
import json
import os
import re
import tempfile
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, Iterable

from .models import HardwareProfile, ModelCandidate, UserNeeds
from .profiles import (
    FAMILY_PROFILES,
    FamilyProfile,
    build_candidate_from_profile,
    discovered_profile,
    seed_catalog,
)


CACHE_VERSION = 2
CACHE_TTL = timedelta(hours=24)
TRUSTED_DOMAINS = {"ollama.com", "registry.ollama.com", "huggingface.co", "github.com"}
ProgressCallback = Callable[[str], None]


def default_cache_path() -> Path:
    base = os.getenv("LOCALAPPDATA")
    root = Path(base) if base else Path.home() / ".cache"
    return root / "SultanAlfaifi" / "AlfaifiModelAdvisor" / "catalog.json"


def _size_to_gb(value: str) -> float | None:
    match = re.fullmatch(r"([0-9.]+)\s*(GB|MB)", value.strip(), re.IGNORECASE)
    if not match:
        return None
    amount = float(match.group(1))
    return round(amount / 1024, 3) if match.group(2).upper() == "MB" else amount


def _context_to_k(value: str) -> int:
    match = re.fullmatch(r"([0-9.]+)\s*([KM]?)", value.strip(), re.IGNORECASE)
    if not match:
        return 0
    amount = float(match.group(1))
    unit = match.group(2).upper()
    if unit == "M":
        return int(amount * 1000)
    if unit == "K":
        return int(amount)
    return max(1, int(amount / 1000))


def _canonical_variant(variant: str) -> bool:
    if variant in {"latest"}:
        return False
    return bool(re.fullmatch(r"[a-z0-9][a-z0-9._-]{0,63}", variant, re.IGNORECASE))


def parse_library_profiles(page: str) -> tuple[list[FamilyProfile], int]:
    anchor = re.compile(
        r'<a\s+href="/library/(?P<family>[^"/:?#]+)"(?P<body>.{0,9000}?)</a>',
        re.IGNORECASE | re.DOTALL,
    )
    description_pattern = re.compile(
        r'<p\s+class="max-w-lg[^"]*">(?P<description>.*?)</p>',
        re.IGNORECASE | re.DOTALL,
    )
    badge_area_pattern = re.compile(
        r'<div\s+class="flex flex-wrap space-x-2">(?P<badges>.*?)</div>',
        re.IGNORECASE | re.DOTALL,
    )
    badge_pattern = re.compile(r">\s*([^<>]+?)\s*</span>", re.IGNORECASE)

    profiles: list[FamilyProfile] = []
    seen: set[str] = set()
    discovered_count = 0
    for match in anchor.finditer(page):
        family = html_module.unescape(match.group("family")).strip().lower()
        if family in seen or not re.fullmatch(r"[a-z0-9][a-z0-9._-]{0,80}", family):
            continue
        seen.add(family)
        discovered_count += 1
        if family in FAMILY_PROFILES:
            profiles.append(FAMILY_PROFILES[family])
            continue

        body = match.group("body")
        description_match = description_pattern.search(body)
        description = ""
        if description_match:
            description = re.sub(r"<[^>]+>", " ", description_match.group("description"))
            description = " ".join(html_module.unescape(description).split())
        badge_area = badge_area_pattern.search(body)
        badges = {
            " ".join(html_module.unescape(value).split()).lower()
            for value in badge_pattern.findall(badge_area.group("badges") if badge_area else "")
        }
        profile = discovered_profile(family, description, badges)
        if profile:
            profiles.append(profile)
    return profiles, discovered_count


def _license_from_page(page: str, fallback: str) -> str:
    if not fallback.startswith("License not indexed"):
        return fallback
    text = " ".join(html_module.unescape(re.sub(r"<[^>]+>", " ", page)).split()).lower()
    if "modified mit" in text:
        return "Modified MIT / verify model card"
    if "apache 2.0 license" in text or "apache license 2.0" in text:
        return "Apache-2.0 / verify model card"
    if "mit license" in text or "licensed under the mit" in text:
        return "MIT / verify model card"
    if "llama community license" in text or "llama 3.1 community license" in text:
        return "Llama Community License / verify model card"
    if "gemma terms of use" in text or "gemma license" in text:
        return "Gemma Terms / verify model card"
    return fallback


def parse_ollama_tags(
    family: str,
    page: str,
    checked_at: str,
    profile: FamilyProfile | None = None,
) -> list[ModelCandidate]:
    profile = profile or FAMILY_PROFILES[family]
    # Each tag is an anchor. Limiting the body avoids accidental cross-card matches.
    anchor = re.compile(
        rf'<a\s+href="/library/{re.escape(family)}:(?P<variant>[^"]+)"(?P<body>.{{0,2600}}?)</a>',
        re.IGNORECASE | re.DOTALL,
    )
    details = re.compile(
        r"•\s*(?P<size>[0-9.]+\s*(?:GB|MB)|(?:Low|Medium|High)\s+Usage)\s*"
        r"•\s*(?P<context>[0-9.]+\s*[KM]?)\s+context window",
        re.IGNORECASE,
    )
    candidates: dict[str, ModelCandidate] = {}
    for match in anchor.finditer(page):
        variant = html_module.unescape(match.group("variant")).strip()
        if not _canonical_variant(variant):
            continue
        if variant not in profile.parameter_map:
            continue
        detail = details.search(match.group("body"))
        if not detail:
            continue
        raw_size = detail.group("size")
        is_cloud = "usage" in raw_size.lower() or variant.endswith("-cloud") or variant == "cloud"
        size_gb = None if is_cloud else _size_to_gb(raw_size)
        context_k = _context_to_k(detail.group("context"))
        if size_gb is None and not is_cloud:
            continue
        candidates[variant] = build_candidate_from_profile(
            profile,
            variant,
            size_gb,
            context_k,
            "cloud" if is_cloud else "local",
            source_state="live",
            last_checked=checked_at,
        )
    return list(candidates.values())


class OllamaOfficialSource:
    def __init__(self, timeout: int = 15) -> None:
        self.timeout = timeout
        self.discovered_family_count = 0
        self.verified_family_count = 0

    def _read(self, url: str) -> str:
        request = urllib.request.Request(
            url,
            headers={"User-Agent": "AlfaifiModelAdvisor/0.2 (+https://github.com/SultanAlfaifi)"},
        )
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            return response.read().decode("utf-8", errors="replace")

    def fetch_family(self, profile: FamilyProfile, checked_at: str) -> list[ModelCandidate]:
        family = profile.family
        page = self._read(f"https://ollama.com/library/{family}/tags")
        if profile.license_name.startswith("License not indexed"):
            overview = self._read(f"https://ollama.com/library/{family}")
            profile = replace(profile, license_name=_license_from_page(overview, profile.license_name))
        values = parse_ollama_tags(family, page, checked_at, profile)
        if not values:
            raise ValueError(f"No trusted tags parsed for {family}")
        return values

    @staticmethod
    def _shortlist(
        profiles: list[FamilyProfile],
        needs: UserNeeds | None,
        hardware: HardwareProfile | None,
        limit: int,
    ) -> list[FamilyProfile]:
        ranked: list[tuple[float, int, FamilyProfile]] = []
        usable_memory = max(4.0, (hardware.ram_gb - 4.0) if hardware else 24.0)
        disk_limit = hardware.free_disk_gb if hardware and hardware.free_disk_gb else 200.0
        max_rough_parameters = min(usable_memory, disk_limit) / 0.52
        for order, profile in enumerate(profiles):
            if needs:
                if needs.needs_vision and "vision" not in profile.capabilities:
                    continue
                if needs.needs_tools and "tools" not in profile.capabilities:
                    continue
                if needs.locality == "local" and set(profile.parameter_map) == {"cloud"}:
                    continue
                local_parameters = [
                    values[0]
                    for variant, values in profile.parameter_map.items()
                    if variant != "cloud" and values[0] is not None
                ]
                if local_parameters and min(local_parameters) > max_rough_parameters * 1.35:
                    continue
                goal_scores = [profile.task_scores.get(goal, 2.5) for goal in needs.goals]
                relevance = sum(goal_scores) / max(1, len(goal_scores))
                relevance += profile.language_scores.get(needs.language, 3.0) * 0.2
            else:
                relevance = 3.0
            if profile.family in FAMILY_PROFILES:
                relevance += 0.45
            popularity_tiebreak = max(0.0, 1.0 - order / max(1, len(profiles)))
            ranked.append((relevance + popularity_tiebreak * 0.35, -order, profile))
        ranked.sort(reverse=True, key=lambda item: (item[0], item[1]))
        return [item[2] for item in ranked[:limit]]

    def fetch_all(
        self,
        *,
        needs: UserNeeds | None = None,
        hardware: HardwareProfile | None = None,
        progress: ProgressCallback | None = None,
    ) -> tuple[list[ModelCandidate], list[str]]:
        checked_at = datetime.now(timezone.utc).isoformat()
        models: list[ModelCandidate] = []
        errors: list[str] = []
        if progress:
            progress("Opening the official Ollama library...")
        try:
            library_page = self._read("https://ollama.com/library")
            profiles, discovered = parse_library_profiles(library_page)
            self.discovered_family_count = discovered
        except (OSError, ValueError, urllib.error.URLError) as exc:
            profiles = list(FAMILY_PROFILES.values())
            self.discovered_family_count = len(profiles)
            errors.append(f"library discovery: {exc}")

        shortlist = self._shortlist(profiles, needs, hardware, limit=36 if needs else 30)
        if progress:
            progress(
                f"Found {self.discovered_family_count} official families. "
                f"Verifying {len(shortlist)} relevant finalists..."
            )
        with ThreadPoolExecutor(max_workers=min(8, len(shortlist))) as pool:
            jobs = {
                pool.submit(self.fetch_family, profile, checked_at): profile.family
                for profile in shortlist
            }
            completed = 0
            for future in as_completed(jobs):
                family = jobs[future]
                try:
                    models.extend(future.result())
                except (OSError, ValueError, urllib.error.URLError) as exc:
                    errors.append(f"{family}: {exc}")
                completed += 1
                if progress and (completed == len(jobs) or completed % 4 == 0):
                    progress(f"Verified {completed}/{len(jobs)} families — building the shortlist...")
        self.verified_family_count = len(shortlist) - sum(
            1 for error in errors if not error.startswith("library discovery:")
        )
        if progress:
            progress(f"Scoring {len(models)} runnable model variants against your answers...")
        return models, errors


class CatalogService:
    def __init__(self, cache_path: Path | None = None, source: OllamaOfficialSource | None = None) -> None:
        self.cache_path = cache_path or default_cache_path()
        self.source = source or OllamaOfficialSource()
        self.last_errors: list[str] = []
        self.source_state = "seed"
        self.checked_at: str | None = None
        self.discovered_family_count = 0
        self.verified_family_count = 0

    def _read_cache(self) -> tuple[list[ModelCandidate], datetime | None]:
        try:
            payload = json.loads(self.cache_path.read_text(encoding="utf-8"))
            if payload.get("version") != CACHE_VERSION:
                return [], None
            checked = datetime.fromisoformat(payload["checked_at"])
            return [ModelCandidate.from_dict(item) for item in payload.get("models", [])], checked
        except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError):
            return [], None

    def _write_cache(self, models: Iterable[ModelCandidate], checked_at: datetime) -> None:
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": CACHE_VERSION,
            "checked_at": checked_at.isoformat(),
            "models": [item.to_dict() for item in models],
        }
        fd, temporary = tempfile.mkstemp(prefix="catalog-", suffix=".json", dir=str(self.cache_path.parent))
        os.close(fd)
        temp_path = Path(temporary)
        try:
            temp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            os.replace(temp_path, self.cache_path)
        finally:
            temp_path.unlink(missing_ok=True)

    @staticmethod
    def _merge(live: list[ModelCandidate], fallback: list[ModelCandidate]) -> list[ModelCandidate]:
        merged = {item.id: item for item in fallback}
        merged.update({item.id: item for item in live})
        return sorted(merged.values(), key=lambda item: (item.family, item.size_gb or 10_000, item.id))

    def load(
        self,
        *,
        offline: bool = False,
        force_refresh: bool = False,
        needs: UserNeeds | None = None,
        hardware: HardwareProfile | None = None,
        progress: ProgressCallback | None = None,
    ) -> list[ModelCandidate]:
        cached, cache_time = self._read_cache()
        now = datetime.now(timezone.utc)
        fresh = (
            cache_time is not None
            and now - cache_time.astimezone(timezone.utc) < CACHE_TTL
        )

        if offline:
            self.source_state = "cache" if cached else "seed"
            self.checked_at = cache_time.isoformat() if cache_time else None
            return cached or seed_catalog()

        if cached and fresh and not force_refresh:
            self.source_state = "cache"
            self.checked_at = cache_time.isoformat() if cache_time else None
            return cached

        live, errors = self.source.fetch_all(needs=needs, hardware=hardware, progress=progress)
        self.last_errors = errors
        self.discovered_family_count = self.source.discovered_family_count
        self.verified_family_count = self.source.verified_family_count
        if live:
            combined = self._merge(live, cached or seed_catalog())
            self._write_cache(combined, now)
            self.source_state = "live"
            self.checked_at = now.isoformat()
            return combined

        self.source_state = "cache" if cached else "seed"
        self.checked_at = cache_time.isoformat() if cache_time else None
        return cached or seed_catalog()
