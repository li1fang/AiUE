param(
    [string]$WorkspaceConfig = "C:\AiUE\local\pipeline_workspace.local.json",
    [string]$InventoryPath = "C:\Projects\toy-yard\_reports\base_mesh_batch_inventory_2026-04-22.md",
    [string]$RunbookPath = "C:\Projects\toy-yard\docs\aiue_base_mesh_trial_runbook_v0.md",
    [string]$OutputRoot,
    [string]$LatestReportPath
)

$ErrorActionPreference = "Stop"
$pythonExe = "C:\Program Files\Epic Games\UE_5.7\Engine\Binaries\ThirdParty\Python3\Win64\python.exe"
$scriptPath = Join-Path $PSScriptRoot "workflows\pmx_pipeline\run_base_mesh_trial_bm0.py"

$arguments = @(
    $scriptPath,
    "--workspace-config",
    $WorkspaceConfig,
    "--inventory-path",
    $InventoryPath,
    "--runbook-path",
    $RunbookPath
)
if ($OutputRoot) { $arguments += @("--output-root", $OutputRoot) }
if ($LatestReportPath) { $arguments += @("--latest-report-path", $LatestReportPath) }

& $pythonExe @arguments
exit $LASTEXITCODE
