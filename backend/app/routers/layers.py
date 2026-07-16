from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.params import Depends
from sqlalchemy.orm import Session

from ..db import get_db
from ..schemas.layer import LayersResponse, ScenariosResponse
from ..services import layer_service as svc

# ---------------------------------------------------------------------------
# Layers router
# ---------------------------------------------------------------------------

router = APIRouter(prefix="/api/v1/layers", tags=["layers"])


@router.get("/", response_model=LayersResponse)
def list_layers(session: Session = Depends(get_db)) -> LayersResponse:
    layers = svc.get_layers(session)
    return LayersResponse(layers=layers)


@router.get("/{layer_id}/geojson")
def layer_geojson(
    layer_id: int,
    session: Session = Depends(get_db),
) -> dict[str, Any]:
    result = svc.layer_to_geojson(layer_id, session)
    if result.get("layer_name") is None:
        raise HTTPException(status_code=404, detail="Layer not found")
    return result


# ---------------------------------------------------------------------------
# Scenarios router  (separate prefix /api/v1/scenarios)
# ---------------------------------------------------------------------------

scenarios_router = APIRouter(prefix="/api/v1/scenarios", tags=["scenarios"])


@scenarios_router.get("/", response_model=ScenariosResponse)
def list_scenarios(session: Session = Depends(get_db)) -> ScenariosResponse:
    scenarios = svc.get_scenarios(session)
    return ScenariosResponse(scenarios=scenarios)


@scenarios_router.get("/{scenario_id}/geojson")
def scenario_geojson(
    scenario_id: int,
    session: Session = Depends(get_db),
) -> dict[str, Any]:
    result = svc.scenario_to_geojson(scenario_id, session)
    if result.get("scenario_name") is None:
        raise HTTPException(status_code=404, detail="Scenario not found")
    return result
