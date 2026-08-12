param([int]$Port=8080,[string]$Distro='')
$ErrorActionPreference = "Stop"
if ([string]::IsNullOrWhiteSpace($Distro)) { $Distro = ((& wsl.exe -l -q) | Where-Object { $_.Trim() } | Select-Object -First 1).Trim() }
if ([string]::IsNullOrWhiteSpace($Distro) -or $Distro.Contains('"')) { throw "Invalid WSL distribution name" }
$lan = Get-NetRoute -DestinationPrefix '0.0.0.0/0' | Sort-Object RouteMetric | ForEach-Object {
    Get-NetIPAddress -InterfaceIndex $_.InterfaceIndex -AddressFamily IPv4 -ErrorAction SilentlyContinue
} | Where-Object { $_.IPAddress -notmatch '^(127|169\.254|172\.(1[6-9]|2[0-9]|3[01])|100\.)\.' } | Select-Object -First 1
if (-not $lan) { throw "No LAN IPv4 address found" }
$dir = Join-Path $env:LOCALAPPDATA 'Ceviz'
New-Item -ItemType Directory -Force -Path $dir | Out-Null
$relay = Join-Path $dir 'ceviz-backend-relay.ps1'
Copy-Item (Join-Path $PSScriptRoot 'ceviz-backend-relay.ps1') $relay -Force
$ruleName = 'Watch Ceviz Backend Relay'
$firewall = "if (Get-NetFirewallRule -DisplayName '$ruleName' -ErrorAction SilentlyContinue) { Remove-NetFirewallRule -DisplayName '$ruleName' }; New-NetFirewallRule -DisplayName '$ruleName' -Direction Inbound -Action Allow -Protocol TCP -LocalAddress '$($lan.IPAddress)' -LocalPort $Port -Profile Private"
$admin = Start-Process powershell.exe -Verb RunAs -ArgumentList @('-NoProfile','-Command',$firewall) -Wait -PassThru
if ($admin.ExitCode -ne 0) { throw "Firewall approval failed" }
$taskName = 'Ceviz Backend Relay'
$args = "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$relay`" -ListenAddress $($lan.IPAddress) -ListenPort $Port -BackendPort $Port -Distro `"$Distro`""
$action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument $args
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$settings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit ([TimeSpan]::Zero) -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)
Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings -Description 'Watch Ceviz WSL2 LAN relay' -Force | Out-Null
Get-CimInstance Win32_Process -Filter "Name='powershell.exe'" | Where-Object { $_.CommandLine -like '*ceviz-backend-relay.ps1*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
& wsl.exe -d $Distro -- pkill -f Watch-Ceviz 2>$null
Start-ScheduledTask -TaskName $taskName
Start-Sleep -Seconds 2
Write-Output "CEVIZ_RELAY_URL=http://$($lan.IPAddress):$Port"
