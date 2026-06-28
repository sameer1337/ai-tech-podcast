# ─────────────────────────────────────────────────────────────
#  Register Windows Task Scheduler job — runs podcast daily at 6 AM
#  Run this ONCE as Administrator:  .\setup_scheduler.ps1
# ─────────────────────────────────────────────────────────────

$TaskName   = "AiTechDailyPodcast"
$PythonExe  = (Get-Command python).Source
$ScriptPath = "$PSScriptRoot\run_daily.py"
$WorkDir    = $PSScriptRoot

# Remove existing task if it exists
Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue

$action  = New-ScheduledTaskAction `
    -Execute $PythonExe `
    -Argument "`"$ScriptPath`"" `
    -WorkingDirectory $WorkDir

$trigger = New-ScheduledTaskTrigger -Daily -At "06:00AM"

$settings = New-ScheduledTaskSettingsSet `
    -ExecutionTimeLimit (New-TimeSpan -Hours 1) `
    -StartWhenAvailable `
    -RunOnlyIfNetworkAvailable

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -RunLevel Highest `
    -Description "Generates and publishes AI Tech Daily podcast episode"

Write-Host "✓ Task '$TaskName' registered — runs daily at 6:00 AM" -ForegroundColor Green
Write-Host "  To run it now:  Start-ScheduledTask -TaskName '$TaskName'"
Write-Host "  To remove it:   Unregister-ScheduledTask -TaskName '$TaskName' -Confirm:`$false"
