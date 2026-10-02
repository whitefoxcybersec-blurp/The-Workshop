from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class SessionCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)


class EvidenceCreate(BaseModel):
    source: str = Field(default="manual observation", min_length=1, max_length=240)
    kind: Literal["HTTP", "TLS", "JWT", "CRYPTO", "OTHER"]
    observation: str = Field(min_length=1, max_length=500)
    bearing: Literal["supports", "neutral", "contradicts"] = "neutral"
    confidence: float = Field(default=0.9, ge=0, le=1)
    artifact_hash: str | None = Field(default=None, pattern=r"^[a-fA-F0-9]{64}$")
    detail: str = Field(default="", max_length=1000)
    observed_at: str | None = Field(default=None, max_length=40)


class EvidenceImport(BaseModel):
    format: Literal["json", "har", "headers"]
    content: str = Field(min_length=1, max_length=5_000_000)
    source: str = Field(default="imported artifact", min_length=1, max_length=240)


class ScopeCheck(BaseModel):
    host: str = Field(min_length=1, max_length=253)