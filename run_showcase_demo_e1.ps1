param(
    [string]$WorkspaceConfig = "C:\AiUE\local\pipeline_workspace.local.json",
    [string]$Q4ReportPath,
    [string]$R3ReportPath,
    [string]$D8ReportPath,
    [string]$D12ReportPath,
    [string]$OutputRoot,
    [string]$LatestReportPath
)

$ErrorActionPreference = "Stop"
$pythonExe = Join-Path $PSScriptRoot ".venv-tooling\Scripts\python.exe"
$scriptPath = Join-Path $PSScriptRoot "workflows\pmx_pipeline\run_showcase_demo_e1.py"
if (-not (Test-Path -LiteralPath $pythonExe)) {
    throw "E1 requires the repo tooling env python: $pythonExe"
}

$arguments = @(
    $scriptPath,
    "--workspace-config",
    $WorkspaceConfig
)
if ($Q4ReportPath) { $arguments += @("--q4-report-path", $Q4ReportPath) }
if ($R3ReportPath) { $arguments += @("--r3-report-path", $R3ReportPath) }
if ($D8ReportPath) { $arguments += @("--d8-report-path", $D8ReportPath) }
if ($D12ReportPath) { $arguments += @("--d12-report-path", $D12ReportPath) }
if ($OutputRoot) { $arguments += @("--output-root", $OutputRoot) }
if ($LatestReportPath) { $arguments += @("--latest-report-path", $LatestReportPath) }

& $pythonExe @arguments
exit $LASTEXITCODE
