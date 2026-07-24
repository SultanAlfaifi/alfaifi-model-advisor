[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'

$programsRoot = Join-Path $env:LOCALAPPDATA 'Programs'
$targetDirectory = Join-Path $programsRoot 'Mustakshif'
$targetCliDirectory = Join-Path $targetDirectory 'cli'
$targetFiles = @(
    (Join-Path $targetDirectory 'Mustakshif.exe'),
    (Join-Path $targetCliDirectory 'mustakshif.exe')
)
$resolvedProgramsRoot = [System.IO.Path]::GetFullPath($programsRoot).TrimEnd('\') + '\'
$resolvedTarget = [System.IO.Path]::GetFullPath($targetDirectory).TrimEnd('\') + '\'

if (-not $resolvedTarget.StartsWith($resolvedProgramsRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw 'Safety check failed: uninstall target is outside the expected Programs directory.'
}

foreach ($targetFile in $targetFiles) {
    if (Test-Path -LiteralPath $targetFile -PathType Leaf) {
        Remove-Item -LiteralPath $targetFile -Force
    }
}

$userPath = [Environment]::GetEnvironmentVariable('Path', 'User')
$pathParts = @($userPath -split ';' | Where-Object {
    $_ -and $_.Trim() -and $_.TrimEnd('\') -ine $targetCliDirectory.TrimEnd('\')
})
[Environment]::SetEnvironmentVariable('Path', ($pathParts -join ';'), 'User')

if ((Test-Path -LiteralPath $targetCliDirectory) -and -not (Get-ChildItem -LiteralPath $targetCliDirectory -Force | Select-Object -First 1)) {
    Remove-Item -LiteralPath $targetCliDirectory -Force
}
if ((Test-Path -LiteralPath $targetDirectory) -and -not (Get-ChildItem -LiteralPath $targetDirectory -Force | Select-Object -First 1)) {
    Remove-Item -LiteralPath $targetDirectory -Force
}

Write-Host 'Mustakshif was uninstalled.' -ForegroundColor Green
Write-Host 'Open a new terminal to refresh PATH.'
