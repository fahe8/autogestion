from datetime import date, datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class VacationSummary(BaseModel):
    diasDisponibles: int
    diasDisfrutados: int
    diasPendientes: int


class VacationTypeOption(BaseModel):
    id: int
    code: str
    name: str


class VacationExcludedDate(BaseModel):
    date: date
    reason: str
    name: Optional[str] = None


class VacationRequestValidationRequest(BaseModel):
    user_id: str = Field(min_length=1)
    vacation_type_id: int = Field(gt=0)
    start_date: date
    end_date: date


class VacationRequestValidationResponse(BaseModel):
    is_valid: bool
    message: str
    total_days: int
    business_dates: List[date] = Field(default_factory=list)
    excluded_dates: List[VacationExcludedDate] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)


class VacationRequestCreateRequest(VacationRequestValidationRequest):
    pass


class VacationRequestCreateResponse(BaseModel):
    id: str
    user_id: str
    vacation_type: VacationTypeOption
    start_date: date
    end_date: date
    total_days: int
    status: str
    payment_date: Optional[date] = None
    created_at: datetime
    validation: VacationRequestValidationResponse


class VacationRequestUser(BaseModel):
    id: str
    email: str
    name: str


class VacationRequestHistoryItem(BaseModel):
    id: str
    vacation_type_code: str = Field(min_length=1),
    vacation_type_name: str = Field(min_length=1),
    start_date: date
    end_date: date
    total_days: int
    status: str
    rejection_reason: Optional[str] = None
    created_at: datetime


class VacationRequestApproveRequest(BaseModel):
    payment_date: date


class VacationRequestRejectRequest(BaseModel):
    rejection_reason: str


class VacationRequestUpdateStatusResponse(BaseModel):
    id: str
    user_id: str
    vacation_type: VacationTypeOption
    start_date: date
    end_date: date
    total_days: int
    status: str
    rejection_reason: Optional[str] = None
    payment_date: Optional[date] = None
    created_at: datetime
    updated_at: datetime


class VacationRequestHistoryResponse(BaseModel):
    items: List[VacationRequestHistoryItem] = Field(default_factory=list)
    total_items: int
    page: int
    page_size: int


class VacationRequestDetailResponse(BaseModel):
    id: str
    user_id: str
    vacation_type: VacationTypeOption
    start_date: date
    end_date: date
    total_days: int
    status: str
    payment_date: Optional[date] = None
    created_at: datetime
    updated_at: datetime
