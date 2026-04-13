param(
    [string]$WorkspaceConfig = "C:\AiUE\local\pipeline_workspace.toyyard.motion.trial-turn-hand-ready.local.json",
    [string]$SummaryPath,
    [string]$RegistryPath,
    [string]$OutputRoot,
    [string]$LatestReportPath
)

$ErrorActionPreference = "Stop"
$pythonExe = "C:\Program Files\Epic Games\UE_5.7\Engine\Binaries\ThirdParty\Python3\Win64\python.exe"
$scriptPath = Join-Path $PSScriptRoot "workflows\pmx_pipeline\run_motion_fixture_diversity_readiness_m2.py"

$arguments = @(
    $scriptPath,
    "--workspace-config",
    $WorkspaceConfig
)
if ($SummaryPath) { $arguments += @("--summary-path", $SummaryPath) }
if ($RegistryPath) { $arguments += @("--registry-path", $RegistryPath) }
if ($OutputRoot) { $arguments += @("--output-root", $OutputRoot) }
if ($LatestReportPath) { $arguments += @("--latest-report-path", $LatestReportPath) }

& $pythonExe @arguments
exit $LASTEXITCODE
