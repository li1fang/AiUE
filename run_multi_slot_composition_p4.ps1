param(
    [string]$WorkspaceConfig = "C:\AiUE\local\pipeline_workspace.local.json",
    [string]$D1ReportPath,
    [string]$OutputRoot,
    [string]$LatestReportPath,
    [string]$ClothingAssetPath = "/Game/Characters/Echo/Meshes/SKM_Echo_Hair.SKM_Echo_Hair",
    [string]$ClothingSlotName = "clothing",
    [string]$ClothingAttachSocketName = "Head",
    [double]$TrackedClothingMinCoverage = 0.001,
    [string]$FxAssetPath = "/Game/Levels/LevelPrototyping/Meshes/SM_Cylinder.SM_Cylinder",
    [string]$FxSlotName = "fx",
    [string]$FxAttachSocketName = "WeaponSocket",
    [double]$TrackedFxMinCoverage = 0.001
)

$ErrorActionPreference = "Stop"
$pythonExe = "C:\Program Files\Epic Games\UE_5.7\Engine\Binaries\ThirdParty\Python3\Win64\python.exe"
$scriptPath = Join-Path $PSScriptRoot "workflows\pmx_pipeline\run_multi_slot_composition_p4.py"

$arguments = @(
    $scriptPath,
    "--workspace-config",
    $WorkspaceConfig,
    "--clothing-asset-path",
    $ClothingAssetPath,
    "--clothing-slot-name",
    $ClothingSlotName,
    "--clothing-attach-socket-name",
    $ClothingAttachSocketName,
    "--tracked-clothing-min-coverage",
    "$TrackedClothingMinCoverage",
    "--fx-asset-path",
    $FxAssetPath,
    "--fx-slot-name",
    $FxSlotName,
    "--fx-attach-socket-name",
    $FxAttachSocketName,
    "--tracked-fx-min-coverage",
    "$TrackedFxMinCoverage"
)
if ($D1ReportPath) { $arguments += @("--d1-report-path", $D1ReportPath) }
if ($OutputRoot) { $arguments += @("--output-root", $OutputRoot) }
if ($LatestReportPath) { $arguments += @("--latest-report-path", $LatestReportPath) }

& $pythonExe @arguments
exit $LASTEXITCODE
