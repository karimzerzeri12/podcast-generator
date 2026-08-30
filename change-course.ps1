# Change the course content to a PDF, in one step.
#
#   .\change-course.ps1 -Pdf "C:\path\to\course.pdf"
#   .\change-course.ps1 -Pdf "C:\path\to\course.pdf" -Title "My Course" -Description "..."
#   # split one PDF into several topics on a heading pattern (no PDF bookmarks needed):
#   .\change-course.ps1 -Pdf "C:\path\to\course.pdf" -SplitOn "Module \d+" -Title "My Course"
#
# It: (1) builds the course from the PDF, (2) stops the backend, (3) wipes the old
# database + generated files, (4) restarts the backend in a new window so it reseeds
# with the new content. After it finishes, wait ~15s and reload the page in your browser.
#
# NOTE: this fully REPLACES the course. It also clears previously generated podcasts and
# engagement data (correct when you're changing what the course *is*).

param(
    [Parameter(Mandatory = $true)][string]$Pdf,
    [string]$Title,
    [string]$Description,
    # Split the PDF into multiple topics on a text-heading pattern (regex), for PDFs whose
    # chapters are only visual headings, not bookmarks. Example: -SplitOn "Module \d+"
    [string]$SplitOn,
    # Optional: group the sub-topics under a parent chapter (two-level chapter -> sub-chapter).
    # Used together with -SplitOn. Example: -SplitOn "[34]\.[0-9]+ [A-Z]" -ChapterOn "Module \d+"
    [string]$ChapterOn
)

$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
$backend = Join-Path $root "backend"
$python = Join-Path $backend ".venv\Scripts\python.exe"

if (-not (Test-Path $Pdf)) { throw "PDF not found: $Pdf" }
if (-not (Test-Path $python)) { throw "Backend venv not found at $python - set up the backend first." }

Write-Host "[1/4] Building course from PDF..." -ForegroundColor Cyan
Set-Location $backend
$buildArgs = @("-m", "app.build_course", $Pdf, "--no-llm")
if ($Title) { $buildArgs += @("--title", $Title) }
if ($Description) { $buildArgs += @("--description", $Description) }
if ($SplitOn) { $buildArgs += @("--split-on", $SplitOn) }
if ($ChapterOn) { $buildArgs += @("--chapter-on", $ChapterOn) }
& $python @buildArgs
if ($LASTEXITCODE -ne 0) { throw "build_course failed (see output above)." }

Write-Host "[2/4] Stopping the backend..." -ForegroundColor Cyan
Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
    Where-Object { $_.CommandLine -like "*uvicorn*" -or $_.CommandLine -like "*multiprocessing*" } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
Start-Sleep -Seconds 2

Write-Host "[3/4] Wiping old database + generated files..." -ForegroundColor Cyan
Remove-Item (Join-Path $backend "storage\db.sqlite3") -Force -ErrorAction SilentlyContinue
Remove-Item (Join-Path $backend "storage\chroma") -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item (Join-Path $backend "storage\scripts") -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item (Join-Path $backend "storage\audio") -Recurse -Force -ErrorAction SilentlyContinue

Write-Host "[4/4] Restarting the backend (new window)..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList @(
    "-NoExit", "-Command",
    "Set-Location '$backend'; .\.venv\Scripts\uvicorn app.main:app"
)

Write-Host ""
Write-Host "Done. The backend is reseeding with the new course." -ForegroundColor Green
Write-Host "Wait ~15 seconds, then reload http://localhost:5173 in your browser." -ForegroundColor Green
Write-Host "(Make sure your frontend 'npm run dev' window is still running too.)" -ForegroundColor Yellow
