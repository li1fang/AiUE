param(
    [string]$PythonExe = "python3.12.exe",
    [string]$ProfilePath = "",
    [string]$OutputRoot = "",
    [string]$LatestReportPath = "",
    [string[]]$LaneId
)

$ErrorActionPreference = "Stop"
$repoRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
$bootstrapScript = Join-Path $repoRoot "tools\\bootstrap_t1_tooling.ps1"
$venvPython = Join-Path $repoRoot ".venv-tooling\\Scripts\\python.exe"
$cliScript = Join-Path $repoRoot "tools\\t1\\python\\run_qa_full.py"

if (-not (Test-Path -LiteralPath $venvPython)) {
    & powershell -NoProfile -ExecutionPolicy Bypass -File $bootstrapScript -PythonExe $PythonExe
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to bootstrap the AiUE tooling environment."
    }
}

$resolvedProfilePath = $ProfilePath
if (-not $resolvedProfilePath) {
    $resolvedProfilePath = Join-Path $repoRoot "examples\\qa\\qa_full_nightly.example.json"
}

$args = @(
    $cliScript,
    "--repo-root",
    $repoRoot,
    "--profile",
    $resolvedProfilePath
)
if ($OutputRoot) {
    $args += @("--output-root", $OutputRoot)
}
if ($LatestReportPath) {
    $args += @("--latest-report-path", $LatestReportPath)
}
if ($LaneId) {
    foreach ($item in $LaneId) {
        if ($item) {
            $args += @("--lane-id", $item)
        }
    }
}

& $venvPython @args
exit $LASTEXITCODE
