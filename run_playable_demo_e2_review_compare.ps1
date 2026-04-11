param(
    [Parameter(Mandatory = $true)]
    [string]$WorkspaceConfig,
    [string]$SessionManifestPath,
    [string]$HistoryReportPath,
    [string]$OutputRoot,
    [string]$LatestReportPath
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$PythonExe = Join-Path $RepoRoot ".venv-tooling\Scripts\python.exe"
$ScriptPath = Join-Path $RepoRoot "workflows\pmx_pipeline\run_playable_demo_e2_review_compare.py"

if (-not (Test-Path -LiteralPath $PythonExe)) {
    throw "Tooling Python not found at $PythonExe"
}

$Args = @($ScriptPath, "--workspace-config", $WorkspaceConfig)
if ($SessionManifestPath) { $Args += @("--session-manifest-path", $SessionManifestPath) }
if ($HistoryReportPath) { $Args += @("--history-report-path", $HistoryReportPath) }
if ($OutputRoot) { $Args += @("--output-root", $OutputRoot) }
if ($LatestReportPath) { $Args += @("--latest-report-path", $LatestReportPath) }

& $PythonExe @Args
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}
