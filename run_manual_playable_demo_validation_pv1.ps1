param(
    [string]$WorkspaceConfig = "C:\AiUE\local\pipeline_workspace.local.json",
    [string]$SessionManifestPath,
    [string]$E2BReportPath,
    [string]$Operator = $env:USERNAME,
    [ValidateSet("pass", "attention")]
    [string]$SignoffStatus = "attention",
    [string]$Notes = "manual_playable_demo_validation_pending",
    [string]$OutputRoot,
    [string]$LatestReportPath
)

$ErrorActionPreference = "Stop"
$pythonExe = Join-Path $PSScriptRoot ".venv-tooling\Scripts\python.exe"
$scriptPath = Join-Path $PSScriptRoot "workflows\pmx_pipeline\run_manual_playable_demo_validation_pv1.py"
if (-not (Test-Path -LiteralPath $pythonExe)) {
    throw "PV1 manual signoff requires the repo tooling env python: $pythonExe"
}

$arguments = @(
    $scriptPath,
    "--workspace-config",
    $WorkspaceConfig,
    "--operator",
    $Operator,
    "--signoff-status",
    $SignoffStatus,
    "--notes",
    $Notes
)
if ($SessionManifestPath) { $arguments += @("--session-manifest-path", $SessionManifestPath) }
if ($E2BReportPath) { $arguments += @("--e2b-report-path", $E2BReportPath) }
if ($OutputRoot) { $arguments += @("--output-root", $OutputRoot) }
if ($LatestReportPath) { $arguments += @("--latest-report-path", $LatestReportPath) }

& $pythonExe @arguments
exit $LASTEXITCODE
