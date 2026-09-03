<#
.SYNOPSIS
    Inicializa o Portal de Noticias para desenvolvimento local: cria o
    venv do backend, instala dependencias (Python e Node), gera os
    arquivos .env locais se nao existirem, roda as migracoes do Django
    e (por padrao) sobe os dois servidores de desenvolvimento.

.DESCRIPTION
    Idempotente: pode ser rodado de novo a qualquer momento sem duplicar
    trabalho (nao recria o venv/.env se ja existirem, nao reinstala o
    node_modules se ja existir).

    Por padrao usa SQLite para o backend (atalho de conveniencia para
    bootstrap local sem precisar de um servidor PostgreSQL rodando -
    ver backend/.env.example). Passe -DbEngine postgresql se ja tiver
    um Postgres local configurado com as credenciais de
    backend/.env.example.

.PARAMETER DbEngine
    "sqlite3" (padrao) ou "postgresql".

.PARAMETER SkipStart
    Nao sobe os servidores de desenvolvimento ao final (so prepara o
    ambiente).

.PARAMETER CreateSuperuser
    Roda "manage.py createsuperuser" (interativo) apos as migracoes.

.EXAMPLE
    .\scripts\init-local.ps1
    Prepara tudo e sobe backend (porta 8000) e frontend (porta 3000).

.EXAMPLE
    .\scripts\init-local.ps1 -SkipStart
    So prepara o ambiente (venv, dependencias, .env, migracoes), sem
    subir os servidores.
#>

[CmdletBinding()]
param(
    [ValidateSet("sqlite3", "postgresql")]
    [string]$DbEngine = "sqlite3",

    [switch]$SkipStart,

    [switch]$CreateSuperuser
)

$ErrorActionPreference = "Stop"

$RootDir = Split-Path -Parent $PSScriptRoot
$BackendDir = Join-Path $RootDir "backend"
$FrontendDir = Join-Path $RootDir "frontend"

function Write-Step($mensagem) {
    Write-Host ""
    Write-Host "==> $mensagem" -ForegroundColor Cyan
}

function Write-Aviso($mensagem) {
    Write-Host "    $mensagem" -ForegroundColor Yellow
}

function Assert-Comando($nome, $ajuda) {
    if (-not (Get-Command $nome -ErrorAction SilentlyContinue)) {
        Write-Host "ERRO: '$nome' nao foi encontrado no PATH. $ajuda" -ForegroundColor Red
        exit 1
    }
}

function New-ChaveSecreta {
    $bytes = New-Object byte[] 48
    $rng = New-Object System.Security.Cryptography.RNGCryptoServiceProvider
    try {
        $rng.GetBytes($bytes)
    } finally {
        $rng.Dispose()
    }
    $bruta = [Convert]::ToBase64String($bytes)
    return ($bruta -replace '[^a-zA-Z0-9]', '').Substring(0, 50)
}

# ---------------------------------------------------------------------------
# 0. Pre-requisitos
# ---------------------------------------------------------------------------
Write-Step "Verificando pre-requisitos"
Assert-Comando "python" "Instale Python 3.13+ (https://www.python.org/downloads/) e garanta que esta no PATH."
Assert-Comando "node" "Instale Node.js 18+ (https://nodejs.org/) e garanta que esta no PATH."
Assert-Comando "npm" "Vem junto com o Node.js - reinstale o Node se estiver faltando."

$pythonVersion = (python --version) 2>&1
$nodeVersion = (node --version) 2>&1
Write-Host "    Python: $pythonVersion"
Write-Host "    Node:   $nodeVersion"

if ($DbEngine -eq "sqlite3") {
    Write-Aviso "Usando SQLite (atalho de conveniencia p/ dev local). Para Postgres, rode com -DbEngine postgresql."
} else {
    Write-Aviso "Usando PostgreSQL - certifique-se de que ha um servidor rodando com as credenciais de backend/.env."
}

# ---------------------------------------------------------------------------
# 1. Backend - venv + dependencias
# ---------------------------------------------------------------------------
Write-Step "Backend: ambiente virtual Python"

$VenvDir = Join-Path $BackendDir ".venv"
$VenvPython = Join-Path $VenvDir "Scripts\python.exe"

if (-not (Test-Path $VenvPython)) {
    Write-Host "    Criando venv em backend\.venv ..."
    python -m venv $VenvDir
} else {
    Write-Host "    venv ja existe, reaproveitando."
}

Write-Step "Backend: instalando dependencias (requirements.txt)"
& $VenvPython -m pip install --upgrade pip --quiet
& $VenvPython -m pip install -r (Join-Path $BackendDir "requirements.txt")
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERRO: pip install falhou (veja o log acima)." -ForegroundColor Red
    exit 1
}

# ---------------------------------------------------------------------------
# 2. Backend - .env local
# ---------------------------------------------------------------------------
Write-Step "Backend: arquivo .env"

$EnvPath = Join-Path $BackendDir ".env"
$EnvExamplePath = Join-Path $BackendDir ".env.example"

if (Test-Path $EnvPath) {
    Write-Host "    backend\.env ja existe - nao foi alterado."
} else {
    Write-Host "    Gerando backend\.env a partir de .env.example ..."
    $conteudo = Get-Content $EnvExamplePath -Raw -Encoding utf8

    $chaveSecreta = New-ChaveSecreta
    $conteudo = $conteudo -replace 'DJANGO_SECRET_KEY=troque-por-uma-chave-secreta-gerada', "DJANGO_SECRET_KEY=$chaveSecreta"
    $conteudo = $conteudo -replace 'DJANGO_DB_ENGINE=postgresql', "DJANGO_DB_ENGINE=$DbEngine"

    Set-Content -Path $EnvPath -Value $conteudo -Encoding utf8 -NoNewline
    Write-Host "    Criado: backend\.env (DJANGO_SECRET_KEY gerada automaticamente, DJANGO_DB_ENGINE=$DbEngine)."
    Write-Aviso "Login social Google e resumo por LLM ficam desativados ate voce preencher GOOGLE_OAUTH_* / CATALOGO_NOTICIAS_LLM_API_KEY em backend\.env - o resto do sistema funciona sem eles."
}

# ---------------------------------------------------------------------------
# 3. Backend - migracoes
# ---------------------------------------------------------------------------
Write-Step "Backend: aplicando migracoes"
& $VenvPython (Join-Path $BackendDir "manage.py") migrate
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERRO: 'manage.py migrate' falhou (veja o log acima)." -ForegroundColor Red
    exit 1
}

if ($CreateSuperuser) {
    Write-Step "Backend: criando superusuario (interativo)"
    & $VenvPython (Join-Path $BackendDir "manage.py") createsuperuser
}

# ---------------------------------------------------------------------------
# 4. Frontend - dependencias
# ---------------------------------------------------------------------------
Write-Step "Frontend: instalando dependencias (npm install)"

$NodeModulesDir = Join-Path $FrontendDir "node_modules"
if (Test-Path $NodeModulesDir) {
    Write-Host "    frontend\node_modules ja existe, reaproveitando (rode 'npm install' manualmente se o package.json mudou)."
} else {
    Push-Location $FrontendDir
    try {
        npm install
        if ($LASTEXITCODE -ne 0) {
            Write-Host "ERRO: 'npm install' falhou (veja o log acima)." -ForegroundColor Red
            exit 1
        }
    } finally {
        Pop-Location
    }
}

# ---------------------------------------------------------------------------
# 5. Frontend - .env.local
# ---------------------------------------------------------------------------
Write-Step "Frontend: arquivo .env.local"

$FrontendEnvPath = Join-Path $FrontendDir ".env.local"
$FrontendEnvExamplePath = Join-Path $FrontendDir ".env.local.example"

if (Test-Path $FrontendEnvPath) {
    Write-Host "    frontend\.env.local ja existe - nao foi alterado."
} else {
    Copy-Item $FrontendEnvExamplePath $FrontendEnvPath
    Write-Host "    Criado: frontend\.env.local (aponta para http://localhost:8000)."
}

# ---------------------------------------------------------------------------
# 6. Subir os servidores (a menos que -SkipStart)
# ---------------------------------------------------------------------------
Write-Step "Ambiente pronto"
Write-Host "    Backend:  http://localhost:8000/api/  (admin em /admin/)"
Write-Host "    Frontend: http://localhost:3000"
Write-Aviso "Feed ainda sem noticias? Rode: backend\.venv\Scripts\python.exe backend\manage.py ingerir_noticias (busca RSS real agora mesmo, sem precisar de Celery/Redis - ver README.md, secao 'Como popular o feed com noticias reais')."
Write-Aviso "Celery (ingestao periodica de noticias, vencimento de assinatura, envio de newsletter) precisa de um Redis local rodando e nao e subido por este script - opcional para so navegar no site. Se tiver Redis: backend\.venv\Scripts\celery.exe -A config worker -l info / -A config beat -l info."

if ($SkipStart) {
    Write-Host ""
    Write-Host "Para subir manualmente:"
    Write-Host "  Backend:  cd backend; .\.venv\Scripts\python.exe manage.py runserver"
    Write-Host "  Frontend: cd frontend; npm run dev"
    exit 0
}

Write-Step "Subindo backend e frontend em janelas separadas"

Start-Process powershell -ArgumentList @(
    "-NoExit",
    "-Command",
    "cd `"$BackendDir`"; & `"$VenvPython`" manage.py runserver"
)

Start-Process powershell -ArgumentList @(
    "-NoExit",
    "-Command",
    "cd `"$FrontendDir`"; npm run dev"
)

Write-Host ""
Write-Host "Backend e frontend estao subindo em janelas novas do PowerShell." -ForegroundColor Green
Write-Host "Feche essas janelas (ou Ctrl+C dentro delas) para encerrar os servidores."
