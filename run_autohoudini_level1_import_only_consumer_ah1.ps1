param(
    [string]$WorkspaceConfig,
    [string]$RequestJson = "",
    [string]$OutputRoot = "",
    [string]$LatestReportPath = ""
)

$ErrorActionPreference = "Stop"
$repoRoot = [System.IO.Path]::GetFullPath($PSScriptRoot)
$venvPython = Join-Path $repoRoot ".venv-tooling\Scripts\python.exe"
$pythonExe = if (Test-Path -LiteralPath $venvPython) { $venvPython } else { "python3.12.exe" }
$scriptPath = Join-Path $repoRoot "workflows\pmx_pipeline\run_autohoudini_level1_import_only_consumer_ah1.py"

$arguments = @(
    $scriptPath,
    "--workspace-config", $WorkspaceConfig
)
if ($RequestJson) { $arguments += @("--request-json", $RequestJson) }
if ($OutputRoot) { $arguments += @("--output-root", $OutputRoot) }
if ($LatestReportPath) { $arguments += @("--latest-report-path", $LatestReportPath) }

& $pythonExe @arguments
exit $LASTEXITCODE
