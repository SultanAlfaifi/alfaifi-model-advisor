import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from mustakshif.catalog import CatalogService, parse_library_profiles, parse_ollama_tags
from mustakshif.profiles import build_candidate_from_profile, discovered_profile, seed_catalog


SAMPLE_PAGE = """
<a href="/library/qwen3.5:9b" class="model-row">
  <span>qwen3.5:9b</span>
  <span>6488c96fa5fa • 6.6GB • 256K context window • Text, Image input</span>
</a>
<a href="/library/qwen3.5:9b-q8_0" class="model-row">
  <span>qwen3.5:9b-q8_0</span>
  <span>abc • 11GB • 256K context window • Text, Image input</span>
</a>
"""

SAMPLE_LIBRARY = """
<a href="/library/example-code" class="group w-full space-y-5">
  <p class="max-w-lg break-words text-neutral-800 text-md">
    A multilingual coding model for software agents.
  </p>
  <div class="flex flex-wrap space-x-2">
    <span class="badge">tools</span>
    <span class="badge">thinking</span>
    <span class="badge">1.5b</span>
    <span class="badge">7b</span>
  </div>
  <span>1.2M</span><span class="hidden sm:flex">&nbsp;Pulls</span>
  <span>14</span><span class="hidden sm:flex">&nbsp;Tags</span>
  <span class="flex items-center" title="July 20, 2026 1:00 PM UTC">Updated</span>
</a>
"""

SAMPLE_DYNAMIC_TAGS = """
<a href="/library/example-code:1.5b" class="model-row">
  <span>example-code:1.5b</span>
  <span>digest • 1.1GB • 64K context window • Text input</span>
</a>
"""


class CatalogTests(unittest.TestCase):
    def test_official_page_parser_keeps_only_canonical_trusted_tag(self):
        profile = discovered_profile(
            "qwen3.5",
            "A multilingual model with tools and thinking.",
            {"vision", "tools", "thinking", "9b"},
        )
        self.assertIsNotNone(profile)
        models = parse_ollama_tags(
            "qwen3.5",
            SAMPLE_PAGE,
            "2026-07-22T00:00:00+00:00",
            profile,
        )
        self.assertEqual([model.id for model in models], ["qwen3.5:9b"])
        self.assertEqual(models[0].size_gb, 6.6)
        self.assertEqual(models[0].context_k, 256)
        self.assertEqual(models[0].source_state, "live")

    def test_offline_mode_uses_seed_when_cache_is_missing(self):
        with tempfile.TemporaryDirectory() as directory:
            service = CatalogService(cache_path=Path(directory) / "missing.json")
            models = service.load(offline=True)
        self.assertGreaterEqual(len(models), 10)
        self.assertTrue(all(model.trusted for model in models))
        self.assertIn(service.source_state, {"bundled", "seed"})

    def test_library_parser_discovers_unknown_official_family(self):
        profiles, discovered = parse_library_profiles(SAMPLE_LIBRARY)
        self.assertEqual(discovered, 1)
        self.assertEqual(len(profiles), 1)
        profile = profiles[0]
        self.assertEqual(profile.family, "example-code")
        self.assertIn("tools", profile.capabilities)
        self.assertIn("coding", profile.capabilities)
        self.assertEqual(profile.parameter_map["1.5b"], (1.5, None))
        self.assertEqual(profile.pulls, 1_200_000)
        self.assertEqual(profile.tag_count, 14)
        self.assertEqual(profile.updated_at, "July 20, 2026 1:00 PM UTC")

        models = parse_ollama_tags(
            profile.family,
            SAMPLE_DYNAMIC_TAGS,
            "2026-07-22T00:00:00+00:00",
            profile,
        )
        self.assertEqual([model.id for model in models], ["example-code:1.5b"])
        self.assertEqual(models[0].size_gb, 1.1)
        self.assertEqual(models[0].context_k, 64)
        self.assertTrue(models[0].license_name.startswith("License not indexed"))

    def test_dynamic_candidate_uses_official_ollama_url(self):
        profile = parse_library_profiles(SAMPLE_LIBRARY)[0][0]
        model = build_candidate_from_profile(
            profile,
            "7b",
            4.5,
            64,
            "local",
            source_state="live",
        )
        self.assertEqual(model.official_url, "https://ollama.com/library/example-code:7b")
        self.assertEqual(model.install_command, "ollama pull example-code:7b")

    def test_seed_ids_are_unique(self):
        ids = [model.id for model in seed_catalog()]
        self.assertEqual(len(ids), len(set(ids)))

    def test_publishers_use_identical_metadata_scoring_rules(self):
        badges = {"vision", "tools", "thinking", "9b"}
        description = "A multilingual model for agentic coding and document reasoning."
        qwen = discovered_profile("qwen-example", description, badges)
        other = discovered_profile("example-labs", description, badges)
        self.assertEqual(qwen.task_scores, other.task_scores)
        self.assertEqual(qwen.language_scores, other.language_scores)

    def test_small_remote_index_is_downloaded_and_cached_automatically(self):
        seed = seed_catalog()[:2]

        class IndexedCatalog(CatalogService):
            def _read_remote_index(self):
                return seed, datetime.now(timezone.utc), 233, 210

        with tempfile.TemporaryDirectory() as directory:
            cache = Path(directory) / "catalog.json"
            service = IndexedCatalog(cache_path=cache)
            models = service.load()
            self.assertTrue(cache.exists())
        self.assertEqual(models, seed)
        self.assertEqual(service.source_state, "index")
        self.assertEqual(service.discovered_family_count, 233)
        self.assertEqual(service.verified_family_count, 210)

    def test_bundled_catalog_is_large_unique_and_official(self):
        payload = json.loads(Path("data/catalog.json").read_text(encoding="utf-8"))
        models, checked, discovered, verified = CatalogService._payload_models(payload, "bundled")
        ids = [model.id for model in models]
        self.assertIsNotNone(checked)
        self.assertGreaterEqual(discovered, 150)
        self.assertGreaterEqual(verified, 150)
        self.assertGreaterEqual(len(models), 300)
        self.assertEqual(len(ids), len(set(ids)))
        self.assertIn("qwen3.6:27b", ids)
        self.assertTrue(all(model.official_url == f"https://ollama.com/library/{model.id}" for model in models))

    def test_downloaded_index_is_sanitized_before_use(self):
        safe = seed_catalog()[0].to_dict()
        safe["install_command"] = "powershell -Command evil"
        safe["publisher_url"] = "http://untrusted.invalid"
        payload = {
            "version": 3,
            "checked_at": "2026-07-24T00:00:00+00:00",
            "models": [safe],
        }
        models, *_ = CatalogService._payload_models(payload, "index")
        self.assertEqual(len(models), 1)
        self.assertEqual(models[0].install_command, f"ollama pull {models[0].id}")
        self.assertEqual(models[0].publisher_url, f"https://ollama.com/library/{models[0].family}")

        safe["official_url"] = "https://evil.invalid/model"
        payload["models"] = [safe]
        rejected, *_ = CatalogService._payload_models(payload, "index")
        self.assertEqual(rejected, [])

        safe["official_url"] = f"https://ollama.com/library/{safe['id']}"
        safe["size_gb"] = "not-a-number"
        payload["models"] = [safe]
        rejected, *_ = CatalogService._payload_models(payload, "index")
        self.assertEqual(rejected, [])


if __name__ == "__main__":
    unittest.main()
