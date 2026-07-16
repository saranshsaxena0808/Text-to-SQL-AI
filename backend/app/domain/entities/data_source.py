from datetime import datetime
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


class DataSourceStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    ERROR = "error"


class DataSource(BaseModel):
    """Target database descriptor. Credentials are represented only by a secret reference."""

    model_config = ConfigDict(frozen=True)

    id: UUID = Field(default_factory=uuid4)
    tenant_id: UUID
    name: str = Field(min_length=1, max_length=255)
    secret_ref: str = Field(min_length=1, max_length=1024)
    status: DataSourceStatus = DataSourceStatus.ACTIVE
    options: dict[str, object] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime
