param(
    [string]$WorkspaceConfig = "C:\AiUE\local\pipeline_workspace.local.json",
    [string]$D1ReportPath,
    [string]$OutputRoot,
    [string]$LatestReportPath,
    [string]$FxAssetPath = "/Niagara/DefaultAssets/Templates/Systems/FountainLightweight.FountainLightweight",
    [string]$FxSlotName = "fx",
    [string]$AttachSocketName = "WeaponSocket",
    [double]$TrackedFxMinCoverage = 0.0001
)

$ErrorActionPreference = "Stop"
$pythonExe = "C:\Program Files\Epic Games\UE_5.7\Engine\Binaries\ThirdParty\Python3\Win64\python.exe"
$scriptPath = Join-Path $PSScriptRoot "workflows\pmx_pipeline\run_real_fx_item_kind_r2.py"

$arguments = @(
    $scriptPath,
    "--workspace-config",
    $WorkspaceConfig,
    "--fx-asset-path",
    $FxAssetPath,
    "--fx-slot-name",
    $FxSlotName,
    "--attach-socket-name",
    $AttachSocketName,
    "--tracked-fx-min-coverage",
    $TrackedFxMinCoverage
)
if ($D1ReportPath) { $arguments += @("--d1-report-path", $D1ReportPath) }
if ($OutputRoot) { $arguments += @("--output-root", $OutputRoot) }
if ($LatestReportPath) { $arguments += @("--latest-report-path", $LatestReportPath) }

& $pythonExe @arguments
exit $LASTEXITCODE
