[CmdletBinding()]
param(
    [string]$HostName = '192.168.1.138',
    [string]$UserName = 'tails',
    [int]$LocalPort = 5556,
    [int]$TestSeconds = 0
)

$ErrorActionPreference = 'Stop'
$Version = '4.1'
$Root = Split-Path -Parent $PSScriptRoot
$ScrcpyDir = Join-Path $Root "local-tools\scrcpy-win64-v$Version"
$Adb = Join-Path $ScrcpyDir 'adb.exe'
$Scrcpy = Join-Path $ScrcpyDir 'scrcpy.exe'
if (-not (Test-Path -LiteralPath $Scrcpy)) {
    & (Join-Path $PSScriptRoot 'install-scrcpy-windows.ps1')
}

$Status = & ssh.exe "$UserName@$HostName" 'waydroid status' 2>&1
if ($LASTEXITCODE -ne 0) { throw "Could not read Waydroid status: $Status" }
$Address = [regex]::Match(($Status -join "`n"), 'IP address:\s*([0-9.]+)').Groups[1].Value
if (-not $Address) { throw 'Waydroid has no usable IP address' }

$Tunnel = Start-Process -FilePath 'ssh.exe' -WindowStyle Hidden -PassThru -ArgumentList @(
    '-N', '-o', 'ExitOnForwardFailure=yes',
    '-L', "127.0.0.1:${LocalPort}:${Address}:5555",
    "$UserName@$HostName"
)
try {
    $Connected = $false
    for ($Attempt = 0; $Attempt -lt 30; $Attempt++) {
        Start-Sleep -Milliseconds 200
        if ($Tunnel.HasExited) { throw 'The SSH tunnel closed before scrcpy connected' }
        & $Adb connect "127.0.0.1:$LocalPort" 2>$null | Out-Null
        if ($LASTEXITCODE -eq 0) { $Connected = $true; break }
    }
    if (-not $Connected) { throw 'ADB did not connect through the SSH tunnel' }

    $ScrcpyArgs = @(
        "--serial=127.0.0.1:$LocalPort",
        '--no-audio',
        '--keyboard=sdk',
        '--mouse=sdk',
        '--max-fps=30',
        '--video-bit-rate=16M',
        '--no-downsize-on-error',
        '--print-fps',
        '--window-title=Azur Lane · scrcpy (direct)'
    )
    if ($TestSeconds -gt 0) {
        $Sample = Join-Path $Root 'local-tools\direct-scrcpy-sample.mkv'
        Remove-Item -LiteralPath $Sample -Force -ErrorAction SilentlyContinue
        $ScrcpyArgs += @("--time-limit=$TestSeconds", "--record=$Sample")
        & $Scrcpy @ScrcpyArgs
        if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $Sample)) {
            throw "Direct scrcpy failed to save a $TestSeconds-second sample"
        }
        Write-Host "Recorded direct sample: $Sample"
    }
    else {
        & $Scrcpy @ScrcpyArgs
    }
}
finally {
    & $Adb disconnect "127.0.0.1:$LocalPort" 2>$null | Out-Null
    if (-not $Tunnel.HasExited) { Stop-Process -Id $Tunnel.Id -Force }
}
