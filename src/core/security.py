from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from starlette.middleware.httpsredirect import HTTPSRedirectMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from typing import List

from src.core.settings import settings
from src.schemas.authSchema import UserProfile
from src.core.azure_auth import get_current_azure_user
from src.services.userService import get_user_profile


def apply_security_middlewares(app: FastAPI) -> None:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allow_origins,
        allow_methods=settings.cors_allow_methods,
        allow_headers=settings.cors_allow_headers,
        allow_credentials=settings.cors_allow_credentials,
    )

    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=settings.allowed_hosts,
    )

    app.add_middleware(GZipMiddleware, minimum_size=500)

    if settings.force_https:
        app.add_middleware(HTTPSRedirectMiddleware)


async def get_authenticated_user_with_permissions(
    current_azure_user: UserProfile = Depends(get_current_azure_user),
) -> UserProfile:
    return await get_user_profile(current_azure_user)


def permission_required(required_permissions: List[str]):
    async def permission_checker(user: UserProfile = Depends(get_authenticated_user_with_permissions)):
        print(user.all_permissions)
        if not any(p in user.all_permissions for p in required_permissions):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tienes los permisos necesarios para realizar esta acción.",
            )
        return user
    return permission_checker

