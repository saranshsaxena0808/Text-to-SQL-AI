from pathlib import Path

import yaml
from pydantic import ValidationError

from app.domain.entities.guardrails import GuardrailPolicy
from app.domain.exceptions import GuardrailConfigurationError


class FileGuardrailPolicyLoader:
    def __init__(self, path: Path) -> None:
        self._path = path

    def load(self) -> GuardrailPolicy:
        try:
            payload = yaml.safe_load(self._path.read_text(encoding="utf-8"))
            if not isinstance(payload, dict):
                raise GuardrailConfigurationError("Guardrail policy must be a YAML object")
            return GuardrailPolicy.model_validate(payload)
        except FileNotFoundError as exc:
            raise GuardrailConfigurationError("Guardrail policy file was not found") from exc
        except (OSError, yaml.YAMLError, ValidationError) as exc:
            raise GuardrailConfigurationError("Guardrail policy file is invalid") from exc
