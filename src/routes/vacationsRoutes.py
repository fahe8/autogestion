from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from src.controllers.vacationsController import (
    get_vacation_history_controller,
    get_vacation_types_controller,
    get_vacations_controller,
    post_vacations_controller,
    validate_vacations_controller,
    get_all_vacation_requests_hr_controller,
    get_vacation_request_detail_controller,
    validate_vacation_request_status_controller,
    approve_vacation_request_controller,
    reject_vacation_request_controller,
)
from src.core.azure_auth import get_current_azure_user
from src.core.security import permission_required
from src.schemas.authSchema import AzureUserClaims
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


router = APIRouter(prefix="/vacations", tags=["Vacations"])


async def get_current_user_id(user: AzureUserClaims = Depends(get_current_azure_user)) -> str:
    return user.oid


@router.get("/types", response_model=List[VacationTypeOption])
async def get_vacation_types(
    user: AzureUserClaims = Depends(get_current_azure_user),
) -> List[VacationTypeOption]:
    return await get_vacation_types_controller()


@router.get("/{user_id}", response_model=VacationSummary)
async def get_vacations(
    user_id: str,
    user: AzureUserClaims = Depends(get_current_azure_user),
) -> VacationSummary:
    print(user)
    if user_id != user.oid:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permiso para ver las vacaciones de este usuario.",
        )
    return await get_vacations_controller(user_id=user.oid)


@router.get(
    "/requests/validate",
    response_model=VacationRequestValidationResponse,
    dependencies=[Depends(permission_required(["CREATE_VACATION_REQUEST"]))],
)
async def validate_vacation_request(
    user_id: str = Query(min_length=1),
    vacation_type_id: int = Query(gt=0),
    start_date: date = Query(),
    end_date: date = Query(),
    user_id_from_auth: str = Depends(get_current_user_id),
) -> VacationRequestValidationResponse:
    if user_id != user_id_from_auth:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permiso para validar solicitudes de vacaciones para este usuario.",
        )

    payload = VacationRequestValidationRequest(
        user_id=user_id_from_auth,
        vacation_type_id=vacation_type_id,
        start_date=start_date,
        end_date=end_date,
    )
    return await validate_vacations_controller(payload)


@router.post(
    "",
    response_model=VacationRequestCreateResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(permission_required(["CREATE_VACATION_REQUEST"]))],
)
async def post_vacations(
    payload: VacationRequestCreateRequest,
    user_id: str = Depends(get_current_user_id),
) -> VacationRequestCreateResponse:
    payload.user_id = user_id
    return await post_vacations_controller(payload)


@router.get("/requests/history/{user_id}", response_model=VacationRequestHistoryResponse)
async def get_vacation_history(
    user_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    user: AzureUserClaims = Depends(get_current_azure_user),
) -> VacationRequestHistoryResponse:
    if user_id != user.oid:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permiso para ver el historial de vacaciones de este usuario.",
        )
    return await get_vacation_history_controller(user_id=user.oid, page=page, page_size=page_size)


@router.get(
    "/requests/all",
    response_model=VacationRequestHistoryResponse,
    dependencies=[Depends(permission_required(["VIEW_ALL_VACATION_REQUESTS"]))],
)
async def get_all_vacation_requests_hr(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    user_id: Optional[str] = Query(None),
    email: Optional[str] = Query(None),
    name: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    vacation_type_id: Optional[int] = Query(None, gt=0),
    sort_by: Optional[str] = Query(None),
    sort_order: Optional[str] = Query(None, enum=["asc", "desc"]),
) -> VacationRequestHistoryResponse:
    return await get_all_vacation_requests_hr_controller(
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


@router.get(
    "/requests/{request_id}",
    response_model=VacationRequestDetailResponse,
    dependencies=[Depends(permission_required(["VIEW_ALL_VACATION_REQUESTS"]))],
)
async def get_vacation_request_detail(request_id: str) -> VacationRequestDetailResponse:
    return await get_vacation_request_detail_controller(request_id)


@router.patch(
    "/requests/{request_id}/validate",
    response_model=VacationRequestUpdateStatusResponse,
    dependencies=[Depends(permission_required(["APPROVE_VACATION_REQUESTS"]))],
)
async def validate_vacation_request_route(request_id: str) -> VacationRequestUpdateStatusResponse:
    return await validate_vacation_request_status_controller(request_id)


@router.patch(
    "/requests/{request_id}/approve",
    response_model=VacationRequestUpdateStatusResponse,
    dependencies=[Depends(permission_required(["APPROVE_VACATION_REQUESTS"]))],
)
async def approve_vacation_request_route(
    request_id: str, payload: VacationRequestApproveRequest
) -> VacationRequestUpdateStatusResponse:
    return await approve_vacation_request_controller(request_id, payload.payment_date)


@router.patch(
    "/requests/{request_id}/reject",
    response_model=VacationRequestUpdateStatusResponse,
    dependencies=[Depends(permission_required(["VALIDATE_VACATION_REQUESTS","APPROVE_VACATION_REQUESTS"]))],
)
async def reject_vacation_request_route(
    request_id: str, payload: VacationRequestRejectRequest
) -> VacationRequestUpdateStatusResponse:
    return await reject_vacation_request_controller(request_id, payload.rejection_reason)
