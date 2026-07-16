import tempfile
import unittest
from pathlib import Path

from app.application.services.confidence_service import ConfidenceEngine
from app.domain.entities.hallucination import ConfidencePolicy, ConfidenceSignals
from app.domain.exceptions import ValidationConfigurationError
from app.infrastructure.validation.config import ValidationPolicyLoader
from app.application.services.hallucination_service import HallucinationEngine


def policy() -> ConfidencePolicy:
    return ConfidencePolicy(
        version="test", low_confidence_threshold=0.7, high_hallucination_threshold=0.4,
        low_component_threshold=0.5,
        weights={"syntax_score": 1, "schema_coverage": 1, "execution_success": 1,
                 "hallucination_score": 1, "multi_query_agreement": 1, "explainability": 1},
    )


class ConfidenceEngineTests(unittest.TestCase):
    def test_returns_weighted_score_and_breakdown(self) -> None:
        signals = ConfidenceSignals(syntax_score=1, schema_coverage=0.8, execution_success=1,
                                    hallucination_probability=0.2, multi_query_agreement=0.6,
                                    explainability=0.8)
        result = ConfidenceEngine(policy()).calculate(signals)
        self.assertAlmostEqual(result.score, 5.0 / 6.0)
        self.assertEqual(len(result.breakdown), 6)
        self.assertEqual(sum(item.contribution for item in result.breakdown), result.score)
        self.assertEqual(result.warnings, ())

    def test_returns_actionable_warnings(self) -> None:
        signals = ConfidenceSignals(syntax_score=0.4, schema_coverage=0.3, execution_success=0,
                                    hallucination_probability=0.8, multi_query_agreement=0.2,
                                    explainability=0.1)
        result = ConfidenceEngine(policy()).calculate(signals)
        self.assertIn("Overall confidence is below the configured threshold.", result.warnings)
        self.assertIn("Hallucination risk is elevated.", result.warnings)
        self.assertIn("SQL execution was not successful.", result.warnings)

    def test_invalid_weight_keys_fail_fast(self) -> None:
        bad = policy().model_copy(update={"weights": {"syntax_score": 1}})
        with self.assertRaises(ValidationConfigurationError):
            ConfidenceEngine(bad)


class ValidationConfigTests(unittest.TestCase):
    def test_loads_both_policy_types(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            confidence = root / "confidence.yaml"
            confidence.write_text(
                "version: v1\nweights:\n  syntax_score: 1\n  schema_coverage: 1\n"
                "  execution_success: 1\n  hallucination_score: 1\n"
                "  multi_query_agreement: 1\n  explainability: 1\n", encoding="utf-8")
            loaded = ValidationPolicyLoader.confidence(confidence)
        self.assertEqual(loaded.version, "v1")

    def test_shipped_policy_files_are_valid(self) -> None:
        root = Path(__file__).parents[2] / "config"
        confidence = ValidationPolicyLoader.confidence(root / "confidence.yaml")
        hallucination = ValidationPolicyLoader.hallucination(root / "hallucination.yaml")
        ConfidenceEngine(confidence)
        HallucinationEngine([], hallucination)
        self.assertEqual(confidence.version, "v1")
        self.assertEqual(hallucination.version, "v1")
