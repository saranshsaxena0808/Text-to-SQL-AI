from abc import ABC, abstractmethod


class SemanticSimilarity(ABC):
    @abstractmethod
    def compare(self, left: str, right: str) -> float: ...


class BackTranslator(ABC):
    @abstractmethod
    def translate(self, sql: str) -> str: ...


class SqlSimilarity(ABC):
    @abstractmethod
    def compare(self, left_sql: str, right_sql: str) -> float: ...
