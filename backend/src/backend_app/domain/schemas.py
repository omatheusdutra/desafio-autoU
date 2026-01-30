from typing import Any, Dict, List, Optional

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


class JobSubmitResponse(BaseModel):
    job_id: Optional[str]
    status: str
    result: Optional[ProcessResponse] = None


class JobStatusResponse(BaseModel):
    status: str
    result: Optional[ProcessResponse] = None
    message: Optional[str] = None


class BatchJobSubmitResponse(BaseModel):
    job_id: Optional[str]
    status: str
    report_urls: Optional[Dict[str, str]] = None
    summary: Optional[Dict[str, int]] = None
    stats: Optional[Dict[str, Any]] = None


class BatchJobStatusResponse(BaseModel):
    status: str
    message: Optional[str] = None
    progress: Optional[Dict[str, int]] = None
    report_urls: Optional[Dict[str, str]] = None
    summary: Optional[Dict[str, int]] = None
    stats: Optional[Dict[str, Any]] = None
