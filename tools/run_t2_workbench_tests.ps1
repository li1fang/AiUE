param(
    [string]$PythonExe = "python3.12.exe",
    [switch]$SkipPrepareLatestPack,
    [switch]$SkipSoak,
    [string[]]$PytestArgs
)

$ErrorActionPreference = "Stop"
$repoRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
$bootstrapScript = Join-Path $repoRoot "tools\\bootstrap_t1_tooling.ps1"
$venvPython = Join-Path $repoRoot ".venv-tooling\\Scripts\\python.exe"

if (-not (Test-Path -LiteralPath $venvPython)) {
    & powershell -NoProfile -ExecutionPolicy Bypass -File $bootstrapScript -PythonExe $PythonExe
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to bootstrap the AiUE tooling environment."
    }
}

if (-not $SkipPrepareLatestPack) {
    $prepareScript = Join-Path $repoRoot "tools\\run_t1_evidence_pack.ps1"
    & powershell -NoProfile -ExecutionPolicy Bypass -File $prepareScript -PythonExe $PythonExe
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to refresh the latest T1 evidence pack before running T2 tests."
    }
}

$env:QT_QPA_PLATFORM = "offscreen"
$env:QT_API = "pyside6"

$args = @("-m", "pytest", "tests\\t2", "-q")
if ($SkipSoak) {
    $args += @("-m", "not soak")
}
if ($PytestArgs) {
    $args += $PytestArgs
}

& $venvPython @args
exit $LASTEXITCODE
