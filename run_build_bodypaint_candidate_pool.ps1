param(
    [string]$WorkspaceConfig = "C:\AiUE\local\pipeline_workspace.local.json",
    [string]$ToyYardDb = "C:\Projects\toy-yard\_db\toyyard.sqlite",
    [string]$ConversionRoot = "",
    [string]$OutputRoot = "",
    [string]$LatestReportPath = "",
    [string]$Tag = "",
    [switch]$ApplyTags,
    [int]$Limit = 0
)

$ErrorActionPreference = "Stop"
if (-not $Tag) {
    $Tag = [string]::Concat(
        [char]0x6E38, [char]0x620F, "_",
        [char]0x4E8C, [char]0x6B21, [char]0x5143,
        [char]0x6E38, [char]0x620F
    )
}

$repoRoot = [System.IO.Path]::GetFullPath($PSScriptRoot)
$venvPython = Join-Path $repoRoot ".venv-tooling\Scripts\python.exe"
$pythonExe = if (Test-Path -LiteralPath $venvPython) { $venvPython } else { "python3.12.exe" }
$scriptPath = Join-Path $repoRoot "workflows\pmx_pipeline\run_build_bodypaint_candidate_pool.py"

$arguments = @(
    $scriptPath,
    "--workspace-config", $WorkspaceConfig,
    "--toy-yard-db", $ToyYardDb,
    "--tag", $Tag
)
if ($ConversionRoot) { $arguments += @("--conversion-root", $ConversionRoot) }
if ($OutputRoot) { $arguments += @("--output-root", $OutputRoot) }
if ($LatestReportPath) { $arguments += @("--latest-report-path", $LatestReportPath) }
if ($ApplyTags) { $arguments += "--apply-tags" }
if ($Limit -gt 0) { $arguments += @("--limit", "$Limit") }

& $pythonExe @arguments
exit $LASTEXITCODE
