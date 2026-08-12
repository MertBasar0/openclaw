param([Parameter(Mandatory=$true)][string]$ListenAddress,[int]$ListenPort=8080,[int]$BackendPort=8080)
$ErrorActionPreference = "Stop"
function Get-WslAddress {
    $address = ((& wsl.exe -e bash -lc "hostname -I | awk '{print `$1}'") | Select-Object -First 1).Trim()
    $parsed = $null
    if (-not [System.Net.IPAddress]::TryParse($address, [ref]$parsed)) { throw "Could not resolve WSL address" }
    $address
}
$listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Parse($ListenAddress),$ListenPort)
$listener.Start()
try {
    while ($true) {
        $client = $listener.AcceptTcpClient()
        $backend = $null
        try {
            $backend = [System.Net.Sockets.TcpClient]::new()
            $backend.Connect((Get-WslAddress),$BackendPort)
            $front = $client.GetStream(); $back = $backend.GetStream()
            $up = $front.CopyToAsync($back); $down = $back.CopyToAsync($front)
            [System.Threading.Tasks.Task]::WaitAny(@($up,$down)) | Out-Null
        } catch { Write-Error $_ } finally {
            if ($backend) { $backend.Dispose() }; $client.Dispose()
        }
    }
} finally { $listener.Stop() }
