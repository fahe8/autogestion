from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class AzureAuthConfig(BaseModel):
    enabled: bool
    client_id: str
    tenant_id: str
    authority: str
    redirect_uri: str
    scopes: List[str]
    openid_configuration_url: str


class AzureTokenRequest(BaseModel):
    access_token: str = Field(min_length=1)


class AzureUserClaims(BaseModel):
    sub: str
    email: str = ""
    name: Optional[str] = None
    preferred_username: Optional[str] = None
    oid: Optional[str] = None
    tid: Optional[str] = None
    aud: str
    iss: str
    roles: List[str] = Field(default_factory=list)
    scopes: List[str] = Field(default_factory=list)
    employee_id: Optional[str] = None
    raw_claims: Dict[str, Any] = Field(default_factory=dict)


class Permission(BaseModel):
    id: int
    name: str
    description: Optional[str] = None


class Role(BaseModel):
    id: int
    name: str
    description: Optional[str] = None



class UserProfile(BaseModel):
    id: str
    email: str
    name: str
    number_identity: Optional[str] = None
    siigo_employee_id: Optional[str] = None
    vacation_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    role: Role
    all_permissions: List[str] = Field(default_factory=list)


class AzureAuthResponse(BaseModel):
    message: str
    user: AzureUserClaims


class AzureLoginStartResponse(BaseModel):
    login_url: str
    redirect_uri: str


class AzureLogoutResponse(BaseModel):
    message: str
