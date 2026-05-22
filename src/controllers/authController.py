from typing import Optional

from fastapi import HTTPException, Request, status
from fastapi.responses import JSONResponse, RedirectResponse

from src.core.azure_auth import (
    build_azure_login_redirect_url,
    clear_authenticated_session,
    clear_login_flow_cookies,
    clear_onboarding_session,
    complete_azure_login,
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
from src.services.userService import (
    create_local_user_from_azure,
    find_local_user_by_email,
    get_user_profile,
)


async def get_azure_auth_config_controller() -> AzureAuthConfig:
    return AzureAuthConfig(
        enabled=settings.azure_ad_enabled,
        client_id=settings.azure_ad_client_id,
        tenant_id=settings.azure_ad_tenant_id,
        authority=settings.azure_ad_authority,
        redirect_uri=settings.azure_ad_redirect_uri,
        scopes=settings.azure_ad_scopes,
        openid_configuration_url=settings.azure_ad_openid_config_url,
    )


async def verify_azure_token_controller(payload: AzureTokenRequest) -> AzureAuthResponse:
    user = await verify_azure_access_token(payload.access_token)
    return AzureAuthResponse(message="Token de Azure validado correctamente.", user=user)


async def login_with_azure_controller() -> RedirectResponse:
    login_url, flow_data = build_azure_login_redirect_url()
    response = RedirectResponse(login_url, status_code=status.HTTP_307_TEMPORARY_REDIRECT)
    set_login_flow_cookies(response, flow_data)
    return response


async def azure_login_callback_controller(
    request: Request,
    *,
    code: Optional[str],
    state: Optional[str],
    error: Optional[str],
    error_description: Optional[str],
) -> RedirectResponse:
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

    existing_user = await find_local_user_by_email(user.email)
    if existing_user is None:
        # Si el usuario no existe, intentamos crearlo automaticamente usando el employee_id
        if not user.employee_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="No se encontro el employeeId en Azure. Contacte al administrador para configurar su ID de empleado.",
            )
        
        await create_local_user_from_azure(
            user,
            number_identity=user.employee_id,
        )
        
        response = RedirectResponse(
            url=settings.frontend_post_login_redirect_url,
            status_code=status.HTTP_302_FOUND,
        )
        clear_onboarding_session(response)
        set_authenticated_session(response, id_token, user)
    else:
        response = RedirectResponse(
            url=settings.frontend_post_login_redirect_url,
            status_code=status.HTTP_302_FOUND,
        )
        clear_onboarding_session(response)
        set_authenticated_session(response, id_token, user)

    clear_login_flow_cookies(response)
    return response


async def logout_from_session_controller() -> JSONResponse:
    response = JSONResponse(
        content=AzureLogoutResponse(
            message="La sesion local de Azure fue cerrada correctamente."
        ).model_dump()
    )
    clear_authenticated_session(response)
    clear_onboarding_session(response)
    clear_login_flow_cookies(response)
    return response


async def get_authenticated_user_controller(
    current_user: AzureUserClaims,
) -> UserProfile:
    return await get_user_profile(current_user)
