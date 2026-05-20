from fastapi import HTTPException, status

from src.core.db import prisma
from src.schemas.authSchema import AzureUserClaims, UserProfile, Permission, Role


DEFAULT_ROLE_NAME = "EMPLOYEE"
DEFAULT_ROLE_DESCRIPTION = "Rol por defecto para usuarios creados desde Azure AD."


async def ensure_local_user_from_azure(user_claims: AzureUserClaims):
    email = (user_claims.email or "").strip().lower()
    name = (user_claims.name or email).strip()
    oid = user_claims.oid

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
            "id": oid,
            "email": email,
            "name": name or email,
            "role": {
                "connect": {
                    "id": role.id,
                }
            },
        }
    )


async def get_user_profile(azure_user: AzureUserClaims) -> UserProfile:
    email = (azure_user.email or "").strip().lower()
    
    if not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Azure AD no devolvio un email util para obtener el perfil del usuario.",
        )
    
    user = await prisma.user.find_unique(
        where={"email": email},
        include={
            "role": {
                "include": {
                    "permissions": {
                        "include": {
                            "permission": True
                        }
                    }
                }
            },
            "permissions": {
                "include": {
                    "permission": True
                }
            }
        }
    )
    
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No existe un usuario registrado con el email proporcionado.",
        )
    
    role_permissions = []
    if user.role and user.role.permissions:
        role_permissions = [
            Permission(
                id=rp.permission.id,
                name=rp.permission.name,
                description=rp.permission.description
            )
            for rp in user.role.permissions
            if rp.permission
        ]
    
    user_permissions = []
    if user.permissions:
        user_permissions = [
            Permission(
                id=up.permission.id,
                name=up.permission.name,
                description=up.permission.description
            )
            for up in user.permissions
            if up.permission
        ]
    
    role = Role(
        id=user.role.id,
        name=user.role.name,
        description=user.role.description,
    )

    all_permissions = list({p.name for p in role_permissions + user_permissions})
    
    return UserProfile(
        id=user.id,
        email=user.email,
        name=user.name,
        siigo_employee_id=user.siigo_employee_id,
        created_at=user.created_at,
        updated_at=user.updated_at,
        role=role,
        all_permissions=all_permissions,
    )
