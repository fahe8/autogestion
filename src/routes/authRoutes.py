from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse, RedirectResponse

from src.controllers.authController import (
    azure_login_callback_controller,
    get_authenticated_user_controller,
    get_azure_auth_config_controller,
    login_with_azure_controller,
    logout_from_session_controller,
    verify_azure_token_controller,
)
from src.core.azure_auth import get_current_azure_user
from src.schemas.authSchema import (
    AzureAuthConfig,
    AzureAuthResponse,
    AzureLogoutResponse,
    AzureTokenRequest,
    AzureUserClaims,
    UserProfile,
)


router = APIRouter(prefix="/auth", tags=["Auth"])


@router.get("/azure/config", response_model=AzureAuthConfig)
async def get_azure_auth_config() -> AzureAuthConfig:
    return await get_azure_auth_config_controller()


@router.post("/azure/verify", response_model=AzureAuthResponse)
async def verify_azure_token(payload: AzureTokenRequest) -> AzureAuthResponse:
    return await verify_azure_token_controller(payload)


@router.get("/login")
async def login_with_azure() -> RedirectResponse:
    return await login_with_azure_controller()


@router.get("/callback")
async def azure_login_callback(
    request: Request,
    code: Optional[str] = Query(default=None),
    state: Optional[str] = Query(default=None),
    error: Optional[str] = Query(default=None),
    error_description: Optional[str] = Query(default=None),
) -> RedirectResponse:
    return await azure_login_callback_controller(
        request,
        code=code,
        state=state,
        error=error,
        error_description=error_description,
    )


@router.post("/logout", response_model=AzureLogoutResponse)
async def logout_from_session() -> JSONResponse:
    return await logout_from_session_controller()


@router.get("/me", response_model=UserProfile)
async def get_authenticated_user(
    current_user: AzureUserClaims = Depends(get_current_azure_user),
) -> UserProfile:
    return await get_authenticated_user_controller(current_user)
