[CmdletBinding()]
param(
    [switch]$Build,
    [switch]$NoBrowser
)

$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot

function Get-EnvPort {
    param(
        [Parameter(Mandatory)] [string]$Name,
        [Parameter(Mandatory)] [int]$Default
    )

    $envFile = Join-Path $PSScriptRoot ".env"
    if (-not (Test-Path -LiteralPath $envFile)) {
        return $Default
    }

    $match = Get-Content -LiteralPath $envFile |
        Where-Object { $_ -match "^\s*$Name\s*=\s*(\d+)\s*$" } |
        Select-Object -Last 1

    if ($match -and $match -match "^\s*$Name\s*=\s*(\d+)\s*$") {
        return [int]$Matches[1]
    }

    return $Default
}

function Test-DockerEngine {
    $previousPreference = $ErrorActionPreference
    $ErrorActionPreference = "SilentlyContinue"
    try {
        & docker info 2> $null | Out-Null
        return $LASTEXITCODE -eq 0
    }
    finally {
        $ErrorActionPreference = $previousPreference
    }
}

function Wait-ForUrl {
    param(
        [Parameter(Mandatory)] [string]$Name,
        [Parameter(Mandatory)] [string]$Url,
        [int]$TimeoutSeconds = 180
    )

    Write-Host "Dang cho $Name san sang..." -ForegroundColor Cyan
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)

    while ((Get-Date) -lt $deadline) {
        try {
            $response = Invoke-WebRequest -UseBasicParsing -Uri $Url -TimeoutSec 5
            if ($response.StatusCode -ge 200 -and $response.StatusCode -lt 500) {
                Write-Host "[OK] $Name da san sang: $Url" -ForegroundColor Green
                return $true
            }
        }
        catch {
            Start-Sleep -Seconds 3
        }
    }

    Write-Warning "$Name chua phan hoi sau $TimeoutSeconds giay. Hay chay: docker compose ps"
    return $false
}

Write-Host "`n=== SiteOps - Khoi dong he thong ===" -ForegroundColor Cyan

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw "Khong tim thay Docker. Hay cai Docker Desktop truoc khi chay file nay."
}

if (-not (Test-DockerEngine)) {
    Write-Host "Docker chua chay. Dang mo Docker Desktop..." -ForegroundColor Yellow

    $dockerDesktopCandidates = @(
        (Join-Path $env:ProgramFiles "Docker\Docker\Docker Desktop.exe"),
        (Join-Path $env:LOCALAPPDATA "Docker\Docker Desktop.exe")
    )
    $dockerDesktop = $dockerDesktopCandidates |
        Where-Object { Test-Path -LiteralPath $_ } |
        Select-Object -First 1

    if (-not $dockerDesktop) {
        throw "Khong tim thay Docker Desktop. Hay mo Docker Desktop thu cong roi chay lai start.ps1."
    }

    Start-Process -FilePath $dockerDesktop
    $deadline = (Get-Date).AddSeconds(180)
    while ((Get-Date) -lt $deadline -and -not (Test-DockerEngine)) {
        Start-Sleep -Seconds 5
    }

    if (-not (Test-DockerEngine)) {
        throw "Docker Desktop khoi dong qua lau. Hay kiem tra Docker Desktop roi chay lai."
    }
}

$composeArguments = @("compose", "up", "-d")
if ($Build) {
    $composeArguments += "--build"
}

Write-Host "Dang khoi dong PostgreSQL, FastAPI, worker, frontend va pgAdmin..." -ForegroundColor Cyan
$previousPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
& docker @composeArguments
$composeExitCode = $LASTEXITCODE
$ErrorActionPreference = $previousPreference
if ($composeExitCode -ne 0) {
    throw "Docker Compose khoi dong that bai. Hay chay 'docker compose logs' de xem chi tiet."
}

$appPort = Get-EnvPort -Name "APP_PORT" -Default 3000
$apiPort = Get-EnvPort -Name "API_PORT" -Default 4000
$pgAdminPort = Get-EnvPort -Name "PGADMIN_PORT" -Default 5051

$appUrl = "http://localhost:$appPort"
$apiUrl = "http://localhost:$apiPort/api/health"
$pgAdminUrl = "http://localhost:$pgAdminPort"

$frontendReady = Wait-ForUrl -Name "Website SiteOps" -Url $appUrl
[void](Wait-ForUrl -Name "FastAPI" -Url $apiUrl -TimeoutSeconds 60)
[void](Wait-ForUrl -Name "pgAdmin" -Url $pgAdminUrl -TimeoutSeconds 60)

Write-Host "`nDia chi truy cap:" -ForegroundColor Cyan
Write-Host "  SiteOps : $appUrl"
Write-Host "  FastAPI : http://localhost:$apiPort/docs"
Write-Host "  pgAdmin : $pgAdminUrl"

if ($frontendReady -and -not $NoBrowser) {
    Start-Process $appUrl
}

Write-Host "`nHe thong da duoc khoi dong. Ban co the dong cua so nay." -ForegroundColor Green
Write-Host "Lan sau can build lai code: .\start.ps1 -Build" -ForegroundColor DarkGray
