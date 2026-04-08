param(
    [Parameter(Mandatory = $true)]
    [string]$WorkspaceConfig,
    [string]$OutputRoot
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$resolvedConfig = [System.IO.Path]::GetFullPath($WorkspaceConfig)
$configDirectory = Split-Path -Parent $resolvedConfig
$projectRoot = Split-Path -Parent $configDirectory
$raw = Get-Content -LiteralPath $resolvedConfig -Raw -Encoding UTF8 | ConvertFrom-Json

function Resolve-WorkspacePathValue {
    param([AllowNull()]$Value)
    if ($null -eq $Value) { return $null }
    $text = [string]$Value
    if ([string]::IsNullOrWhiteSpace($text)) { return $text }
    if ($text.StartsWith("/Game/")) { return $text }
    $expanded = $text.Replace('${project_root}', $projectRoot).Replace('${config_dir}', $configDirectory).Replace('${workspace_dir}', $configDirectory)
    if ([System.IO.Path]::IsPathRooted($expanded)) { return [System.IO.Path]::GetFullPath($expanded) }
    return [System.IO.Path]::GetFullPath((Join-Path $configDirectory $expanded))
}

$pythonExe = Resolve-WorkspacePathValue $raw.paths.blender_python_exe
if (-not (Test-Path -LiteralPath $pythonExe)) {
    throw "Workspace config does not resolve to a valid blender_python_exe: $pythonExe"
}

$runId = (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssZ")
$baseOutputRoot = if ($OutputRoot) { [System.IO.Path]::GetFullPath($OutputRoot) } else { Join-Path $repoRoot "Saved\\triplines" }
$runRoot = Join-Path $baseOutputRoot $runId
New-Item -ItemType Directory -Path $runRoot -Force | Out-Null

$repoSurfaceReport = Join-Path $runRoot "repo_surface_report.json"
$schemaReport = Join-Path $runRoot "schema_contract_report.json"
$workspaceReport = Join-Path $runRoot "workspace_dry_run_report.json"
$triplineReport = Join-Path $runRoot "alpha_tripline_report.json"
$bundleOutputRoot = Join-Path $runRoot "bundle"

& $pythonExe (Join-Path $repoRoot "tools\\check_repo_surface.py") --repo-root $repoRoot --output $repoSurfaceReport
if ($LASTEXITCODE -ne 0) { throw "Repo surface check failed." }

& $pythonExe (Join-Path $repoRoot "tools\\check_schema_contracts.py") --repo-root $repoRoot --output $schemaReport
if ($LASTEXITCODE -ne 0) { throw "Schema contract check failed." }

& $pythonExe (Join-Path $repoRoot "tools\\workspace_dry_run.py") --config $resolvedConfig --output $workspaceReport
if ($LASTEXITCODE -ne 0) { throw "Workspace dry-run failed." }

& powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $repoRoot "export_open_source_bundle.ps1") -OutputRoot $bundleOutputRoot -FailOnLeaks
if ($LASTEXITCODE -ne 0) { throw "Open-source bundle audit failed." }

& $pythonExe (Join-Path $repoRoot "tools\\check_tripline_reports.py") --workspace-config $resolvedConfig --aiue-root $repoRoot --output $triplineReport
if ($LASTEXITCODE -ne 0) { throw "Tripline report check failed." }

Write-Host "AiUE alpha triplines passed."
Write-Host "Run root: $runRoot"
