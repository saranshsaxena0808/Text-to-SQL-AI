from collections.abc import Iterator
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.domain.entities.prompt import BuiltPrompt


class SqlGenerationResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    sql: str | None
    confidence: float = Field(ge=0.0, le=1.0)
    explanation: str = Field(min_length=1)
    tables: tuple[str, ...]
    columns: tuple[str, ...]
    clarification_needed: bool
    clarification_question: str | None

    @model_validator(mode="after")
    def validate_clarification(self) -> "SqlGenerationResult":
        if self.clarification_needed and not self.clarification_question:
            raise ValueError("clarification_question is required when clarification is needed")
        return self


class LLMUsage(BaseModel):
    model_config = ConfigDict(frozen=True)
    prompt_tokens: int = Field(default=0, ge=0)
    completion_tokens: int = Field(default=0, ge=0)
    total_tokens: int = Field(default=0, ge=0)


class LLMResponse(BaseModel):
    model_config = ConfigDict(frozen=True)
    request_id: str | None = None
    model: str
    result: SqlGenerationResult
    usage: LLMUsage = Field(default_factory=LLMUsage)
    system_fingerprint: str | None = None


class GenerationOptions(BaseModel):
    model_config = ConfigDict(frozen=True)
    model: str
    temperature: float = Field(default=0.0, ge=0.0, le=2.0)
    max_completion_tokens: int = Field(default=1024, ge=1, le=32768)
    seed: int | None = None


class GenerationRequest(BaseModel):
    model_config = ConfigDict(frozen=True)
    prompt: BuiltPrompt
    options: GenerationOptions


class StreamEvent(BaseModel):
    model_config = ConfigDict(frozen=True)
    type: Literal["delta", "completed"]
    text: str = ""
    response: LLMResponse | None = None


LLMStream = Iterator[StreamEvent]
