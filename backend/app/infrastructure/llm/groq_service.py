import json
import random
import time
from collections.abc import Callable, Iterator
from typing import Any

from pydantic import ValidationError

from app.config.settings import GroqSettings
from app.domain.entities.llm import (
    GenerationRequest, LLMResponse, LLMUsage, SqlGenerationResult, StreamEvent,
)
from app.domain.exceptions import (
    LLMConfigurationError, LLMRateLimitError, LLMResponseError, LLMServiceUnavailableError,
)
from app.domain.ports.llm import LLMGateway
from app.infrastructure.observability import get_logger


logger = get_logger(__name__)


class GroqLLMGateway(LLMGateway):
    """Provider adapter only: transport, retries, streaming, and response decoding."""

    def __init__(self, settings: GroqSettings, client: Any | None = None,
                 sleeper: Callable[[float], None] = time.sleep,
                 jitter: Callable[[float, float], float] = random.uniform) -> None:
        self._settings = settings
        self._validate_settings()
        self._client = client or self._create_client()
        self._sleep = sleeper
        self._jitter = jitter

    def generate(self, request: GenerationRequest) -> LLMResponse:
        self._ensure_model_allowed(request.options.model)
        response = self._with_retry(lambda: self._client.chat.completions.create(
            **self._request_payload(request, stream=False)
        ), request.options.model)
        return self._decode_response(response, request.options.model)

    def stream(self, request: GenerationRequest) -> Iterator[StreamEvent]:
        self._ensure_model_allowed(request.options.model)
        stream = self._with_retry(lambda: self._client.chat.completions.create(
            **self._request_payload(request, stream=True)
        ), request.options.model)
        fragments: list[str] = []
        request_id: str | None = None
        fingerprint: str | None = None
        usage = LLMUsage()
        try:
            for chunk in stream:
                request_id = request_id or getattr(chunk, "id", None)
                fingerprint = fingerprint or getattr(chunk, "system_fingerprint", None)
                chunk_usage = getattr(chunk, "usage", None)
                if chunk_usage is not None:
                    usage = self._usage(chunk_usage)
                choices = getattr(chunk, "choices", ())
                text = getattr(getattr(choices[0], "delta", None), "content", None) if choices else None
                if text:
                    fragments.append(text)
                    yield StreamEvent(type="delta", text=text)
        except Exception as exc:
            raise self._map_error(exc, exhausted=True) from exc
        result = self._parse_result("".join(fragments))
        yield StreamEvent(type="completed", response=LLMResponse(
            request_id=request_id, model=request.options.model, result=result,
            usage=usage, system_fingerprint=fingerprint,
        ))

    def _request_payload(self, request: GenerationRequest, stream: bool) -> dict[str, Any]:
        options = request.options
        payload: dict[str, Any] = {
            "model": options.model,
            "messages": [
                {"role": "system", "content": request.prompt.system},
                {"role": "user", "content": request.prompt.user},
            ],
            "temperature": options.temperature,
            "max_completion_tokens": options.max_completion_tokens,
            "stream": stream,
        }
        if options.seed is not None:
            payload["seed"] = options.seed
        if stream:
            payload["response_format"] = {"type": "json_object"}
        else:
            payload["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": "text_to_sql_response",
                    "strict": options.model in self._settings.strict_models,
                    "schema": SqlGenerationResult.model_json_schema(),
                },
            }
        return payload

    def _decode_response(self, response: Any, requested_model: str) -> LLMResponse:
        choices = getattr(response, "choices", ())
        message = getattr(choices[0], "message", None) if choices else None
        refusal = getattr(message, "refusal", None)
        if refusal:
            raise LLMResponseError("Groq refused to produce the requested structured response")
        content = getattr(message, "content", None)
        if not content:
            raise LLMResponseError("Groq returned no completion content")
        return LLMResponse(
            request_id=getattr(response, "id", None),
            model=getattr(response, "model", None) or requested_model,
            result=self._parse_result(content),
            usage=self._usage(getattr(response, "usage", None)),
            system_fingerprint=getattr(response, "system_fingerprint", None),
        )

    @staticmethod
    def _parse_result(content: str) -> SqlGenerationResult:
        try:
            return SqlGenerationResult.model_validate_json(content)
        except (ValidationError, ValueError, json.JSONDecodeError) as exc:
            raise LLMResponseError("Groq returned an invalid structured response") from exc

    @staticmethod
    def _usage(usage: Any) -> LLMUsage:
        if usage is None:
            return LLMUsage()
        return LLMUsage(prompt_tokens=getattr(usage, "prompt_tokens", 0) or 0,
                        completion_tokens=getattr(usage, "completion_tokens", 0) or 0,
                        total_tokens=getattr(usage, "total_tokens", 0) or 0)

    def _with_retry(self, operation: Callable[[], Any], model: str) -> Any:
        for attempt in range(1, self._settings.max_attempts + 1):
            try:
                return operation()
            except Exception as exc:
                retryable, retry_after = self._retry_details(exc)
                if not retryable or attempt == self._settings.max_attempts:
                    raise self._map_error(exc, exhausted=True) from exc
                delay = retry_after if retry_after is not None else min(
                    self._settings.max_backoff_seconds,
                    self._settings.base_backoff_seconds * (2 ** (attempt - 1)),
                )
                actual_delay = max(0.0, delay + self._jitter(0.0, delay * 0.1))
                logger.warning("Retrying Groq request", extra={
                    "event": "groq_retry", "model": model, "attempt": attempt,
                    "delay_seconds": actual_delay, "status_code": getattr(exc, "status_code", None),
                })
                self._sleep(actual_delay)
        raise AssertionError("retry loop terminated unexpectedly")

    @staticmethod
    def _retry_details(exc: Exception) -> tuple[bool, float | None]:
        status = getattr(exc, "status_code", None)
        name = type(exc).__name__
        retryable = status == 429 or (isinstance(status, int) and status >= 500) or name in {
            "RateLimitError", "APITimeoutError", "APIConnectionError", "InternalServerError"
        }
        retry_after = None
        response = getattr(exc, "response", None)
        headers = getattr(response, "headers", {}) if response is not None else {}
        if status == 429 or name == "RateLimitError":
            try:
                retry_after = float(headers.get("retry-after"))
            except (TypeError, ValueError):
                pass
        return retryable, retry_after

    @staticmethod
    def _map_error(exc: Exception, exhausted: bool) -> Exception:
        status = getattr(exc, "status_code", None)
        if status == 429 or type(exc).__name__ == "RateLimitError":
            return LLMRateLimitError("Groq rate limit exceeded after retry attempts")
        if exhausted and (status is not None and status >= 500 or type(exc).__name__ in {
            "APITimeoutError", "APIConnectionError", "InternalServerError"
        }):
            return LLMServiceUnavailableError("Groq service is temporarily unavailable")
        return LLMServiceUnavailableError("Groq request failed")

    def _ensure_model_allowed(self, model: str) -> None:
        if model not in self._settings.allowed_models:
            raise LLMConfigurationError(f"Groq model is not allowed: {model}")

    def _validate_settings(self) -> None:
        if not self._settings.allowed_models:
            raise LLMConfigurationError("At least one Groq model must be allowed")
        unknown_strict = set(self._settings.strict_models) - set(self._settings.allowed_models)
        if unknown_strict:
            raise LLMConfigurationError("Strict models must be included in allowed_models")
        if self._settings.max_backoff_seconds < self._settings.base_backoff_seconds:
            raise LLMConfigurationError("max_backoff_seconds must be >= base_backoff_seconds")

    def _create_client(self) -> Any:
        api_key = self._settings.api_key.get_secret_value()
        if not api_key:
            raise LLMConfigurationError("Groq API key is not configured")
        try:
            from groq import Groq
        except ImportError as exc:
            raise LLMConfigurationError("groq dependency is not installed") from exc
        return Groq(api_key=api_key, timeout=self._settings.timeout_seconds, max_retries=0)
