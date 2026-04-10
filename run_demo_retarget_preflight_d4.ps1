param(
    [string]$WorkspaceConfig = "C:\AiUE\local\pipeline_workspace.local.json",
    [string]$D1ReportPath,
    [string]$D3ReportPath,
    [string]$PackageId,
    [string]$AnimationAssetPath,
    [string]$OutputRoot,
    [string]$LatestReportPath
)

$ErrorActionPreference = "Stop"
$pythonExe = "C:\Program Files\Epic Games\UE_5.7\Engine\Binaries\ThirdParty\Python3\Win64\python.exe"
$scriptPath = Join-Path $PSScriptRoot "workflows\pmx_pipeline\run_demo_retarget_preflight_d4.py"

$arguments = @(
    $scriptPath,
    "--workspace-config",
    $WorkspaceConfig
)
if ($D1ReportPath) { $arguments += @("--d1-report-path", $D1ReportPath) }
if ($D3ReportPath) { $arguments += @("--d3-report-path", $D3ReportPath) }
if ($PackageId) { $arguments += @("--package-id", $PackageId) }
if ($AnimationAssetPath) { $arguments += @("--animation-asset-path", $AnimationAssetPath) }
if ($OutputRoot) { $arguments += @("--output-root", $OutputRoot) }
if ($LatestReportPath) { $arguments += @("--latest-report-path", $LatestReportPath) }

& $pythonExe @arguments
exit $LASTEXITCODE
