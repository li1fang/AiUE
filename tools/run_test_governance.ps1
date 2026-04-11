param(
    [string]$PythonExe = "python3.12.exe",
    [string]$RepoRoot = "",
    [string]$VerificationRoot = "",
    [string]$CoverageLedger = "",
    [ValidateSet("worktree", "head")]
    [string]$ChangeSource = "worktree"
)

$ErrorActionPreference = "Stop"
$repoRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
$bootstrapScript = Join-Path $repoRoot "tools\\bootstrap_t1_tooling.ps1"
$venvPython = Join-Path $repoRoot ".venv-tooling\\Scripts\\python.exe"
$cliScript = Join-Path $repoRoot "tools\\t1\\python\\run_test_governance.py"

if (-not (Test-Path -LiteralPath $venvPython)) {
    & powershell -NoProfile -ExecutionPolicy Bypass -File $bootstrapScript -PythonExe $PythonExe
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to bootstrap the T1 tooling environment."
    }
}

$args = @($cliScript, "--change-source", $ChangeSource)
if ($RepoRoot) {
    $args += @("--repo-root", $RepoRoot)
}
if ($VerificationRoot) {
    $args += @("--verification-root", $VerificationRoot)
}
if ($CoverageLedger) {
    $args += @("--coverage-ledger", $CoverageLedger)
}

& $venvPython @args
if ($LASTEXITCODE -ne 0) {
    throw "Test governance report generation failed."
}
