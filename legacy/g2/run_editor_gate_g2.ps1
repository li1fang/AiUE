param(
    [Parameter(Mandatory = $true)]
    [string]$WorkspaceConfig,
    [string]$EquipmentReportPath,
    [string]$SummaryPath,
    [string]$StageProfilePath,
    [string]$OutputRoot,
    [string]$LatestReportPath,
    [switch]$EnsureStageAnchors
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
if (-not $pythonExe -or -not (Test-Path -LiteralPath $pythonExe)) {
    throw "Workspace config does not resolve to a valid blender_python_exe: $pythonExe"
}

$scriptPath = Join-Path $repoRoot "workflows\pmx_pipeline\run_editor_gate_g2.py"
$args = @($scriptPath, "--workspace-config", $resolvedConfig)
if ($EquipmentReportPath) { $args += @("--equipment-report-path", [System.IO.Path]::GetFullPath($EquipmentReportPath)) }
if ($SummaryPath) { $args += @("--summary-path", [System.IO.Path]::GetFullPath($SummaryPath)) }
if ($StageProfilePath) { $args += @("--stage-profile-path", [System.IO.Path]::GetFullPath($StageProfilePath)) }
if ($OutputRoot) { $args += @("--output-root", [System.IO.Path]::GetFullPath($OutputRoot)) }
if ($LatestReportPath) { $args += @("--latest-report-path", [System.IO.Path]::GetFullPath($LatestReportPath)) }
if ($EnsureStageAnchors) { $args += "--ensure-stage-anchors" }

& $pythonExe @args
exit $LASTEXITCODE
