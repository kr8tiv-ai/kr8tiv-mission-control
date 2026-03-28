param(
  [Parameter(Mandatory = $true)][string]$SourceDir,
  [Parameter(Mandatory = $true)][string]$OutFile
)

$ErrorActionPreference = 'Stop'

if (!(Test-Path $SourceDir)) {
  throw "SourceDir not found: $SourceDir"
}

$parent = Split-Path -Parent $OutFile
if ($parent -and !(Test-Path $parent)) {
  New-Item -ItemType Directory -Force -Path $parent | Out-Null
}

if (Test-Path $OutFile) {
  Remove-Item -Force $OutFile
}

Compress-Archive -Path (Join-Path $SourceDir '*') -DestinationPath $OutFile
Write-Output "BOOT_BUNDLE_CREATED: $OutFile"
