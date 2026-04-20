param(
    [string]$WorkspaceConfig = "C:\AiUE\local\pipeline_workspace.local.json",
    [string]$SummaryPath,
    [string]$SoloSummaryPath,
    [string]$BundleSummaryPath,
    [string]$RegistryPath,
    [string]$BundleRegistryPath,
    [string]$SoloWorkspaceConfig,
    [string]$BundleWorkspaceConfig,
    [string]$OutputRoot,
    [string]$LatestReportPath
)

$ErrorActionPreference = "Stop"
$pythonExe = "C:\Program Files\Epic Games\UE_5.7\Engine\Binaries\ThirdParty\Python3\Win64\python.exe"
$scriptPath = Join-Path $PSScriptRoot "workflows\pmx_pipeline\run_toy_yard_default_source_t2.py"

$arguments = @(
    $scriptPath,
    "--workspace-config",
    $WorkspaceConfig
)
if ($SummaryPath) { $arguments += @("--summary-path", $SummaryPath) }
if ($SoloSummaryPath) { $arguments += @("--solo-summary-path", $SoloSummaryPath) }
if ($BundleSummaryPath) { $arguments += @("--bundle-summary-path", $BundleSummaryPath) }
if ($RegistryPath) { $arguments += @("--registry-path", $RegistryPath) }
if ($BundleRegistryPath) { $arguments += @("--bundle-registry-path", $BundleRegistryPath) }
if ($SoloWorkspaceConfig) { $arguments += @("--solo-workspace-config", $SoloWorkspaceConfig) }
if ($BundleWorkspaceConfig) { $arguments += @("--bundle-workspace-config", $BundleWorkspaceConfig) }
if ($OutputRoot) { $arguments += @("--output-root", $OutputRoot) }
if ($LatestReportPath) { $arguments += @("--latest-report-path", $LatestReportPath) }

& $pythonExe @arguments
exit $LASTEXITCODE
