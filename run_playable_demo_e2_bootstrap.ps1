param(
    [string]$WorkspaceConfig = "C:\AiUE\local\pipeline_workspace.local.json",
    [string]$E1StabilityReportPath,
    [string]$E1ReportPath,
    [string]$Q4ReportPath,
    [string]$R3ReportPath,
    [string]$D8ReportPath,
    [string]$D12ReportPath,
    [string]$D1ReportPath,
    [string]$OutputRoot,
    [string]$LatestReportPath,
    [string]$SessionOutputPath,
    [string]$LatestSessionPath
)

$ErrorActionPreference = "Stop"
$pythonExe = Join-Path $PSScriptRoot ".venv-tooling\Scripts\python.exe"
$scriptPath = Join-Path $PSScriptRoot "workflows\pmx_pipeline\run_playable_demo_e2_bootstrap.py"
if (-not (Test-Path -LiteralPath $pythonExe)) {
    throw "E2 bootstrap requires the repo tooling env python: $pythonExe"
}

$arguments = @(
    $scriptPath,
    "--workspace-config",
    $WorkspaceConfig
)
if ($E1StabilityReportPath) { $arguments += @("--e1-stability-report-path", $E1StabilityReportPath) }
if ($E1ReportPath) { $arguments += @("--e1-report-path", $E1ReportPath) }
if ($Q4ReportPath) { $arguments += @("--q4-report-path", $Q4ReportPath) }
if ($R3ReportPath) { $arguments += @("--r3-report-path", $R3ReportPath) }
if ($D8ReportPath) { $arguments += @("--d8-report-path", $D8ReportPath) }
if ($D12ReportPath) { $arguments += @("--d12-report-path", $D12ReportPath) }
if ($D1ReportPath) { $arguments += @("--d1-report-path", $D1ReportPath) }
if ($OutputRoot) { $arguments += @("--output-root", $OutputRoot) }
if ($LatestReportPath) { $arguments += @("--latest-report-path", $LatestReportPath) }
if ($SessionOutputPath) { $arguments += @("--session-output-path", $SessionOutputPath) }
if ($LatestSessionPath) { $arguments += @("--latest-session-path", $LatestSessionPath) }

& $pythonExe @arguments
exit $LASTEXITCODE
