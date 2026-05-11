param(
    [Parameter(Mandatory = $true)]
    [string]$RequestPath
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$workspaceRootLinux = '/home/mertb/.openclaw/workspace'
$blenderPocRootLinux = "$workspaceRootLinux/blender-bonsai-poc"
$bridgeOutRootLinux = "$blenderPocRootLinux/out/bridge"
$handlerScriptLinux = "$blenderPocRootLinux/scripts/handle_blender_bonsai_request.py"

function Test-IsWslPowerShell {
    return [bool]$env:WSL_DISTRO_NAME
}

function Get-WslDistroName {
    if ($env:WSL_DISTRO_NAME) {
        return $env:WSL_DISTRO_NAME
    }

    $distro = (& wsl.exe sh -lc 'printf %s "$WSL_DISTRO_NAME"' 2>$null)
    if ($LASTEXITCODE -ne 0 -or -not $distro) {
        throw 'Unable to determine the WSL distro name for Blender+Bonsai bridge execution.'
    }
    return ($distro | Out-String).Trim()
}

function Convert-LinuxPathToHostPath {
    param([Parameter(Mandatory = $true)][string]$LinuxPath)

    if (Test-IsWslPowerShell) {
        return $LinuxPath
    }

    $trimmed = $LinuxPath.TrimStart('/')
    $segments = @()
    if ($trimmed) {
        $segments = $trimmed -split '/'
    }

    $distro = Get-WslDistroName
    $base = "\\wsl.localhost\$distro"
    if ($segments.Count -eq 0) {
        return $base
    }
    return $base + '\' + ($segments -join '\')
}

function New-DirIfMissing {
    param([Parameter(Mandatory = $true)][string]$Path)

    if (-not (Test-Path -LiteralPath $Path)) {
        New-Item -ItemType Directory -Path $Path -Force | Out-Null
    }
}

function Copy-JsonObject {
    param([Parameter(Mandatory = $false)][object]$InputObject)

    if ($null -eq $InputObject) {
        return @{}
    }

    $clone = [ordered]@{}
    foreach ($property in $InputObject.PSObject.Properties) {
        $clone[$property.Name] = $property.Value
    }
    return $clone
}

function Get-JsonProperty {
    param(
        [Parameter(Mandatory = $false)][object]$InputObject,
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $false)][object]$Default = $null
    )

    if ($null -eq $InputObject) {
        return $Default
    }

    if ($InputObject -is [System.Collections.IDictionary]) {
        if ($InputObject.Contains($Name)) {
            return $InputObject[$Name]
        }
        return $Default
    }

    $property = $InputObject.PSObject.Properties[$Name]
    if ($null -eq $property) {
        return $Default
    }
    return $property.Value
}

function Write-JsonUtf8NoBom {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][object]$Data
    )

    $directory = Split-Path -Parent $Path
    if ($directory) {
        New-DirIfMissing -Path $directory
    }

    $json = $Data | ConvertTo-Json -Depth 20
    $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($Path, $json + [Environment]::NewLine, $utf8NoBom)
}

function Read-JsonObject {
    param([Parameter(Mandatory = $true)][string]$Path)

    return (Get-Content -LiteralPath $Path -Raw | ConvertFrom-Json -Depth 20)
}

function Build-BlenderEnvelope {
    param(
        [Parameter(Mandatory = $true)][object]$BridgeRequest,
        [Parameter(Mandatory = $true)][object]$Payload,
        [Parameter(Mandatory = $true)][string]$ResponsePathLinux
    )

    $payloadFields = $Payload
    $envelopeSource = 'merged-fields'
    if ((Get-JsonProperty -InputObject $Payload -Name 'kind') -eq 'blender-bonsai-request') {
        $envelopeSource = 'full-envelope'
    }

    $envelope = Copy-JsonObject -InputObject $payloadFields
    $envelope.kind = 'blender-bonsai-request'
    if (-not (Get-JsonProperty -InputObject $envelope -Name 'contractVersion')) {
        $envelope.contractVersion = '0.1.0'
    }
    if (-not (Get-JsonProperty -InputObject $envelope -Name 'requestId')) {
        $envelope.requestId = [string](Get-JsonProperty -InputObject $BridgeRequest -Name 'requestId')
    }
    if (-not (Get-JsonProperty -InputObject $envelope -Name 'sourceKind')) {
        $envelope.sourceKind = 'windows-bridge-bootstrap'
    }
    if (-not (Get-JsonProperty -InputObject $envelope -Name 'action')) {
        throw 'Blender+Bonsai payload must provide action or a full blender-bonsai-request envelope.'
    }

    $readOnly = Get-JsonProperty -InputObject $envelope -Name 'readOnly'
    if ($null -eq $readOnly) {
        $envelope.readOnly = $true
    }
    elseif (-not [bool]$readOnly) {
        throw 'Blender+Bonsai bridge only supports readOnly=true payloads.'
    }

    $artifacts = Copy-JsonObject -InputObject (Get-JsonProperty -InputObject $envelope -Name 'artifacts')
    if (-not (Get-JsonProperty -InputObject $artifacts -Name 'responsePath')) {
        $artifacts.responsePath = $ResponsePathLinux
    }
    $envelope.artifacts = $artifacts

    return [ordered]@{
        envelope = $envelope
        envelopeSource = $envelopeSource
    }
}

function Invoke-BlenderHandler {
    param(
        [Parameter(Mandatory = $true)][string]$RequestEnvelopeLinux,
        [Parameter(Mandatory = $true)][string]$ResponseEnvelopeLinux
    )

    if (Test-IsWslPowerShell) {
        $stdout = & python3 $handlerScriptLinux --request $RequestEnvelopeLinux --response $ResponseEnvelopeLinux 2>&1
    }
    else {
        $stdout = & wsl.exe python3 $handlerScriptLinux --request $RequestEnvelopeLinux --response $ResponseEnvelopeLinux 2>&1
    }

    $lines = @($stdout | ForEach-Object { "$_" })
    $exitCode = $LASTEXITCODE
    return [ordered]@{
        exitCode = $exitCode
        stdoutLines = $lines
    }
}

$bridgeRequest = Read-JsonObject -Path $RequestPath
if (-not $bridgeRequest.requestId) {
    throw "Bridge request is missing requestId: $RequestPath"
}
if (-not $bridgeRequest.payload) {
    throw "Bridge request is missing payload: $RequestPath"
}

$requestId = [string]$bridgeRequest.requestId
$requestEnvelopeLinux = "$bridgeOutRootLinux/$requestId.request.json"
$responseEnvelopeLinux = "$bridgeOutRootLinux/$requestId.result.json"
$requestEnvelopeHost = Convert-LinuxPathToHostPath -LinuxPath $requestEnvelopeLinux
$responseEnvelopeHost = Convert-LinuxPathToHostPath -LinuxPath $responseEnvelopeLinux

$built = Build-BlenderEnvelope -BridgeRequest $bridgeRequest -Payload $bridgeRequest.payload -ResponsePathLinux $responseEnvelopeLinux
$requestEnvelope = $built.envelope
Write-JsonUtf8NoBom -Path $requestEnvelopeHost -Data $requestEnvelope

$invokeResult = Invoke-BlenderHandler -RequestEnvelopeLinux $requestEnvelopeLinux -ResponseEnvelopeLinux $responseEnvelopeLinux
if ($invokeResult.exitCode -ne 0) {
    $response = $null
    if (Test-Path -LiteralPath $responseEnvelopeHost) {
        $response = Read-JsonObject -Path $responseEnvelopeHost
    }

    throw ('Blender+Bonsai handler failed with exit code {0}. Response: {1}. Output: {2}' -f
        $invokeResult.exitCode,
        (($response | ConvertTo-Json -Depth 20 -Compress) ?? 'null'),
        (($invokeResult.stdoutLines -join "`n").Trim()))
}

if (-not (Test-Path -LiteralPath $responseEnvelopeHost)) {
    throw "Blender+Bonsai handler did not produce response envelope: $responseEnvelopeLinux"
}

$responseEnvelope = Read-JsonObject -Path $responseEnvelopeHost

return [ordered]@{
    handler = 'blender-bonsai-action'
    bridgeRequestId = $requestId
    envelopeSource = [string]$built.envelopeSource
    requestEnvelopePath = $requestEnvelopeLinux
    responseEnvelopePath = $responseEnvelopeLinux
    action = [string]$requestEnvelope.action
    readOnly = [bool]$requestEnvelope.readOnly
    execution = [ordered]@{
        mode = if (Test-IsWslPowerShell) { 'wsl-pwsh-direct-python3' } else { 'windows-pwsh-via-wsl-python3' }
        commandExitCode = [int]$invokeResult.exitCode
    }
    response = $responseEnvelope
    handlerStdoutLines = $invokeResult.stdoutLines
}
