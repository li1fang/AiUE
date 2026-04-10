param(
    [Parameter(Mandatory = $true)][string]$WorkspaceConfig,
    [string]$Q5AReportPath,
    [string]$OutputRoot,
    [string]$LatestReportPath
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$pythonExe = Join-Path $repoRoot ".venv-tooling\Scripts\python.exe"
$scriptPath = Join-Path $repoRoot "workflows\pmx_pipeline\run_volumetric_fit_inspection_q5b.py"

if (-not (Test-Path -LiteralPath $pythonExe)) {
    throw "Tooling Python not found: $pythonExe"
}
if (-not (Test-Path -LiteralPath $scriptPath)) {
    throw "Q5B gate script not found: $scriptPath"
}

$arguments = @(
    $scriptPath,
    "--workspace-config", (Resolve-Path -LiteralPath $WorkspaceConfig).Path
)
if ($Q5AReportPath) { $arguments += @("--q5a-report-path", (Resolve-Path -LiteralPath $Q5AReportPath).Path) }
if ($OutputRoot) { $arguments += @("--output-root", $OutputRoot) }
if ($LatestReportPath) { $arguments += @("--latest-report-path", $LatestReportPath) }

& $pythonExe @arguments
if ($LASTEXITCODE -ne 0) {
    throw "Q5B volumetric fit inspection failed."
}
