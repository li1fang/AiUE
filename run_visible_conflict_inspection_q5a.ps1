param(
    [string]$WorkspaceConfig = "C:\AiUE\local\pipeline_workspace.local.json",
    [string]$P2ReportPath,
    [string]$OutputRoot,
    [string]$LatestReportPath,
    [string]$LevelPath = "/Game/Levels/DefaultLevel",
    [string]$ClothingAssetPath = "/Game/Characters/Echo/Meshes/SKM_Echo_Hair.SKM_Echo_Hair",
    [string]$SlotName = "clothing",
    [string]$AttachSocketName = "Head"
)

$ErrorActionPreference = "Stop"
$pythonExe = Join-Path $PSScriptRoot ".venv-tooling\Scripts\python.exe"
$scriptPath = Join-Path $PSScriptRoot "workflows\pmx_pipeline\run_visible_conflict_inspection_q5a.py"
if (-not (Test-Path -LiteralPath $pythonExe)) {
    throw "Q5A requires the repo tooling env python: $pythonExe"
}

$arguments = @(
    $scriptPath,
    "--workspace-config",
    $WorkspaceConfig,
    "--level-path",
    $LevelPath,
    "--clothing-asset-path",
    $ClothingAssetPath,
    "--slot-name",
    $SlotName,
    "--attach-socket-name",
    $AttachSocketName
)
if ($P2ReportPath) { $arguments += @("--p2-report-path", $P2ReportPath) }
if ($OutputRoot) { $arguments += @("--output-root", $OutputRoot) }
if ($LatestReportPath) { $arguments += @("--latest-report-path", $LatestReportPath) }

& $pythonExe @arguments
exit $LASTEXITCODE
