from datetime import date, datetime, time, timedelta
from typing import List, Optional

import holidays
from fastapi import HTTPException, status

from src.core.db import prisma
from src.generated.prisma.enums import RequestStatus
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
            return VacationSummary(diasDisponibles=DEFAULT_AVAILABLE_DAYS, diasDisfrutados=0)

        await self._ensure_user_exists(user_id)
        requests = await self.prisma_client.vacationrequest.find_many(
            where={
                "user_id": user_id,
                "OR": [
                    {"status": RequestStatus.VALIDATED},
                    {"status": RequestStatus.APPROVED},
                ],
            }
        )
        used_days = sum(request.requested_days for request in requests)
        return VacationSummary(
            diasDisponibles=max(DEFAULT_AVAILABLE_DAYS - used_days, 0),
            diasDisfrutados=used_days,
        )

    async def get_vacation_types(self) -> List[VacationTypeOption]:
        vacation_types = await self.prisma_client.vacationtype.find_many(order={"name": "asc"})
        return [self._to_vacation_type_option(vacation_type) for vacation_type in vacation_types]

    async def validate_vacation_request(
        self, payload: VacationRequestValidationRequest
    ) -> VacationRequestValidationResponse:
        await self._ensure_user_exists(payload.user_id)
        await self._ensure_vacation_type_exists(payload.vacation_type_id)

        errors: List[str] = []
        excluded_dates = self._get_excluded_dates(payload.start_date, payload.end_date)
        business_dates = self._get_business_dates(payload.start_date, payload.end_date)

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
            requested_days=len(business_dates),
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
                "requested_days": validation.requested_days,
                "payment_date": (
                    self._to_datetime(payload.payment_date) if payload.payment_date else None
                ),
            }
        )

        return VacationRequestCreateResponse(
            id=created_request.id,
            user_id=created_request.user_id,
            vacation_type=self._to_vacation_type_option(vacation_type),
            start_date=created_request.start_date.date(),
            end_date=created_request.end_date.date(),
            requested_days=created_request.requested_days,
            status=created_request.status,
            payment_date=(
                created_request.payment_date.date()
                if created_request.payment_date is not None
                else None
            ),
            created_at=created_request.created_at,
            validation=validation,
        )

    async def get_vacation_history(self, user_id: str) -> VacationRequestHistoryResponse:
        await self._ensure_user_exists(user_id)
        requests = await self.prisma_client.vacationrequest.find_many(
            where={"user_id": user_id},
            include={"vacation_type": True},
            order={"created_at": "desc"},
        )

        items = [
            VacationRequestHistoryItem(
                id=request.id,
                vacation_type=self._to_vacation_type_option(request.vacation_type),
                start_date=request.start_date.date(),
                end_date=request.end_date.date(),
                requested_days=request.requested_days,
                status=request.status,
                rejection_reason=request.rejection_reason,
                payment_date=request.payment_date.date() if request.payment_date else None,
                created_at=request.created_at,
                updated_at=request.updated_at,
            )
            for request in requests
            if request.vacation_type is not None
        ]
        return VacationRequestHistoryResponse(items=items)

    async def _ensure_user_exists(self, user_id: str):
        user = await self.prisma_client.user.find_unique(where={"id": user_id})
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No existe un usuario registrado con el user_id enviado.",
            )
        return user

    async def _ensure_vacation_type_exists(self, vacation_type_id: str):
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
