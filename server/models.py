from pydantic import BaseModel
from typing import Any


class AnalysisRequest(BaseModel):
    company_name: str


class CompareRequest(BaseModel):
    analysis_ids: list[str]


class ChatRequest(BaseModel):
    message: str


class ChatSource(BaseModel):
    title: str
    url: str


class ProposedUpdate(BaseModel):
    field: str
    old_value: str | None = None
    new_value: str
    reason: str


class ChatResponse(BaseModel):
    answer: str
    sources: list[ChatSource] | None = None
    proposed_updates: list[ProposedUpdate] | None = None


class UrlExtractRequest(BaseModel):
    url: str


class AddYearsRequest(BaseModel):
    years: int = 5
