@echo off
setlocal DisableDelayedExpansion
chcp 65001 >nul
title BRD Portal Noticias - localhost
cd /d "%~dp0"

set "ADMIN_EMAIL=admin@local.test"
set "ADMIN_PASS=LocalAdmin123"
if not "%LOCAL_ADMIN_EMAIL%"=="" set "ADMIN_EMAIL=%LOCAL_ADMIN_EMAIL%"
if not "%LOCAL_ADMIN_PASSWORD%"=="" set "ADMIN_PASS=%LOCAL_ADMIN_PASSWORD%"

echo ============================================================
echo  BRD Portal de Noticias - localhost
echo  frontend Next.js 14 (HUD/bento) + backend Django
echo  Uso:
echo    subir-localhost.bat          nativo (venv + sqlite)
echo    subir-localhost.bat --docker docker (postgres + redis)
echo    subir-localhost.bat --check  valida tsc + build
echo    subir-localhost.bat --stop   para containers
echo    subir-localhost.bat --help   esta ajuda
echo.
echo  Admin: %ADMIN_EMAIL% / %ADMIN_PASS%
echo ============================================================
echo.

if /I "%~1"=="--help" goto :help
if /I "%~1"=="-h" goto :help
if /I "%~1"=="--stop" goto :stop
if /I "%~1"=="--docker" goto :docker
if /I "%~1"=="--check" goto :check
goto :native

:help
echo Requisitos nativo: Python 3.12+, Node 20+, npm
echo Requisitos docker: Docker Desktop + compose v2
echo URLs: http://localhost:3000  http://localhost:8000/healthz  http://localhost:8000/admin/
goto :end

:stop
echo -- Parando containers --
docker compose -f docker-compose.yml -f docker-compose.localhost.yml --env-file .env.localhost down 2>nul
docker compose --env-file .env.localhost down 2>nul
docker compose down 2>nul
echo Pronto. Feche as janelas brd-backend e brd-frontend se abertas.
goto :end

:check
echo [CHECK] validando stack...
if not exist "frontend\app\globals.css" goto :err_frontend
if not exist "frontend\app\layout.tsx" goto :err_frontend
where python >nul 2>&1
if errorlevel 1 goto :err_python
where node >nul 2>&1
if errorlevel 1 goto :err_node
for /f "delims=" %%v in ('python --version 2^>^&1') do echo   %%v
for /f "delims=" %%v in ('node --version 2^>^&1') do echo   Node %%v
echo -- tsc --
pushd frontend
if exist "node_modules\.bin\tsc.cmd" (
  call node_modules\.bin\tsc --noEmit
) else (
  call npx --yes tsc --noEmit
)
if errorlevel 1 (
  popd
  echo ERRO: tsc falhou
  goto :end
)
popd
echo   tsc OK
echo -- next build (pode demorar) --
pushd frontend
call npm run build
if errorlevel 1 (
  popd
  echo ERRO: build falhou
  goto :end
)
popd
echo   build OK
echo CHECK passou.
goto :end

:native
echo [NATIVO] venv + sqlite + locmem
echo.
where python >nul 2>&1
if errorlevel 1 goto :err_python
where node >nul 2>&1
if errorlevel 1 goto :err_node
where npm >nul 2>&1
if errorlevel 1 goto :err_npm
for /f "delims=" %%v in ('python --version 2^>^&1') do echo   %%v
for /f "delims=" %%v in ('node --version 2^>^&1') do echo   Node %%v
echo.

if not exist "frontend\app\globals.css" goto :err_frontend
if not exist "frontend\app\layout.tsx" goto :err_frontend
echo   frontend OK

if not exist "backend\.venv\Scripts\python.exe" (
  echo ==^> Criando backend\.venv ...
  python -m venv backend\.venv
  if errorlevel 1 goto :err_venv
) else echo ==^> backend\.venv ok

echo ==^> pip install ...
backend\.venv\Scripts\python.exe -m pip install --upgrade pip --quiet
backend\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
if errorlevel 1 goto :err_pip

if not exist "backend\.env" (
  echo ==^> Gerando backend\.env ...
  copy /y "backend\.env.example" "backend\.env" >nul
  python -c "import secrets,pathlib;p=pathlib.Path('backend/.env');t=p.read_text(encoding='utf-8');s=secrets.token_urlsafe(50);t=t.replace('troque-por-uma-chave-secreta-gerada',s).replace('DJANGO_DB_ENGINE=postgresql','DJANGO_DB_ENGINE=sqlite3').replace('DJANGO_DEBUG=false','DJANGO_DEBUG=true');t=t if 'DJANGO_CACHE_BACKEND' in t else t+'\nDJANGO_CACHE_BACKEND=locmem\n';t=t.replace('DJANGO_CACHE_BACKEND=redis','DJANGO_CACHE_BACKEND=locmem');p.write_text(t,encoding='utf-8')"
  if errorlevel 1 goto :err_env
  echo     backend\.env criado (sqlite, locmem, SECRET nova)
) else echo ==^> backend\.env ok

if not exist "frontend\node_modules" (
  echo ==^> npm install ...
  pushd frontend
  call npm install
  if errorlevel 1 (
    popd
    goto :err_npm_install
  )
  popd
) else echo ==^> frontend\node_modules ok

if not exist "frontend\.env.local" (
  echo ==^> Gerando frontend\.env.local ...
  if exist "frontend\.env.local.example" (
    copy /y "frontend\.env.local.example" "frontend\.env.local" >nul
  ) else (
    echo NEXT_PUBLIC_API_BASE_URL=http://localhost:8000> "frontend\.env.local"
    echo NEXT_PUBLIC_SITE_URL=http://localhost:3000>> "frontend\.env.local"
  )
) else echo ==^> frontend\.env.local ok

echo ==^> tsc ...
pushd frontend
if exist "node_modules\.bin\tsc.cmd" (
  call node_modules\.bin\tsc --noEmit
) else (
  call npx --yes tsc --noEmit
)
if errorlevel 1 (
  popd
  echo ERRO: tsc falhou
  goto :end
)
popd
echo     tsc OK

echo ==^> migrate ...
backend\.venv\Scripts\python.exe backend\manage.py migrate --noinput
if errorlevel 1 goto :err_migrate

echo ==^> admin ...
set "LOCAL_ADMIN_EMAIL=%ADMIN_EMAIL%"
set "LOCAL_ADMIN_PASSWORD=%ADMIN_PASS%"
backend\.venv\Scripts\python.exe backend\ensure_local_admin.py --email "%ADMIN_EMAIL%" --password "%ADMIN_PASS%"
if errorlevel 1 goto :err_admin

echo ==^> django check ...
backend\.venv\Scripts\python.exe backend\manage.py check
if errorlevel 1 goto :err_check

echo.
echo ============================================================
echo  Subindo backend + frontend ...
echo    Frontend: http://localhost:3000
echo    API:      http://localhost:8000/api/
echo    Health:   http://localhost:8000/healthz
echo    Admin:    http://localhost:8000/admin/  %ADMIN_EMAIL% / %ADMIN_PASS%
echo ============================================================
echo.

powershell -NoProfile -Command "try { $r=Invoke-WebRequest http://127.0.0.1:8000/healthz -UseBasicParsing -TimeoutSec 2; exit ($r.StatusCode -eq 200 ? 0 : 1) } catch { exit 1 }" >nul 2>nul
if errorlevel 1 (
  echo     backend -^> nova janela brd-backend
  start "brd-backend" /D "%~dp0backend" cmd /k ".\.venv\Scripts\python.exe manage.py runserver 0.0.0.0:8000"
) else echo     backend ja online em :8000

powershell -NoProfile -Command "try { $r=Invoke-WebRequest http://127.0.0.1:3000/ -UseBasicParsing -TimeoutSec 2; exit ($r.StatusCode -eq 200 ? 0 : 1) } catch { exit 1 }" >nul 2>nul
if errorlevel 1 (
  echo     frontend -^> nova janela brd-frontend
  start "brd-frontend" /D "%~dp0frontend" cmd /k "npm run dev"
) else echo     frontend ja online em :3000

echo ==^> Aguardando backend ...
powershell -NoProfile -Command "$ok=$false; for($i=0;$i -lt 30;$i++){ try { $r=Invoke-WebRequest http://localhost:8000/healthz -UseBasicParsing -TimeoutSec 3; if($r.StatusCode -eq 200){ $ok=$true; break } } catch {}; Start-Sleep 2 }; if($ok){ exit 0 } else { exit 1 }"
if errorlevel 1 (
  echo AVISO: backend nao respondeu em 60s - veja janela brd-backend
) else echo     backend OK

echo ==^> Aguardando frontend ...
powershell -NoProfile -Command "$ok=$false; for($i=0;$i -lt 30;$i++){ try { $r=Invoke-WebRequest http://localhost:3000/ -UseBasicParsing -TimeoutSec 3; if($r.StatusCode -eq 200){ $ok=$true; break } } catch {}; Start-Sleep 2 }; if($ok){ exit 0 } else { exit 1 }"
if errorlevel 1 (
  echo AVISO: frontend nao respondeu em 60s - veja janela brd-frontend
) else echo     frontend OK

echo.
echo ============================================================
echo  Online!
echo    http://localhost:3000
echo    http://localhost:8000/admin/
echo  Janelas brd-backend e brd-frontend continuam abertas.
echo  Parar: feche as janelas ou subir-localhost.bat --stop
echo ============================================================
start "" "http://localhost:3000"
start "" "http://localhost:8000/admin/"
goto :end

:docker
echo [DOCKER] postgres + redis + frontend standalone
where docker >nul 2>&1
if errorlevel 1 goto :err_docker
docker info >nul 2>&1
if errorlevel 1 goto :err_docker_run
docker compose version >nul 2>&1
if errorlevel 1 goto :err_compose
if not exist "frontend\app\globals.css" goto :err_frontend
setlocal EnableDelayedExpansion
if not exist ".env.localhost" (
  echo ==^> Gerando .env.localhost ...
  for /f "delims=" %%s in ('python -c "import secrets;print(secrets.token_urlsafe(50))" 2^>nul') do set "GEN_SECRET=%%s"
  if not defined GEN_SECRET set "GEN_SECRET=django-insecure-localhost-only"
  (
    echo # Gerado por subir-localhost.bat --docker
    echo DJANGO_SECRET_KEY=!GEN_SECRET!
    echo DJANGO_DEBUG=true
    echo DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1,web,frontend
    echo DJANGO_DB_NAME=brd_portal_noticias
    echo DJANGO_DB_USER=postgres
    echo DJANGO_DB_PASSWORD=postgres
    echo DJANGO_CACHE_BACKEND=redis
    echo DJANGO_CACHE_REDIS_URL=redis://redis:6379/2
    echo CELERY_BROKER_URL=redis://redis:6379/0
    echo CELERY_RESULT_BACKEND=redis://redis:6379/1
    echo FRONTEND_BASE_URL=http://localhost:3000
    echo DJANGO_SECURE_SSL_REDIRECT=false
    echo DJANGO_SESSION_COOKIE_SECURE=false
    echo DJANGO_CSRF_COOKIE_SECURE=false
    echo NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
    echo NEXT_PUBLIC_SITE_URL=http://localhost:3000
    echo DOMAIN_API=localhost
    echo DOMAIN_FRONTEND=localhost
    echo DJANGO_EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend
    echo DJANGO_DEFAULT_FROM_EMAIL=no-reply@brdportalnoticias.local
    echo ASSINATURA_PAYMENT_GATEWAY_PROVIDER=manual
    echo LOCAL_ADMIN_EMAIL=%ADMIN_EMAIL%
    echo LOCAL_ADMIN_PASSWORD=%ADMIN_PASS%
  ) > .env.localhost
) else echo ==^> .env.localhost ok
endlocal
if not exist "docker-compose.localhost.yml" (
  echo ==^> Gerando docker-compose.localhost.yml ...
  (
    echo services:
    echo   web:
    echo     ports: ["8000:8000"]
    echo     env_file: [.env.localhost]
    echo     environment:
    echo       DJANGO_DB_HOST: db
    echo       DJANGO_DEBUG: "true"
    echo       DJANGO_ALLOWED_HOSTS: "localhost,127.0.0.1,web"
    echo       FRONTEND_BASE_URL: "http://localhost:3000"
    echo       DJANGO_SECURE_SSL_REDIRECT: "false"
    echo       DJANGO_SESSION_COOKIE_SECURE: "false"
    echo       DJANGO_CSRF_COOKIE_SECURE: "false"
    echo   celery-worker:
    echo     env_file: [.env.localhost]
    echo     environment: {DJANGO_DB_HOST: db}
    echo   celery-beat:
    echo     env_file: [.env.localhost]
    echo     environment: {DJANGO_DB_HOST: db}
    echo   frontend:
    echo     ports: ["3000:3000"]
    echo     build:
    echo       args:
    echo         NEXT_PUBLIC_API_BASE_URL: "http://localhost:8000"
    echo         NEXT_PUBLIC_SITE_URL: "http://localhost:3000"
    echo   caddy:
    echo     profiles: ["prod"]
  ) > docker-compose.localhost.yml
) else echo ==^> docker-compose.localhost.yml ok
echo ==^> tsc antes do build docker ...
pushd frontend
if exist "node_modules\.bin\tsc.cmd" (
  call node_modules\.bin\tsc --noEmit
) else (
  call npx --yes tsc --noEmit
)
if errorlevel 1 (
  popd
  echo ERRO tsc
  goto :end
)
popd
echo ==^> compose up --build ...
docker compose -f docker-compose.yml -f docker-compose.localhost.yml --env-file .env.localhost up -d --build
if errorlevel 1 goto :err_compose_up
powershell -NoProfile -Command "$ok=$false; for($i=0;$i -lt 30;$i++){ try { $r=Invoke-WebRequest http://localhost:8000/healthz -UseBasicParsing -TimeoutSec 3; if($r.StatusCode -eq 200){ $ok=$true; break } } catch {}; Start-Sleep 3 }; if($ok){ exit 0 } else { exit 1 }"
if errorlevel 1 (
  echo AVISO: web nao respondeu
  docker compose -f docker-compose.yml -f docker-compose.localhost.yml --env-file .env.localhost logs --tail=50 web
  goto :end
)
echo     web OK
powershell -NoProfile -Command "$ok=$false; for($i=0;$i -lt 20;$i++){ try { $r=Invoke-WebRequest http://localhost:3000/ -UseBasicParsing -TimeoutSec 3; if($r.StatusCode -eq 200){ $ok=$true; break } } catch {}; Start-Sleep 3 }; if($ok){ exit 0 } else { exit 1 }"
if errorlevel 1 (
  echo AVISO: frontend nao respondeu
  docker compose -f docker-compose.yml -f docker-compose.localhost.yml --env-file .env.localhost logs --tail=50 frontend
) else echo     frontend OK
docker compose -f docker-compose.yml -f docker-compose.localhost.yml --env-file .env.localhost exec -T web python ensure_local_admin.py --email "%ADMIN_EMAIL%" --password "%ADMIN_PASS%"
if errorlevel 1 (
  docker compose -f docker-compose.yml -f docker-compose.localhost.yml --env-file .env.localhost cp backend\ensure_local_admin.py web:/app/ensure_local_admin.py
  docker compose -f docker-compose.yml -f docker-compose.localhost.yml --env-file .env.localhost exec -T web python /app/ensure_local_admin.py --email "%ADMIN_EMAIL%" --password "%ADMIN_PASS%"
  if errorlevel 1 goto :err_admin_docker
)
docker compose -f docker-compose.yml -f docker-compose.localhost.yml --env-file .env.localhost ps
start "" "http://localhost:3000"
start "" "http://localhost:8000/admin/"
goto :end

:err_frontend
echo ERRO: frontend futurista ausente (globals.css/layout.tsx). Rode git status.
goto :end
:err_python
echo ERRO: python nao no PATH. Instale Python 3.12+
goto :end
:err_node
echo ERRO: node nao no PATH. Instale Node 20+
goto :end
:err_npm
echo ERRO: npm nao no PATH. Reinstale Node
goto :end
:err_venv
echo ERRO: falha ao criar venv
goto :end
:err_pip
echo ERRO: pip install falhou
goto :end
:err_env
echo ERRO: falha ao gerar backend\.env
goto :end
:err_npm_install
echo ERRO: npm install falhou
goto :end
:err_migrate
echo ERRO: migrate falhou
goto :end
:err_admin
echo ERRO: ensure_local_admin falhou
goto :end
:err_check
echo ERRO: django check falhou
goto :end
:err_docker
echo ERRO: docker nao instalado
goto :end
:err_docker_run
echo ERRO: Docker nao esta rodando. Abra Docker Desktop
goto :end
:err_compose
echo ERRO: docker compose v2 requerido
goto :end
:err_compose_up
echo ERRO: compose up falhou
goto :end
:err_admin_docker
echo ERRO: admin docker falhou
goto :end

:end
echo.
echo [FIM] Se subiu, janelas brd-backend/brd-frontend permanecem abertas.
pause
