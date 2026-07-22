[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'

$programsRoot = Join-Path $env:LOCALAPPDATA 'Programs'
$targetDirectory = Join-Path $programsRoot 'AlfaifiModelAdvisor'
$targetBinary = Join-Path $targetDirectory 'alfaifi.exe'
$resolvedProgramsRoot = [System.IO.Path]::GetFullPath($programsRoot).TrimEnd('\') + '\'
$resolvedTarget = [System.IO.Path]::GetFullPath($targetDirectory).TrimEnd('\') + '\'

if (-not $resolvedTarget.StartsWith($resolvedProgramsRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw 'Safety check failed: uninstall target is outside the expected Programs directory.'
}

if (Test-Path -LiteralPath $targetBinary -PathType Leaf) {
    Remove-Item -LiteralPath $targetBinary -Force
}

$userPath = [Environment]::GetEnvironmentVariable('Path', 'User')
$pathParts = @($userPath -split ';' | Where-Object {
    $_ -and $_.Trim() -and $_.TrimEnd('\') -ine $targetDirectory.TrimEnd('\')
})
[Environment]::SetEnvironmentVariable('Path', ($pathParts -join ';'), 'User')

if ((Test-Path -LiteralPath $targetDirectory) -and -not (Get-ChildItem -LiteralPath $targetDirectory -Force | Select-Object -First 1)) {
    Remove-Item -LiteralPath $targetDirectory -Force
}

Write-Host 'Alfaifi Model Advisor was uninstalled.' -ForegroundColor Green
Write-Host 'Open a new terminal to refresh PATH.'
