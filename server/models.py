from pydantic import BaseModel


class AnalysisRequest(BaseModel):
    company_name: str


class CompareRequest(BaseModel):
    analysis_ids: list[str]
