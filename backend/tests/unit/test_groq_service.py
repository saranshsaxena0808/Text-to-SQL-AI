import json
import unittest
from types import SimpleNamespace

from pydantic import SecretStr

from app.config.settings import GroqSettings
from app.domain.entities.llm import GenerationOptions, GenerationRequest
from app.domain.entities.prompt import BuiltPrompt
from app.domain.exceptions import (
    LLMConfigurationError, LLMRateLimitError, LLMResponseError, LLMServiceUnavailableError,
)
from app.infrastructure.llm.groq_service import GroqLLMGateway


MODEL = "Llama 3.3 70B"  # matches the default in GroqSettings.allowed_models


def valid_payload() -> dict[str, object]:
    return {
        "sql": "SELECT id FROM orders LIMIT 100",
        "confidence": 0.91,
        "explanation": "Uses the orders table.",
        "tables": ["orders"],
        "columns": ["orders.id"],
        "clarification_needed": False,
        "clarification_question": None,
    }


def request(model: str = MODEL) -> GenerationRequest:
    prompt = BuiltPrompt(template_name="text_to_sql", template_version="v1",
                         template_checksum="abc", system="system", user="question")
    return GenerationRequest(prompt=prompt, options=GenerationOptions(
        model=model, temperature=0, max_completion_tokens=512, seed=7
    ))


class FakeCompletions:
    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


class FakeClient:
    def __init__(self, outcomes):
        self.completions = FakeCompletions(outcomes)
        self.chat = SimpleNamespace(completions=self.completions)


def response(content: str | None = None):
    usage = SimpleNamespace(prompt_tokens=20, completion_tokens=30, total_tokens=50)
    message = SimpleNamespace(content=content or json.dumps(valid_payload()))
    return SimpleNamespace(id="req-1", model=MODEL, choices=[SimpleNamespace(message=message)],
                           usage=usage, system_fingerprint="fp-1")


def refusal_response():
    message = SimpleNamespace(content=None, refusal="safety policy")
    return SimpleNamespace(id="req-refusal", model=MODEL,
                           choices=[SimpleNamespace(message=message)], usage=None)


class ProviderError(Exception):
    def __init__(self, status_code: int, retry_after: str | None = None):
        super().__init__("provider failure")
        self.status_code = status_code
        headers = {} if retry_after is None else {"retry-after": retry_after}
        self.response = SimpleNamespace(headers=headers)


class GroqGatewayTests(unittest.TestCase):
    def settings(self, **overrides) -> GroqSettings:
        values = {
            "api_key": SecretStr("test-key"), "allowed_models": [MODEL, "fallback"],
            "strict_models": [MODEL], "max_attempts": 3,
            "base_backoff_seconds": 1, "max_backoff_seconds": 4,
        }
        values.update(overrides)
        return GroqSettings(**values)

    def test_generates_typed_structured_response(self) -> None:
        client = FakeClient([response()])
        gateway = GroqLLMGateway(self.settings(), client=client)
        result = gateway.generate(request())
        self.assertEqual(result.result.sql, "SELECT id FROM orders LIMIT 100")
        self.assertEqual(result.usage.total_tokens, 50)
        call = client.completions.calls[0]
        self.assertEqual(call["model"], MODEL)
        self.assertEqual(call["max_completion_tokens"], 512)
        self.assertEqual(call["seed"], 7)
        self.assertTrue(call["response_format"]["json_schema"]["strict"])
        schema = call["response_format"]["json_schema"]["schema"]
        self.assertFalse(schema["additionalProperties"])

    def test_best_effort_schema_for_non_strict_allowed_model(self) -> None:
        client = FakeClient([response()])
        GroqLLMGateway(self.settings(), client=client).generate(request("fallback"))
        self.assertFalse(client.completions.calls[0]["response_format"]["json_schema"]["strict"])

    def test_rejects_unknown_model_before_provider_call(self) -> None:
        client = FakeClient([response()])
        with self.assertRaises(LLMConfigurationError):
            GroqLLMGateway(self.settings(), client=client).generate(request("unknown"))
        self.assertEqual(client.completions.calls, [])

    def test_invalid_structured_output_is_normalized(self) -> None:
        gateway = GroqLLMGateway(self.settings(), client=FakeClient([response('{"sql": 1}')]))
        with self.assertRaises(LLMResponseError):
            gateway.generate(request())

    def test_provider_refusal_is_normalized(self) -> None:
        gateway = GroqLLMGateway(self.settings(), client=FakeClient([refusal_response()]))
        with self.assertRaisesRegex(LLMResponseError, "refused"):
            gateway.generate(request())

    def test_rate_limit_honors_retry_after(self) -> None:
        sleeps = []
        client = FakeClient([ProviderError(429, "2.5"), response()])
        gateway = GroqLLMGateway(self.settings(), client=client, sleeper=sleeps.append,
                                 jitter=lambda _a, _b: 0)
        result = gateway.generate(request())
        self.assertEqual(result.request_id, "req-1")
        self.assertEqual(sleeps, [2.5])
        self.assertEqual(len(client.completions.calls), 2)

    def test_rate_limit_exhaustion_returns_domain_error(self) -> None:
        client = FakeClient([ProviderError(429), ProviderError(429)])
        gateway = GroqLLMGateway(self.settings(max_attempts=2), client=client,
                                 sleeper=lambda _delay: None, jitter=lambda _a, _b: 0)
        with self.assertRaises(LLMRateLimitError):
            gateway.generate(request())

    def test_non_retryable_error_is_not_retried(self) -> None:
        client = FakeClient([ProviderError(400)])
        gateway = GroqLLMGateway(self.settings(), client=client)
        with self.assertRaises(LLMServiceUnavailableError):
            gateway.generate(request())
        self.assertEqual(len(client.completions.calls), 1)

    def test_stream_emits_deltas_and_validated_completion(self) -> None:
        encoded = json.dumps(valid_payload())
        midpoint = len(encoded) // 2
        chunks = [
            SimpleNamespace(id="stream-1", system_fingerprint="fp", usage=None,
                            choices=[SimpleNamespace(delta=SimpleNamespace(content=encoded[:midpoint]))]),
            SimpleNamespace(id="stream-1", system_fingerprint="fp",
                            usage=SimpleNamespace(prompt_tokens=2, completion_tokens=3, total_tokens=5),
                            choices=[SimpleNamespace(delta=SimpleNamespace(content=encoded[midpoint:]))]),
        ]
        client = FakeClient([iter(chunks)])
        events = list(GroqLLMGateway(self.settings(), client=client).stream(request()))
        self.assertEqual([event.type for event in events], ["delta", "delta", "completed"])
        self.assertEqual(events[-1].response.result.tables, ("orders",))
        self.assertEqual(events[-1].response.usage.total_tokens, 5)
        self.assertEqual(client.completions.calls[0]["response_format"], {"type": "json_object"})

    def test_missing_api_key_fails_when_constructing_real_client(self) -> None:
        with self.assertRaises(LLMConfigurationError):
            GroqLLMGateway(self.settings(api_key=SecretStr("")))

    def test_invalid_strict_model_configuration_fails(self) -> None:
        with self.assertRaises(LLMConfigurationError):
            GroqLLMGateway(self.settings(strict_models=["not-allowed"]), client=FakeClient([]))
