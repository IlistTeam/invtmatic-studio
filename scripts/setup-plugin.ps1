param(
    [Parameter(Mandatory = $true)][string]$Workspace,
    [string]$StudioExe,
    [string]$StudioProfile
)
$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path -Parent $PSScriptRoot
if (-not [IO.Path]::IsPathRooted($Workspace)) { throw 'Workspace must be absolute.' }
$taskWorkspace = [IO.Path]::GetFullPath($Workspace).TrimEnd('\')
$taskPackage = [IO.Path]::GetFullPath($taskRoot).TrimEnd('\')
if ($taskWorkspace -eq $taskPackage -or $taskWorkspace.StartsWith($taskPackage + '\', [StringComparison]::OrdinalIgnoreCase)) {
    throw 'Choose a workspace outside the plugin cache.'
}
if ($StudioExe -and -not (Test-Path -LiteralPath $StudioExe -PathType Leaf)) { throw 'StudioExe does not exist.' }
if (-not $env:LOCALAPPDATA) { throw 'LOCALAPPDATA is required.' }
$null = Get-Command node -CommandType Application -ErrorAction Stop
$taskNpm = (Get-Command npm.cmd -CommandType Application -ErrorAction Stop).Source
Push-Location (Join-Path $taskRoot 'mcp')
try {
    & $taskNpm ci --ignore-scripts
    if ($LASTEXITCODE -ne 0) { throw 'npm ci failed.' }
    & $taskNpm run build
    if ($LASTEXITCODE -ne 0) { throw 'MCP build failed.' }
} finally { Pop-Location }
New-Item -ItemType Directory -Path $taskWorkspace -Force | Out-Null
$taskConfigDirectory = Join-Path $env:LOCALAPPDATA 'IlistTeam\invtmatic-studio'
New-Item -ItemType Directory -Path $taskConfigDirectory -Force | Out-Null
$taskSettings = @{ workspace = (Resolve-Path -LiteralPath $taskWorkspace).Path }
if ($StudioExe) { $taskSettings.studio_exe = (Resolve-Path -LiteralPath $StudioExe).Path }
if ($StudioProfile) { $taskSettings.studio_profile = $StudioProfile }
$taskConfig = Join-Path $taskConfigDirectory 'config.json'
[IO.File]::WriteAllText($taskConfig, ($taskSettings | ConvertTo-Json), (New-Object Text.UTF8Encoding($false)))
Write-Output "Configured $taskConfig. Reconnect MCP; Studio and physical PLC operations were not started."
