[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'

$sourceDesktop = Join-Path $PSScriptRoot 'Mustakshif.exe'
$sourceCliDirectory = Join-Path $PSScriptRoot 'cli'
$sourceCli = Join-Path $sourceCliDirectory 'mustakshif.exe'
if (-not (Test-Path -LiteralPath $sourceDesktop -PathType Leaf)) {
    throw "Mustakshif.exe was not found next to this installer."
}
if (-not (Test-Path -LiteralPath $sourceCli -PathType Leaf)) {
    throw "cli\mustakshif.exe was not found next to this installer."
}

$targetDirectory = Join-Path $env:LOCALAPPDATA 'Programs\Mustakshif'
$targetCliDirectory = Join-Path $targetDirectory 'cli'
$targetDesktop = Join-Path $targetDirectory 'Mustakshif.exe'
$targetCli = Join-Path $targetCliDirectory 'mustakshif.exe'

New-Item -ItemType Directory -Path $targetDirectory -Force | Out-Null
New-Item -ItemType Directory -Path $targetCliDirectory -Force | Out-Null
Copy-Item -LiteralPath $sourceDesktop -Destination $targetDesktop -Force
Copy-Item -LiteralPath (Join-Path $sourceCliDirectory 'mustakshif.exe') -Destination $targetCli -Force

$userPath = [Environment]::GetEnvironmentVariable('Path', 'User')
$pathParts = @($userPath -split ';' | Where-Object { $_ -and $_.Trim() })
$alreadyPresent = $pathParts | Where-Object {
    $_.TrimEnd('\') -ieq $targetCliDirectory.TrimEnd('\')
}

if (-not $alreadyPresent) {
    $newUserPath = (@($pathParts) + $targetCliDirectory) -join ';'
    [Environment]::SetEnvironmentVariable('Path', $newUserPath, 'User')
}

if (($env:Path -split ';') -notcontains $targetCliDirectory) {
    $env:Path = "$targetCliDirectory;$env:Path"
}

Write-Host ''
Write-Host 'Mustakshif was installed successfully.' -ForegroundColor Green
Write-Host "Desktop app: $targetDesktop"
Write-Host "CLI: $targetCli"
Write-Host 'Open a new terminal and run: mustakshif'
