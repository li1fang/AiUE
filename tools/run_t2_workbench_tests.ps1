param(
    [string]$PythonExe = "python3.12.exe",
    [ValidateSet("smoke", "default", "full")]
    [string]$Profile = "default",
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

$prepareLatestPack = -not $SkipPrepareLatestPack
if ($Profile -eq "smoke" -and -not $PSBoundParameters.ContainsKey("SkipPrepareLatestPack")) {
    $prepareLatestPack = $false
}

if ($prepareLatestPack) {
    $prepareScript = Join-Path $repoRoot "tools\\run_t1_evidence_pack.ps1"
    & powershell -NoProfile -ExecutionPolicy Bypass -File $prepareScript -PythonExe $PythonExe
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to refresh the latest T1 evidence pack before running T2 tests."
    }
}

$env:QT_QPA_PLATFORM = "offscreen"
$env:QT_API = "pyside6"

$pytestTargets = @("tests\\t2")
if ($Profile -eq "smoke") {
    $pytestTargets = @(
        "tests\\t2\\test_state.py::test_load_workbench_state_reads_q5c_contrast_focus",
        "tests\\t2\\test_process.py::test_workbench_cli_reads_q5c_quality_summary",
        "tests\\t2\\test_ui.py::test_workbench_window_shows_q5c_quality_summary"
    )
}

$args = @("-m", "pytest") + $pytestTargets + @("-q")
$skipSoakResolved = $SkipSoak -or $Profile -eq "smoke"
if ($skipSoakResolved -and $Profile -ne "smoke") {
    $args += @("-m", "not soak")
}
if ($PytestArgs) {
    $args += $PytestArgs
}

& $venvPython @args
exit $LASTEXITCODE
