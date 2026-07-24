import unittest

from mustakshif.models import GpuInfo, HardwareProfile, OllamaInfo, UserNeeds
from mustakshif.catalog import parse_library_profiles
from mustakshif.profiles import build_candidate_from_profile, discovered_profile, seed_catalog
from mustakshif.recommender import RecommendationEngine


def hardware(ram: float, vram: float = 0, disk: float = 200) -> HardwareProfile:
    gpu = (
        GpuInfo(
            name="Test GPU",
            vram_gb=vram,
            free_vram_gb=vram,
            vendor="Test",
            source="fixture",
            discrete=True,
        )
        if vram
        else None
    )
    return HardwareProfile(
        os_name="Windows 11",
        machine="AMD64",
        cpu="Test CPU",
        physical_cores=8,
        logical_cores=16,
        ram_gb=ram,
        free_ram_gb=max(1, ram - 4),
        gpus=[gpu] if gpu else [],
        best_gpu=gpu,
        free_disk_gb=disk,
        model_path="C:/models",
        ollama=OllamaInfo(installed=True, path="ollama"),
    )


def needs(**overrides) -> UserNeeds:
    values = dict(
        experience="intermediate",
        goals=["general"],
        language="both",
        priority="balanced",
        locality="local",
        needs_vision=False,
        needs_tools=False,
        context_size="medium",
        permissive_license_only=False,
    )
    values.update(overrides)
    return UserNeeds(**values)


class RecommenderTests(unittest.TestCase):
    def setUp(self):
        self.models = seed_catalog()
        self.engine = RecommendationEngine()

    def test_weak_cpu_device_gets_a_small_local_model(self):
        results, _ = self.engine.recommend(self.models, hardware(8), needs())
        self.assertTrue(results)
        self.assertLessEqual(results[0].model.size_gb or 999, 2.7)
        self.assertEqual(results[0].model.runtime, "local")

    def test_vram_safety_margin_marks_borderline_model_as_hybrid(self):
        qwen = next(model for model in self.models if model.id == "qwen3.5:9b")
        results, _ = self.engine.recommend([qwen], hardware(32, 8), needs())
        self.assertTrue(results)
        self.assertEqual(results[0].hardware_mode, "hybrid")
        self.assertTrue(any("10% safety margin" in warning for warning in results[0].warnings))

    def test_local_only_excludes_kimi_cloud(self):
        results, _ = self.engine.recommend(
            self.models,
            hardware(32, 8),
            needs(goals=["agents", "coding"], locality="local", needs_tools=True),
            limit=20,
        )
        self.assertFalse(any(item.model.family.startswith("kimi") for item in results))

    def test_cloud_allowed_can_recommend_kimi_for_agentic_design(self):
        results, _ = self.engine.recommend(
            self.models,
            hardware(16, 4),
            needs(
                goals=["agents", "coding", "ui_design"],
                language="en",
                locality="both",
                needs_vision=True,
                needs_tools=True,
                priority="quality",
            ),
        )
        self.assertTrue(any(item.model.family.startswith("kimi") for item in results))

    def test_insufficient_disk_excludes_large_local_models(self):
        results, _ = self.engine.recommend(self.models, hardware(64, 24, disk=5), needs(), limit=20)
        self.assertTrue(all((item.model.size_gb or 0) <= 3 for item in results))

    def test_unknown_dynamic_license_is_excluded_when_permissive_is_required(self):
        page = """
        <a href="/library/example">
          <p class="max-w-lg">A general model.</p>
          <div class="flex flex-wrap space-x-2"><span>7b</span></div>
        </a>
        """
        profile = parse_library_profiles(page)[0][0]
        model = build_candidate_from_profile(
            profile,
            "7b",
            4.5,
            32,
            "local",
            source_state="live",
        )
        results, excluded = self.engine.recommend(
            [model],
            hardware(32, 8),
            needs(permissive_license_only=True),
        )
        self.assertEqual(results, [])
        self.assertEqual(excluded[0][1], "The license does not match the selected preference")

    def test_identical_metadata_produces_identical_scores_across_publishers(self):
        description = "A multilingual model for agentic coding and reasoning."
        badges = {"tools", "thinking", "8b"}
        first = discovered_profile(
            "qwen-example",
            description,
            badges,
            pulls=100_000,
            updated_at="July 20, 2026 1:00 PM UTC",
        )
        second = discovered_profile(
            "independent-example",
            description,
            badges,
            pulls=100_000,
            updated_at="July 20, 2026 1:00 PM UTC",
        )
        models = [
            build_candidate_from_profile(profile, "8b", 5.0, 32, "local", source_state="live")
            for profile in (first, second)
        ]
        results, _ = self.engine.recommend(models, hardware(32, 12), needs(), limit=2)
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0].score, results[1].score)

    def test_shortlist_is_diverse_across_families(self):
        results, _ = self.engine.recommend(self.models, hardware(32, 8), needs(), limit=5)
        families = [item.model.family for item in results]
        self.assertEqual(len(families), len(set(families)))
        self.assertEqual(
            [item.category for item in results],
            ["best_overall", "best_quality", "fastest", "lightest", "most_popular"],
        )

    def test_community_popularity_is_capped_at_five_points(self):
        profile_a = discovered_profile(
            "model-a",
            "A general multilingual model.",
            {"7b"},
            pulls=0,
            updated_at="July 20, 2026 1:00 PM UTC",
        )
        profile_b = discovered_profile(
            "model-b",
            "A general multilingual model.",
            {"7b"},
            pulls=10_000_000,
            updated_at="July 20, 2026 1:00 PM UTC",
        )
        models = [
            build_candidate_from_profile(profile, "7b", 4.5, 32, "local", source_state="live")
            for profile in (profile_a, profile_b)
        ]
        results, _ = self.engine.recommend(models, hardware(32, 12), needs(), limit=2)
        by_id = {item.model.id: item for item in results}
        difference = by_id["model-b:7b"].score - by_id["model-a:7b"].score
        self.assertGreater(difference, 0)
        self.assertLessEqual(difference, 5.0)


if __name__ == "__main__":
    unittest.main()
