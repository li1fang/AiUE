param(
    [string]$PythonExe = "python3.12.exe",
    [switch]$Latest,
    [string]$Manifest = "",
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
if ($DumpStateJson) {
    $args += "--dump-state-json"
}
if ($ExitAfterLoad) {
    $args += "--exit-after-load"
}

& $venvPython @args
exit $LASTEXITCODE
