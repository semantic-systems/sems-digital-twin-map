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
    status: str | None = None  # 'ok', 'error', 'no_candidates' — geocoding outcome for this mention

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
    event_types: list[str] = []
    relevance: str
    processing_status: str | None = None  # 'ok' (default/legacy), 'error', 'no_text'
    geo_recognition_status: str | None = None  # 'ok' (default/legacy), 'error'
    # Zero or more of 'classification_failed' | 'no_text' | 'geo_recognition_failed' |
    # 'geoparsing_failed' — classification and the geo pipeline fail independently,
    # so a report can carry more than one at once. Empty when it isn't an issue.
    issue_kinds: list[str] = []
    author: str | None = None
    locations: list[LocationEntry] = []
    original_locations: list[LocationEntry] = []
    user_state: UserStateDTO = UserStateDTO()

    model_config = ConfigDict(from_attributes=True)


class DotDTO(BaseModel):
    """A single map-dot, one per geocoded location (not one per report — a
    report with 3 locations yields 3 of these pre-clustering). Matches the dict
    build_dots() constructs; giving it a real schema (rather than list[dict])
    is what lets the frontend's DotDTO type be generated from this schema
    instead of hand-maintained in parallel."""
    report_id: int
    lat: float
    lon: float
    seen: bool
    hide: bool
    flag: bool
    new: bool
    location_name: str
    location_display: str
    text: str
    author: str
    platform: str
    timestamp: str
    event_types: list[str] = []
    relevance: str
    url: str
    location_bbox_area: float | None = None
    location_bbox: list[float] | None = None


class DotsResponse(BaseModel):
    dots: list[DotDTO] = []


class ReportsResponse(BaseModel):
    reports: list[ReportDTO]
    pending_count: int
    loaded_at: str  # ISO 8601
    # Facet fields are None (not empty dicts) under the lean views
    # (only_new/only_issues), where the expensive facet scan is skipped —
    # None means "not computed this request, keep what you had", while {} is a
    # real result meaning "nothing matches". Making that distinction part of
    # the schema replaces the old implicit convention (zeros + the client just
    # having to know not to apply them), which was silently violated twice.
    event_type_totals: dict[str, int] | None = None
    relevance_totals: dict[str, int] | None = None
    location_counts: dict[str, int] | None = None
    processing_status_totals: dict[str, int] = {}
    # Reports-view totals, always computed regardless of which tab is active (the
    # Issues-view counterpart is processing_status_totals' sum) — see
    # report_service.get_reports. Together with processing_status_totals, these
    # let the frontend show a tab-independent combined header plus a plain total
    # on each tab pill.
    reports_total_count: int = 0
    reports_unseen_count: int = 0
    # None under lean views, same convention as the facet fields above.
    all_platforms: list[str] | None = None
    platform_counts: dict[str, int] | None = None
    platform_added_counts: dict[str, int] | None = None
    has_more: bool = False
    total_count: int = 0
    unseen_count: int = 0


class ReportsBundleResponse(ReportsResponse):
    """Reports list + map dots in one payload, so a filter change needs a single
    round trip instead of two parallel requests contending on one sync worker."""
    dots: list[DotDTO] = []


class NewCountResponse(BaseModel):
    count: int


class VersionResponse(BaseModel):
    """Opaque change token — see report_service.get_change_token."""
    token: str


# Request bodies below no longer carry `username` — the acting user is derived
# server-side from the session (see auth.get_current_username). AcknowledgeRequest
# has no remaining fields, so acknowledge/logout-style endpoints take no body.

class HideRequest(BaseModel):
    hide: bool


class FlagRequest(BaseModel):
    flag: bool


class LocationsRequest(BaseModel):
    locations: list[LocationEntry]
