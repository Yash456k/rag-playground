$ErrorActionPreference = 'Stop'

$taskName = 'Yash Portfolio Activity Sync'
$wslCommand = '-d Ubuntu bash -lc "cd /home/yash456k/coding-stuff/rag-playground && python3 scripts/sync_portfolio_activity.py --publish"'
$action = New-ScheduledTaskAction -Execute "$env:SystemRoot\System32\wsl.exe" -Argument $wslCommand
$trigger = New-ScheduledTaskTrigger -Daily -At '11:55 PM'
$settings = New-ScheduledTaskSettingsSet `
  -StartWhenAvailable `
  -MultipleInstances IgnoreNew `
  -ExecutionTimeLimit (New-TimeSpan -Minutes 15)

Register-ScheduledTask `
  -TaskName $taskName `
  -Action $action `
  -Trigger $trigger `
  -Settings $settings `
  -Description 'Refresh Codex and GitHub activity data, then publish the portfolio snapshot.' `
  -Force | Out-Null

Write-Host "Installed '$taskName' to run daily at 11:55 PM and catch up after missed runs."
