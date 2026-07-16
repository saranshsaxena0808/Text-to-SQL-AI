from app.domain.entities.hallucination import (
    ConfidenceAssessment, ConfidenceComponent, ConfidencePolicy, ConfidenceSignals,
)
from app.domain.exceptions import ValidationConfigurationError


class ConfidenceEngine:
    _SIGNALS = (
        "syntax_score", "schema_coverage", "execution_success", "hallucination_score",
        "multi_query_agreement", "explainability",
    )

    def __init__(self, policy: ConfidencePolicy) -> None:
        self._policy = policy
        if set(policy.weights) != set(self._SIGNALS):
            raise ValidationConfigurationError("Confidence weights must define every signal exactly once")
        if any(weight <= 0 for weight in policy.weights.values()):
            raise ValidationConfigurationError("Confidence weights must be positive")

    def calculate(self, signals: ConfidenceSignals) -> ConfidenceAssessment:
        values = {
            "syntax_score": signals.syntax_score,
            "schema_coverage": signals.schema_coverage,
            "execution_success": signals.execution_success,
            "hallucination_score": 1.0 - signals.hallucination_probability,
            "multi_query_agreement": signals.multi_query_agreement,
            "explainability": signals.explainability,
        }
        total_weight = sum(self._policy.weights.values())
        components = tuple(ConfidenceComponent(
            name=name, raw_score=values[name], weight=self._policy.weights[name] / total_weight,
            contribution=values[name] * self._policy.weights[name] / total_weight,
        ) for name in self._SIGNALS)
        score = sum(component.contribution for component in components)
        warnings = self._warnings(score, signals, values)
        return ConfidenceAssessment(score=score, breakdown=components, warnings=warnings,
                                    policy_version=self._policy.version)

    def _warnings(self, score: float, signals: ConfidenceSignals,
                  values: dict[str, float]) -> tuple[str, ...]:
        warnings = []
        if score < self._policy.low_confidence_threshold:
            warnings.append("Overall confidence is below the configured threshold.")
        if signals.hallucination_probability >= self._policy.high_hallucination_threshold:
            warnings.append("Hallucination risk is elevated.")
        labels = {
            "syntax_score": "Syntax validation is weak.",
            "schema_coverage": "Schema coverage is incomplete.",
            "execution_success": "SQL execution was not successful.",
            "multi_query_agreement": "Independent SQL candidates disagree.",
            "explainability": "The generated explanation is weak.",
        }
        for name, warning in labels.items():
            if values[name] < self._policy.low_component_threshold:
                warnings.append(warning)
        return tuple(warnings)
