from fastapi import HTTPException, status

from src.core.db import prisma
from src.schemas.authSchema import AzureUserClaims


DEFAULT_ROLE_NAME = "EMPLOYEE"
DEFAULT_ROLE_DESCRIPTION = "Rol por defecto para usuarios creados desde Azure AD."


async def ensure_local_user_from_azure(user_claims: AzureUserClaims):
    email = (user_claims.email or "").strip().lower()
    name = (user_claims.name or email).strip()

    if not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Azure AD no devolvio un email util para crear el usuario local.",
        )

    existing_user = await prisma.user.find_unique(where={"email": email})
    if existing_user is not None:
        return existing_user

    role = await prisma.role.find_unique(where={"name": DEFAULT_ROLE_NAME})
    if role is None:
        role = await prisma.role.create(
            data={
                "name": DEFAULT_ROLE_NAME,
                "description": DEFAULT_ROLE_DESCRIPTION,
            }
        )

    return await prisma.user.create(
        data={
            "email": email,
            "name": name or email,
            "role": {
                "connect": {
                    "id": role.id,
                }
            },
        }
    )
