from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class LocationEntry(BaseModel):
    mention: str | None = None
    name: str | None = None
    lat: float | None = None
    lon: float | None = None
    osm_id: str | None = None
    osm_type: str | None = None
    display_name: str | None = None
    boundingbox: list | None = None
    polygon: dict | None = None

    model_config = ConfigDict(extra="allow")


class UserStateDTO(BaseModel):
    hide: bool = False
    flag: bool = False
    flag_author: str | None = None
    new: bool = True
    locations: list[LocationEntry] | None = None


class ReportDTO(BaseModel):
    id: int
    identifier: str
    text: str
    url: str
    platform: str
    timestamp: datetime
    event_type: str
    relevance: str
    author: str | None = None
    locations: list[LocationEntry] = []
    original_locations: list[LocationEntry] = []
    user_state: UserStateDTO = UserStateDTO()

    model_config = ConfigDict(from_attributes=True)


class ReportsResponse(BaseModel):
    reports: list[ReportDTO]
    pending_count: int
    loaded_at: str  # ISO 8601
    event_type_totals: dict[str, int] = {}
    relevance_totals: dict[str, int] = {}
    all_platforms: list[str] = []
    platform_counts: dict[str, int] = {}
    platform_added_counts: dict[str, int] = {}
    has_more: bool = False


class NewCountResponse(BaseModel):
    count: int


class AdmitRequest(BaseModel):
    username: str
    report_ids: list[int]


class AdmitResponse(BaseModel):
    admitted: list[int]


class HideRequest(BaseModel):
    username: str
    hide: bool


class FlagRequest(BaseModel):
    username: str
    flag: bool


class AcknowledgeRequest(BaseModel):
    username: str


class LocationsRequest(BaseModel):
    username: str
    locations: list[LocationEntry]
