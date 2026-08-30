# Share the app with a public link via a Cloudflare quick tunnel.
# No Docker, no account, no deploy. The link works while this stays running.
#
#   .\share.ps1
#
# It: (1) builds the frontend into the backend so everything is served on one port,
# (2) starts the backend in a new window, (3) opens a public tunnel and prints a
# https://<random>.trycloudflare.com URL. Send that URL (plus a roster login from
# backend/app/seed/data/roster.csv) to your professor.
#
# To stop sharing: press Ctrl-C in this window (and close the backend window).
# NOTE: the link only works while your laptop is on and this script is running, and the
# URL changes each time you run it. For an always-on link, use a real deployment later.

$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
$backend = Join-Path $root "backend"
$frontend = Join-Path $root "frontend"
$static = Join-Path $backend "static"

# Make cloudflared visible even if it was just installed this session.
$env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" +
            [System.Environment]::GetEnvironmentVariable("Path", "User")
if (-not (Get-Command cloudflared -ErrorAction SilentlyContinue)) {
    Write-Host "cloudflared is not installed. Install it once with:" -ForegroundColor Yellow
    Write-Host "  winget install --id Cloudflare.cloudflared" -ForegroundColor Yellow
    exit 1
}

Write-Host "[1/3] Building the frontend into the backend (single port)..." -ForegroundColor Cyan
Set-Location $frontend
$env:VITE_API_BASE_URL = ""   # empty => frontend calls the API on its own (tunnel) origin
npm run build
if (Test-Path $static) { Remove-Item $static -Recurse -Force }
Copy-Item (Join-Path $frontend "dist") $static -Recurse

Write-Host "[2/3] Starting the backend in a new window..." -ForegroundColor Cyan
# Stop any previous backend and tunnel so re-running doesn't leave duplicates behind.
Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
    Where-Object { $_.CommandLine -like "*uvicorn*" } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
Get-Process cloudflared -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 2
Start-Process powershell -ArgumentList @(
    "-NoExit", "-Command",
    "Set-Location '$backend'; .\.venv\Scripts\uvicorn app.main:app"
)

Write-Host "    Waiting for the backend to be ready..." -ForegroundColor Cyan
$ready = $false
for ($i = 0; $i -lt 25; $i++) {
    Start-Sleep -Seconds 2
    try {
        Invoke-WebRequest -UseBasicParsing "http://localhost:8000/health" -TimeoutSec 3 | Out-Null
        $ready = $true; break
    } catch {}
}
if (-not $ready) {
    Write-Host "Backend didn't respond in time - check the backend window for errors." -ForegroundColor Red
    exit 1
}

Write-Host "[3/3] Opening the public tunnel..." -ForegroundColor Cyan
$outLog = Join-Path $env:TEMP "podcast_tunnel.out.log"
$errLog = Join-Path $env:TEMP "podcast_tunnel.err.log"
Remove-Item $outLog, $errLog -ErrorAction SilentlyContinue
$tunnel = Start-Process cloudflared `
    -ArgumentList "tunnel", "--url", "http://localhost:8000" `
    -RedirectStandardOutput $outLog -RedirectStandardError $errLog `
    -NoNewWindow -PassThru

# cloudflared prints the assigned URL to its logs a few seconds after starting; grab it.
$publicUrl = $null
for ($i = 0; $i -lt 30; $i++) {
    Start-Sleep -Seconds 1
    $hit = Select-String -Path $errLog, $outLog -Pattern "https://[a-z0-9-]+\.trycloudflare\.com" `
        -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($hit) { $publicUrl = $hit.Matches[0].Value; break }
}

Write-Host ""
if ($publicUrl) {
    Write-Host "==================================================================" -ForegroundColor Green
    Write-Host "  YOUR APP IS LIVE" -ForegroundColor Green
    Write-Host "==================================================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "  Student link (send this to your professor):" -ForegroundColor White
    Write-Host "    $publicUrl" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "  Admin dashboard (keep this to yourself):" -ForegroundColor White
    Write-Host "    $publicUrl/#/admin   -> enter your ADMIN_TOKEN" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "  Log in as a student with an email/code from" -ForegroundColor White
    Write-Host "    backend/app/seed/data/roster.csv  (e.g. alice@example.edu / alice123)" -ForegroundColor White
    Write-Host "==================================================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "Keep this window open to stay live. Press Ctrl-C to stop sharing." -ForegroundColor Yellow
} else {
    Write-Host "Couldn't auto-detect the tunnel URL. Open this file and look for a" -ForegroundColor Yellow
    Write-Host "line like https://<something>.trycloudflare.com :" -ForegroundColor Yellow
    Write-Host "  $errLog" -ForegroundColor Yellow
    Write-Host "That address is the student link; add /#/admin for the admin page." -ForegroundColor Yellow
}

# Keep the tunnel process running until this window is closed / Ctrl-C.
Wait-Process -Id $tunnel.Id
