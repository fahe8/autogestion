from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Query, status

from src.controllers.vacationsController import (
    get_vacation_history_controller,
    get_vacation_types_controller,
    get_vacations_controller,
    post_vacations_controller,
    validate_vacations_controller,
)
from src.schemas.vacationsSchema import (
    VacationRequestCreateRequest,
    VacationRequestCreateResponse,
    VacationRequestHistoryResponse,
    VacationRequestValidationRequest,
    VacationRequestValidationResponse,
    VacationSummary,
    VacationTypeOption,
)


router = APIRouter(prefix="/vacations", tags=["Vacations"])


@router.get("", response_model=VacationSummary)
async def get_vacations(user_id: Optional[str] = Query(default=None)) -> VacationSummary:
    return await get_vacations_controller(user_id=user_id)


@router.get("/types", response_model=List[VacationTypeOption])
async def get_vacation_types() -> List[VacationTypeOption]:
    return await get_vacation_types_controller()


@router.get("/requests/validate", response_model=VacationRequestValidationResponse)
async def validate_vacation_request(
    user_id: str = Query(min_length=1),
    vacation_type_id: str = Query(min_length=1),
    start_date: date = Query(),
    end_date: date = Query(),
) -> VacationRequestValidationResponse:
    payload = VacationRequestValidationRequest(
        user_id=user_id,
        vacation_type_id=vacation_type_id,
        start_date=start_date,
        end_date=end_date,
    )
    return await validate_vacations_controller(payload)


@router.post("", response_model=VacationRequestCreateResponse, status_code=status.HTTP_201_CREATED)
async def post_vacations(
    payload: VacationRequestCreateRequest,
) -> VacationRequestCreateResponse:
    return await post_vacations_controller(payload)


@router.get("/requests/history", response_model=VacationRequestHistoryResponse)
async def get_vacation_history(
    user_id: str = Query(min_length=1),
) -> VacationRequestHistoryResponse:
    return await get_vacation_history_controller(user_id=user_id)
