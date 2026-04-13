param(
    [string]$WorkspaceConfig = "C:\AiUE\local\pipeline_workspace.toyyard.motion.trial-m2-diversity.local.json",
    [string]$SourceReport,
    [string]$OutputRoot,
    [string]$StateRoot,
    [string]$LatestReportPath,
    [string]$TargetPackageId
)

$ErrorActionPreference = "Stop"
$pythonExe = "C:\Program Files\Epic Games\UE_5.7\Engine\Binaries\ThirdParty\Python3\Win64\python.exe"
$scriptPath = Join-Path $PSScriptRoot "workflows\pmx_pipeline\run_motion_default_source_switch_m3_5.py"

$arguments = @(
    $scriptPath,
    "--workspace-config",
    $WorkspaceConfig
)
if ($SourceReport) { $arguments += @("--source-report", $SourceReport) }
if ($OutputRoot) { $arguments += @("--output-root", $OutputRoot) }
if ($StateRoot) { $arguments += @("--state-root", $StateRoot) }
if ($LatestReportPath) { $arguments += @("--latest-report-path", $LatestReportPath) }
if ($TargetPackageId) { $arguments += @("--target-package-id", $TargetPackageId) }

& $pythonExe @arguments
exit $LASTEXITCODE
