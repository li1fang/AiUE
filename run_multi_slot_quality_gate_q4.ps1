param(
    [string]$WorkspaceConfig = "C:\AiUE\local\pipeline_workspace.local.json",
    [string]$P4ReportPath,
    [string]$OutputRoot,
    [string]$LatestReportPath
)

$ErrorActionPreference = "Stop"
$pythonExe = "C:\Program Files\Epic Games\UE_5.7\Engine\Binaries\ThirdParty\Python3\Win64\python.exe"
$scriptPath = Join-Path $PSScriptRoot "workflows\pmx_pipeline\run_multi_slot_quality_gate_q4.py"

$arguments = @(
    $scriptPath,
    "--workspace-config",
    $WorkspaceConfig
)
if ($P4ReportPath) { $arguments += @("--p4-report-path", $P4ReportPath) }
if ($OutputRoot) { $arguments += @("--output-root", $OutputRoot) }
if ($LatestReportPath) { $arguments += @("--latest-report-path", $LatestReportPath) }

& $pythonExe @arguments
exit $LASTEXITCODE
