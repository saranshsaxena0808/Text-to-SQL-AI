class DatabaseLayerError(Exception):
    """Base error safe for application-layer handling."""


class DatabaseConnectionError(DatabaseLayerError):
    pass


class RepositoryError(DatabaseLayerError):
    pass


class SchemaExtractionError(DatabaseLayerError):
    pass


class DataSourceNotFoundError(DatabaseLayerError):
    pass


class RetrievalError(Exception):
    pass


class PromptTemplateError(Exception):
    pass


class LLMError(Exception):
    """Provider-neutral LLM failure."""


class LLMConfigurationError(LLMError):
    pass


class LLMRateLimitError(LLMError):
    pass


class LLMResponseError(LLMError):
    pass


class LLMServiceUnavailableError(LLMError):
    pass


class SqlParseError(Exception):
    pass


class GuardrailConfigurationError(Exception):
    pass


class QueryPlanError(Exception):
    pass


class SqlExecutionError(Exception):
    """Base safe execution error; raw database details remain chained internally."""


class ExecutionRejectedError(SqlExecutionError):
    pass


class ExecutionTimeoutError(SqlExecutionError):
    pass


class ExecutionConnectionError(SqlExecutionError):
    pass


class ExecutionQueryError(SqlExecutionError):
    pass


class ExecutionDatabaseError(SqlExecutionError):
    pass


class ValidationConfigurationError(Exception):
    pass
