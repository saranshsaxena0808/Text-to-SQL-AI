from pathlib import Path
from typing import TypeVar

import yaml
from pydantic import BaseModel, ValidationError

from app.domain.entities.hallucination import ConfidencePolicy, HallucinationPolicy
from app.domain.exceptions import ValidationConfigurationError


PolicyT = TypeVar("PolicyT", bound=BaseModel)


def _load(path: Path, model: type[PolicyT]) -> PolicyT:
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValidationConfigurationError("Validation policy must be a YAML object")
        return model.model_validate(payload)
    except FileNotFoundError as exc:
        raise ValidationConfigurationError("Validation policy file was not found") from exc
    except (OSError, yaml.YAMLError, ValidationError) as exc:
        raise ValidationConfigurationError("Validation policy file is invalid") from exc


class ValidationPolicyLoader:
    @staticmethod
    def hallucination(path: Path) -> HallucinationPolicy:
        return _load(path, HallucinationPolicy)

    @staticmethod
    def confidence(path: Path) -> ConfidencePolicy:
        return _load(path, ConfidencePolicy)
