param(
    [string]$WorkspaceConfig = "C:\AiUE\local\pipeline_workspace.local.json",
    [string]$D12ReportPath,
    [string]$D11ReportPath,
    [string]$Q1ReportPath,
    [string]$OutputRoot,
    [string]$LatestReportPath
)

$ErrorActionPreference = "Stop"
$pythonExe = "C:\Program Files\Epic Games\UE_5.7\Engine\Binaries\ThirdParty\Python3\Win64\python.exe"
$scriptPath = Join-Path $PSScriptRoot "workflows\pmx_pipeline\run_demo_composition_quality_gate_q2.py"

$arguments = @(
    $scriptPath,
    "--workspace-config",
    $WorkspaceConfig
)
if ($D12ReportPath) { $arguments += @("--d12-report-path", $D12ReportPath) }
if ($D11ReportPath) { $arguments += @("--d11-report-path", $D11ReportPath) }
if ($Q1ReportPath) { $arguments += @("--q1-report-path", $Q1ReportPath) }
if ($OutputRoot) { $arguments += @("--output-root", $OutputRoot) }
if ($LatestReportPath) { $arguments += @("--latest-report-path", $LatestReportPath) }

& $pythonExe @arguments
exit $LASTEXITCODE
