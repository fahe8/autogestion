import asyncio
from typing import Any, Dict, Optional

import httpx
from fastapi import HTTPException, status

from src.core.settings import settings
from src.schemas.siigoSchema import SiigoTokenResponse


class SiigoService:
    _instance: Optional["SiigoService"] = None
    _lock: asyncio.Lock = asyncio.Lock()

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(SiigoService, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if not hasattr(self, '_initialized'):  # Ensure __init__ runs only once for the singleton
            self.client = httpx.AsyncClient(base_url=settings.siigo_base_url)
            self.token: Optional[SiigoTokenResponse] = None
            self.partner_id: str = settings.siigo_company_name.replace(" ", "").upper() # Generar Partner-Id
            self._initialized = True

    async def _get_token(self) -> SiigoTokenResponse:
        """Obtiene un nuevo token de autenticación de la API de Siigo."""
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Partner-Id": self.partner_id, # Añadir Partner-Id aquí también
        }
        payload = {
            "username": settings.siigo_user_api,
            "access_key": settings.siigo_api_key,
        }
        try:
            response = await self.client.post("/authenticate", headers=headers, json=payload)
            response.raise_for_status()
            token_data = response.json()
            self.token = SiigoTokenResponse(**token_data)
            return self.token
        except httpx.HTTPStatusError as e:
            raise HTTPException(
                status_code=e.response.status_code,
                detail=f"Error al autenticarse con Siigo: {e.response.text}"
            )
        except httpx.RequestError as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error de red al intentar autenticarse con Siigo: {e}"
            )

    async def _ensure_token(self) -> str:
        """Asegura que haya un token válido disponible, refrescándolo si es necesario."""
        async with self._lock:
            if self.token is None or self.token.is_expired():
                self.token = await self._get_token()
            return self.token.access_token

    async def _request(self, method: str, url: str, idempotency_key: Optional[str] = None, **kwargs) -> Dict[str, Any]:
        """
        Realiza una solicitud autenticada a la API de Siigo.
        Refresca el token automáticamente si es necesario.
        """
        access_token = await self._ensure_token()
        headers = kwargs.pop("headers", {})
        headers["Authorization"] = f"{self.token.token_type} {access_token}"
        headers["Content-Type"] = "application/json"
        headers["Accept"] = "application/json"
        headers["Partner-Id"] = self.partner_id # Añadir Partner-Id a todas las solicitudes

        if method.upper() == "POST" and idempotency_key:
            headers["Idempotency-Key"] = idempotency_key

        try:
            response = await self.client.request(method, url, headers=headers, **kwargs)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            raise HTTPException(
                status_code=e.response.status_code,
                detail=f"Error en la API de Siigo ({method} {url}): {e.response.text}"
            )
        except httpx.RequestError as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error de red al comunicarse con la API de Siigo ({method} {url}): {e}"
            )

    # Métodos específicos para interactuar con la API de Siigo
    async def get_products(self) -> Dict[str, Any]:
        """Ejemplo: Obtiene una lista de productos de Siigo."""
        return await self._request("GET", "/products")

    async def get_clients(self) -> Dict[str, Any]:
        """Ejemplo: Obtiene una lista de clientes de Siigo."""
        return await self._request("GET", "/customers")

    # Puedes añadir más métodos aquí para diferentes recursos de Siigo
    # Por ejemplo:
    # async def create_invoice(self, invoice_data: Dict[str, Any]) -> Dict[str, Any]:
    #     return await self._request("POST", "/invoices", json=invoice_data)
