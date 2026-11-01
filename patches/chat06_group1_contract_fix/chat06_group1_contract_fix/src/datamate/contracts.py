from __future__ import annotations

from typing import Any, Literal

from pydantic import AliasChoices, BaseModel, ConfigDict, Field


AnswerType = Literal[
    "number",
    "percent",
    "list",
    "date",
    "string",
    "boolean",
    "table",
    "unanswerable",
]


class Question(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    business_id: str | None = None
    question: str | None = None
    as_of_date: str | None = None


class TrainAnswer(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    type: AnswerType = Field(
        validation_alias=AliasChoices("type", "answer_type")
    )
    answer: Any = None


class SubmissionRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    type: Literal[
        "number",
        "percent",
        "list",
        "date",
        "string",
        "boolean",
        "table",
        "unanswerable",
        "abstain",
    ]
    answer: Any = None
    reason: str | None = None
