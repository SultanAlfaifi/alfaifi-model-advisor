[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'

$source = Join-Path $PSScriptRoot 'alfaifi.exe'
if (-not (Test-Path -LiteralPath $source -PathType Leaf)) {
    throw "alfaifi.exe was not found next to this installer."
}

$targetDirectory = Join-Path $env:LOCALAPPDATA 'Programs\AlfaifiModelAdvisor'
$targetBinary = Join-Path $targetDirectory 'alfaifi.exe'

New-Item -ItemType Directory -Path $targetDirectory -Force | Out-Null
Copy-Item -LiteralPath $source -Destination $targetBinary -Force

$userPath = [Environment]::GetEnvironmentVariable('Path', 'User')
$pathParts = @($userPath -split ';' | Where-Object { $_ -and $_.Trim() })
$alreadyPresent = $pathParts | Where-Object {
    $_.TrimEnd('\') -ieq $targetDirectory.TrimEnd('\')
}

if (-not $alreadyPresent) {
    $newUserPath = (@($pathParts) + $targetDirectory) -join ';'
    [Environment]::SetEnvironmentVariable('Path', $newUserPath, 'User')
}

if (($env:Path -split ';') -notcontains $targetDirectory) {
    $env:Path = "$targetDirectory;$env:Path"
}

Write-Host ''
Write-Host 'Alfaifi Model Advisor was installed successfully.' -ForegroundColor Green
Write-Host "Installed at: $targetBinary"
Write-Host 'Open a new terminal and run: alfaifi'
