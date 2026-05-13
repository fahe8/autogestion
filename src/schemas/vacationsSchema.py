from datetime import date, datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class VacationSummary(BaseModel):
    diasDisponibles: int
    diasDisfrutados: int


class VacationTypeOption(BaseModel):
    id: str
    code: str
    name: str


class VacationExcludedDate(BaseModel):
    date: date
    reason: str
    name: Optional[str] = None


class VacationRequestValidationRequest(BaseModel):
    user_id: str = Field(min_length=1)
    vacation_type_id: str = Field(min_length=1)
    start_date: date
    end_date: date


class VacationRequestValidationResponse(BaseModel):
    is_valid: bool
    message: str
    requested_days: int
    business_dates: List[date] = Field(default_factory=list)
    excluded_dates: List[VacationExcludedDate] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)


class VacationRequestCreateRequest(VacationRequestValidationRequest):
    payment_date: Optional[date] = None


class VacationRequestCreateResponse(BaseModel):
    id: str
    user_id: str
    vacation_type: VacationTypeOption
    start_date: date
    end_date: date
    requested_days: int
    status: str
    payment_date: Optional[date] = None
    created_at: datetime
    validation: VacationRequestValidationResponse


class VacationRequestHistoryItem(BaseModel):
    id: str
    vacation_type: VacationTypeOption
    start_date: date
    end_date: date
    requested_days: int
    status: str
    rejection_reason: Optional[str] = None
    payment_date: Optional[date] = None
    created_at: datetime
    updated_at: datetime


class VacationRequestHistoryResponse(BaseModel):
    items: List[VacationRequestHistoryItem] = Field(default_factory=list)
