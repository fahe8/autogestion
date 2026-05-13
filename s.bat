@echo off
setlocal

cd /d "%~dp0"

set "PYTHON_EXE=%CD%\venv\Scripts\python.exe"

if exist "%PYTHON_EXE%" (
    echo [INFO] Usando entorno virtual: %PYTHON_EXE%
) else (
    echo [WARN] No se encontro venv\Scripts\python.exe. Usando python del sistema.
    set "PYTHON_EXE=python"
)

echo [INFO] Verificando uvicorn...
"%PYTHON_EXE%" -c "import uvicorn" >nul 2>&1
if errorlevel 1 (
    echo [INFO] uvicorn no esta instalado. Instalando...
    "%PYTHON_EXE%" -m pip install uvicorn
    if errorlevel 1 (
        echo [ERROR] No se pudo instalar uvicorn.
        pause
        exit /b 1
    )
)

echo [INFO] Levantando backend en http://127.0.0.1:3001
"%PYTHON_EXE%" -m uvicorn src.main:app --reload --host 127.0.0.1 --port 3001

if errorlevel 1 (
    echo [ERROR] El backend se cerro con error.
    pause
    exit /b 1
)

endlocal