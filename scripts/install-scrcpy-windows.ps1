[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$Version = '4.1'
$ExpectedHash = '5b12172b3264b2889f4583ee64752ce832e29bc8b1089dca81093459697165db'
$Root = Split-Path -Parent $PSScriptRoot
$Tools = Join-Path $Root 'local-tools'
$Archive = Join-Path $Tools "scrcpy-win64-v$Version.zip"
$Install = Join-Path $Tools "scrcpy-win64-v$Version"
$Url = "https://github.com/Genymobile/scrcpy/releases/download/v$Version/scrcpy-win64-v$Version.zip"

New-Item -ItemType Directory -Force -Path $Tools | Out-Null
if (-not (Test-Path -LiteralPath (Join-Path $Install 'scrcpy.exe'))) {
    Invoke-WebRequest -Uri $Url -OutFile $Archive -UseBasicParsing
    $ActualHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $Archive).Hash.ToLowerInvariant()
    if ($ActualHash -ne $ExpectedHash) {
        Remove-Item -LiteralPath $Archive -Force
        throw "scrcpy archive checksum mismatch: $ActualHash"
    }
    Expand-Archive -LiteralPath $Archive -DestinationPath $Tools -Force
}

& (Join-Path $Install 'scrcpy.exe') --version
Write-Host "Installed official scrcpy v$Version in $Install"
