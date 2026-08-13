param([string]$ListenAddress='auto',[int]$ListenPort=8080,[int]$BackendPort=8080,[Parameter(Mandatory=$true)][string]$Distro)
$ErrorActionPreference = "Stop"
function Start-WslKeeper {
    Start-Process wsl.exe -ArgumentList @('-d',$Distro,'--','systemd-inhibit','--what=idle','--why=Watch-Ceviz','sleep','infinity') -WindowStyle Hidden -PassThru
}
function Get-LanAddress {
    $lan = Get-NetRoute -DestinationPrefix '0.0.0.0/0' | Sort-Object RouteMetric | ForEach-Object {
        Get-NetIPAddress -InterfaceIndex $_.InterfaceIndex -AddressFamily IPv4 -ErrorAction SilentlyContinue
    } | Where-Object { $_.IPAddress -notmatch '^(127|169\.254|172\.(1[6-9]|2[0-9]|3[01])|100\.)\.' } | Select-Object -First 1
    if (-not $lan) { throw "No LAN IPv4 address found" }
    $lan.IPAddress
}
function Get-WslAddress {
    $address = ((& wsl.exe -d $Distro -e bash -lc "hostname -I | awk '{print `$1}'") | Select-Object -First 1).Trim()
    $parsed = $null
    if (-not [System.Net.IPAddress]::TryParse($address, [ref]$parsed)) { throw "Could not resolve WSL address" }
    $address
}
function Start-Listener([string]$Address) {
    $instance = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Parse($Address),$ListenPort)
    $instance.Start()
    $instance
}
function Sync-FirewallRule([string]$Address) {
    $ruleName = 'Watch Ceviz Backend Relay'
    Get-NetFirewallRule -DisplayName $ruleName -ErrorAction SilentlyContinue | Remove-NetFirewallRule
    New-NetFirewallRule -DisplayName $ruleName -Direction Inbound -Action Allow -Protocol TCP -LocalAddress $Address -LocalPort $ListenPort -Profile Private | Out-Null
}
$keeper = Start-WslKeeper
$activeAddress = if ($ListenAddress -eq 'auto') { Get-LanAddress } else { $ListenAddress }
Sync-FirewallRule $activeAddress
$listener = Start-Listener $activeAddress
$lastAddressCheck = [DateTime]::UtcNow
try {
    while ($true) {
        if ($keeper.HasExited) { $keeper.Dispose(); $keeper = Start-WslKeeper }
        if ($ListenAddress -eq 'auto' -and ([DateTime]::UtcNow - $lastAddressCheck).TotalSeconds -ge 2) {
            $lastAddressCheck = [DateTime]::UtcNow
            $currentAddress = Get-LanAddress
            if ($currentAddress -ne $activeAddress) {
                $listener.Stop()
                $activeAddress = $currentAddress
                $listener = Start-Listener $activeAddress
                Add-Content -LiteralPath (Join-Path $PSScriptRoot 'relay.log') -Value "$(Get-Date -Format o) LAN address changed to $activeAddress"
            }
        }
        if (-not $listener.Pending()) { Start-Sleep -Milliseconds 500; continue }
        $client = $listener.AcceptTcpClient()
        $backend = $null
        try {
            $backend = [System.Net.Sockets.TcpClient]::new()
            $backend.Connect((Get-WslAddress),$BackendPort)
            $front = $client.GetStream(); $back = $backend.GetStream()
            $up = $front.CopyToAsync($back); $down = $back.CopyToAsync($front)
            [System.Threading.Tasks.Task]::WaitAny(@($up,$down)) | Out-Null
        } catch {
            Add-Content -LiteralPath (Join-Path $PSScriptRoot 'relay.log') -Value "$(Get-Date -Format o) $($_.Exception.Message)"
            Start-Sleep -Milliseconds 500
        } finally {
            if ($backend) { $backend.Dispose() }; $client.Dispose()
        }
    }
} finally {
    $listener.Stop()
    if ($keeper -and -not $keeper.HasExited) { Stop-Process -Id $keeper.Id -Force -ErrorAction SilentlyContinue }
    & wsl.exe -d $Distro -- pkill -f Watch-Ceviz 2>$null
    if ($keeper) { $keeper.Dispose() }
}
