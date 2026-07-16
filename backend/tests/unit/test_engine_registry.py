import unittest

from app.infrastructure.target_database.engine_registry import TargetEngineRegistry


class EngineRegistryTests(unittest.TestCase):
    def test_reuses_engine_for_same_key(self) -> None:
        registry = TargetEngineRegistry(max_size=2)
        first = registry.get_or_create("a", "sqlite+pysqlite:///:memory:")
        second = registry.get_or_create("a", "sqlite+pysqlite:///:memory:")
        self.assertIs(first, second)
        registry.dispose_all()

    def test_validates_cache_size(self) -> None:
        with self.assertRaises(ValueError):
            TargetEngineRegistry(max_size=0)
