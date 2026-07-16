import math
from threading import RLock

from app.domain.entities.retrieval import QualifiedTable, RelevantSchema, RetrievedTable
from app.domain.entities.schema import SchemaSnapshot, TableSchema
from app.domain.exceptions import RetrievalError
from app.domain.ports.retrieval import EmbeddingProvider, VectorIndex


class SchemaRetrievalService:
    """Indexes table documents and retrieves semantic matches plus FK neighbors."""

    def __init__(self, embeddings: EmbeddingProvider, index: VectorIndex,
                 top_k: int = 5, max_tables: int = 10) -> None:
        if top_k < 1 or max_tables < top_k:
            raise ValueError("Require 1 <= top_k <= max_tables")
        self._embeddings = embeddings
        self._index = index
        self._top_k = top_k
        self._max_tables = max_tables
        self._lock = RLock()

    def retrieve(self, question: str, snapshot: SchemaSnapshot) -> RelevantSchema:
        with self._lock:
            return self._retrieve_locked(question, snapshot)

    def _retrieve_locked(self, question: str, snapshot: SchemaSnapshot) -> RelevantSchema:
        if not question.strip():
            raise ValueError("question must not be blank")
        tables = self._flatten(snapshot)
        if not tables:
            return RelevantSchema(snapshot_checksum=snapshot.checksum, tables=())
        by_key = {table.qualified_name: table for table in tables}
        if self._index.version != snapshot.checksum:
            documents = [self._document(table) for table in tables]
            vectors = self._embeddings.embed(documents)
            if len(vectors) != len(tables):
                raise RetrievalError("Embedding provider returned an unexpected vector count")
            self._index.rebuild(list(by_key), vectors, snapshot.checksum)
        query_vectors = self._embeddings.embed([question.strip()])
        if len(query_vectors) != 1:
            raise RetrievalError("Embedding provider returned an invalid query vector")
        matches = self._index.search(query_vectors[0], self._top_k)
        selected: dict[str, RetrievedTable] = {}
        for key, score in matches:
            if key in by_key:
                selected[key] = RetrievedTable(
                    schema_name=by_key[key].schema_name, table=by_key[key].table,
                    score=self._normalize_score(score), selection_reason="semantic_match",
                )
        self._include_relationship_neighbors(selected, by_key)
        ordered = sorted(selected.values(), key=lambda item: (-item.score, item.qualified_name))
        return RelevantSchema(snapshot_checksum=snapshot.checksum,
                              tables=tuple(ordered[:self._max_tables]))

    @staticmethod
    def _flatten(snapshot: SchemaSnapshot) -> list[QualifiedTable]:
        return [QualifiedTable(schema_name=namespace.name, table=table)
                for namespace in snapshot.schemas for table in namespace.tables]

    @staticmethod
    def _document(table: QualifiedTable) -> str:
        columns = ", ".join(f"{c.name} {c.data_type}" for c in table.table.columns)
        relationships = "; ".join(
            f"{','.join(r.from_columns)} -> {r.target_schema or table.schema_name}."
            f"{r.target_table}({','.join(r.target_columns)})"
            for r in table.table.relationships
        )
        return (f"table {table.qualified_name}. comment {table.table.comment or ''}. "
                f"columns {columns}. relationships {relationships}")

    def _include_relationship_neighbors(self, selected: dict[str, RetrievedTable],
                                        by_key: dict[str, QualifiedTable]) -> None:
        seeds = list(selected.values())
        for item in seeds:
            if len(selected) >= self._max_tables:
                return
            for relation in item.table.relationships:
                key = f"{relation.target_schema or item.schema_name}.{relation.target_table}"
                if key in by_key and key not in selected:
                    selected[key] = RetrievedTable(
                        schema_name=by_key[key].schema_name, table=by_key[key].table,
                        score=max(0.0, item.score * 0.8), selection_reason=f"related_to:{item.qualified_name}",
                    )
            for candidate in by_key.values():
                if len(selected) >= self._max_tables:
                    return
                if candidate.qualified_name in selected:
                    continue
                points_to_seed = any(
                    f"{relation.target_schema or candidate.schema_name}.{relation.target_table}"
                    == item.qualified_name
                    for relation in candidate.table.relationships
                )
                if points_to_seed:
                    selected[candidate.qualified_name] = RetrievedTable(
                        schema_name=candidate.schema_name, table=candidate.table,
                        score=max(0.0, item.score * 0.8),
                        selection_reason=f"related_to:{item.qualified_name}",
                    )

    @staticmethod
    def _normalize_score(score: float) -> float:
        if not math.isfinite(score):
            return 0.0
        return max(0.0, min(1.0, score))
