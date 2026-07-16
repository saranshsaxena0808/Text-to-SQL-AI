from abc import ABC, abstractmethod

from app.application.dto.validation import HallucinationContext
from app.domain.entities.hallucination import ValidationEvidence


class HallucinationCheck(ABC):
    @property
    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    def evaluate(self, context: HallucinationContext) -> ValidationEvidence: ...
