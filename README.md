# Autogestión de Vacaciones API

Esta API proporciona funcionalidades para la gestión de solicitudes de vacaciones.

## Autenticación

La API utiliza autenticación basada en Azure AD, implementando un flujo de autenticación web (OAuth 2.0 Authorization Code Flow con PKCE).

**Flujo de Autenticación:**

1.  **Inicio de Sesión:** Cuando un usuario intenta acceder a un recurso protegido, es redirigido a la página de inicio de sesión de Microsoft.
2.  **Redirección y Código de Autorización:** Tras una autenticación exitosa en Microsoft, el usuario es redirigido de vuelta a un endpoint de callback de la API (`/auth/callback`) con un código de autorización.
3.  **Intercambio de Token:** La API intercambia este código de autorización por un ID Token y un Access Token con el servidor de Azure AD.
4.  **Creación Automática de Usuarios:**
    *   Si Azure AD autentica al usuario pero todavía no existe un registro local en la tabla `users`, el backend crea el usuario automáticamente.
    *   Se utiliza el campo `employeeId` de Microsoft Graph como el `number_identity` (documento de identidad) del usuario.
    *   Si el `employeeId` no está configurado en Azure AD, el login fallará, ya que este campo es obligatorio para la vinculación local.
5.  **Sesión Basada en Cookies:**
    *   Una vez el usuario ya existe, el **ID Token** se almacena en una cookie segura, HTTP-only y SameSite=Lax llamada `autogestion_session`.
    *   Esta cookie es gestionada por el backend y enviada automáticamente por el navegador con cada solicitud subsiguiente a la API.
    *   El frontend **no tiene acceso directo** a esta cookie ni al token, lo que mejora la seguridad (protección contra ataques XSS).
6.  **Autorización de Solicitudes:** Para cada solicitud a un endpoint protegido, la API verifica la validez del ID Token en la cookie `autogestion_session`. La función `get_current_azure_user` (definida como una dependencia de FastAPI) se encarga de extraer y validar este token, proporcionando la información del usuario (`AzureUserClaims`) a las funciones de ruta.
7.  **Cierre de Sesión:** El endpoint `/auth/logout` elimina la cookie de sesión `autogestion_session`.

Este enfoque basado en cookies HTTP-only es ideal para aplicaciones web tradicionales donde el frontend y el backend residen en el mismo dominio o dominios controlados, proporcionando una capa adicional de seguridad al no exponer el token directamente al JavaScript del cliente.

## Estructura del Proyecto

El proyecto sigue una estructura modular para organizar el código de manera lógica:

*   **`src/`**: Contiene el código fuente principal de la aplicación.
    *   **`controllers/`**: Funciones que orquestan la lógica de negocio, interactuando con los servicios y preparando los datos para las respuestas de la API.
    *   **`core/`**: Módulos con funcionalidades centrales como la configuración de la aplicación (`settings.py`), la autenticación con Azure AD (`azure_auth.py`) y la conexión a la base de datos (`db.py`).
    *   **`routes/`**: Define los endpoints de la API utilizando `APIRouter` de FastAPI, mapeando URLs a funciones de controlador.
    *   **`schemas/`**: Modelos Pydantic que definen la estructura de los datos de entrada (requests) y salida (responses) de la API, asegurando la validación y serialización.
    *   **`services/`**: Contiene la lógica de negocio principal y la interacción con recursos externos (bases de datos, otras APIs como Siigo).
*   **`.env`**: Archivo para almacenar variables de entorno y configuraciones sensibles.
*   **`requirements.txt`**: Lista de dependencias del proyecto.
*   **`README.md`**: Documentación del proyecto.

## Endpoints de Vacaciones

### 1. Obtener Tipos de Vacaciones

*   **URL:** `GET /vacations/types`
*   **Descripción:** Obtiene una lista de los tipos de vacaciones disponibles.
*   **Respuesta (200 OK):** `List[VacationTypeOption]`
    ```json
    [
      {
        "id": 1,
        "code": "ANUAL",
        "name": "Vacaciones Anuales"
      },
      {
        "id": 2,
        "code": "ENFERMEDAD",
        "name": "Licencia por Enfermedad"
      }
    ]
    ```
*   **Permisos Requeridos:** Ninguno (acceso público)

### 2. Obtener Resumen de Vacaciones por Usuario

*   **URL:** `GET /vacations/{user_id}`
*   **Descripción:** Obtiene un resumen de los días de vacaciones disponibles y disfrutados para un usuario específico.
*   **Parámetros de Ruta:**
    *   `user_id` (string, requerido): El ID del usuario.
*   **Respuesta (200 OK):** `VacationSummary`
    ```json
    {
      "diasDisponibles": 10,
      "diasDisfrutados": 5
    }
    ```
*   **Permisos Requeridos:** El `user_id` en la ruta debe coincidir con el ID del usuario autenticado.

### 3. Validar Solicitud de Vacaciones (Pre-creación)

*   **URL:** `GET /vacations/requests/validate`
*   **Descripción:** Valida un rango de fechas y tipo de vacaciones para una nueva solicitud, sin crearla. Verifica superposiciones, días hábiles y festivos.
*   **Parámetros de Query:**
    *   `user_id` (string, requerido): El ID del usuario para quien se valida la solicitud.
    *   `vacation_type_id` (integer, requerido): El ID del tipo de vacaciones.
    *   `start_date` (date, requerido): Fecha de inicio de las vacaciones (formato YYYY-MM-DD).
    *   `end_date` (date, requerido): Fecha de fin de las vacaciones (formato YYYY-MM-DD).
*   **Respuesta (200 OK):** `VacationRequestValidationResponse`
    ```json
    {
      "is_valid": true,
      "message": "La solicitud es valida y se puede registrar.",
      "total_days": 5,
      "business_dates": ["2026-06-01", "2026-06-02", "2026-06-03", "2026-06-04", "2026-06-05"],
      "excluded_dates": [],
      "errors": []
    }
    ```
*   **Permisos Requeridos:** `CREATE_VACATION_REQUEST`

### 4. Crear Solicitud de Vacaciones

*   **URL:** `POST /vacations`
*   **Descripción:** Crea una nueva solicitud de vacaciones para el usuario autenticado.
*   **Cuerpo de la Solicitud:** `VacationRequestCreateRequest`
    ```json
    {
      "user_id": "string",
      "vacation_type_id": 0,
      "start_date": "2026-05-19",
      "end_date": "2026-05-19"
    }
    ```
*   **Respuesta (201 Created):** `text/plain`
    ```
    Created success
    ```
*   **Permisos Requeridos:** `CREATE_VACATION_REQUEST`

### 5. Obtener Historial de Solicitudes de Vacaciones por Usuario

*   **URL:** `GET /vacations/requests/history/{user_id}`
*   **Descripción:** Obtiene el historial de solicitudes de vacaciones para un usuario específico, con paginación.
*   **Parámetros de Ruta:**
    *   `user_id` (string, requerido): El ID del usuario.
*   **Parámetros de Query:**
    *   `page` (integer, opcional, default: 1): Número de página.
    *   `page_size` (integer, opcional, default: 10): Tamaño de la página.
*   **Respuesta (200 OK):** `VacationRequestHistoryResponse`
    ```json
    {
      "items": [
        {
          "id": "string",
          "code": "string",
          "name": "string",
          "start_date": "2026-05-19",
          "end_date": "2026-05-19",
          "total_days": 0,
          "status": "string",
          "rejection_reason": "string",
          "payment_date": "2026-05-19",
          "created_at": "2026-05-19T23:36:00.000Z",
          "updated_at": "2026-05-19T23:36:00.000Z"
        }
      ],
      "total_items": 0,
      "page": 0,
      "page_size": 0
    }
    ```
*   **Permisos Requeridos:** El `user_id` en la ruta debe coincidir con el ID del usuario autenticado.

### 6. Obtener Todas las Solicitudes de Vacaciones (HR)

*   **URL:** `GET /vacations/requests/all`
*   **Descripción:** Obtiene todas las solicitudes de vacaciones, con opciones de filtrado y paginación. Diseñado para roles de RRHH.
*   **Parámetros de Query:**
    *   `page` (integer, opcional, default: 1): Número de página.
    *   `page_size` (integer, opcional, default: 10): Tamaño de la página.
    *   `user_id` (string, opcional): Filtra por ID de usuario.
    *   `email` (string, opcional): Filtra por email del usuario.
    *   `name` (string, opcional): Filtra por nombre del usuario.
    *   `status` (string, opcional): Filtra por estado de la solicitud (PENDING, VALIDATED, APPROVED, REJECTED).
    *   `vacation_type_id` (integer, opcional): Filtra por ID de tipo de vacaciones.
    *   `sort_by` (string, opcional): Campo para ordenar (e.g., `created_at`, `start_date`, `status`).
    *   `sort_order` (string, opcional, enum: ["asc", "desc"]): Orden de clasificación.
*   **Respuesta (200 OK):** `VacationRequestHistoryResponse` (mismo formato que el historial por usuario)
*   **Permisos Requeridos:** `VIEW_ALL_VACATION_REQUESTS`

### 7. Obtener Detalle de Solicitud de Vacaciones

*   **URL:** `GET /vacations/requests/{request_id}`
*   **Descripción:** Obtiene los detalles de una solicitud de vacaciones específica.
*   **Parámetros de Ruta:**
    *   `request_id` (string, requerido): El ID de la solicitud de vacaciones.
*   **Respuesta (200 OK):** `VacationRequestDetailResponse`
    ```json
    {
      "id": "string",
      "user_id": "string",
      "vacation_type": {
        "id": 0,
        "code": "string",
        "name": "string"
      },
      "start_date": "2026-05-19",
      "end_date": "2026-05-19",
      "total_days": 0,
      "status": "string",
      "payment_date": "2026-05-19",
      "created_at": "2026-05-19T23:36:00.000Z",
      "updated_at": "2026-05-19T23:36:00.000Z"
    }
    ```
*   **Permisos Requeridos:** `VIEW_ALL_VACATION_REQUESTS`

### 8. Validar Solicitud de Vacaciones (Cambio de Estado)

*   **URL:** `PATCH /vacations/requests/{request_id}/validate`
*   **Descripción:** Cambia el estado de una solicitud de vacaciones de `PENDING` a `VALIDATED`.
*   **Parámetros de Ruta:**
    *   `request_id` (string, requerido): El ID de la solicitud de vacaciones.
*   **Respuesta (200 OK):** `VacationRequestUpdateStatusResponse` (mismo formato que el detalle de solicitud)
*   **Permisos Requeridos:** `APPROVE_VACATION_REQUESTS`

### 9. Aprobar Solicitud de Vacaciones

*   **URL:** `PATCH /vacations/requests/{request_id}/approve`
*   **Descripción:** Aprueba una solicitud de vacaciones y establece la fecha de pago.
*   **Parámetros de Ruta:**
    *   `request_id` (string, requerido): El ID de la solicitud de vacaciones.
*   **Cuerpo de la Solicitud:** `VacationRequestApproveRequest`
    ```json
    {
      "payment_date": "2026-05-19"
    }
    ```
*   **Respuesta (200 OK):** `VacationRequestUpdateStatusResponse` (mismo formato que el detalle de solicitud)
*   **Permisos Requeridos:** `APPROVE_VACATION_REQUESTS`

### 10. Rechazar Solicitud de Vacaciones

*   **URL:** `PATCH /vacations/requests/{request_id}/reject`
*   **Descripción:** Rechaza una solicitud de vacaciones y proporciona una razón.
*   **Parámetros de Ruta:**
    *   `request_id` (string, requerido): El ID de la solicitud de vacaciones.
*   **Cuerpo de la Solicitud:** `VacationRequestRejectRequest`
    ```json
    {
      "rejection_reason": "Motivo del rechazo."
    }
    ```
*   **Respuesta (200 OK):** `VacationRequestUpdateStatusResponse` (mismo formato que el detalle de solicitud)
*   **Permisos Requeridos:** `APPROVE_VACATION_REQUESTS`

---
