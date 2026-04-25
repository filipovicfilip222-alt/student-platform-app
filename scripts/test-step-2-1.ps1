$ErrorActionPreference = "Continue"
$allGood = $true

function Check {
    param(
        [string]$Name,
        [bool]$Ok,
        [string]$Details = ""
    )

    if ($Ok) {
        Write-Host "[PASS] $Name" -ForegroundColor Green
    }
    else {
        Write-Host "[FAIL] $Name" -ForegroundColor Red
        if ($Details) {
            Write-Host "       $Details" -ForegroundColor DarkRed
        }
        $script:allGood = $false
    }
}

Write-Host "== Korak 2.1 smoke test ==" -ForegroundColor Cyan

# If invoked from infra/, jump to repo root.
if ((Test-Path ".\\docker-compose.yml") -and -not (Test-Path ".\\infra\\docker-compose.yml")) {
    Set-Location ..
}

$composeFile = "infra/docker-compose.yml"

# 1) Start services.
$upOut = docker compose -f $composeFile --profile app up -d 2>&1 | Out-String
Check "docker compose up" ($LASTEXITCODE -eq 0) $upOut

# 2) Verify celery-beat startup.
$beatLogs = docker compose -f $composeFile logs celery-beat --tail 80 2>&1 | Out-String
$beatOk = ($beatLogs -match "beat:\\s*Starting|Scheduler") -and -not ($beatLogs -match "Traceback|ModuleNotFoundError|django_celery_beat")
Check "celery-beat start bez greske" $beatOk $beatLogs

# 3) Trigger waitlist task manually.
$callOut = docker exec studentska_backend celery -A app.celery_app call waitlist_tasks.process_waitlist_offers 2>&1 | Out-String
$taskIdMatch = [regex]::Match($callOut, "[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}")
$taskId = if ($taskIdMatch.Success) { $taskIdMatch.Value } else { "" }
$callOk = ($LASTEXITCODE -eq 0) -and [bool]$taskId
Check "manual celery call" $callOk $callOut

# 4) Verify task result to ensure no runtime NameError.
$taskResultOut = ""
$taskResultOk = $false
if ($taskId) {
    $taskResultOut = docker exec studentska_backend celery -A app.celery_app result $taskId 2>&1 | Out-String
    $taskResultOk = ($LASTEXITCODE -eq 0) -and -not ($taskResultOut -match "NameError|FAILURE|Traceback")
}
Check "worker izvrsio task bez NameError" $taskResultOk $taskResultOut

# 5) Verify compose scheduler setting.
$composeText = Get-Content -Raw $composeFile
$schedulerOk = $composeText.Contains("celery.beat.PersistentScheduler")
Check "compose koristi PersistentScheduler" $schedulerOk

# 6) Verify main.py comment cleanup.
$mainPath = "backend/app/main.py"
$mainText = Get-Content -Raw $mainPath
$futureImportOk = $mainText.Contains("appointments, admin, search, notifications")
$studentsRegistered = $mainText.Contains("include_router(students.router")
$professorsRegistered = $mainText.Contains("include_router(professors.router")
$usersCommentGone = -not $mainText.Contains("include_router(users.router")
Check "main.py komentari-router cleanup" ($futureImportOk -and $studentsRegistered -and $professorsRegistered -and $usersCommentGone)

# 7) Verify django-celery-beat is not in requirements.
$reqText = Get-Content -Raw "backend/requirements.txt"
$reqOk = -not ($reqText -match "django-celery-beat")
Check "requirements bez django-celery-beat" $reqOk

Write-Host ""
if ($allGood) {
    Write-Host "KONACNO: PASS (Korak 2.1 je ispravno postavljen)." -ForegroundColor Green
    exit 0
}
else {
    Write-Host "KONACNO: FAIL (pogledaj FAIL stavke iznad)." -ForegroundColor Red
    exit 1
}
