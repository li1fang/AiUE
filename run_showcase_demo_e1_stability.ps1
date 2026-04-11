param(
    [string]$WorkspaceConfig = "C:\AiUE\local\pipeline_workspace.local.json",
    [string]$OutputRoot,
    [string]$LatestReportPath
)

$ErrorActionPreference = "Stop"
$pythonExe = Join-Path $PSScriptRoot ".venv-tooling\Scripts\python.exe"
$scriptPath = Join-Path $PSScriptRoot "workflows\pmx_pipeline\run_showcase_demo_e1_stability.py"
if (-not (Test-Path -LiteralPath $pythonExe)) {
    throw "E1 stability requires the repo tooling env python: $pythonExe"
}

$arguments = @(
    $scriptPath,
    "--workspace-config",
    $WorkspaceConfig
)
if ($OutputRoot) { $arguments += @("--output-root", $OutputRoot) }
if ($LatestReportPath) { $arguments += @("--latest-report-path", $LatestReportPath) }

& $pythonExe @arguments
exit $LASTEXITCODE
