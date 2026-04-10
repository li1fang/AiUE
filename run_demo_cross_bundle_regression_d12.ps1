param(
    [string]$WorkspaceConfig = "C:\AiUE\local\pipeline_workspace.local.json",
    [string]$D1ReportPath,
    [string]$PrimaryPackageId,
    [string]$SecondaryPackageId,
    [string]$AnimationAssetPath = "/Game/CombatMagicAnims/Demo/Mannequins/Anims/Unarmed/Attack/MM_Attack_01",
    [string]$OutputRoot,
    [string]$LatestReportPath
)

$ErrorActionPreference = "Stop"
$pythonExe = "C:\Program Files\Epic Games\UE_5.7\Engine\Binaries\ThirdParty\Python3\Win64\python.exe"
$scriptPath = Join-Path $PSScriptRoot "workflows\pmx_pipeline\run_demo_cross_bundle_regression_d12.py"

$arguments = @(
    $scriptPath,
    "--workspace-config",
    $WorkspaceConfig,
    "--animation-asset-path",
    $AnimationAssetPath
)
if ($D1ReportPath) { $arguments += @("--d1-report-path", $D1ReportPath) }
if ($PrimaryPackageId) { $arguments += @("--primary-package-id", $PrimaryPackageId) }
if ($SecondaryPackageId) { $arguments += @("--secondary-package-id", $SecondaryPackageId) }
if ($OutputRoot) { $arguments += @("--output-root", $OutputRoot) }
if ($LatestReportPath) { $arguments += @("--latest-report-path", $LatestReportPath) }

& $pythonExe @arguments
exit $LASTEXITCODE
