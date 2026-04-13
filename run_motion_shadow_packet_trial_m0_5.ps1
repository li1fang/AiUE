param(
    [string]$WorkspaceConfig = "C:\AiUE\local\pipeline_workspace.toyyard.motion.trial-turn-hand-ready.local.json",
    [string]$SummaryPath,
    [string]$RegistryPath,
    [string]$PacketCheckPath,
    [string]$OutputRoot,
    [string]$StateRoot,
    [string]$LatestReportPath,
    [string]$TargetPackageId
)

$ErrorActionPreference = "Stop"
$pythonExe = "C:\Program Files\Epic Games\UE_5.7\Engine\Binaries\ThirdParty\Python3\Win64\python.exe"
$scriptPath = Join-Path $PSScriptRoot "workflows\pmx_pipeline\run_motion_shadow_packet_trial_m0_5.py"

$arguments = @(
    $scriptPath,
    "--workspace-config",
    $WorkspaceConfig
)
if ($SummaryPath) { $arguments += @("--summary-path", $SummaryPath) }
if ($RegistryPath) { $arguments += @("--registry-path", $RegistryPath) }
if ($PacketCheckPath) { $arguments += @("--packet-check-path", $PacketCheckPath) }
if ($OutputRoot) { $arguments += @("--output-root", $OutputRoot) }
if ($StateRoot) { $arguments += @("--state-root", $StateRoot) }
if ($LatestReportPath) { $arguments += @("--latest-report-path", $LatestReportPath) }
if ($TargetPackageId) { $arguments += @("--target-package-id", $TargetPackageId) }

& $pythonExe @arguments
exit $LASTEXITCODE
