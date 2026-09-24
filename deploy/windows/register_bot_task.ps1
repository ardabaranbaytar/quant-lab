# Register a Windows scheduled task that steps the paper bot after each US close.
#
#   powershell -ExecutionPolicy Bypass -File deploy\windows\register_bot_task.ps1
#   Get-ScheduledTask "quant-lab paper bot" | Get-ScheduledTaskInfo      # last/next run
#   Unregister-ScheduledTask "quant-lab paper bot" -Confirm:$false       # remove
#
# Why 00:30 Tuesday-Saturday: Windows triggers use local time and Turkey has no
# DST, but New York does. 00:30 Istanbul = 17:30 New York in summer and 16:30 in
# winter, so it is after the close all year. (23:30 would be 15:30 New York in
# winter, before the close; the bot would then always lag a day.)
# If the PC is off at that time, the task runs at the next start-up and the bot
# catches up on every missed close.
param(
    [string]$At = "00:30",
    [string]$BotName = "sp500-pairs",
    [string]$TaskName = "quant-lab paper bot"
)

$root = (Resolve-Path "$PSScriptRoot\..\..").Path
$script = Join-Path $root "deploy\windows\run_bot.ps1"

$action = New-ScheduledTaskAction -Execute "powershell.exe" `
    -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$script`" -BotName $BotName" `
    -WorkingDirectory $root
$trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Tuesday, Wednesday, Thursday, Friday, Saturday -At $At
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Hours 1) `
    -MultipleInstances IgnoreNew

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings `
    -Description "Steps the quant-lab paper-trading bot after the New York close (idempotent)." -Force |
    Out-Null
Write-Host "Registered '$TaskName': Tue-Sat at $At local time -> $script"
