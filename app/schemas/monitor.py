from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class MonitorCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    url: HttpUrl
    interval_seconds: int = Field(default=60, ge=10, le=86_400)
    timeout_seconds: int = Field(default=10, ge=1, le=60)
    expected_status: int = Field(default=200, ge=100, le=599)
    failure_threshold: int = Field(default=3, ge=1, le=10)
    webhook_url: HttpUrl | None = None


class MonitorUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    interval_seconds: int | None = Field(default=None, ge=10, le=86_400)
    timeout_seconds: int | None = Field(default=None, ge=1, le=60)
    expected_status: int | None = Field(default=None, ge=100, le=599)
    failure_threshold: int | None = Field(default=None, ge=1, le=10)
    webhook_url: HttpUrl | None = None
    is_active: bool | None = None


class MonitorOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    url: str
    interval_seconds: int
    timeout_seconds: int
    expected_status: int
    failure_threshold: int
    webhook_url: str | None
    is_active: bool
    consecutive_failures: int
    next_check_at: datetime
    created_at: datetime


class MonitorPage(BaseModel):
    items: list[MonitorOut]
    next_cursor: int | None


class CheckResultOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    checked_at: datetime
    status_code: int | None
    latency_ms: int | None
    ok: bool
    error: str | None


class CheckResultPage(BaseModel):
    items: list[CheckResultOut]
    next_cursor: int | None
