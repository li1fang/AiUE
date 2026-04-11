param(
    [string]$PythonExe = "python3.12.exe",
    [switch]$Latest,
    [string]$Manifest = "",
    [string]$SessionManifest = "",
    [string]$PackageId = "",
    [string]$ActionPresetId = "",
    [string]$AnimationPresetId = "",
    [ValidateSet("action_preview", "animation_preview")]
    [string]$RequestKind = "action_preview",
    [switch]$DumpRequestJson,
    [string]$WriteRequestPath = "",
    [string]$WorkspaceConfig = "",
    [string]$ResultJsonPath = "",
    [switch]$Invoke,
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"
$repoRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
$bootstrapScript = Join-Path $repoRoot "tools\\bootstrap_t1_tooling.ps1"
$venvPython = Join-Path $repoRoot ".venv-tooling\\Scripts\\python.exe"
$cliScript = Join-Path $repoRoot "tools\\t2\\python\\run_e2_demo_request.py"

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
if ($PackageId) {
    $args += @("--package-id", $PackageId)
}
if ($ActionPresetId) {
    $args += @("--action-preset-id", $ActionPresetId)
}
if ($AnimationPresetId) {
    $args += @("--animation-preset-id", $AnimationPresetId)
}
if ($RequestKind) {
    $args += @("--request-kind", $RequestKind)
}
if ($DumpRequestJson) {
    $args += "--dump-request-json"
}
if ($WriteRequestPath) {
    $args += @("--write-request-path", $WriteRequestPath)
}
if ($WorkspaceConfig) {
    $args += @("--workspace-config", $WorkspaceConfig)
}
if ($ResultJsonPath) {
    $args += @("--result-json-path", $ResultJsonPath)
}
if ($Invoke) {
    $args += "--invoke"
}
if ($DryRun) {
    $args += "--dry-run"
}

& $venvPython @args
exit $LASTEXITCODE
