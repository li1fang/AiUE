param(
    [string]$WorkspaceConfig = "C:\AiUE\local\pipeline_workspace.local.json",
    [string]$FixtureZip = "",
    [string]$FixtureRoot = "",
    [string]$OutputRoot = "",
    [string]$LatestReportPath = "",
    [string]$LatestProviderPath = ""
)

$ErrorActionPreference = "Stop"
$repoRoot = [System.IO.Path]::GetFullPath($PSScriptRoot)
$venvPython = Join-Path $repoRoot ".venv-tooling\Scripts\python.exe"
$pythonExe = if (Test-Path -LiteralPath $venvPython) { $venvPython } else { "python3.12.exe" }
$scriptPath = Join-Path $repoRoot "workflows\pmx_pipeline\run_check_c2_provider_ready_source_handoff.py"

$arguments = @(
    $scriptPath,
    "--workspace-config",
    $WorkspaceConfig
)
if ($FixtureZip) { $arguments += @("--fixture-zip", $FixtureZip) }
if ($FixtureRoot) { $arguments += @("--fixture-root", $FixtureRoot) }
if ($OutputRoot) { $arguments += @("--output-root", $OutputRoot) }
if ($LatestReportPath) { $arguments += @("--latest-report-path", $LatestReportPath) }
if ($LatestProviderPath) { $arguments += @("--latest-provider-path", $LatestProviderPath) }

& $pythonExe @arguments
exit $LASTEXITCODE
