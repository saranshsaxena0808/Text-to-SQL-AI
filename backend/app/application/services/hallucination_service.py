from app.application.dto.validation import HallucinationContext
from app.application.interfaces.validation import HallucinationCheck
from app.domain.entities.hallucination import (
    HallucinationAssessment, HallucinationPolicy, ValidationEvidence,
)
from app.domain.exceptions import ValidationConfigurationError


class HallucinationEngine:
    def __init__(self, checks: list[HallucinationCheck], policy: HallucinationPolicy) -> None:
        self._checks = tuple(checks)
        self._policy = policy
        names = [check.name for check in checks]
        if len(names) != len(set(names)):
            raise ValidationConfigurationError("Hallucination check names must be unique")
        missing = set(names) - set(policy.weights)
        if missing or any(weight < 0 for weight in policy.weights.values()):
            raise ValidationConfigurationError("Hallucination weights are missing or invalid")

    def evaluate(self, context: HallucinationContext) -> HallucinationAssessment:
        evidence = tuple(self._safe_evaluate(check, context) for check in self._checks)
        weighted = [(item, self._policy.weights[item.check]) for item in evidence
                    if item.available and self._policy.weights[item.check] > 0]
        denominator = sum(weight for _, weight in weighted)
        probability = (sum(item.risk * weight for item, weight in weighted) / denominator
                       if denominator else 1.0)
        highest = sorted((item for item in evidence if item.available),
                         key=lambda item: item.risk, reverse=True)[:3]
        explanation = ("; ".join(f"{item.check}: {item.explanation}" for item in highest)
                       if highest else "No validation evidence was available; assessment failed closed.")
        return HallucinationAssessment(probability=probability, explanation=explanation,
                                       evidence=evidence, policy_version=self._policy.version)

    @staticmethod
    def _safe_evaluate(check: HallucinationCheck,
                       context: HallucinationContext) -> ValidationEvidence:
        try:
            return check.evaluate(context)
        except Exception:
            return ValidationEvidence(check=check.name, available=False, risk=0,
                                      explanation="Check was unavailable due to an internal validation error.")
