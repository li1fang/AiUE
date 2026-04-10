param(
    [string]$WorkspaceConfig = "C:\AiUE\local\pipeline_workspace.local.json",
    [string]$D1ReportPath,
    [string]$OutputRoot,
    [string]$LatestReportPath,
    [string[]]$StaticMeshFixture
)

$ErrorActionPreference = "Stop"
$pythonExe = "C:\Program Files\Epic Games\UE_5.7\Engine\Binaries\ThirdParty\Python3\Win64\python.exe"
$scriptPath = Join-Path $PSScriptRoot "workflows\pmx_pipeline\run_generic_slot_abstraction_p1.py"

$arguments = @(
    $scriptPath,
    "--workspace-config",
    $WorkspaceConfig
)
if ($D1ReportPath) { $arguments += @("--d1-report-path", $D1ReportPath) }
if ($OutputRoot) { $arguments += @("--output-root", $OutputRoot) }
if ($LatestReportPath) { $arguments += @("--latest-report-path", $LatestReportPath) }
if ($StaticMeshFixture) {
    foreach ($fixture in $StaticMeshFixture) {
        $arguments += @("--static-mesh-fixture", $fixture)
    }
}

& $pythonExe @arguments
exit $LASTEXITCODE
