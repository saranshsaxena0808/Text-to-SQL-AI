import hashlib
import json
import re
from pathlib import Path

from pydantic import ValidationError

from app.domain.entities.prompt import PromptTemplate
from app.domain.exceptions import PromptTemplateError
from app.domain.ports.prompts import PromptTemplateRepository


_SAFE_COMPONENT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,99}$")


class FilePromptTemplateRepository(PromptTemplateRepository):
    """Loads immutable JSON prompt versions from a configured directory."""

    def __init__(self, root: Path) -> None:
        self._root = root.resolve()

    def get(self, name: str, version: str) -> PromptTemplate:
        if not _SAFE_COMPONENT.fullmatch(name) or not _SAFE_COMPONENT.fullmatch(version):
            raise PromptTemplateError("Invalid prompt template name or version")
        path = self._root / name / f"{version}.json"
        try:
            raw = path.read_bytes()
            payload = json.loads(raw)
            checksum = hashlib.sha256(raw).hexdigest()
            return PromptTemplate(name=name, version=version, checksum=checksum,
                                  system_prompt=payload["system_prompt"],
                                  output_contract=payload["output_contract"])
        except FileNotFoundError as exc:
            raise PromptTemplateError(f"Prompt template {name}:{version} was not found") from exc
        except (json.JSONDecodeError, KeyError, ValidationError, OSError) as exc:
            raise PromptTemplateError(f"Prompt template {name}:{version} is invalid") from exc
