from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


FactCategory = Literal[
    "company",
    "pricing",
    "measurement",
    "estimate",
    "portfolio",
    "warranty",
    "payment",
    "regions",
    "services",
    "communication",
]
FactPriority = Literal["core", "scenario"]
FactValueType = Literal["text", "number", "url", "boolean", "list"]


class CompanyFactBase(BaseModel):
    key: str = Field(min_length=2, max_length=100, pattern=r"^[a-z][a-z0-9_]*$")
    title: str = Field(min_length=2, max_length=255)
    value: str = Field(min_length=1, max_length=5000)
    category: FactCategory = "company"
    value_type: FactValueType = "text"
    priority: FactPriority = "scenario"
    tags: list[str] = Field(default_factory=list)
    stages: list[str] = Field(default_factory=list)
    questions: list[str] = Field(default_factory=list)
    hint: str | None = Field(default=None, max_length=1000)
    display_order: int = 0
    is_active: bool = True

    @field_validator("tags", "stages", "questions", mode="before")
    @classmethod
    def normalize_list(cls, value):
        if value is None:
            return []
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value


class CompanyFactCreate(CompanyFactBase):
    pass


class CompanyFactUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=255)
    value: str | None = Field(default=None, min_length=1, max_length=5000)
    category: FactCategory | None = None
    value_type: FactValueType | None = None
    priority: FactPriority | None = None
    tags: list[str] | None = None
    stages: list[str] | None = None
    questions: list[str] | None = None
    hint: str | None = Field(default=None, max_length=1000)
    display_order: int | None = None
    is_active: bool | None = None

    @field_validator("tags", "stages", "questions", mode="before")
    @classmethod
    def normalize_list(cls, value):
        if value is None:
            return value
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value


class CompanyFactResponse(CompanyFactBase):
    id: UUID
    org_id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
