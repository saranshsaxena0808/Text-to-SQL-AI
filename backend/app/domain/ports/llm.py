from abc import ABC, abstractmethod

from app.domain.entities.llm import GenerationRequest, LLMResponse, LLMStream


class LLMGateway(ABC):
    @abstractmethod
    def generate(self, request: GenerationRequest) -> LLMResponse: ...

    @abstractmethod
    def stream(self, request: GenerationRequest) -> LLMStream: ...
