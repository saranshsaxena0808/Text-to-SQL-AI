from pydantic import BaseModel, ConfigDict, Field

from app.domain.entities.schema import TableSchema


class QualifiedTable(BaseModel):
    model_config = ConfigDict(frozen=True)
    schema_name: str
    table: TableSchema

    @property
    def qualified_name(self) -> str:
        return f"{self.schema_name}.{self.table.name}"


class RetrievedTable(BaseModel):
    model_config = ConfigDict(frozen=True)
    schema_name: str
    table: TableSchema
    score: float = Field(ge=0.0, le=1.0)
    selection_reason: str

    @property
    def qualified_name(self) -> str:
        return f"{self.schema_name}.{self.table.name}"


class RelevantSchema(BaseModel):
    model_config = ConfigDict(frozen=True)
    snapshot_checksum: str
    tables: tuple[RetrievedTable, ...]
