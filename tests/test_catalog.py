import tempfile
import unittest
from pathlib import Path

from alfaifi_model_advisor.catalog import CatalogService, parse_library_profiles, parse_ollama_tags
from alfaifi_model_advisor.profiles import build_candidate_from_profile, seed_catalog


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
        models = parse_ollama_tags("qwen3.5", SAMPLE_PAGE, "2026-07-22T00:00:00+00:00")
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
        self.assertEqual(service.source_state, "seed")

    def test_library_parser_discovers_unknown_official_family(self):
        profiles, discovered = parse_library_profiles(SAMPLE_LIBRARY)
        self.assertEqual(discovered, 1)
        self.assertEqual(len(profiles), 1)
        profile = profiles[0]
        self.assertEqual(profile.family, "example-code")
        self.assertIn("tools", profile.capabilities)
        self.assertIn("coding", profile.capabilities)
        self.assertEqual(profile.parameter_map["1.5b"], (1.5, None))

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


if __name__ == "__main__":
    unittest.main()
