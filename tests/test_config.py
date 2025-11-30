import os
import unittest
from pathlib import Path

from auto_deployer.config import AppConfig, load_config


class ConfigTests(unittest.TestCase):
    def test_loads_default_config(self) -> None:
        config = load_config()
        self.assertIsInstance(config, AppConfig)
        self.assertEqual(config.deployment.default_max_retries, 3)
        self.assertEqual(config.llm.provider, "gemini")

    def test_loads_custom_config(self) -> None:
        temp_file = Path("tests/tmp_config.json")
        temp_file.write_text(
            """
{
  \"llm\": {\"provider\": \"custom\", \"model\": \"x\"},
  \"deployment\": {\"default_max_retries\": 5}
}
""".strip()
        )
        try:
            config = load_config(str(temp_file))
            self.assertEqual(config.llm.provider, "custom")
            self.assertEqual(config.deployment.default_max_retries, 5)
        finally:
            temp_file.unlink(missing_ok=True)

    def test_env_var_populates_api_key(self) -> None:
        temp_file = Path("tests/tmp_config_env.json")
        temp_file.write_text(
            """
{
  "llm": {"provider": "dummy", "model": "planning-v0", "api_key": null}
}
""".strip()
        )
        original = os.environ.get("AUTO_DEPLOYER_LLM_API_KEY")
        os.environ["AUTO_DEPLOYER_LLM_API_KEY"] = "secret-key"
        try:
            config = load_config(str(temp_file))
            self.assertEqual(config.llm.api_key, "secret-key")
        finally:
            temp_file.unlink(missing_ok=True)
            if original is None:
                os.environ.pop("AUTO_DEPLOYER_LLM_API_KEY", None)
            else:
                os.environ["AUTO_DEPLOYER_LLM_API_KEY"] = original

    def test_provider_specific_env_populates_api_key(self) -> None:
        temp_file = Path("tests/tmp_config_gemini.json")
        temp_file.write_text(
            """
{
  "llm": {"provider": "gemini", "model": "gemini-1.5"}
}
""".strip()
        )
        original_global = os.environ.get("AUTO_DEPLOYER_LLM_API_KEY")
        original_gemini = os.environ.get("AUTO_DEPLOYER_GEMINI_API_KEY")
        os.environ.pop("AUTO_DEPLOYER_LLM_API_KEY", None)
        os.environ["AUTO_DEPLOYER_GEMINI_API_KEY"] = "gemini-secret"
        try:
            config = load_config(str(temp_file))
            self.assertEqual(config.llm.api_key, "gemini-secret")
        finally:
            temp_file.unlink(missing_ok=True)
            if original_global is None:
                os.environ.pop("AUTO_DEPLOYER_LLM_API_KEY", None)
            else:
                os.environ["AUTO_DEPLOYER_LLM_API_KEY"] = original_global
            if original_gemini is None:
                os.environ.pop("AUTO_DEPLOYER_GEMINI_API_KEY", None)
            else:
                os.environ["AUTO_DEPLOYER_GEMINI_API_KEY"] = original_gemini


if __name__ == "__main__":
    unittest.main()
