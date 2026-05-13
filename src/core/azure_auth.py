from base64 import urlsafe_b64encode
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from secrets import token_urlsafe
from time import time
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlencode

import httpx
import jwt
from fastapi import Depends, HTTPException, Request, Response, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import InvalidTokenError, PyJWKClient

from src.core.settings import settings
from src.schemas.authSchema import AzureUserClaims


_openid_config_cache: Optional[Dict[str, Any]] = None
_openid_config_cache_expires_at: Optional[datetime] = None
_jwks_client: Optional[PyJWKClient] = None
_bearer_scheme = HTTPBearer(auto_error=False)
_OPENID_CACHE_TTL = timedelta(hours=6)
_AUTH_STATE_COOKIE = "autogestion_oauth_state"
_AUTH_NONCE_COOKIE = "autogestion_oauth_nonce"
_AUTH_CODE_VERIFIER_COOKIE = "autogestion_oauth_code_verifier"
_DEFAULT_AZURE_SCOPES = ("openid", "profile", "email")


def _ensure_azure_is_configured() -> None:
    if settings.azure_ad_enabled:
        return

    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail=(
            "Azure AD no esta configurado. Define AZURE_AD_CLIENT_ID y "
            "AZURE_AD_TENANT_ID en el entorno."
        ),
    )


def _normalize_email(payload: Dict[str, Any]) -> str:
    possible_keys = ("preferred_username", "email", "upn", "unique_name")
    for key in possible_keys:
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip().lower()
    return ""


def _base64url_encode(raw_value: bytes) -> str:
    return urlsafe_b64encode(raw_value).rstrip(b"=").decode("ascii")


def _get_login_scopes() -> str:
    scopes: List[str] = []
    for scope in [*settings.azure_ad_scopes, *_DEFAULT_AZURE_SCOPES]:
        if scope not in scopes:
            scopes.append(scope)
    return " ".join(scopes)


def _build_code_challenge(code_verifier: str) -> str:
    return _base64url_encode(sha256(code_verifier.encode("ascii")).digest())


def _token_to_user_claims(payload: Dict[str, Any]) -> AzureUserClaims:
    email = _normalize_email(payload)
    roles = payload.get("roles", [])
    if not isinstance(roles, list):
        roles = []

    scopes_claim = payload.get("scp", "")
    scopes = scopes_claim.split() if isinstance(scopes_claim, str) else []

    return AzureUserClaims(
        sub=str(payload.get("sub", "")),
        email=email,
        name=payload.get("name"),
        preferred_username=payload.get("preferred_username"),
        oid=payload.get("oid"),
        tid=payload.get("tid"),
        aud=str(payload.get("aud", "")),
        iss=str(payload.get("iss", "")),
        roles=roles,
        scopes=scopes,
        raw_claims=payload,
    )


async def fetch_openid_config() -> Dict[str, Any]:
    global _openid_config_cache, _openid_config_cache_expires_at

    _ensure_azure_is_configured()
    now = datetime.now(timezone.utc)
    if (
        _openid_config_cache is not None
        and _openid_config_cache_expires_at is not None
        and now < _openid_config_cache_expires_at
    ):
        return _openid_config_cache

    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(settings.azure_ad_openid_config_url)
        response.raise_for_status()
        _openid_config_cache = response.json()
        _openid_config_cache_expires_at = now + _OPENID_CACHE_TTL
        return _openid_config_cache


async def get_jwks_client() -> PyJWKClient:
    global _jwks_client

    if _jwks_client is not None:
        return _jwks_client

    openid_config = await fetch_openid_config()
    jwks_uri = openid_config.get("jwks_uri")
    if not isinstance(jwks_uri, str) or not jwks_uri:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No fue posible obtener la configuracion JWKS de Azure AD.",
        )

    _jwks_client = PyJWKClient(jwks_uri)
    return _jwks_client


def build_azure_login_redirect_url() -> Tuple[str, Dict[str, str]]:
    _ensure_azure_is_configured()
    if not settings.azure_ad_redirect_uri:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Falta configurar AZURE_AD_REDIRECT_URI para el login con Azure.",
        )

    state = token_urlsafe(32)
    nonce = token_urlsafe(32)
    code_verifier = token_urlsafe(64)
    query_params = urlencode(
        {
            "client_id": settings.azure_ad_client_id,
            "response_type": "code",
            "redirect_uri": settings.azure_ad_redirect_uri,
            "response_mode": "query",
            "scope": _get_login_scopes(),
            "state": state,
            "nonce": nonce,
            "code_challenge": _build_code_challenge(code_verifier),
            "code_challenge_method": "S256",
        }
    )

    return (
        f"{settings.azure_ad_authorize_url}?{query_params}",
        {
            "state": state,
            "nonce": nonce,
            "code_verifier": code_verifier,
        },
    )


def set_login_flow_cookies(response: Response, flow_data: Dict[str, str]) -> None:
    cookie_options = {
        "httponly": True,
        "secure": settings.auth_cookie_secure,
        "samesite": "lax",
        "path": "/",
        "max_age": settings.auth_temp_cookie_max_age,
    }
    response.set_cookie(_AUTH_STATE_COOKIE, flow_data["state"], **cookie_options)
    response.set_cookie(_AUTH_NONCE_COOKIE, flow_data["nonce"], **cookie_options)
    response.set_cookie(
        _AUTH_CODE_VERIFIER_COOKIE,
        flow_data["code_verifier"],
        **cookie_options,
    )


def clear_login_flow_cookies(response: Response) -> None:
    response.delete_cookie(_AUTH_STATE_COOKIE, path="/")
    response.delete_cookie(_AUTH_NONCE_COOKIE, path="/")
    response.delete_cookie(_AUTH_CODE_VERIFIER_COOKIE, path="/")


def set_authenticated_session(response: Response, token: str, user: AzureUserClaims) -> None:
    max_age: Optional[int] = None
    expires_at = user.raw_claims.get("exp")
    if isinstance(expires_at, int):
        max_age = max(0, expires_at - int(time()))

    response.set_cookie(
        settings.auth_session_cookie_name,
        token,
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite="lax",
        path="/",
        max_age=max_age,
    )


def clear_authenticated_session(response: Response) -> None:
    response.delete_cookie(settings.auth_session_cookie_name, path="/")


async def exchange_authorization_code(code: str, code_verifier: str) -> Dict[str, Any]:
    _ensure_azure_is_configured()
    if not settings.azure_ad_redirect_uri:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Falta configurar AZURE_AD_REDIRECT_URI para el login con Azure.",
        )

    token_payload = {
        "grant_type": "authorization_code",
        "client_id": settings.azure_ad_client_id,
        "code": code,
        "redirect_uri": settings.azure_ad_redirect_uri,
        "code_verifier": code_verifier,
        "scope": _get_login_scopes(),
    }
    if settings.azure_ad_client_secret:
        token_payload["client_secret"] = settings.azure_ad_client_secret

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                settings.azure_ad_token_url,
                data=token_payload,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            response.raise_for_status()
            return response.json()
    except httpx.HTTPStatusError as exc:
        detail = "No fue posible completar el intercambio del code con Azure AD."
        try:
            error_payload = exc.response.json()
        except ValueError:
            error_payload = {}

        error_description = error_payload.get("error_description") or error_payload.get(
            "error"
        )
        if isinstance(error_description, str) and error_description.strip():
            detail = error_description.strip()

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
        ) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No fue posible comunicarse con Azure AD durante el login.",
        ) from exc


async def verify_azure_token(
    token: str,
    *,
    expected_nonce: Optional[str] = None,
) -> AzureUserClaims:
    _ensure_azure_is_configured()

    try:
        jwks_client = await get_jwks_client()
        signing_key = jwks_client.get_signing_key_from_jwt(token)
        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            audience=settings.azure_ad_client_id,
            issuer=settings.azure_ad_issuer,
            options={"require": ["exp", "iat", "iss", "aud"]},
        )
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No fue posible consultar la configuracion de Azure AD.",
        ) from exc
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="El token de Azure expiró.",
        ) from exc
    except InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="El token de Azure no es valido.",
        ) from exc

    if expected_nonce is not None and payload.get("nonce") != expected_nonce:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="El login de Azure no es valido porque el nonce no coincide.",
        )

    return _token_to_user_claims(payload)


async def verify_azure_access_token(token: str) -> AzureUserClaims:
    return await verify_azure_token(token)


async def complete_azure_login(
    *,
    code: str,
    state: str,
    expected_state: Optional[str],
    code_verifier: Optional[str],
    expected_nonce: Optional[str],
) -> Tuple[AzureUserClaims, str]:
    if not expected_state or state != expected_state:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El state devuelto por Azure AD no coincide.",
        )

    if not code_verifier:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No se encontro el code verifier de la sesion de login.",
        )

    token_payload = await exchange_authorization_code(code, code_verifier)
    id_token = token_payload.get("id_token")
    if not isinstance(id_token, str) or not id_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Azure AD no devolvio un id_token valido para iniciar sesion.",
        )

    user = await verify_azure_token(id_token, expected_nonce=expected_nonce)
    return user, id_token


async def get_current_azure_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(_bearer_scheme),
) -> AzureUserClaims:
    token = None
    if credentials is not None and credentials.credentials:
        token = credentials.credentials
    else:
        token = request.cookies.get(settings.auth_session_cookie_name)

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Falta el token Bearer de Azure o una sesion iniciada.",
        )

    return await verify_azure_access_token(token)
