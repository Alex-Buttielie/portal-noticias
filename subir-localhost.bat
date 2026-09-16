@echo off
setlocal EnableDelayedExpansion
chcp 65001 >nul
title BRD Portal Noticias - localhost
cd /d "%~dp0"

set "ADMIN_EMAIL=admin@local.test"
set "ADMIN_PASS=LocalAdmin123"
if not "%LOCAL_ADMIN_EMAIL%"=="" set "ADMIN_EMAIL=%LOCAL_ADMIN_EMAIL%"
if not "%LOCAL_ADMIN_PASSWORD%"=="" set "ADMIN_PASS=%LOCAL_ADMIN_PASSWORD%"

echo ============================================================
echo  BRD Portal de Noticias - localhost (completo + admin)
echo    subir-localhost.bat            nativo  venv + sqlite
echo    subir-localhost.bat --docker   docker  postgres + redis
echo    subir-localhost.bat --stop     para tudo
echo.
echo  Admin local: %ADMIN_EMAIL% / %ADMIN_PASS%
echo  (override: set LOCAL_ADMIN_EMAIL / LOCAL_ADMIN_PASSWORD)
echo ============================================================
echo.

if /I "%~1"=="--stop" goto :stop
if /I "%~1"=="--docker" goto :docker
goto :native

:stop
echo -- Parando containers --
docker compose -f docker-compose.yml -f docker-compose.localhost.yml --env-file .env.localhost down 2>nul
docker compose --env-file .env.localhost down 2>nul
docker compose down 2>nul
echo Pronto. Feche as janelas brd-backend / brd-frontend se abertas.
goto :end

:check_ports
REM %1=porta %2=nome -> ERRORLEVEL 1 se ocupada
powershell -NoProfile -Command "exit ((Get-NetTCPConnection -LocalPort %1 -State Listen -ErrorAction SilentlyContinue) ? 0 : 1)" >nul 2>nul
if %errorlevel%==0 (
  echo AVISO: porta %1 ^(%2^) ja em uso. Feche o processo ou use --docker.
  echo   Para ver: netstat -ano ^| findstr :%1
)
exit /b 0

:native
echo [NATIVO] venv + sqlite + locmem (sem Docker)
echo.
where python >nul 2>nul || (echo ERRO: python nao no PATH. Instale Python 3.12+ & pause & exit /b 1)
where node >nul 2>nul || (echo ERRO: node nao no PATH. Instale Node 20+ & pause & exit /b 1)
where npm >nul 2>nul || (echo ERRO: npm nao no PATH. Reinstale o Node & pause & exit /b 1)
for /f "delims=" %%v in ('python --version 2^>^&1') do echo   %%v
for /f "delims=" %%v in ('node --version 2^>^&1') do echo   Node %%v
echo.
call :check_ports 8000 backend
call :check_ports 3000 frontend
echo.

if not exist "backend\.venv\Scripts\python.exe" (
  echo ==^> Criando backend\.venv ...
  python -m venv backend\.venv || (echo ERRO venv & pause & exit /b 1)
) else echo ==^> backend\.venv ok

echo ==^> pip install ...
backend\.venv\Scripts\python.exe -m pip install --upgrade pip --quiet
backend\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt || (echo ERRO pip install & pause & exit /b 1)

if not exist "backend\.env" (
  echo ==^> Gerando backend\.env ...
  copy /y "backend\.env.example" "backend\.env" >nul
  for /f "delims=" %%s in ('python -c "import secrets;print(secrets.token_urlsafe(50))"') do set "GEN_SECRET=%%s"
  powershell -NoProfile -Command "$t=Get-Content 'backend\.env' -Raw -Encoding utf8; $t=$t -replace 'troque-por-uma-chave-secreta-gerada', $env:GEN_SECRET; $t=$t -replace 'DJANGO_DB_ENGINE=postgresql','DJANGO_DB_ENGINE=sqlite3'; $t=$t -replace 'DJANGO_DEBUG=false','DJANGO_DEBUG=true'; if($t -notmatch 'DJANGO_CACHE_BACKEND'){ $t+=\"`nDJANGO_CACHE_BACKEND=locmem\" }; $t=$t -replace 'DJANGO_CACHE_BACKEND=redis','DJANGO_CACHE_BACKEND=locmem'; Set-Content 'backend\.env' $t -Encoding utf8 -NoNewline"
  echo     backend\.env criado: SECRET aleatoria, DEBUG=true, DB=sqlite3, CACHE=locmem
) else echo ==^> backend\.env ja existe

if not exist "frontend\node_modules" (
  echo ==^> npm install ...
  pushd frontend & call npm install || (popd & echo ERRO npm install & pause & exit /b 1) & popd
) else echo ==^> frontend\node_modules ok

if not exist "frontend\.env.local" (
  echo ==^> Gerando frontend\.env.local ...
  if exist "frontend\.env.local.example" (copy /y "frontend\.env.local.example" "frontend\.env.local" >nul) else (
    echo NEXT_PUBLIC_API_BASE_URL=http://localhost:8000> "frontend\.env.local"
    echo NEXT_PUBLIC_SITE_URL=http://localhost:3000>> "frontend\.env.local"
  )
) else echo ==^> frontend\.env.local ok

echo ==^> migrate ...
backend\.venv\Scripts\python.exe backend\manage.py migrate --noinput || (echo ERRO migrate & pause & exit /b 1)

echo ==^> admin + seeds locais ...
set "LOCAL_ADMIN_EMAIL=%ADMIN_EMAIL%"
set "LOCAL_ADMIN_PASSWORD=%ADMIN_PASS%"
backend\.venv\Scripts\python.exe backend\ensure_local_admin.py --email "%ADMIN_EMAIL%" --password "%ADMIN_PASS%" || (echo ERRO ensure admin & pause & exit /b 1)

echo ==^> django check ...
backend\.venv\Scripts\python.exe backend\manage.py check || (echo ERRO check & pause & exit /b 1)

echo.
choice /c SN /n /m "Popular feed com RSS agora? (pode demorar) [S/N]: "
if errorlevel 2 goto :skip_feed
echo ==^> ingerindo noticias ...
backend\.venv\Scripts\python.exe backend\manage.py ingerir_noticias || echo AVISO: ingestao falhou (sem internet ou RSS fora). O resto funciona; aprove itens no admin.
:skip_feed

echo.
echo ============================================================
echo  Pronto para testar!
echo    Frontend: http://localhost:3000
echo    API:      http://localhost:8000/api/
echo    Health:   http://localhost:8000/healthz
echo    Admin:    http://localhost:8000/admin/
echo    Login:    %ADMIN_EMAIL% / %ADMIN_PASS%
echo.
echo  Feed vazio? backend\.venv\Scripts\python.exe backend\manage.py ingerir_noticias
echo  Depois aprove em /admin (catalogo_noticias) p/ ver no feed publico.
echo ============================================================
echo.
choice /c SN /n /m "Subir backend + frontend agora? [S/N]: "
if errorlevel 2 goto :manual_native
goto :launch_native
:manual_native
echo Suba manual: backend\.venv\Scripts\python.exe backend\manage.py runserver  ^|  cd frontend ^&^& npm run dev
goto :end

:launch_native
powershell -NoProfile -Command "try { exit ((Invoke-WebRequest http://127.0.0.1:8000/healthz -UseBasicParsing -TimeoutSec 3).StatusCode -eq 200 ? 0 : 1) } catch { exit 1 }" >nul 2>nul
if %errorlevel%==0 (echo     backend ja online em :8000 - reaproveitando) else start "brd-backend" cmd /k "cd /d "%~dp0backend" && "%~dp0backend\.venv\Scripts\python.exe" manage.py runserver 0.0.0.0:8000"
powershell -NoProfile -Command "try { exit ((Invoke-WebRequest http://127.0.0.1:3000/ -UseBasicParsing -TimeoutSec 3).StatusCode -eq 200 ? 0 : 1) } catch { exit 1 }" >nul 2>nul
if %errorlevel%==0 (echo     frontend ja online em :3000 - reaproveitando) else start "brd-frontend" cmd /k "cd /d "%~dp0frontend" && npm run dev"
echo ==^> Aguardando backend responder ...
powershell -NoProfile -Command "$ok=$false; for($i=0;$i -lt 30;$i++){ try { $r=Invoke-WebRequest http://localhost:8000/healthz -UseBasicParsing -TimeoutSec 3; if($r.StatusCode -eq 200){ $ok=$true; break } } catch {}; Start-Sleep 2 }; if($ok){ exit 0 } else { exit 1 }"
if %errorlevel%==0 (echo     backend OK) else (echo AVISO: backend nao respondeu em 60s. Veja a janela brd-backend.)
start "" "http://localhost:3000"
start "" "http://localhost:8000/admin/"
goto :end

:docker
echo [DOCKER] postgres + redis (replica prod, sem TLS)
echo.
where docker >nul 2>nul || (echo ERRO: docker nao instalado & pause & exit /b 1)
docker info >nul 2>nul || (echo ERRO: Docker nao esta rodando. Abra o Docker Desktop & pause & exit /b 1)
docker compose version >nul 2>nul || (echo ERRO: docker compose v2 requerido & pause & exit /b 1)

if not exist ".env.localhost" (
  echo ==^> Gerando .env.localhost ...
  for /f "delims=" %%s in ('python -c "import secrets;print(secrets.token_urlsafe(50))" 2^>nul') do set "GEN_SECRET=%%s"
  if not defined GEN_SECRET set "GEN_SECRET=django-insecure-localhost-only-please-change-me"
  (
    echo # Gerado por subir-localhost.bat --docker - NAO commitar
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

if not exist "docker-compose.localhost.yml" (
  echo ==^> Gerando docker-compose.localhost.yml ...
  (
    echo # Override localhost: portas diretas, sem TLS, DEBUG true
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
    echo   caddy:
    echo     profiles: ["prod"]
  ) > docker-compose.localhost.yml
) else echo ==^> docker-compose.localhost.yml ok

echo ==^> Build + up ...
docker compose -f docker-compose.yml -f docker-compose.localhost.yml --env-file .env.localhost up -d --build || (echo ERRO compose up & pause & exit /b 1)

echo ==^> Aguardando web saudavel ...
powershell -NoProfile -Command "$ok=$false; for($i=0;$i -lt 30;$i++){ try { $r=Invoke-WebRequest http://localhost:8000/healthz -UseBasicParsing -TimeoutSec 3; if($r.StatusCode -eq 200){ $ok=$true; break } } catch {}; Start-Sleep 3 }; if($ok){ exit 0 } else { exit 1 }"
if not %errorlevel%==0 (
  echo AVISO: web nao respondeu. Logs:
  docker compose -f docker-compose.yml -f docker-compose.localhost.yml --env-file .env.localhost logs --tail=50 web
  pause & exit /b 1
)
echo     web OK

echo ==^> admin + seeds no container ...
docker compose -f docker-compose.yml -f docker-compose.localhost.yml --env-file .env.localhost exec -T web python ensure_local_admin.py --email "%ADMIN_EMAIL%" --password "%ADMIN_PASS%" || (
  echo AVISO: ensure via exec falhou; tentando copiar script...
  docker compose -f docker-compose.yml -f docker-compose.localhost.yml --env-file .env.localhost cp backend\ensure_local_admin.py web:/app/ensure_local_admin.py
  docker compose -f docker-compose.yml -f docker-compose.localhost.yml --env-file .env.localhost exec -T web python /app/ensure_local_admin.py --email "%ADMIN_EMAIL%" --password "%ADMIN_PASS%" || (echo ERRO admin docker & pause & exit /b 1)
)

docker compose -f docker-compose.yml -f docker-compose.localhost.yml --env-file .env.localhost ps
echo.
echo ============================================================
echo  Docker no ar!
echo    Frontend: http://localhost:3000
echo    Admin:    http://localhost:8000/admin/  %ADMIN_EMAIL% / %ADMIN_PASS%
echo    API:      http://localhost:8000/api/
echo    Parar:    subir-localhost.bat --stop
echo    Feed:     docker compose -f docker-compose.yml -f docker-compose.localhost.yml --env-file .env.localhost exec web python manage.py ingerir_noticias
echo ============================================================
start "" "http://localhost:3000"
start "" "http://localhost:8000/admin/"
goto :end

:end
echo.
pause
