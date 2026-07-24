import unittest

from mustakshif.models import GpuInfo, HardwareProfile, OllamaInfo, UserNeeds
from mustakshif.service import AdvisorService


class ServiceTests(unittest.TestCase):
    def test_offline_discovery_returns_a_complete_result(self):
        gpu = GpuInfo(
            name="Test GPU",
            vram_gb=8,
            free_vram_gb=8,
            vendor="Test",
            source="fixture",
            discrete=True,
        )
        hardware = HardwareProfile(
            os_name="Windows 11",
            machine="AMD64",
            cpu="Test CPU",
            physical_cores=8,
            logical_cores=16,
            ram_gb=32,
            free_ram_gb=24,
            gpus=[gpu],
            best_gpu=gpu,
            free_disk_gb=100,
            model_path="C:/models",
            ollama=OllamaInfo(installed=True, path="ollama"),
        )
        needs = UserNeeds(
            experience="intermediate",
            goals=["general"],
            language="both",
            priority="balanced",
            locality="local",
            needs_vision=False,
            needs_tools=False,
            context_size="medium",
        )

        result = AdvisorService().discover(needs, hardware=hardware, offline=True)

        self.assertIs(result.hardware, hardware)
        self.assertTrue(result.recommendations)
        self.assertIn(result.source_state, {"cache", "bundled", "seed"})
        self.assertGreater(result.candidate_count, 0)


if __name__ == "__main__":
    unittest.main()
