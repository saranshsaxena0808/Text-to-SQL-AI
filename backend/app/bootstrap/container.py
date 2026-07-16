from dataclasses import dataclass
from collections.abc import Callable

from app.application.interfaces.runtime import ReadinessProbe
from app.application.services.query_service import RunTextToSql
from app.application.services.resource_services import (
    DataSourceService, FeedbackService, HistoryService, SchemaApplicationService,
)


@dataclass(frozen=True, slots=True)
class ApplicationContainer:
    queries: RunTextToSql
    data_sources: DataSourceService
    schemas: SchemaApplicationService
    history: HistoryService
    feedback: FeedbackService
    readiness: ReadinessProbe
    shutdown: Callable[[], None] = lambda: None
