from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseSettings(BaseSettings):
    """Control-plane database and target-pool defaults."""

    model_config = SettingsConfigDict(env_prefix="TEXT2SQL_DATABASE__", extra="ignore")

    url: SecretStr = Field(
        default=SecretStr("postgresql+psycopg://text2sql:text2sql@localhost:5432/text2sql")
    )
    pool_size: int = Field(default=10, ge=1, le=100)
    max_overflow: int = Field(default=20, ge=0, le=200)
    pool_timeout_seconds: int = Field(default=30, ge=1, le=300)
    pool_recycle_seconds: int = Field(default=1800, ge=60)
    target_engine_cache_size: int = Field(default=32, ge=1, le=500)
    sample_value_limit: int = Field(default=5, ge=0, le=20)


class RetrievalSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="TEXT2SQL_RETRIEVAL__", extra="ignore")

    model_name: str = "sentence-transformers/all-MiniLM-L6-v2"
    embedding_dimension: int = Field(default=384, ge=1, le=4096)
    top_k: int = Field(default=5, ge=1, le=100)
    max_tables: int = Field(default=10, ge=1, le=200)


class PromptSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="TEXT2SQL_PROMPT__", extra="ignore")

    template_root: str = "config/prompts"
    default_name: str = "text_to_sql"
    default_version: str = "v1"
    sample_value_limit: int = Field(default=5, ge=0, le=20)


class GroqSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="TEXT2SQL_GROQ__", extra="ignore")

    api_key: SecretStr = SecretStr("")
    allowed_models: list[str] = Field(default_factory=lambda: [
        "llama-3.3-70b-versatile"
    ])
    strict_models: list[str] = Field(default_factory=lambda: [
        "openai/gpt-oss-20b", "openai/gpt-oss-120b"
    ])
    timeout_seconds: float = Field(default=30.0, gt=0, le=300)
    max_attempts: int = Field(default=3, ge=1, le=10)
    base_backoff_seconds: float = Field(default=0.5, ge=0, le=30)
    max_backoff_seconds: float = Field(default=8.0, ge=0, le=120)


class GuardrailSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="TEXT2SQL_GUARDRAILS__", extra="ignore")
    policy_path: str = "config/guardrails.yaml"


class ExecutionSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="TEXT2SQL_EXECUTION__", extra="ignore")
    statement_timeout_ms: int = Field(default=30000, ge=100, le=300000)
    lock_timeout_ms: int = Field(default=3000, ge=100, le=60000)
    max_rows: int = Field(default=10000, ge=1, le=100000)


class ValidationSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="TEXT2SQL_VALIDATION__", extra="ignore")
    hallucination_policy_path: str = "config/hallucination.yaml"
    confidence_policy_path: str = "config/confidence.yaml"


class ApiSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="TEXT2SQL_API__", extra="ignore")
    allowed_origins: list[str] = Field(default_factory=lambda: ["http://localhost:5173"])


class AuthSettings(BaseSettings):
    """OIDC resource-server validation. Header mode is local/test only."""

    model_config = SettingsConfigDict(env_prefix="TEXT2SQL_AUTH__", extra="ignore")
    mode: str = "trusted_headers"
    issuer: str = ""
    audience: str = ""
    jwks_url: str = ""
    algorithms: list[str] = Field(default_factory=lambda: ["RS256"])
    tenant_claim: str = "tenant_id"
    user_claim: str = "sub"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="TEXT2SQL_", env_nested_delimiter="__", env_file=".env", extra="ignore"
    )

    environment: str = "development"
    log_level: str = "INFO"
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    retrieval: RetrievalSettings = Field(default_factory=RetrievalSettings)
    prompt: PromptSettings = Field(default_factory=PromptSettings)
    groq: GroqSettings = Field(default_factory=GroqSettings)
    guardrails: GuardrailSettings = Field(default_factory=GuardrailSettings)
    execution: ExecutionSettings = Field(default_factory=ExecutionSettings)
    validation: ValidationSettings = Field(default_factory=ValidationSettings)
    api: ApiSettings = Field(default_factory=ApiSettings)
    auth: AuthSettings = Field(default_factory=AuthSettings)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
