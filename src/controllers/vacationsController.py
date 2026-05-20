from typing import List, Optional

from src.schemas.vacationsSchema import (
    VacationRequestCreateRequest,
    VacationRequestCreateResponse,
    VacationRequestHistoryResponse,
    VacationRequestValidationRequest,
    VacationRequestValidationResponse,
    VacationSummary,
    VacationTypeOption,
    VacationRequestDetailResponse,
    VacationRequestApproveRequest,
    VacationRequestRejectRequest,
    VacationRequestUpdateStatusResponse,
)
from src.services.vacationsService import VacationService
from datetime import datetime, date



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


async def get_vacation_history_controller(
    user_id: str, page: int, page_size: int
) -> VacationRequestHistoryResponse:
    return await VacationService().get_vacation_history(
        user_id=user_id, page=page, page_size=page_size
    )


async def get_all_vacation_requests_hr_controller(
    page: int,
    page_size: int,
    user_id: Optional[str],
    email: Optional[str],
    name: Optional[str],
    status: Optional[str],
    vacation_type_id: Optional[int],
    sort_by: Optional[str],
    sort_order: Optional[str],
) -> VacationRequestHistoryResponse:
    return await VacationService().get_all_vacation_requests_hr(
        page=page,
        page_size=page_size,
        user_id=user_id,
        email=email,
        name=name,
        status=status,
        vacation_type_id=vacation_type_id,
        sort_by=sort_by,
        sort_order=sort_order,
    )


async def get_vacation_request_detail_controller(request_id: str) -> VacationRequestDetailResponse:
    return await VacationService().get_vacation_request_detail(request_id)


async def validate_vacation_request_status_controller(
    request_id: str,
) -> VacationRequestUpdateStatusResponse:
    return await VacationService().validate_vacation_request_status(request_id)


async def approve_vacation_request_controller(
    request_id: str, payment_date: date
) -> VacationRequestUpdateStatusResponse:
    return await VacationService().approve_vacation_request(request_id, payment_date)


async def reject_vacation_request_controller(
    request_id: str, rejection_reason: str
) -> VacationRequestUpdateStatusResponse:
    return await VacationService().reject_vacation_request(request_id, rejection_reason)
