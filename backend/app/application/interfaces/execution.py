from abc import ABC, abstractmethod

from app.application.dto.execution import SqlExecutionResult
from app.domain.entities.guardrails import GuardrailDecision


class QueryExecutor(ABC):
    @abstractmethod
    def execute(self, decision: GuardrailDecision) -> SqlExecutionResult: ...
