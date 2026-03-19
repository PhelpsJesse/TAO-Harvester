$python = "c:/Users/Jesse Phelps/TAO-Harvester/bittensor-harvester/.venv/Scripts/python.exe"
$logFile = "c:/Users/Jesse Phelps/TAO-Harvester/bittensor-harvester/data/retry_daily_report.log"
$maxAttempts = 10
$waitMinutes = 10

for ($i = 1; $i -le $maxAttempts; $i++) {
    $ts = (Get-Date -Format "yyyy-MM-dd HH:mm:ss")
    Add-Content $logFile "[$ts] Attempt $i of $maxAttempts"

    $output = & $python -m v2.tao_harvester.cli daily-report --source taostats --dry-run --date 2026-03-19 2>&1
    $exitCode = $LASTEXITCODE

    $output | ForEach-Object { Add-Content $logFile "  $_" }

    if ($exitCode -eq 0) {
        Add-Content $logFile "[$ts] SUCCESS on attempt $i"
        Write-Host "SUCCESS on attempt $i — see $logFile"
        exit 0
    }

    $ts2 = (Get-Date -Format "yyyy-MM-dd HH:mm:ss")
    Add-Content $logFile "[$ts2] Failed (exit $exitCode). Waiting $waitMinutes min before retry..."

    if ($i -lt $maxAttempts) {
        Start-Sleep -Seconds ($waitMinutes * 60)
    }
}

$ts = (Get-Date -Format "yyyy-MM-dd HH:mm:ss")
Add-Content $logFile "[$ts] All $maxAttempts attempts exhausted. Manual retry required."
Write-Host "All attempts exhausted — see $logFile"
exit 1
