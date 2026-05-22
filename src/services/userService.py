from prisma.errors import UniqueViolationError
from fastapi import HTTPException, status

from src.core.db import prisma
from src.schemas.authSchema import AzureUserClaims, Permission, Role, UserProfile


DEFAULT_ROLE_NAME = "EMPLOYEE"
DEFAULT_ROLE_DESCRIPTION = "Rol por defecto para usuarios creados desde Azure AD."


def _get_user_identity(user_claims: AzureUserClaims) -> str:
    identity = (user_claims.oid or user_claims.sub or "").strip()
    if identity:
        return identity

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Azure AD no devolvio un identificador util para crear el usuario local.",
    )


async def find_local_user_by_email(email: str):
    normalized_email = (email or "").strip().lower()
    if not normalized_email:
        return None

    return await prisma.user.find_unique(where={"email": normalized_email})


async def _get_default_role():
    role = await prisma.role.find_unique(where={"name": DEFAULT_ROLE_NAME})
    if role is not None:
        return role

    return await prisma.role.create(
        data={
            "name": DEFAULT_ROLE_NAME,
            "description": DEFAULT_ROLE_DESCRIPTION,
        }
    )


async def create_local_user_from_azure(
    user_claims: AzureUserClaims,
    *,
    number_identity: str,
):
    email = (user_claims.email or "").strip().lower()
    name = (user_claims.name or email).strip()
    normalized_number_identity = number_identity.strip()
    if not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Azure AD no devolvio un email util para crear el usuario local.",
        )

    if not normalized_number_identity:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El numero de identificacion es obligatorio.",
        )

    existing_user = await find_local_user_by_email(email)
    if existing_user is not None:
        return existing_user

    existing_identity_user = await prisma.user.find_unique(
        where={"number_identity": normalized_number_identity}
    )
    if existing_identity_user is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El numero de identificacion ya esta asociado a otro usuario.",
        )

    role = await _get_default_role()

    # Buscar registro de vacaciones por número de identificación para vincularlo automáticamente
    vacation = await prisma.vacation.find_first(
        where={"number_identity": normalized_number_identity}
    )

    user_data = {
        "id": _get_user_identity(user_claims),
        "email": email,
        "name": name or email,
        "number_identity": normalized_number_identity,
        "role_id": role.id,
    }

    if vacation:
        user_data["vacation_id"] = vacation.id

    try:
        return await prisma.user.create(data=user_data)
    except UniqueViolationError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El usuario o el numero de identificacion ya existen.",
        ) from exc


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

    all_permissions = sorted({p.name for p in role_permissions + user_permissions})

    return UserProfile(
        id=user.id,
        email=user.email,
        name=user.name,
        number_identity=user.number_identity,
        siigo_employee_id=user.siigo_employee_id,
        vacation_id=user.vacation_id,
        created_at=user.created_at,
        updated_at=user.updated_at,
        role=role,
        all_permissions=all_permissions,
    )
