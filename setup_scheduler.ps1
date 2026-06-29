# ─────────────────────────────────────────────────────────────
#  Register Windows Task Scheduler job — runs podcast daily at 6 AM
#  Run this ONCE as Administrator:  .\setup_scheduler.ps1
# ─────────────────────────────────────────────────────────────

$TaskName   = "AiTechDailyPodcast"
$PythonExe  = (Get-Command py -ErrorAction SilentlyContinue).Source
if (-not $PythonExe) { $PythonExe = (Get-Command python3 -ErrorAction SilentlyContinue).Source }
if (-not $PythonExe) { $PythonExe = "C:\Users\Sameer\AppData\Local\Programs\Python\Python313\python.exe" }
$ScriptPath = "$PSScriptRoot\run_daily.py"
$WorkDir    = $PSScriptRoot

# Remove existing task if it exists
Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue

$GroqKey = [System.Environment]::GetEnvironmentVariable("GROQ_API_KEY", "User")
$action  = New-ScheduledTaskAction `
    -Execute $PythonExe `
    -Argument "-u `"$ScriptPath`"" `
    -WorkingDirectory $WorkDir

# Set env vars for the task
$envVars = @("GROQ_API_KEY=$GroqKey", "PYTHONUTF8=1")

$trigger = New-ScheduledTaskTrigger -Daily -At "06:00AM"

$settings = New-ScheduledTaskSettingsSet `
    -ExecutionTimeLimit (New-TimeSpan -Hours 1) `
    -StartWhenAvailable `
    -RunOnlyIfNetworkAvailable

$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -RunLevel Highest

$task = New-ScheduledTask -Action $action -Trigger $trigger -Settings $settings -Principal $principal `
    -Description "Generates and publishes AI Tech Daily podcast episode"

Register-ScheduledTask -TaskName $TaskName -InputObject $task -Force

# Inject environment variables into the task XML
$xml = (Export-ScheduledTask -TaskName $TaskName)
$envBlock = "<EnvironmentVariables>" + ($envVars | ForEach-Object { "<Variable><Name>$($_.Split('=')[0])</Name><Value>$($_.Split('=',2)[1])</Value></Variable>" }) + "</EnvironmentVariables>"
# Note: Task Scheduler doesn't natively support env vars via PowerShell cmdlets easily.
# The GROQ_API_KEY is already set as a User environment variable so it will be available.

Write-Host "✓ Task '$TaskName' registered — runs daily at 6:00 AM" -ForegroundColor Green
Write-Host "  To run it now:  Start-ScheduledTask -TaskName '$TaskName'"
Write-Host "  To remove it:   Unregister-ScheduledTask -TaskName '$TaskName' -Confirm:`$false"
