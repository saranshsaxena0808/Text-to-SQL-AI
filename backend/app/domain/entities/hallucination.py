from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ValidationEvidence(BaseModel):
    model_config = ConfigDict(frozen=True)
    check: str
    available: bool = True
    risk: float = Field(ge=0.0, le=1.0)
    explanation: str
    details: dict[str, Any] = Field(default_factory=dict)


class HallucinationAssessment(BaseModel):
    model_config = ConfigDict(frozen=True)
    probability: float = Field(ge=0.0, le=1.0)
    explanation: str
    evidence: tuple[ValidationEvidence, ...]
    policy_version: str


class HallucinationPolicy(BaseModel):
    model_config = ConfigDict(frozen=True)
    version: str
    weights: dict[str, float]
    empty_result_risk: float = Field(default=0.25, ge=0, le=1)


class ConfidenceSignals(BaseModel):
    model_config = ConfigDict(frozen=True)
    syntax_score: float = Field(ge=0, le=1)
    schema_coverage: float = Field(ge=0, le=1)
    execution_success: float = Field(ge=0, le=1)
    hallucination_probability: float = Field(ge=0, le=1)
    multi_query_agreement: float = Field(ge=0, le=1)
    explainability: float = Field(ge=0, le=1)


class ConfidenceComponent(BaseModel):
    model_config = ConfigDict(frozen=True)
    name: str
    raw_score: float = Field(ge=0, le=1)
    weight: float = Field(gt=0)
    contribution: float = Field(ge=0, le=1)


class ConfidenceAssessment(BaseModel):
    model_config = ConfigDict(frozen=True)
    score: float = Field(ge=0, le=1)
    breakdown: tuple[ConfidenceComponent, ...]
    warnings: tuple[str, ...]
    policy_version: str


class ConfidencePolicy(BaseModel):
    model_config = ConfigDict(frozen=True)
    version: str
    weights: dict[str, float]
    low_confidence_threshold: float = Field(default=0.6, ge=0, le=1)
    high_hallucination_threshold: float = Field(default=0.45, ge=0, le=1)
    low_component_threshold: float = Field(default=0.5, ge=0, le=1)
