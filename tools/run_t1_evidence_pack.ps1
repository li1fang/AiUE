param(
    [string]$PythonExe = "python3.12.exe",
    [string]$VerificationRoot = "",
    [string]$OutputRoot = "",
    [string]$LatestRoot = ""
)

$ErrorActionPreference = "Stop"
$repoRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
$bootstrapScript = Join-Path $repoRoot "tools\\bootstrap_t1_tooling.ps1"
$venvPython = Join-Path $repoRoot ".venv-tooling\\Scripts\\python.exe"
$cliScript = Join-Path $repoRoot "tools\\t1\\python\\generate_t1_evidence_pack.py"

if (-not (Test-Path -LiteralPath $venvPython)) {
    & powershell -NoProfile -ExecutionPolicy Bypass -File $bootstrapScript -PythonExe $PythonExe
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to bootstrap the T1 tooling environment."
    }
}

$args = @($cliScript)
if ($VerificationRoot) {
    $args += @("--verification-root", $VerificationRoot)
}
if ($OutputRoot) {
    $args += @("--output-root", $OutputRoot)
}
if ($LatestRoot) {
    $args += @("--latest-root", $LatestRoot)
}

& $venvPython @args
if ($LASTEXITCODE -ne 0) {
    throw "T1 evidence pack generation failed."
}
