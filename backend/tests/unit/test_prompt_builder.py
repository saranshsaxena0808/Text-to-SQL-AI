import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from app.application.services.prompt_builder import DynamicPromptBuilder
from app.domain.entities.prompt import BusinessRule, FewShotExample, PromptContext
from app.domain.entities.retrieval import RelevantSchema, RetrievedTable
from app.domain.entities.schema import ColumnSchema, RelationshipSchema, TableSchema
from app.domain.exceptions import PromptTemplateError
from app.infrastructure.prompts.file_repository import FilePromptTemplateRepository


class PromptBuilderTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        directory = root / "text_to_sql"
        directory.mkdir()
        self.raw = json.dumps({
            "system_prompt": " Generate safe PostgreSQL. ",
            "output_contract": {"type": "object", "required": ["sql"]},
        }).encode()
        (directory / "v1.json").write_bytes(self.raw)
        self.repository = FilePromptTemplateRepository(root)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _context(self) -> PromptContext:
        orders = TableSchema(
            name="orders",
            columns=(ColumnSchema(name="id", data_type="INTEGER", nullable=False),
                     ColumnSchema(name="customer_id", data_type="INTEGER", nullable=False)),
            primary_key=("id",),
            relationships=(RelationshipSchema(from_columns=("customer_id",),
                                               target_table="customers", target_columns=("id",)),),
            sample_values={"id": (1, 2, 3), "customer_id": (10,)},
        )
        relevant = RelevantSchema(snapshot_checksum="abc", tables=(RetrievedTable(
            schema_name="public", table=orders, score=0.9, selection_reason="semantic_match"),))
        return PromptContext(
            question="Total orders by customer",
            relevant_schema=relevant,
            business_rules=(BusinessRule(rule_id="currency", description="Amounts are USD."),),
            few_shot_examples=(FewShotExample(question="All orders", sql="SELECT * FROM orders LIMIT 10"),),
        )

    def test_builds_all_required_sections_and_metadata(self) -> None:
        prompt = DynamicPromptBuilder(self.repository, sample_limit=2).build(
            self._context(), "text_to_sql", "v1"
        )
        for section in ("# Question", "# Relevant Schema", "# Relationships",
                        "# Business Rules", "# Sample Values", "# Few-shot Examples",
                        "# Output Format"):
            self.assertIn(section, prompt.user)
        self.assertIn("public.orders(customer_id) -> public.customers(id)", prompt.user)
        self.assertIn('public.orders.id: [1, 2]', prompt.user)
        self.assertNotIn("[1, 2, 3]", prompt.user)
        self.assertEqual(prompt.system, "Generate safe PostgreSQL.")
        self.assertEqual(prompt.template_checksum, hashlib.sha256(self.raw).hexdigest())

    def test_template_repository_rejects_path_traversal(self) -> None:
        with self.assertRaises(PromptTemplateError):
            self.repository.get("../secrets", "v1")

    def test_missing_version_returns_domain_error(self) -> None:
        with self.assertRaises(PromptTemplateError):
            self.repository.get("text_to_sql", "v2")
