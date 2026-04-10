param(
    [string]$WorkspaceConfig = "C:\AiUE\local\pipeline_workspace.local.json",
    [string]$D4ReportPath,
    [string]$PackageId,
    [string]$AnimationAssetPath,
    [string]$TargetIkRigAssetPath,
    [string]$OutputRoot,
    [string]$LatestReportPath
)

$ErrorActionPreference = "Stop"
$pythonExe = "C:\Program Files\Epic Games\UE_5.7\Engine\Binaries\ThirdParty\Python3\Win64\python.exe"
$scriptPath = Join-Path $PSScriptRoot "workflows\pmx_pipeline\run_demo_retarget_bootstrap_d5.py"

$arguments = @(
    $scriptPath,
    "--workspace-config",
    $WorkspaceConfig
)
if ($D4ReportPath) { $arguments += @("--d4-report-path", $D4ReportPath) }
if ($PackageId) { $arguments += @("--package-id", $PackageId) }
if ($AnimationAssetPath) { $arguments += @("--animation-asset-path", $AnimationAssetPath) }
if ($TargetIkRigAssetPath) { $arguments += @("--target-ik-rig-asset-path", $TargetIkRigAssetPath) }
if ($OutputRoot) { $arguments += @("--output-root", $OutputRoot) }
if ($LatestReportPath) { $arguments += @("--latest-report-path", $LatestReportPath) }

& $pythonExe @arguments
exit $LASTEXITCODE
