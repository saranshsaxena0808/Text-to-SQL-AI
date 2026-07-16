import json
from typing import Any

from app.domain.entities.prompt import BuiltPrompt, PromptContext
from app.domain.entities.retrieval import RetrievedTable
from app.domain.ports.prompts import PromptTemplateRepository


class DynamicPromptBuilder:
    """Builds deterministic provider-neutral prompts from validated context."""

    def __init__(self, templates: PromptTemplateRepository, sample_limit: int = 5) -> None:
        if not 0 <= sample_limit <= 20:
            raise ValueError("sample_limit must be between 0 and 20")
        self._templates = templates
        self._sample_limit = sample_limit

    def build(self, context: PromptContext, template_name: str, version: str) -> BuiltPrompt:
        template = self._templates.get(template_name, version)
        sections = [
            "# Question\n" + context.question.strip(),
            "# Relevant Schema\n" + self._render_schema(context.relevant_schema.tables),
            "# Relationships\n" + self._render_relationships(context.relevant_schema.tables),
            "# Business Rules\n" + ("\n".join(
                f"- [{rule.rule_id}] {rule.description}" for rule in context.business_rules
            ) or "- None provided"),
            "# Sample Values\n" + self._render_samples(context.relevant_schema.tables),
            "# Few-shot Examples\n" + self._render_examples(context),
            "# Output Format\nReturn exactly one JSON object matching this JSON Schema:\n"
            + json.dumps(template.output_contract, sort_keys=True, separators=(",", ":")),
        ]
        return BuiltPrompt(template_name=template.name, template_version=template.version,
                           template_checksum=template.checksum, system=template.system_prompt.strip(),
                           user="\n\n".join(sections))

    @staticmethod
    def _render_schema(tables: tuple[RetrievedTable, ...]) -> str:
        lines = []
        for item in tables:
            columns = ", ".join(
                f"{column.name} {column.data_type}{'' if column.nullable else ' NOT NULL'}"
                for column in item.table.columns
            )
            pk = ", ".join(item.table.primary_key) or "none"
            lines.append(f"- {item.qualified_name} ({columns}); primary_key=({pk})")
        return "\n".join(lines) or "- No tables retrieved"

    @staticmethod
    def _render_relationships(tables: tuple[RetrievedTable, ...]) -> str:
        lines = []
        for item in tables:
            for relation in item.table.relationships:
                target = f"{relation.target_schema or item.schema_name}.{relation.target_table}"
                lines.append(f"- {item.qualified_name}({', '.join(relation.from_columns)}) -> "
                             f"{target}({', '.join(relation.target_columns)})")
        return "\n".join(lines) or "- None"

    def _render_samples(self, tables: tuple[RetrievedTable, ...]) -> str:
        lines = []
        for item in tables:
            for column, values in sorted(item.table.sample_values.items()):
                bounded = [self._safe_value(value) for value in values[:self._sample_limit]]
                if bounded:
                    lines.append(f"- {item.qualified_name}.{column}: " + json.dumps(bounded, default=str))
        return "\n".join(lines) or "- None"

    @staticmethod
    def _safe_value(value: Any) -> Any:
        if isinstance(value, str) and len(value) > 100:
            return value[:97] + "..."
        return value

    @staticmethod
    def _render_examples(context: PromptContext) -> str:
        if not context.few_shot_examples:
            return "- None"
        return "\n\n".join(
            f"Example {number}\nQuestion: {example.question}\nSQL: {example.sql}\n"
            f"Explanation: {example.explanation or 'Not provided'}"
            for number, example in enumerate(context.few_shot_examples, start=1)
        )
