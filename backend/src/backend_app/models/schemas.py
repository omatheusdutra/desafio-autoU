from typing import List

from pydantic import BaseModel, Field


class ProcessRequest(BaseModel):
    text: str = Field(..., description="Email body text")


class ProcessResponse(BaseModel):
    primary_category: str
    overall_category: str
    confidence: float
    engine: str
    reply: str
    text_hash: str


class BatchProcessRequest(BaseModel):
    texts: List[str] = Field(..., description="List of email body texts")


class BatchProcessResponse(BaseModel):
    results: List[ProcessResponse]
