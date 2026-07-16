from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class StyleDTO(BaseModel):
    color: str | None = None
    weight: float | None = None
    opacity: float | None = None
    fill: bool | None = None
    fillColor: str | None = None
    fillOpacity: float | None = None
    stroke: bool | None = None
    dashArray: str | None = None
    marker_icon: str | None = None
    marker_color: str | None = None

    model_config = ConfigDict(from_attributes=True)


class LayerDTO(BaseModel):
    id: int
    name: str

    model_config = ConfigDict(from_attributes=True)


class LayersResponse(BaseModel):
    layers: list[LayerDTO]


class ScenarioDTO(BaseModel):
    id: int
    name: str
    description: str | None = None

    model_config = ConfigDict(from_attributes=True)


class ScenariosResponse(BaseModel):
    scenarios: list[ScenarioDTO]
