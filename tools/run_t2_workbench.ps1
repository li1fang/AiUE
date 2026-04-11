param(
    [string]$PythonExe = "python3.12.exe",
    [switch]$Latest,
    [string]$Manifest = "",
    [string]$SessionManifest = "",
    [string]$WorkspaceConfig = "",
    [string]$PackageId = "",
    [string]$ActionPresetId = "",
    [string]$AnimationPresetId = "",
    [int]$ReviewCompareIndex = 0,
    [switch]$DemoRequestExport,
    [switch]$DemoRequestDryRun,
    [switch]$DemoRequestInvoke,
    [switch]$DemoSessionRoundInvoke,
    [switch]$DemoReviewReplay,
    [ValidateSet("action_preview", "animation_preview")]
    [string]$DemoRequestKind = "action_preview",
    [switch]$DumpStateJson,
    [switch]$ExitAfterLoad
)

$ErrorActionPreference = "Stop"
$repoRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
$bootstrapScript = Join-Path $repoRoot "tools\\bootstrap_t1_tooling.ps1"
$venvPython = Join-Path $repoRoot ".venv-tooling\\Scripts\\python.exe"
$cliScript = Join-Path $repoRoot "tools\\t2\\python\\run_t2_workbench.py"

if (-not (Test-Path -LiteralPath $venvPython)) {
    & powershell -NoProfile -ExecutionPolicy Bypass -File $bootstrapScript -PythonExe $PythonExe
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to bootstrap the AiUE tooling environment."
    }
}

$args = @($cliScript)
if ($Latest -or -not $Manifest) {
    $args += "--latest"
}
if ($Manifest) {
    $args += @("--manifest", $Manifest)
}
if ($SessionManifest) {
    $args += @("--session-manifest", $SessionManifest)
}
if ($WorkspaceConfig) {
    $args += @("--workspace-config", $WorkspaceConfig)
}
if ($PackageId) {
    $args += @("--package-id", $PackageId)
}
if ($ActionPresetId) {
    $args += @("--action-preset-id", $ActionPresetId)
}
if ($AnimationPresetId) {
    $args += @("--animation-preset-id", $AnimationPresetId)
}
if ($ReviewCompareIndex -ge 0) {
    $args += @("--review-compare-index", [string]$ReviewCompareIndex)
}
if ($DemoRequestExport) {
    $args += "--demo-request-export"
}
if ($DemoRequestDryRun) {
    $args += "--demo-request-dry-run"
}
if ($DemoRequestInvoke) {
    $args += "--demo-request-invoke"
}
if ($DemoSessionRoundInvoke) {
    $args += "--demo-session-round-invoke"
}
if ($DemoReviewReplay) {
    $args += "--demo-review-replay"
}
if ($DemoRequestKind) {
    $args += @("--demo-request-kind", $DemoRequestKind)
}
if ($DumpStateJson) {
    $args += "--dump-state-json"
}
if ($ExitAfterLoad) {
    $args += "--exit-after-load"
}

& $venvPython @args
exit $LASTEXITCODE
