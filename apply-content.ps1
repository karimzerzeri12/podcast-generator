# Apply hand-edits to the course content.
#
# Edit the files under backend\app\seed\data\ (see below), then run:
#   .\apply-content.ps1
#
# Files you can edit:
#   course.json           - the course title + description
#   topics.json           - the list of topics: title, description, chapter, order_index, filename
#   roster.csv            - the students (email, access_code, name)
#   topics\*.txt          - the actual course text each topic is generated from
#
# This rebuilds the database from those files so your edits take effect. It clears
# previously generated podcasts/engagement (correct when changing what the course IS).
# If you're sharing via .\share.ps1, the same tunnel link keeps working - it just serves
# the updated content once the backend restarts.

$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
$backend = Join-Path $root "backend"

Write-Host "[1/2] Stopping the backend and clearing the old database..." -ForegroundColor Cyan
Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
    Where-Object { $_.CommandLine -like "*uvicorn*" -or $_.CommandLine -like "*multiprocessing*" } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
Start-Sleep -Seconds 2
Remove-Item (Join-Path $backend "storage\db.sqlite3") -Force -ErrorAction SilentlyContinue
Remove-Item (Join-Path $backend "storage\chroma") -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item (Join-Path $backend "storage\scripts") -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item (Join-Path $backend "storage\audio") -Recurse -Force -ErrorAction SilentlyContinue

Write-Host "[2/2] Restarting the backend (it re-seeds from your edited files)..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList @(
    "-NoExit", "-Command",
    "Set-Location '$backend'; .\.venv\Scripts\uvicorn app.main:app"
)

Write-Host ""
Write-Host "Done. Wait ~15 seconds, then reload the app in your browser." -ForegroundColor Green
Write-Host "(If a topics.json field is malformed, the backend window will show an error.)" -ForegroundColor Yellow
