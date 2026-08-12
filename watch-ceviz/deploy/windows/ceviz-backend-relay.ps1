param([Parameter(Mandatory=$true)][string]$ListenAddress,[int]$ListenPort=8080,[int]$BackendPort=8080,[Parameter(Mandatory=$true)][string]$Distro)
$ErrorActionPreference = "Stop"
function Start-WslKeeper {
    Start-Process wsl.exe -ArgumentList @('-d',$Distro,'--','systemd-inhibit','--what=idle','--why=Watch-Ceviz','sleep','infinity') -WindowStyle Hidden -PassThru
}
function Get-WslAddress {
    $address = ((& wsl.exe -d $Distro -e bash -lc "hostname -I | awk '{print `$1}'") | Select-Object -First 1).Trim()
    $parsed = $null
    if (-not [System.Net.IPAddress]::TryParse($address, [ref]$parsed)) { throw "Could not resolve WSL address" }
    $address
}
$keeper = Start-WslKeeper
$listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Parse($ListenAddress),$ListenPort)
$listener.Start()
try {
    while ($true) {
        if ($keeper.HasExited) { $keeper.Dispose(); $keeper = Start-WslKeeper }
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
