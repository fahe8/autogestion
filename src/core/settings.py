import os
from pathlib import Path
from typing import List, Optional

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parents[2]
load_dotenv(BASE_DIR / ".env")


def _parse_csv(value: Optional[str], default: List[str]) -> List[str]:
    if not value:
        return default

    return [item.strip() for item in value.split(",") if item.strip()]


def _parse_bool(value: Optional[str], default: bool) -> bool:
    if value is None:
        return default

    return value.strip().lower() in {"1", "true", "yes", "on"}


def _parse_int(value: Optional[str], default: int) -> int:
    if value is None:
        return default

    try:
        return int(value)
    except ValueError:
        return default


class Settings:
    app_name: str = os.getenv("APP_NAME", "Autogestion API")
    app_version: str = os.getenv("APP_VERSION", "1.0.0")
    app_env: str = os.getenv("APP_ENV", "development")
    docs_enabled: bool = _parse_bool(os.getenv("DOCS_ENABLED"), True)
    force_https: bool = _parse_bool(os.getenv("FORCE_HTTPS"), False)

    cors_allow_origins: List[str] = _parse_csv(
        os.getenv("CORS_ALLOW_ORIGINS"),
        ["http://localhost:3000", "http://127.0.0.1:3000"],
    )
    cors_allow_methods: List[str] = _parse_csv(
        os.getenv("CORS_ALLOW_METHODS"),
        ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    )
    cors_allow_headers: List[str] = _parse_csv(
        os.getenv("CORS_ALLOW_HEADERS"),
        ["Authorization", "Content-Type", "Accept", "Origin"],
    )
    cors_allow_credentials: bool = _parse_bool(
        os.getenv("CORS_ALLOW_CREDENTIALS"),
        True,
    )

    allowed_hosts: List[str] = _parse_csv(
        os.getenv("ALLOWED_HOSTS"),
        ["localhost", "127.0.0.1"],
    )

    azure_ad_client_id: str = (
        os.getenv("AZURE_AD_CLIENT_ID")
        or os.getenv("NEXT_PUBLIC_AZURE_AD_CLIENT_ID_2NV")
        or os.getenv("NEXT_PUBLIC_AZURE_AD_CLIENT_ID")
        or ""
    )
    azure_ad_tenant_id: str = (
        os.getenv("AZURE_AD_TENANT_ID")
        or os.getenv("NEXT_PUBLIC_AZURE_AD_TENANT_ID_2NV")
        or os.getenv("NEXT_PUBLIC_AZURE_AD_TENANT_ID")
        or ""
    )
    azure_ad_redirect_uri: str = (
        os.getenv("AZURE_AD_REDIRECT_URI")
        or os.getenv("NEXT_PUBLIC_AZURE_AD_REDIRECT_URI")
        or ""
    )
    azure_ad_client_secret: str = os.getenv("AZURE_AD_CLIENT_SECRET", "")
    azure_ad_scopes: List[str] = _parse_csv(
        os.getenv("AZURE_AD_SCOPES"),
        ["openid", "profile", "email"],
    )
    auth_session_cookie_name: str = os.getenv(
        "AUTH_SESSION_COOKIE_NAME",
        "autogestion_session",
    )
    auth_onboarding_cookie_name: str = os.getenv(
        "AUTH_ONBOARDING_COOKIE_NAME",
        "autogestion_onboarding_session",
    )
    auth_cookie_secure: bool = _parse_bool(
        os.getenv("AUTH_COOKIE_SECURE"),
        False,
    )
    auth_temp_cookie_max_age: int = _parse_int(
        os.getenv("AUTH_TEMP_COOKIE_MAX_AGE"),
        600,
    )

    siigo_api_key: str = os.getenv("SIIGO_API_KEY", "")
    siigo_user_api: str = os.getenv("SIIGO_USER_API", "")
    siigo_base_url: str = os.getenv("SIIGO_BASE_URL", "https://api.siigo.com/v1")
    siigo_company_name: str = os.getenv("SIIGO_COMPANY_NAME", "2NV SAS")

    frontend_post_login_redirect_url: str = os.getenv(
        "FRONTEND_POST_LOGIN_REDIRECT_URL",
        "http://localhost:3000/inicio",
    )
    frontend_onboarding_redirect_url: str = os.getenv(
        "FRONTEND_ONBOARDING_REDIRECT_URL",
        "http://localhost:3000/completar-perfil",
    )

    azure_graph_url: str = os.getenv(
        "AZURE_GRAPH_URL",
        "https://graph.microsoft.com/v1.0/me",
    )

    @property
    def docs_url(self) -> Optional[str]:
        return "/docs" if self.docs_enabled else None

    @property
    def redoc_url(self) -> Optional[str]:
        return "/redoc" if self.docs_enabled else None

    @property
    def openapi_url(self) -> Optional[str]:
        return "/openapi.json" if self.docs_enabled else None

    @property
    def azure_ad_enabled(self) -> bool:
        return bool(self.azure_ad_client_id and self.azure_ad_tenant_id)

    @property
    def azure_ad_authority(self) -> str:
        if not self.azure_ad_tenant_id:
            return ""
        return f"https://login.microsoftonline.com/{self.azure_ad_tenant_id}"

    @property
    def azure_ad_issuer(self) -> str:
        if not self.azure_ad_tenant_id:
            return ""
        return f"{self.azure_ad_authority}/v2.0"

    @property
    def azure_ad_openid_config_url(self) -> str:
        if not self.azure_ad_tenant_id:
            return ""
        return f"{self.azure_ad_issuer}/.well-known/openid-configuration"

    @property
    def azure_ad_authorize_url(self) -> str:
        if not self.azure_ad_tenant_id:
            return ""
        return f"{self.azure_ad_authority}/oauth2/v2.0/authorize"

    @property
    def azure_ad_token_url(self) -> str:
        if not self.azure_ad_tenant_id:
            return ""
        return f"{self.azure_ad_authority}/oauth2/v2.0/token"


settings = Settings()
