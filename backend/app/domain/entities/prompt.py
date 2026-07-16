from pydantic import BaseModel, ConfigDict, Field

from app.domain.entities.retrieval import RelevantSchema


class BusinessRule(BaseModel):
    model_config = ConfigDict(frozen=True)
    rule_id: str = Field(min_length=1, max_length=100)
    description: str = Field(min_length=1, max_length=2000)


class FewShotExample(BaseModel):
    model_config = ConfigDict(frozen=True)
    question: str = Field(min_length=1, max_length=2000)
    sql: str = Field(min_length=1, max_length=10000)
    explanation: str | None = Field(default=None, max_length=2000)


class PromptContext(BaseModel):
    model_config = ConfigDict(frozen=True)
    question: str = Field(min_length=1, max_length=5000)
    relevant_schema: RelevantSchema
    business_rules: tuple[BusinessRule, ...] = ()
    few_shot_examples: tuple[FewShotExample, ...] = ()


class PromptTemplate(BaseModel):
    model_config = ConfigDict(frozen=True)
    name: str
    version: str
    system_prompt: str
    output_contract: dict[str, object]
    checksum: str


class BuiltPrompt(BaseModel):
    model_config = ConfigDict(frozen=True)
    template_name: str
    template_version: str
    template_checksum: str
    system: str
    user: str
