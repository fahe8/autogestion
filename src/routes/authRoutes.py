from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse, RedirectResponse

from src.core.azure_auth import (
    build_azure_login_redirect_url,
    clear_authenticated_session,
    clear_login_flow_cookies,
    complete_azure_login,
    get_current_azure_user,
    set_authenticated_session,
    set_login_flow_cookies,
    verify_azure_access_token,
)
from src.core.settings import settings
from src.schemas.authSchema import (
    AzureAuthConfig,
    AzureAuthResponse,
    AzureLogoutResponse,
    AzureTokenRequest,
    AzureUserClaims,
    UserProfile,
)
from src.services.userService import ensure_local_user_from_azure, get_user_profile


router = APIRouter(prefix="/auth", tags=["Auth"])


@router.get("/azure/config", response_model=AzureAuthConfig)
async def get_azure_auth_config() -> AzureAuthConfig:
    return AzureAuthConfig(
        enabled=settings.azure_ad_enabled,
        client_id=settings.azure_ad_client_id,
        tenant_id=settings.azure_ad_tenant_id,
        authority=settings.azure_ad_authority,
        redirect_uri=settings.azure_ad_redirect_uri,
        scopes=settings.azure_ad_scopes,
        openid_configuration_url=settings.azure_ad_openid_config_url,
    )


@router.post("/azure/verify", response_model=AzureAuthResponse)
async def verify_azure_token(payload: AzureTokenRequest) -> AzureAuthResponse:
    user = await verify_azure_access_token(payload.access_token)
    return AzureAuthResponse(message="Token de Azure validado correctamente.", user=user)


@router.get("/login")
async def login_with_azure() -> RedirectResponse:
    login_url, flow_data = build_azure_login_redirect_url()
    response = RedirectResponse(login_url, status_code=status.HTTP_307_TEMPORARY_REDIRECT)
    set_login_flow_cookies(response, flow_data)
    return response


@router.get("/callback", response_model=AzureAuthResponse)
async def azure_login_callback(
    request: Request,
    code: Optional[str] = Query(default=None),
    state: Optional[str] = Query(default=None),
    error: Optional[str] = Query(default=None),
    error_description: Optional[str] = Query(default=None),
) -> JSONResponse:
    if error:
        detail = error_description or error
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Azure AD devolvio un error durante el login: {detail}",
        )

    if not code or not state:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Azure AD no devolvio el code o el state esperado.",
        )

    user, id_token = await complete_azure_login(
        code=code,
        state=state,
        expected_state=request.cookies.get("autogestion_oauth_state"),
        code_verifier=request.cookies.get("autogestion_oauth_code_verifier"),
        expected_nonce=request.cookies.get("autogestion_oauth_nonce"),
    )
    await ensure_local_user_from_azure(user)
    response = JSONResponse(
        content=AzureAuthResponse(
            message="Login con Azure completado correctamente.",
            user=user,
        ).model_dump()
    )
    set_authenticated_session(response, id_token, user)
    clear_login_flow_cookies(response)
    return response


@router.post("/logout", response_model=AzureLogoutResponse)
async def logout_from_session() -> JSONResponse:
    response = JSONResponse(
        content=AzureLogoutResponse(
            message="La sesion local de Azure fue cerrada correctamente."
        ).model_dump()
    )
    clear_authenticated_session(response)
    clear_login_flow_cookies(response)
    return response


@router.get("/me", response_model=UserProfile)
async def get_authenticated_user(
    current_user: AzureUserClaims = Depends(get_current_azure_user),
) -> UserProfile:
    return await get_user_profile(current_user)
