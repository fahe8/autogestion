from typing import List, Optional

from src.schemas.vacationsSchema import (
    VacationRequestCreateRequest,
    VacationRequestCreateResponse,
    VacationRequestHistoryResponse,
    VacationRequestValidationRequest,
    VacationRequestValidationResponse,
    VacationSummary,
    VacationTypeOption,
)
from src.services.vacationsService import VacationService


async def get_vacations_controller(user_id: Optional[str] = None) -> VacationSummary:
    return await VacationService().get_vacation_summary(user_id=user_id)


async def get_vacation_types_controller() -> List[VacationTypeOption]:
    return await VacationService().get_vacation_types()


async def validate_vacations_controller(
    payload: VacationRequestValidationRequest,
) -> VacationRequestValidationResponse:
    return await VacationService().validate_vacation_request(payload)


async def post_vacations_controller(
    payload: VacationRequestCreateRequest,
) -> VacationRequestCreateResponse:
    return await VacationService().create_vacation_request(payload)


async def get_vacation_history_controller(user_id: str) -> VacationRequestHistoryResponse:
    return await VacationService().get_vacation_history(user_id=user_id)
