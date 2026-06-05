from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask

from src.dependencies.auth import get_current_user
from src.models import User
from src.schemas.estimate import EstimateFactsPayload, EstimateTotalsResponse
from src.services.estimates.service import build_estimate_from_payload, export_estimate_payload_xlsx

router = APIRouter(prefix="/estimates", tags=["estimates"])


@router.post("/isaev/totals", response_model=EstimateTotalsResponse)
async def calculate_isaev_estimate_totals(
    payload: EstimateFactsPayload,
    current_user: User = Depends(get_current_user),
) -> EstimateTotalsResponse:
    estimate = build_estimate_from_payload(payload.model_dump())
    return EstimateTotalsResponse(
        rough_total=estimate.rough_total,
        clean_total=estimate.clean_total,
        rough_discounted_total=estimate.rough_discounted_total,
        clean_discounted_total=estimate.clean_discounted_total,
        discounted_total=estimate.discounted_total,
    )


@router.post("/isaev/export")
async def export_isaev_estimate(
    payload: EstimateFactsPayload,
    current_user: User = Depends(get_current_user),
) -> FileResponse:
    output_path = export_estimate_payload_xlsx(payload.model_dump())
    filename = "smeta_isaev_group.xlsx"
    return FileResponse(
        path=output_path,
        filename=filename,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        background=BackgroundTask(output_path.unlink, missing_ok=True),
    )
