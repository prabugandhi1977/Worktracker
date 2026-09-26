# Brings the WorkTrack RFID Docker stack back up. Safe to run repeatedly (idempotent) --
# `docker compose up -d` only (re)creates containers that aren't already running.
# Invoked automatically by the "WorkTrack RFID AutoStart" scheduled task on logon,
# system startup, and when Windows resumes from sleep.

$ErrorActionPreference = "Continue"
$projectDir = Split-Path -Parent $PSScriptRoot
$logFile = Join-Path $projectDir "autostart.log"

function Write-Log($message) {
    $line = "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') $message"
    Add-Content -Path $logFile -Value $line
}

Write-Log "Trigger fired. Ensuring WorkTrack RFID stack is up..."

$dockerDesktopExe = "C:\Program Files\Docker\Docker\Docker Desktop.exe"
if (-not (Get-Process -Name "Docker Desktop" -ErrorAction SilentlyContinue)) {
    if (Test-Path $dockerDesktopExe) {
        Write-Log "Docker Desktop is not running; launching it."
        Start-Process -FilePath $dockerDesktopExe
    } else {
        Write-Log "Docker Desktop executable not found at expected path. Aborting."
        exit 1
    }
}

$maxWaitSeconds = 300
$elapsed = 0
$dockerReady = $false

while ($elapsed -lt $maxWaitSeconds) {
    docker info *> $null
    if ($LASTEXITCODE -eq 0) {
        $dockerReady = $true
        break
    }
    Start-Sleep -Seconds 5
    $elapsed += 5
}

if (-not $dockerReady) {
    Write-Log "Docker daemon did not become ready within $maxWaitSeconds seconds. Giving up."
    exit 1
}

Write-Log "Docker daemon is ready. Running docker compose up -d."
Set-Location $projectDir
$output = docker compose up -d 2>&1 | Out-String
Add-Content -Path $logFile -Value $output
Write-Log "docker compose up -d finished with exit code $LASTEXITCODE."
