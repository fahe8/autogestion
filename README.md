# Autogestión API

Backend construido con FastAPI para gestionar autenticación con Azure AD y el módulo de solicitudes/resumen de vacaciones.

## Objetivo

Este proyecto expone una API que:

- valida tokens emitidos por Azure Active Directory
- devuelve información del usuario autenticado
- ofrece endpoints relacionados con vacaciones
- aplica middlewares de seguridad HTTP
- prepara la base para integración con Prisma/PostgreSQL

## Stack Tecnológico

- Python
- FastAPI
- Uvicorn
- PyJWT
- HTTPX
- Prisma
- PostgreSQL
- python-dotenv

## Estructura del Proyecto

```text
autogestion/
├── prisma/
│   ├── migrations/
│   └── schema.prisma
├── src/
│   ├── controllers/
│   │   └── vacationsController.py
│   ├── core/
│   │   ├── azure_auth.py
│   │   ├── security.py
│   │   └── settings.py
│   ├── middlewares/
│   │   └── securityHeaders.py
│   ├── routes/
│   │   ├── authRoutes.py
│   │   └── vacationsRoutes.py
│   ├── schemas/
│   │   ├── authSchema.py
│   │   └── vacationsSchema.py
│   ├── services/
│   │   └── vacationsService.py
│   └── main.py
├── .env.example
├── requirements.txt
└── s.bat
```

## Arquitectura General

La API sigue una estructura por capas:

### 1. `routes`
Define los endpoints HTTP públicos.

### 2. `controllers`
Reciben la llamada desde la ruta y coordinan la ejecución de la lógica.

### 3. `services`
Contienen la lógica de negocio.

### 4. `schemas`
Definen los modelos de entrada y salida usando Pydantic.

### 5. `core`
Contiene configuración global, autenticación y middlewares de seguridad.

### 6. `middlewares`
Agrega cabeceras de seguridad a las respuestas.

## Punto de Entrada

El punto de entrada es:

- `src/main.py`

Allí se:

- crea la aplicación FastAPI
- configuran URLs de documentación
- agregan middlewares de seguridad
- registran las rutas
- expone un endpoint `/health`

## Flujo de Inicialización

Al iniciar la aplicación:

1. se cargan variables de entorno desde `.env`
2. se construye `settings`
3. se crea la app FastAPI
4. se agregan middlewares
5. se montan rutas de auth y vacations

## Configuración

La configuración vive en:

- `src/core/settings.py`

Se encarga de leer variables de entorno para:

- nombre y versión de la app
- habilitación de docs
- CORS
- HTTPS
- hosts permitidos
- configuración de Azure AD

### Variables relevantes

```env
APP_NAME=Autogestion API
APP_VERSION=1.0.0
APP_ENV=development
DOCS_ENABLED=true
FORCE_HTTPS=false

CORS_ALLOW_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
CORS_ALLOW_METHODS=GET,POST,PUT,PATCH,DELETE,OPTIONS
CORS_ALLOW_HEADERS=Authorization,Content-Type,Accept,Origin
CORS_ALLOW_CREDENTIALS=true
ALLOWED_HOSTS=localhost,127.0.0.1

AZURE_AD_CLIENT_ID=
AZURE_AD_TENANT_ID=
AZURE_AD_REDIRECT_URI=http://localhost:3000/login
AZURE_AD_SCOPES=openid,profile,email
```

## Seguridad HTTP

La aplicación agrega varios middlewares en `src/core/security.py` y `src/middlewares/securityHeaders.py`.

### Middlewares aplicados

- `CORSMiddleware`
- `TrustedHostMiddleware`
- `GZipMiddleware`
- `HTTPSRedirectMiddleware` si `FORCE_HTTPS=true`
- `SecurityHeadersMiddleware`

### Headers agregados

- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `Referrer-Policy: strict-origin-when-cross-origin`
- `Permissions-Policy`
- `Content-Security-Policy`
- `Strict-Transport-Security` si la request llega por HTTPS

## Autenticación

## Cómo funciona el auth

Este proyecto no hace login tradicional con usuario y contraseña dentro del backend.

El login se realiza con Azure AD mediante Authorization Code Flow con PKCE. El backend inicia el flujo, recibe el `code` en el callback, lo intercambia por tokens y crea una sesión local usando cookie HttpOnly.

### Resumen del flujo

1. el cliente llama `GET /auth/login`
2. el backend genera `state`, `nonce` y `code_verifier`
3. el backend redirige al usuario a Azure AD
4. Azure AD autentica al usuario y devuelve un `code` a `GET /auth/callback`
5. el backend intercambia ese `code` por tokens usando PKCE
6. el backend valida el `id_token` con JWKS de Azure
7. el backend crea una sesión local en cookie HttpOnly
8. el usuario puede consultar `GET /auth/me` sin reenviar manualmente el token

## Archivos involucrados en auth

### `src/routes/authRoutes.py`
Expone los endpoints de autenticación.

### `src/core/azure_auth.py`
Implementa la lógica de validación del token de Azure AD.

### `src/schemas/authSchema.py`
Define los modelos de request/response del módulo auth.

## Configuración de Azure AD

La autenticación solo se considera habilitada si existen:

- `AZURE_AD_CLIENT_ID`
- `AZURE_AD_TENANT_ID`

Si falta alguna de esas variables, el backend responderá con error indicando que Azure AD no está configurado.

## OpenID y JWKS

El backend construye dinámicamente:

- `authority`: `https://login.microsoftonline.com/{tenant_id}`
- `issuer`: `https://login.microsoftonline.com/{tenant_id}/v2.0`
- `openid configuration url`: `https://login.microsoftonline.com/{tenant_id}/v2.0/.well-known/openid-configuration`

Luego obtiene desde Azure:

- metadata OpenID
- `jwks_uri`
- claves públicas para validar tokens firmados

## Validaciones que hace el backend

Cuando recibe un token:

- valida que Azure esté configurado
- obtiene la clave pública correcta según el JWT
- valida firma con `RS256`
- valida audiencia contra `AZURE_AD_CLIENT_ID`
- valida issuer contra el issuer esperado
- valida expiración y campos requeridos
- valida `nonce` cuando el token viene del callback de login

### Claims procesados

Del payload del token se extraen principalmente:

- `sub`
- `email`
- `name`
- `preferred_username`
- `oid`
- `tid`
- `aud`
- `iss`
- `roles`
- `scp`

Además, se conserva el payload completo en `raw_claims`.

## Endpoints de Auth

### `GET /auth/login`

Inicia el login con Azure AD.

Este endpoint:

- genera `state`, `nonce` y `code_verifier`
- guarda esos valores temporalmente en cookies HttpOnly
- redirige al usuario al endpoint de autorización de Azure

### `GET /auth/callback`

Recibe el `code` de Azure AD.

Este endpoint:

- valida el `state`
- intercambia el `code` por tokens en Azure
- valida el `id_token`
- crea una cookie de sesión local
- devuelve el usuario autenticado

### `GET /auth/azure/config`

Devuelve configuración pública necesaria para un cliente que quiera autenticarse con Azure.

Respuesta esperada:

- si auth está habilitado
- `client_id`
- `tenant_id`
- `authority`
- `redirect_uri`
- `scopes`
- URL de configuración OpenID

### `POST /auth/azure/verify`

Recibe un body con:

```json
{
  "access_token": "token_emitido_por_azure"
}
```

Valida el token y retorna datos del usuario autenticado.

### `POST /auth/logout`

Cierra la sesión local eliminando la cookie de autenticación.

### `GET /auth/me`

Puede autenticarse de dos formas:

- con header `Authorization: Bearer <token>`
- con la cookie de sesión creada por `GET /auth/callback`

Header esperado si se usa Bearer:

```http
Authorization: Bearer <token>
```

Valida el token y devuelve los claims normalizados del usuario.

## Errores comunes de Auth

### `503 Service Unavailable`
Azure AD no está configurado correctamente.

### `401 Unauthorized`
El token:

- expiró
- no es válido
- no tiene la audiencia esperada
- no trae firma válida
- no fue enviado en el header Bearer

## Cómo probar el auth sin frontend

Aunque no exista frontend, el auth se puede probar manualmente.

### Opción 1. Swagger
Si `DOCS_ENABLED=true`, la documentación estará disponible en:

- `/docs`
- `/redoc`

### Opción 2. Navegador

Abre directamente:

- `http://127.0.0.1:3001/auth/login`

Si la app de Azure tiene registrado el redirect URI del backend, Azure redirigirá a `GET /auth/callback`, el backend creará la cookie y luego podrás abrir:

- `http://127.0.0.1:3001/auth/me`

### Opción 3. Postman
Se puede seguir usando OAuth 2.0 con Azure AD para generar un token y luego invocar:

- `POST /auth/azure/verify`
- `GET /auth/me`

### Opción 4. Curl
Si ya se tiene un token emitido por Azure:

```bash
curl -X POST http://127.0.0.1:3001/auth/azure/verify \
  -H "Content-Type: application/json" \
  -d "{\"access_token\":\"TU_TOKEN\"}"
```

o:

```bash
curl http://127.0.0.1:3001/auth/me \
  -H "Authorization: Bearer TU_TOKEN"
```

## Módulo de Vacaciones

## Cómo está organizado

### Ruta
- `src/routes/vacationsRoutes.py`

### Controlador
- `src/controllers/vacationsController.py`

### Servicio
- `src/services/vacationsService.py`

### Schema
- `src/schemas/vacationsSchema.py`

## Endpoints actuales

### `GET /vacations`
Devuelve un resumen de vacaciones.

Respuesta actual:

```json
{
  "diasDisponibles": 15,
  "diasDisfrutados": 5
}
```

Actualmente esta respuesta está mockeada o stubbeada desde el servicio.

### `POST /vacations`
Está planteado para registrar una solicitud de vacaciones, pero aún no está completamente implementado.

## Estado actual del servicio de vacaciones

El servicio `VacationService` hoy funciona como base inicial:

- `get_vacation_summary()` devuelve datos de ejemplo
- `post_vacation()` devuelve un texto de prueba
- todavía no hay conexión activa a base de datos desde este servicio

## Base de Datos

El proyecto incluye un esquema Prisma en:

- `prisma/schema.prisma`

## Modelos principales

### `Role`
Representa roles del sistema.

### `Permission`
Representa permisos individuales.

### `RolePermission`
Relaciona roles con permisos.

### `UserPermission`
Relaciona permisos específicos con usuarios.

### `User`
Usuario del sistema.

Campos relevantes:

- email
- name
- role
- siigo_employee_id

### `VacationType`
Tipos de vacaciones o ausencias.

### `VacationRequest`
Solicitudes de vacaciones.

Campos relevantes:

- usuario
- tipo de vacaciones
- fechas
- días solicitados
- estado
- datos de sincronización con Siigo

## Estados definidos

### `RequestStatus`
- `PENDING`
- `VALIDATED`
- `APPROVED`
- `REJECTED`

### `SyncStatus`
- `PENDING`
- `SUCCESS`
- `FAILED`

## Levantar el Proyecto

## Requisitos

Instalar dependencias desde `requirements.txt`.

## Inicio rápido

Con el script incluido:

```bat
s.bat
```

O manualmente:

```bash
venv\Scripts\python.exe -m uvicorn src.main:app --reload --host 127.0.0.1 --port 3001
```

La API queda disponible en:

- `http://127.0.0.1:3001`

## Endpoint de Salud

### `GET /health`

Devuelve algo similar a:

```json
{
  "status": "ok",
  "environment": "development"
}
```

## Dependencias principales

Según `requirements.txt`:

- `fastapi`
- `httpx`
- `prisma`
- `PyJWT[crypto]`
- `python-dotenv`
- `uvicorn`

## Estado actual del proyecto

Actualmente el proyecto ya tiene:

- estructura base por capas
- autenticación con Azure AD implementada
- middlewares de seguridad aplicados
- esquema Prisma definido
- módulo de vacaciones en estado inicial

## Pendientes naturales del proyecto

Algunos siguientes pasos esperables serían:

- conectar `VacationService` a Prisma/PostgreSQL
- implementar correctamente creación de solicitudes de vacaciones
- asociar auth con usuarios internos de base de datos
- proteger rutas de negocio con autorización por roles/permisos
- agregar validaciones y tests
- documentar flujo de despliegue y variables productivas

## Notas

- El backend ahora puede iniciar el login con Azure y crear una sesión local basada en cookie.
- Para entornos reales, el `redirect_uri` y los scopes deben coincidir con la app registrada en Azure AD.
- El redirect URI del backend debe estar registrado en Azure AD, por ejemplo `http://127.0.0.1:3001/auth/callback` para desarrollo local.
- El módulo de vacaciones todavía está en fase de construcción.
