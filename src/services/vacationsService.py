from datetime import date, datetime, time, timedelta
from typing import Any, Dict, List, Optional

import holidays
from fastapi import HTTPException, status

from src.core.db import prisma
from src.generated.enums import RequestStatus
from src.schemas.vacationsSchema import (
    VacationExcludedDate,
    VacationRequestCreateRequest,
    VacationRequestCreateResponse,
    VacationRequestHistoryItem,
    VacationRequestHistoryResponse,
    VacationRequestValidationRequest,
    VacationRequestValidationResponse,
    VacationSummary,
    VacationTypeOption,
    VacationRequestUser,
    VacationRequestDetailResponse,
    VacationRequestUpdateStatusResponse,
)


ACTIVE_REQUEST_STATUSES = (
    RequestStatus.PENDING,
    RequestStatus.VALIDATED,
    RequestStatus.APPROVED,
)
DEFAULT_AVAILABLE_DAYS = 15


class VacationService:
    def __init__(self, prisma_client=prisma):
        self.prisma_client = prisma_client

    async def get_vacation_summary(self, user_id: Optional[str] = None) -> VacationSummary:
        if not user_id:
            return VacationSummary(diasDisponibles=0, diasDisfrutados=0, diasPendientes=0)

        user = await self._ensure_user_exists(user_id, include_vacation=True)
    
        if not user.vacation:
            return VacationSummary(diasDisponibles=0, diasDisfrutados=0, diasPendientes=0)

        return VacationSummary(
            diasDisponibles=user.vacation.days_available,
            diasDisfrutados=user.vacation.days_used,
            diasPendientes=user.vacation.days_pending,
        )

    async def get_vacation_types(self) -> List[VacationTypeOption]:
        vacation_types = await self.prisma_client.vacationtype.find_many(order={"name": "asc"})
        return [self._to_vacation_type_option(vacation_type) for vacation_type in vacation_types]

    async def validate_vacation_request(
        self, payload: VacationRequestValidationRequest
    ) -> VacationRequestValidationResponse:
        user = await self._ensure_user_exists(payload.user_id, include_vacation=True)
        await self._ensure_vacation_type_exists(payload.vacation_type_id)

        errors: List[str] = []
        excluded_dates = self._get_excluded_dates(payload.start_date, payload.end_date)
        business_dates = self._get_business_dates(payload.start_date, payload.end_date)
        total_days = len(business_dates)
        
        current_date = date.today()

        if payload.start_date < current_date:
            errors.append("La fecha inicial no puede ser anterior a la fecha actual.")
        if payload.end_date < current_date:
            errors.append("La fecha final no puede ser anterior a la fecha actual.")
        
        if payload.start_date > payload.end_date:
            errors.append("La fecha inicial no puede ser mayor a la fecha final.")
        else:
            if self._is_non_business_day(payload.start_date):
                errors.append(
                    "La fecha inicial no puede ser sabado, domingo o festivo colombiano."
                )
            if self._is_non_business_day(payload.end_date):
                errors.append(
                    "La fecha final no puede ser sabado, domingo o festivo colombiano."
                )

        if not business_dates:
            errors.append("El rango seleccionado no contiene dias habiles.")

        # Validación de saldo de días
        if user.vacation:
            if total_days > user.vacation.days_pending:
                errors.append(
                    f"La cantidad de días solicitados ({total_days}) supera los días pendientes disponibles ({user.vacation.days_pending})."
                )
        else:
            errors.append("No se encontró un registro de vacaciones vinculado a su usuario.")

        overlapping_requests = await self._find_overlapping_requests(
            user_id=payload.user_id,
            start_date=payload.start_date,
            end_date=payload.end_date,
        )
        if overlapping_requests:
            errors.append("Ya existe una solicitud que se cruza con el rango seleccionado.")

        is_valid = not errors
        return VacationRequestValidationResponse(
            is_valid=is_valid,
            message=(
                "La solicitud es valida y se puede registrar."
                if is_valid
                else "La solicitud no supera las validaciones."
            ),
            total_days=total_days,
            business_dates=business_dates,
            excluded_dates=excluded_dates,
            errors=errors,
        )

    async def create_vacation_request(
        self, payload: VacationRequestCreateRequest
    ) -> VacationRequestCreateResponse:
        validation = await self.validate_vacation_request(payload)
        if not validation.is_valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "message": validation.message,
                    "errors": validation.errors,
                    "excluded_dates": [item.model_dump() for item in validation.excluded_dates],
                },
            )

        vacation_type = await self._ensure_vacation_type_exists(payload.vacation_type_id)
        created_request = await self.prisma_client.vacationrequest.create(
            data={
                "user_id": payload.user_id,
                "vacation_type_id": payload.vacation_type_id,
                "start_date": self._to_datetime(payload.start_date),
                "end_date": self._to_datetime(payload.end_date),
                "requested_days": validation.total_days,
            }
        )

        return VacationRequestCreateResponse(
            id=created_request.id,
            user_id=created_request.user_id,
            vacation_type=self._to_vacation_type_option(vacation_type),
            start_date=created_request.start_date.date(),
            end_date=created_request.end_date.date(),
            total_days=created_request.requested_days,
            status=created_request.status,
            payment_date=(
                created_request.payment_date.date()
                if created_request.payment_date is not None
                else None
            ),
            created_at=created_request.created_at,
            validation=validation,
        )

    async def get_vacation_history(
        self, user_id: str, page: int, page_size: int
    ) -> VacationRequestHistoryResponse:
        await self._ensure_user_exists(user_id)
        skip = (page - 1) * page_size
        take = page_size

        requests = await self.prisma_client.vacationrequest.find_many(
            where={"user_id": user_id},
            include={"vacation_type": True},
            order={"created_at": "desc"},
            skip=skip,
            take=take,
        )

        total_requests = await self.prisma_client.vacationrequest.count(
            where={"user_id": user_id}
        )

        items = [
            VacationRequestHistoryItem(
                id=request.id,
                vacation_type_code=request.vacation_type.code,
                vacation_type_name=request.vacation_type.name,
                start_date=request.start_date.date(),
                end_date=request.end_date.date(),
                total_days=request.requested_days,
                status=request.status,
                rejection_reason=request.rejection_reason,
                created_at=request.created_at,
            )
            for request in requests
            if request.vacation_type is not None
        ]
        return VacationRequestHistoryResponse(
            items=items, total_items=total_requests, page=page, page_size=page_size
        )

    async def get_vacation_request_detail(self, request_id: str) -> VacationRequestDetailResponse:
        print(request_id)
        request = await self.prisma_client.vacationrequest.find_unique(
            where={"id": request_id},
            include={"vacation_type": True},
        )

        if not request:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Solicitud de vacaciones no encontrada.",
            )
        if not request.vacation_type:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Tipo de vacaciones no encontrado para la solicitud.",
            )

        return VacationRequestDetailResponse(
            id=request.id,
            user_id=request.user_id,
            vacation_type=self._to_vacation_type_option(request.vacation_type),
            start_date=request.start_date.date(),
            end_date=request.end_date.date(),
            total_days=request.requested_days,
            status=request.status,
            payment_date=request.payment_date.date() if request.payment_date else None,
            created_at=request.created_at,
            updated_at=request.updated_at,
        )

    async def validate_vacation_request_status(
        self, request_id: str
    ) -> VacationRequestUpdateStatusResponse:
        print(f"Validando solicitud de vacaciones con ID: {request_id}")

        request = await self.prisma_client.vacationrequest.find_unique(
            where={"id": request_id},
            include={"vacation_type": True},
        )

        if not request:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Solicitud de vacaciones no encontrada.",
            )
        if not request.vacation_type:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Tipo de vacaciones no encontrado para la solicitud.",
            )

        current_status = RequestStatus(request.status)
        new_status = RequestStatus.VALIDATED

        allowed_transitions = {
            RequestStatus.PENDING: [RequestStatus.VALIDATED, RequestStatus.REJECTED],
            RequestStatus.VALIDATED: [RequestStatus.APPROVED, RequestStatus.REJECTED],
            RequestStatus.APPROVED: [],
            RequestStatus.REJECTED: [],
        }

        if new_status not in allowed_transitions.get(current_status, []):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Transición de estado no válida de '{current_status.value}' a '{new_status.value}'.",
            )

        updated_request = await self.prisma_client.vacationrequest.update(
            where={"id": request_id},
            data={
                "status": new_status,
                "updated_at": datetime.now(),
            },
        )

        return VacationRequestUpdateStatusResponse(
            id=updated_request.id,
            user_id=updated_request.user_id,
            vacation_type=self._to_vacation_type_option(request.vacation_type),
            start_date=updated_request.start_date.date(),
            end_date=updated_request.end_date.date(),
            total_days=request.requested_days,
            status=updated_request.status,
            rejection_reason=updated_request.rejection_reason,
            payment_date=updated_request.payment_date.date() if updated_request.payment_date else None,
            created_at=updated_request.created_at,
            updated_at=updated_request.updated_at,
        )

    async def approve_vacation_request(
        self, request_id: str, payment_date: date
    ) -> VacationRequestUpdateStatusResponse:
        request = await self.prisma_client.vacationrequest.find_unique(
            where={"id": request_id},
            include={"vacation_type": True},
        )

        if not request:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Solicitud de vacaciones no encontrada.",
            )
        if not request.vacation_type:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Tipo de vacaciones no encontrado para la solicitud.",
            )

        current_status = RequestStatus(request.status)
        new_status = RequestStatus.APPROVED

        allowed_transitions = {
            RequestStatus.PENDING: [RequestStatus.VALIDATED, RequestStatus.REJECTED],
            RequestStatus.VALIDATED: [RequestStatus.APPROVED, RequestStatus.REJECTED],
            RequestStatus.APPROVED: [],
            RequestStatus.REJECTED: [],
        }

        if new_status not in allowed_transitions.get(current_status, []):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Transición de estado no válida de '{current_status.value}' a '{new_status.value}'.",
            )

        updated_request = await self.prisma_client.vacationrequest.update(
            where={"id": request_id},
            data={
                "status": new_status,
                "payment_date": self._to_datetime(payment_date),
                "updated_at": datetime.now(),
            },
        )

        return VacationRequestUpdateStatusResponse(
            id=updated_request.id,
            user_id=updated_request.user_id,
            vacation_type=self._to_vacation_type_option(request.vacation_type),
            start_date=updated_request.start_date.date(),
            end_date=updated_request.end_date.date(),
            total_days=request.requested_days,
            status=updated_request.status,
            rejection_reason=updated_request.rejection_reason,
            payment_date=updated_request.payment_date.date() if updated_request.payment_date else None,
            created_at=updated_request.created_at,
            updated_at=updated_request.updated_at,
        )

    async def reject_vacation_request(
        self, request_id: str, rejection_reason: str
    ) -> VacationRequestUpdateStatusResponse:
        request = await self.prisma_client.vacationrequest.find_unique(
            where={"id": request_id},
            include={"vacation_type": True},
        )

        if not request:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Solicitud de vacaciones no encontrada.",
            )
        if not request.vacation_type:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Tipo de vacaciones no encontrado para la solicitud.",
            )

        current_status = RequestStatus(request.status)
        new_status = RequestStatus.REJECTED

        allowed_transitions = {
            RequestStatus.PENDING: [RequestStatus.VALIDATED, RequestStatus.REJECTED],
            RequestStatus.VALIDATED: [RequestStatus.APPROVED, RequestStatus.REJECTED],
            RequestStatus.APPROVED: [],
            RequestStatus.REJECTED: [],
        }

        if new_status not in allowed_transitions.get(current_status, []):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Transición de estado no válida de '{current_status.value}' a '{new_status.value}'.",
            )

        if not rejection_reason:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="La razón de rechazo es obligatoria cuando el estado es REJECTED.",
            )

        updated_request = await self.prisma_client.vacationrequest.update(
            where={"id": request_id},
            data={
                "status": new_status,
                "rejection_reason": rejection_reason,
                "updated_at": datetime.now(),
            },
        )

        return VacationRequestUpdateStatusResponse(
            id=updated_request.id,
            user_id=updated_request.user_id,
            vacation_type=self._to_vacation_type_option(request.vacation_type),
            start_date=updated_request.start_date.date(),
            end_date=updated_request.end_date.date(),
            total_days=request.requested_days,
            status=updated_request.status,
            rejection_reason=updated_request.rejection_reason,
            payment_date=updated_request.payment_date.date() if updated_request.payment_date else None,
            created_at=updated_request.created_at,
            updated_at=updated_request.updated_at,
        )

    async def get_all_vacation_requests_hr(
        self,
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
        skip = (page - 1) * page_size
        take = page_size

        where_conditions: Dict[str, Any] = {}
        user_where_conditions: Dict[str, Any] = {}

        if user_id:
            where_conditions["user_id"] = user_id
        if email:
            user_where_conditions["email"] = {"contains": email, "mode": "insensitive"}
        if name:
            user_where_conditions["name"] = {"contains": name, "mode": "insensitive"}

        if user_where_conditions:
            where_conditions["user"] = user_where_conditions

        if status:
            where_conditions["status"] = RequestStatus(status)
        if vacation_type_id:
            where_conditions["vacation_type_id"] = vacation_type_id

        order_by_clause: Dict[str, Any] = {}
        order_direction = sort_order if sort_order else "asc"

        if sort_by == "user_id":
            order_by_clause = {"user_id": order_direction}
        elif sort_by == "email":
            order_by_clause = {"user": {"email": order_direction}}
        elif sort_by == "name":
            order_by_clause = {"user": {"name": order_direction}}
        elif sort_by == "status":
            order_by_clause = {"status": order_direction}
        elif sort_by == "vacation_type_id":
            order_by_clause = {"vacation_type_id": order_direction}
        elif sort_by == "start_date":
            order_by_clause = {"start_date": order_direction}
        elif sort_by == "end_date":
            order_by_clause = {"end_date": order_direction}
        elif sort_by == "requested_days":
                order_by_clause = {"total_days": order_direction}
        else:  # Default to created_at if sort_by is None or invalid
            order_by_clause = {"created_at": "desc"}

        requests = await self.prisma_client.vacationrequest.find_many(
            where=where_conditions,
            include={"user": True, "vacation_type": True},
            order=order_by_clause,
            skip=skip,
            take=take,
        )

        total_requests = await self.prisma_client.vacationrequest.count(where=where_conditions)

        items = [
            VacationRequestHistoryItem(
                id=request.id,
                user=VacationRequestUser(
                    id=request.user.id, email=request.user.email, name=request.user.name
                ),
                vacation_type=self._to_vacation_type_option(request.vacation_type),
                start_date=request.start_date.date(),
                end_date=request.end_date.date(),
                total_days=request.requested_days,
                status=request.status,
                rejection_reason=request.rejection_reason,
                payment_date=request.payment_date.date() if request.payment_date else None,
                created_at=request.created_at,
                updated_at=request.updated_at,
            )
            for request in requests
            if request.vacation_type is not None and request.user is not None
        ]
        return VacationRequestHistoryResponse(
            items=items, total_items=total_requests, page=page, page_size=page_size
        )

    async def _ensure_user_exists(self, user_id: str, include_vacation: bool = False):
        include = {"vacation": True} if include_vacation else None
        user = await self.prisma_client.user.find_unique(where={"id": user_id}, include=include)
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No existe un usuario registrado con el user_id enviado.",
            )
        return user

    async def _ensure_vacation_type_exists(self, vacation_type_id: int):
        vacation_type = await self.prisma_client.vacationtype.find_unique(
            where={"id": vacation_type_id}
        )
        if vacation_type is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No existe un tipo de vacaciones con el id enviado.",
            )
        return vacation_type

    async def _find_overlapping_requests(
        self,
        user_id: str,
        start_date: date,
        end_date: date,
    ):
        if start_date > end_date:
            return []

        return await self.prisma_client.vacationrequest.find_many(
            where={
                "user_id": user_id,
                "start_date": {"lte": self._to_datetime(end_date)},
                "end_date": {"gte": self._to_datetime(start_date)},
                "OR": [{"status": status_value} for status_value in ACTIVE_REQUEST_STATUSES],
            }
        )

    def _get_business_dates(self, start_date: date, end_date: date) -> List[date]:
        if start_date > end_date:
            return []

        business_dates: List[date] = []
        current_date = start_date
        while current_date <= end_date:
            if not self._is_non_business_day(current_date):
                business_dates.append(current_date)
            current_date += timedelta(days=1)
        return business_dates

    def _get_excluded_dates(self, start_date: date, end_date: date) -> List[VacationExcludedDate]:
        if start_date > end_date:
            return []

        excluded_dates: List[VacationExcludedDate] = []
        colombia_holidays = self._get_colombia_holidays(start_date, end_date)
        current_date = start_date
        while current_date <= end_date:
            if current_date.weekday() >= 5:
                excluded_dates.append(
                    VacationExcludedDate(date=current_date, reason="weekend")
                )
            elif current_date in colombia_holidays:
                excluded_dates.append(
                    VacationExcludedDate(
                        date=current_date,
                        reason="holiday",
                        name=str(colombia_holidays.get(current_date)),
                    )
                )
            current_date += timedelta(days=1)
        return excluded_dates

    def _is_non_business_day(self, value: date) -> bool:
        if value.weekday() >= 5:
            return True
        return value in self._get_colombia_holidays(value, value)

    def _get_colombia_holidays(self, start_date: date, end_date: date):
        years = list(range(start_date.year, end_date.year + 1))
        return holidays.country_holidays("CO", years=years)

    def _to_datetime(self, value: date) -> datetime:
        return datetime.combine(value, time.min)

    def _to_vacation_type_option(self, vacation_type) -> VacationTypeOption:
        return VacationTypeOption(
            id=vacation_type.id,
            code=vacation_type.code,
            name=vacation_type.name,
        )
