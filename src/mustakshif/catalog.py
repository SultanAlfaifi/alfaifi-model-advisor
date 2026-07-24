from __future__ import annotations

import html as html_module
import http.client
import json
import math
import os
import re
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, Iterable

from .models import HardwareProfile, ModelCandidate, UserNeeds
from .profiles import FamilyProfile, build_candidate_from_profile, discovered_profile, seed_catalog


CATALOG_SCHEMA_VERSION = 3
CACHE_TTL = timedelta(hours=24)
REMOTE_CATALOG_URL = "https://raw.githubusercontent.com/SultanAlfaifi/mustakshif/main/data/catalog.json"
TRUSTED_DOMAINS = {"ollama.com", "registry.ollama.com", "huggingface.co", "github.com"}
ProgressCallback = Callable[[str], None]


def default_cache_path() -> Path:
    base = os.getenv("LOCALAPPDATA")
    root = Path(base) if base else Path.home() / ".cache"
    return root / "SultanAlfaifi" / "Mustakshif" / "catalog.json"


def bundled_catalog_path() -> Path:
    bundle_root = getattr(sys, "_MEIPASS", None)
    if bundle_root:
        return Path(bundle_root) / "data" / "catalog.json"
    return Path(__file__).resolve().parents[2] / "data" / "catalog.json"


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


def _human_count(value: str) -> int:
    match = re.fullmatch(r"\s*([0-9]+(?:\.[0-9]+)?)\s*([KMB]?)\s*", value, re.IGNORECASE)
    if not match:
        return 0
    amount = float(match.group(1))
    multiplier = {"": 1, "K": 1_000, "M": 1_000_000, "B": 1_000_000_000}[match.group(2).upper()]
    return max(0, int(amount * multiplier))


def _canonical_variant(variant: str) -> bool:
    if variant in {"latest"}:
        return False
    return bool(re.fullmatch(r"[a-z0-9][a-z0-9._-]{0,63}", variant, re.IGNORECASE))


def _clean_text(value: str) -> str:
    return " ".join(html_module.unescape(re.sub(r"<[^>]+>", " ", value)).split())


def parse_library_profiles(page: str) -> tuple[list[FamilyProfile], int]:
    """Parse every runnable family listed in Ollama's official library."""
    anchor = re.compile(
        r'<a\s+href="/library/(?P<family>[^"/:?#]+)"(?P<body>.{0,12000}?)</a>',
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
    pulls_pattern = re.compile(
        r"<span[^>]*>\s*([0-9.]+\s*[KMB]?)\s*</span>\s*"
        r'<span[^>]*class="hidden sm:flex"[^>]*>\s*&nbsp;Pulls\s*</span>',
        re.IGNORECASE,
    )
    tags_pattern = re.compile(
        r"<span[^>]*>\s*([0-9]+)\s*</span>\s*"
        r'<span[^>]*class="hidden sm:flex"[^>]*>\s*&nbsp;Tags\s*</span>',
        re.IGNORECASE,
    )
    updated_pattern = re.compile(
        r'class="flex items-center"\s+title="([^"]+\sUTC)"',
        re.IGNORECASE,
    )

    profiles: list[FamilyProfile] = []
    seen: set[str] = set()
    discovered_count = 0
    for match in anchor.finditer(page):
        family = html_module.unescape(match.group("family")).strip().lower()
        if family in seen or not re.fullmatch(r"[a-z0-9][a-z0-9._-]{0,80}", family):
            continue
        seen.add(family)
        discovered_count += 1

        body = match.group("body")
        description_match = description_pattern.search(body)
        description = _clean_text(description_match.group("description")) if description_match else ""
        badge_area = badge_area_pattern.search(body)
        badges = {
            _clean_text(value).lower()
            for value in badge_pattern.findall(badge_area.group("badges") if badge_area else "")
        }
        pulls_match = pulls_pattern.search(body)
        tags_match = tags_pattern.search(body)
        updated_match = updated_pattern.search(body)
        profile = discovered_profile(
            family,
            description,
            badges,
            pulls=_human_count(pulls_match.group(1)) if pulls_match else 0,
            tag_count=int(tags_match.group(1)) if tags_match else 0,
            updated_at=updated_match.group(1) if updated_match else None,
        )
        if profile:
            profiles.append(profile)
    return profiles, discovered_count


def _license_from_page(page: str, fallback: str) -> str:
    if not fallback.startswith("License not indexed"):
        return fallback
    text = _clean_text(page).lower()
    if "modified mit" in text:
        return "Modified MIT / verify model card"
    if "apache 2.0 license" in text or "apache license 2.0" in text or "apache-2.0" in text:
        return "Apache-2.0 / verify model card"
    if "mit license" in text or "licensed under the mit" in text:
        return "MIT / verify model card"
    if "bsd-3-clause" in text or "bsd 3-clause" in text:
        return "BSD-3-Clause / verify model card"
    if "llama community license" in text or "llama 3.1 community license" in text:
        return "Llama Community License / verify model card"
    if "gemma terms of use" in text or "gemma license" in text:
        return "Gemma Terms / verify model card"
    return fallback


def parse_ollama_tags(
    family: str,
    page: str,
    checked_at: str,
    profile: FamilyProfile,
) -> list[ModelCandidate]:
    # Only canonical family variants from official badges are retained. Quantization
    # variants stay available on the official page without flooding recommendations.
    anchor = re.compile(
        rf'<a\s+href="/library/{re.escape(family)}:(?P<variant>[^"]+)"(?P<body>.{{0,3600}}?)</a>',
        re.IGNORECASE | re.DOTALL,
    )
    details = re.compile(
        r"(?:\u2022|\u00b7)\s*(?P<size>[0-9.]+\s*(?:GB|MB)|(?:Low|Medium|High)\s+Usage)\s*"
        r"(?:\u2022|\u00b7)\s*(?P<context>[0-9.]+\s*[KM]?)\s+context window",
        re.IGNORECASE,
    )
    candidates: dict[str, ModelCandidate] = {}
    for match in anchor.finditer(page):
        variant = html_module.unescape(match.group("variant")).strip()
        if not _canonical_variant(variant) or variant not in profile.parameter_map:
            continue
        detail = details.search(_clean_text(match.group("body")))
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
    def __init__(self, timeout: int = 20, workers: int = 12) -> None:
        self.timeout = timeout
        self.workers = max(1, workers)
        self.discovered_family_count = 0
        self.verified_family_count = 0

    def _read(self, url: str) -> str:
        last_error: Exception | None = None
        for _attempt in range(3):
            request = urllib.request.Request(
                url,
                headers={"User-Agent": "Mustakshif/0.4 (+https://github.com/SultanAlfaifi/mustakshif)"},
            )
            try:
                with urllib.request.urlopen(request, timeout=self.timeout) as response:
                    return response.read().decode("utf-8", errors="replace")
            except (OSError, TimeoutError, urllib.error.URLError, http.client.HTTPException) as exc:
                last_error = exc
        assert last_error is not None
        raise last_error

    def fetch_family(self, profile: FamilyProfile, checked_at: str) -> list[ModelCandidate]:
        family = profile.family
        page = self._read(f"https://ollama.com/library/{family}/tags")
        license_name = _license_from_page(page, profile.license_name)
        if license_name.startswith("License not indexed"):
            overview = self._read(f"https://ollama.com/library/{family}")
            license_name = _license_from_page(overview, license_name)
        profile = replace(profile, license_name=license_name)
        values = parse_ollama_tags(family, page, checked_at, profile)
        if not values:
            raise ValueError(f"No canonical runnable tags parsed for {family}")
        return values

    def fetch_all(
        self,
        *,
        needs: UserNeeds | None = None,
        hardware: HardwareProfile | None = None,
        progress: ProgressCallback | None = None,
    ) -> tuple[list[ModelCandidate], list[str]]:
        del needs, hardware  # Every official family is indexed before personal filtering.
        checked_at = datetime.now(timezone.utc).isoformat()
        models: list[ModelCandidate] = []
        errors: list[str] = []
        if progress:
            progress("Opening the complete official Ollama library...")
        try:
            library_page = self._read("https://ollama.com/library")
            profiles, discovered = parse_library_profiles(library_page)
            self.discovered_family_count = discovered
        except (OSError, ValueError, urllib.error.URLError) as exc:
            self.discovered_family_count = 0
            return [], [f"library discovery: {exc}"]

        if progress:
            progress(
                f"Found {self.discovered_family_count} official families. "
                f"Verifying all {len(profiles)} runnable families..."
            )
        successful = 0
        with ThreadPoolExecutor(max_workers=min(self.workers, max(1, len(profiles)))) as pool:
            jobs = {
                pool.submit(self.fetch_family, profile, checked_at): profile.family
                for profile in profiles
            }
            completed = 0
            for future in as_completed(jobs):
                family = jobs[future]
                try:
                    values = future.result()
                    models.extend(values)
                    successful += 1
                except (OSError, ValueError, urllib.error.URLError, http.client.HTTPException) as exc:
                    errors.append(f"{family}: {exc}")
                completed += 1
                if progress and (completed == len(jobs) or completed % 10 == 0):
                    progress(f"Verified {completed}/{len(jobs)} official families — building the evidence index...")

        self.verified_family_count = successful
        if progress:
            progress(f"Scoring {len(models)} runnable model variants against your answers...")
        return models, errors


def _clamp_scores(values: object) -> dict[str, float]:
    if not isinstance(values, dict):
        return {}
    result: dict[str, float] = {}
    for key, value in values.items():
        try:
            result[str(key)] = round(min(5.0, max(0.0, float(value))), 3)
        except (TypeError, ValueError):
            continue
    return result


def _bounded_float(
    value: object,
    *,
    minimum: float = 0.0,
    maximum: float = 10_000.0,
    optional: bool = False,
) -> float | None:
    if value is None and optional:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number) or number < minimum or number > maximum:
        return None
    return number


def _sanitize_index_model(value: object, source_state: str) -> ModelCandidate | None:
    if not isinstance(value, dict):
        return None
    try:
        model = ModelCandidate.from_dict(value)
    except (TypeError, ValueError):
        return None
    if not all(
        isinstance(item, str)
        for item in (
            model.id,
            model.family,
            model.variant,
            model.display_name,
            model.publisher,
            model.license_name,
            model.official_url,
            model.publisher_url,
            model.runtime,
        )
    ):
        return None
    if not re.fullmatch(r"[a-z0-9][a-z0-9._-]{0,80}", model.family, re.IGNORECASE):
        return None
    if not _canonical_variant(model.variant) or model.id != f"{model.family}:{model.variant}":
        return None
    parsed = urllib.parse.urlparse(model.official_url)
    expected_path = f"/library/{model.id}"
    if (
        parsed.scheme != "https"
        or parsed.netloc != "ollama.com"
        or parsed.path != expected_path
        or parsed.params
        or parsed.query
        or parsed.fragment
    ):
        return None
    publisher = urllib.parse.urlparse(model.publisher_url)
    publisher_url = model.publisher_url
    if publisher.scheme != "https" or publisher.hostname not in TRUSTED_DOMAINS:
        publisher_url = f"https://ollama.com/library/{model.family}"
    if model.runtime not in {"local", "cloud"}:
        return None
    size_gb = _bounded_float(model.size_gb, minimum=0.001, optional=True)
    if model.runtime == "local" and size_gb is None:
        return None
    try:
        context_k = int(model.context_k)
        pulls = max(0, min(10**12, int(model.pulls or 0)))
        tag_count = max(0, min(1_000_000, int(model.tag_count or 0)))
    except (TypeError, ValueError, OverflowError):
        return None
    if not 1 <= context_k <= 10_000:
        return None
    parameter_b = _bounded_float(model.parameter_b, optional=True)
    active_parameter_b = _bounded_float(model.active_parameter_b, optional=True)
    benchmark_score = _bounded_float(model.benchmark_score, maximum=5.0, optional=True)
    if not isinstance(model.modalities, list) or not isinstance(model.capabilities, list):
        return None
    modalities = sorted({str(item)[:80] for item in model.modalities if isinstance(item, str)})
    capabilities = sorted({str(item)[:80] for item in model.capabilities if isinstance(item, str)})
    return replace(
        model,
        display_name=model.display_name[:160],
        description=str(model.description or "")[:2_000],
        size_gb=size_gb,
        context_k=context_k,
        parameter_b=parameter_b,
        active_parameter_b=active_parameter_b,
        modalities=modalities,
        capabilities=capabilities,
        license_name=model.license_name[:240],
        publisher_url=publisher_url,
        install_command=f"ollama pull {model.id}",
        task_scores=_clamp_scores(model.task_scores),
        language_scores=_clamp_scores(model.language_scores),
        pulls=pulls,
        tag_count=tag_count,
        family_updated_at=(
            str(model.family_updated_at)[:160] if model.family_updated_at is not None else None
        ),
        benchmark_score=benchmark_score,
        benchmark_source=(
            str(model.benchmark_source)[:500] if model.benchmark_source is not None else None
        ),
        trusted=True,
        source_state=source_state,
        last_checked=str(model.last_checked)[:160] if model.last_checked is not None else None,
    )


class CatalogService:
    def __init__(
        self,
        cache_path: Path | None = None,
        source: OllamaOfficialSource | None = None,
        remote_catalog_url: str | None = REMOTE_CATALOG_URL,
    ) -> None:
        self.cache_path = cache_path or default_cache_path()
        self.source = source or OllamaOfficialSource()
        self.remote_catalog_url = remote_catalog_url
        self.last_errors: list[str] = []
        self.source_state = "seed"
        self.checked_at: str | None = None
        self.discovered_family_count = 0
        self.verified_family_count = 0

    @staticmethod
    def _payload_models(payload: object, source_state: str) -> tuple[list[ModelCandidate], datetime | None, int, int]:
        if not isinstance(payload, dict) or payload.get("version") != CATALOG_SCHEMA_VERSION:
            return [], None, 0, 0
        try:
            checked = datetime.fromisoformat(str(payload["checked_at"]))
        except (ValueError, TypeError, KeyError):
            return [], None, 0, 0
        models = [
            model
            for item in payload.get("models", [])
            if (model := _sanitize_index_model(item, source_state)) is not None
        ]
        discovered = max(0, int(payload.get("discovered_families", 0) or 0))
        verified = max(0, int(payload.get("verified_families", 0) or 0))
        return models, checked, discovered, verified

    def _read_cache(self) -> tuple[list[ModelCandidate], datetime | None, int, int]:
        try:
            payload = json.loads(self.cache_path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            return [], None, 0, 0
        return self._payload_models(payload, "cache")

    def _read_remote_index(self) -> tuple[list[ModelCandidate], datetime | None, int, int]:
        if not self.remote_catalog_url:
            return [], None, 0, 0
        request = urllib.request.Request(
            self.remote_catalog_url,
            headers={"User-Agent": "Mustakshif/0.4 (+https://github.com/SultanAlfaifi/mustakshif)"},
        )
        with urllib.request.urlopen(request, timeout=20) as response:
            payload = json.loads(response.read().decode("utf-8"))
        return self._payload_models(payload, "index")

    def _read_bundled_index(self) -> tuple[list[ModelCandidate], datetime | None, int, int]:
        try:
            payload = json.loads(bundled_catalog_path().read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            return [], None, 0, 0
        return self._payload_models(payload, "bundled")

    def _write_cache(
        self,
        models: Iterable[ModelCandidate],
        checked_at: datetime,
        discovered: int,
        verified: int,
    ) -> None:
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": CATALOG_SCHEMA_VERSION,
            "checked_at": checked_at.isoformat(),
            "discovered_families": discovered,
            "verified_families": verified,
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

    def _set_metadata(self, checked: datetime | None, discovered: int, verified: int) -> None:
        self.checked_at = checked.isoformat() if checked else None
        self.discovered_family_count = discovered
        self.verified_family_count = verified

    def load(
        self,
        *,
        offline: bool = False,
        force_refresh: bool = False,
        needs: UserNeeds | None = None,
        hardware: HardwareProfile | None = None,
        progress: ProgressCallback | None = None,
    ) -> list[ModelCandidate]:
        self.last_errors = []
        cached, cache_time, cached_discovered, cached_verified = self._read_cache()
        bundled, bundled_time, bundled_discovered, bundled_verified = self._read_bundled_index()
        now = datetime.now(timezone.utc)
        fresh = cache_time is not None and now - cache_time.astimezone(timezone.utc) < CACHE_TTL

        if offline:
            if cached:
                self.source_state = "cache"
                self._set_metadata(cache_time, cached_discovered, cached_verified)
                return cached
            if bundled:
                self.source_state = "bundled"
                self._set_metadata(bundled_time, bundled_discovered, bundled_verified)
                return bundled
            self.source_state = "seed"
            self._set_metadata(None, 0, 0)
            return seed_catalog()

        if cached and fresh and not force_refresh:
            self.source_state = "cache"
            self._set_metadata(cache_time, cached_discovered, cached_verified)
            return cached

        if not force_refresh and self.remote_catalog_url:
            if progress:
                progress("Downloading the small automatic Mustakshif catalog index...")
            try:
                indexed, index_time, discovered, verified = self._read_remote_index()
                if indexed and index_time:
                    self._write_cache(indexed, index_time, discovered, verified)
                    self.source_state = "index"
                    self._set_metadata(index_time, discovered, verified)
                    return indexed
            except (OSError, ValueError, TypeError, urllib.error.URLError, json.JSONDecodeError) as exc:
                self.last_errors.append(f"catalog index: {exc}")

        live, errors = self.source.fetch_all(needs=needs, hardware=hardware, progress=progress)
        self.last_errors.extend(errors)
        discovered = self.source.discovered_family_count
        verified = self.source.verified_family_count
        if live:
            combined = self._merge(live, cached)
            self._write_cache(combined, now, discovered, verified)
            self.source_state = "live"
            self._set_metadata(now, discovered, verified)
            return combined

        if cached:
            self.source_state = "cache"
            self._set_metadata(cache_time, cached_discovered, cached_verified)
            return cached
        if bundled:
            self.source_state = "bundled"
            self._set_metadata(bundled_time, bundled_discovered, bundled_verified)
            return bundled
        self.source_state = "seed"
        self._set_metadata(None, 0, 0)
        return seed_catalog()
