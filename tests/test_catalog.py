import tempfile
import unittest
from pathlib import Path

from alfaifi_model_advisor.catalog import CatalogService, parse_ollama_tags
from alfaifi_model_advisor.profiles import seed_catalog


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

    def test_seed_ids_are_unique(self):
        ids = [model.id for model in seed_catalog()]
        self.assertEqual(len(ids), len(set(ids)))


if __name__ == "__main__":
    unittest.main()
