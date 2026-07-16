import unittest

from pydantic import ValidationError

from app.config.settings import DatabaseSettings, ExecutionSettings, GroqSettings, RetrievalSettings


class SettingsTests(unittest.TestCase):
    def test_rejects_unbounded_sample_limit(self) -> None:
        with self.assertRaises(ValidationError):
            DatabaseSettings(sample_value_limit=21)

    def test_database_url_is_secret(self) -> None:
        settings = DatabaseSettings()
        self.assertNotIn("text2sql@", str(settings.url))

    def test_retrieval_limits_are_validated(self) -> None:
        with self.assertRaises(ValidationError):
            RetrievalSettings(top_k=0)

    def test_groq_attempts_are_bounded(self) -> None:
        with self.assertRaises(ValidationError):
            GroqSettings(max_attempts=11)

    def test_groq_api_key_is_secret(self) -> None:
        settings = GroqSettings(api_key="super-secret")
        self.assertNotIn("super-secret", str(settings.api_key))

    def test_execution_row_limit_is_bounded(self) -> None:
        with self.assertRaises(ValidationError):
            ExecutionSettings(max_rows=100001)
