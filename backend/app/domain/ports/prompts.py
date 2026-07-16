from abc import ABC, abstractmethod

from app.domain.entities.prompt import PromptTemplate


class PromptTemplateRepository(ABC):
    @abstractmethod
    def get(self, name: str, version: str) -> PromptTemplate: ...
