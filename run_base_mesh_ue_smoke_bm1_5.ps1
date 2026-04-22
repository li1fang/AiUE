param(
    [string]$WorkspaceConfig = "C:\AiUE\local\pipeline_workspace.local.json",
    [string]$Bm0ReportPath,
    [string]$Bm1ReportPath,
    [string]$OutputRoot,
    [string]$LatestReportPath
)

$ErrorActionPreference = "Stop"
$pythonExe = "C:\Program Files\Epic Games\UE_5.7\Engine\Binaries\ThirdParty\Python3\Win64\python.exe"
$scriptPath = Join-Path $PSScriptRoot "workflows\pmx_pipeline\run_base_mesh_ue_smoke_bm1_5.py"

$arguments = @(
    $scriptPath,
    "--workspace-config",
    $WorkspaceConfig
)
if ($Bm0ReportPath) { $arguments += @("--bm0-report-path", $Bm0ReportPath) }
if ($Bm1ReportPath) { $arguments += @("--bm1-report-path", $Bm1ReportPath) }
if ($OutputRoot) { $arguments += @("--output-root", $OutputRoot) }
if ($LatestReportPath) { $arguments += @("--latest-report-path", $LatestReportPath) }

& $pythonExe @arguments
exit $LASTEXITCODE
