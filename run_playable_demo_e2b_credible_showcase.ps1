param(
    [string]$WorkspaceConfig = "C:\AiUE\local\pipeline_workspace.local.json",
    [string]$SessionManifestPath,
    [string]$E2CredibilityReportPath,
    [string]$M1ReportPath,
    [string]$OutputRoot,
    [string]$LatestReportPath
)

$ErrorActionPreference = "Stop"
$pythonExe = Join-Path $PSScriptRoot ".venv-tooling\Scripts\python.exe"
$scriptPath = Join-Path $PSScriptRoot "workflows\pmx_pipeline\run_playable_demo_e2b_credible_showcase.py"
if (-not (Test-Path -LiteralPath $pythonExe)) {
    throw "E2B credible showcase requires the repo tooling env python: $pythonExe"
}

$arguments = @(
    $scriptPath,
    "--workspace-config",
    $WorkspaceConfig
)
if ($SessionManifestPath) { $arguments += @("--session-manifest-path", $SessionManifestPath) }
if ($E2CredibilityReportPath) { $arguments += @("--e2-credibility-report-path", $E2CredibilityReportPath) }
if ($M1ReportPath) { $arguments += @("--m1-report-path", $M1ReportPath) }
if ($OutputRoot) { $arguments += @("--output-root", $OutputRoot) }
if ($LatestReportPath) { $arguments += @("--latest-report-path", $LatestReportPath) }

& $pythonExe @arguments
exit $LASTEXITCODE
