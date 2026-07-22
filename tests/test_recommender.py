import unittest

from alfaifi_model_advisor.models import GpuInfo, HardwareProfile, OllamaInfo, UserNeeds
from alfaifi_model_advisor.profiles import seed_catalog
from alfaifi_model_advisor.recommender import RecommendationEngine


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

    def test_rtx_4060_class_device_prefers_qwen_9b_for_bilingual_general_use(self):
        results, _ = self.engine.recommend(self.models, hardware(32, 8), needs())
        self.assertTrue(results)
        self.assertEqual(results[0].model.id, "qwen3.5:9b")
        self.assertEqual(results[0].hardware_mode, "full_gpu")

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


if __name__ == "__main__":
    unittest.main()
