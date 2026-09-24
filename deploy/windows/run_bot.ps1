# Step the paper bot once and append the output to logs\bot.log.
# Called by the scheduled task (see register_bot_task.ps1); safe to run by hand.
param([string]$BotName = "sp500-pairs")

$root = (Resolve-Path "$PSScriptRoot\..\..").Path
Set-Location $root
New-Item -ItemType Directory -Force (Join-Path $root "logs") | Out-Null
$log = Join-Path $root "logs\bot.log"
$python = Join-Path $root ".venv\Scripts\python.exe"

$env:PYTHONIOENCODING = "utf-8"
Add-Content -Path $log -Encoding utf8 -Value "=== $((Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ'))"
# cmd.exe does the redirection so the log stays plain UTF-8 (PowerShell 5.1 would write UTF-16).
cmd.exe /c "`"$python`" -m quantlab.bot run --name $BotName >> `"$log`" 2>&1"
exit $LASTEXITCODE
