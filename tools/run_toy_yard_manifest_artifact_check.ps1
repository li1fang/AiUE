param(
    [string]$PythonExe = "python3.12.exe",
    [string]$WorkspaceConfig = "",
    [string]$ViewRoot = "",
    [string]$Summary = "",
    [string]$Manifest = "",
    [string]$OutputPath = ""
)

$ErrorActionPreference = "Stop"
$repoRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
$bootstrapScript = Join-Path $repoRoot "tools\\bootstrap_t1_tooling.ps1"
$venvPython = Join-Path $repoRoot ".venv-tooling\\Scripts\\python.exe"
$cliScript = Join-Path $repoRoot "tools\\t1\\python\\run_toy_yard_manifest_artifact_check.py"

if (-not (Test-Path -LiteralPath $venvPython)) {
    & powershell -NoProfile -ExecutionPolicy Bypass -File $bootstrapScript -PythonExe $PythonExe
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to bootstrap the T1 tooling environment."
    }
}

$args = @($cliScript)
if ($WorkspaceConfig) {
    $args += @("--workspace-config", $WorkspaceConfig)
}
if ($ViewRoot) {
    $args += @("--view-root", $ViewRoot)
}
if ($Summary) {
    $args += @("--summary", $Summary)
}
if ($Manifest) {
    $args += @("--manifest", $Manifest)
}
if ($OutputPath) {
    $args += @("--output-path", $OutputPath)
}

& $venvPython @args
if ($LASTEXITCODE -gt 1) {
    throw "Toy-yard manifest artifact self-check failed unexpectedly."
}
