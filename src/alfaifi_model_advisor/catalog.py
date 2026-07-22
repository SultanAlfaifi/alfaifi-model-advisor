from __future__ import annotations

import html as html_module
import json
import os
import re
import tempfile
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable

from .models import ModelCandidate
from .profiles import FAMILY_PROFILES, build_candidate, seed_catalog


CACHE_VERSION = 1
CACHE_TTL = timedelta(hours=24)
TRUSTED_DOMAINS = {"ollama.com", "registry.ollama.com", "huggingface.co", "github.com"}


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
    return bool(
        re.fullmatch(
            r"(?:e?[0-9]+(?:\.[0-9]+)?b|[0-9]+(?:\.[0-9]+)?b-cloud|cloud)",
            variant,
            re.IGNORECASE,
        )
    )


def parse_ollama_tags(family: str, page: str, checked_at: str) -> list[ModelCandidate]:
    profile = FAMILY_PROFILES[family]
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
        detail = details.search(match.group("body"))
        if not detail:
            continue
        raw_size = detail.group("size")
        is_cloud = "usage" in raw_size.lower() or variant.endswith("-cloud") or variant == "cloud"
        size_gb = None if is_cloud else _size_to_gb(raw_size)
        context_k = _context_to_k(detail.group("context"))
        if size_gb is None and not is_cloud:
            continue
        if variant not in profile.parameter_map:
            # A new official size is visible but cannot be safely scored until its
            # parameter layout is known. It is intentionally skipped, not guessed.
            continue
        candidates[variant] = build_candidate(
            family,
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

    def fetch_family(self, family: str, checked_at: str) -> list[ModelCandidate]:
        url = f"https://ollama.com/library/{family}/tags"
        request = urllib.request.Request(
            url,
            headers={"User-Agent": "AlfaifiModelAdvisor/0.1 (+https://x.com/SultAlfaifi)"},
        )
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            page = response.read().decode("utf-8", errors="replace")
        values = parse_ollama_tags(family, page, checked_at)
        if not values:
            raise ValueError(f"No trusted tags parsed for {family}")
        return values

    def fetch_all(self) -> tuple[list[ModelCandidate], list[str]]:
        checked_at = datetime.now(timezone.utc).isoformat()
        models: list[ModelCandidate] = []
        errors: list[str] = []
        with ThreadPoolExecutor(max_workers=min(5, len(FAMILY_PROFILES))) as pool:
            jobs = {
                pool.submit(self.fetch_family, family, checked_at): family
                for family in FAMILY_PROFILES
            }
            for future in as_completed(jobs):
                family = jobs[future]
                try:
                    models.extend(future.result())
                except (OSError, ValueError, urllib.error.URLError) as exc:
                    errors.append(f"{family}: {exc}")
        return models, errors


class CatalogService:
    def __init__(self, cache_path: Path | None = None, source: OllamaOfficialSource | None = None) -> None:
        self.cache_path = cache_path or default_cache_path()
        self.source = source or OllamaOfficialSource()
        self.last_errors: list[str] = []
        self.source_state = "seed"
        self.checked_at: str | None = None

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

    def load(self, *, offline: bool = False, force_refresh: bool = False) -> list[ModelCandidate]:
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

        live, errors = self.source.fetch_all()
        self.last_errors = errors
        if live:
            combined = self._merge(live, cached or seed_catalog())
            self._write_cache(combined, now)
            self.source_state = "live"
            self.checked_at = now.isoformat()
            return combined

        self.source_state = "cache" if cached else "seed"
        self.checked_at = cache_time.isoformat() if cache_time else None
        return cached or seed_catalog()
