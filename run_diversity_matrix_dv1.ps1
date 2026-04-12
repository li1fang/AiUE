param(
    [Parameter(Mandatory = $true)]
    [string]$WorkspaceConfig,
    [string]$PythonExe = "python3.12.exe",
    [string]$SessionManifestPath = "",
    [string]$E2CredibilityReportPath = "",
    [string]$M1ReportPath = "",
    [string]$OutputRoot = "",
    [string]$LatestReportPath = ""
)

$ErrorActionPreference = "Stop"
$repoRoot = [System.IO.Path]::GetFullPath($PSScriptRoot)
$scriptPath = Join-Path $repoRoot "workflows\pmx_pipeline\run_diversity_matrix_dv1.py"

$args = @(
    $scriptPath,
    "--workspace-config", $WorkspaceConfig
)
if ($SessionManifestPath) {
    $args += @("--session-manifest-path", $SessionManifestPath)
}
if ($E2CredibilityReportPath) {
    $args += @("--e2-credibility-report-path", $E2CredibilityReportPath)
}
if ($M1ReportPath) {
    $args += @("--m1-report-path", $M1ReportPath)
}
if ($OutputRoot) {
    $args += @("--output-root", $OutputRoot)
}
if ($LatestReportPath) {
    $args += @("--latest-report-path", $LatestReportPath)
}

& $PythonExe @args
exit $LASTEXITCODE
