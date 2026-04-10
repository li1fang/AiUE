param(
    [string]$WorkspaceConfig = "C:\AiUE\local\pipeline_workspace.local.json",
    [string]$D1ReportPath,
    [string]$OutputRoot,
    [string]$LatestReportPath,
    [string]$ClothingAssetPath = "/Game/Characters/Echo/Meshes/SKM_Echo_Hair.SKM_Echo_Hair",
    [string]$ClothingSlotName = "clothing",
    [string]$AttachSocketName = "Head",
    [double]$TrackedClothingMinCoverage = 0.001
)

$ErrorActionPreference = "Stop"
$pythonExe = "C:\Program Files\Epic Games\UE_5.7\Engine\Binaries\ThirdParty\Python3\Win64\python.exe"
$scriptPath = Join-Path $PSScriptRoot "workflows\pmx_pipeline\run_clothing_vertical_slice_p2.py"

$arguments = @(
    $scriptPath,
    "--workspace-config",
    $WorkspaceConfig,
    "--clothing-asset-path",
    $ClothingAssetPath,
    "--clothing-slot-name",
    $ClothingSlotName,
    "--attach-socket-name",
    $AttachSocketName,
    "--tracked-clothing-min-coverage",
    "$TrackedClothingMinCoverage"
)
if ($D1ReportPath) { $arguments += @("--d1-report-path", $D1ReportPath) }
if ($OutputRoot) { $arguments += @("--output-root", $OutputRoot) }
if ($LatestReportPath) { $arguments += @("--latest-report-path", $LatestReportPath) }

& $pythonExe @arguments
exit $LASTEXITCODE
