import unittest

from mustakshif.installer import safe_official_url, validate_installable
from mustakshif.profiles import seed_catalog


class SecurityTests(unittest.TestCase):
    def test_only_https_allowlisted_domains_are_opened(self):
        self.assertTrue(safe_official_url("https://ollama.com/library/qwen3.5"))
        self.assertFalse(safe_official_url("http://ollama.com/library/qwen3.5"))
        self.assertFalse(safe_official_url("https://ollama.com.evil.example/model"))

    def test_shell_metacharacters_are_rejected(self):
        model = seed_catalog()[0]
        model.id = "qwen3.5:4b;whoami"
        with self.assertRaises(ValueError):
            validate_installable(model)

    def test_untrusted_model_is_rejected(self):
        model = seed_catalog()[0]
        model.trusted = False
        with self.assertRaises(ValueError):
            validate_installable(model)


if __name__ == "__main__":
    unittest.main()
