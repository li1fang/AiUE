param(
    [string]$PythonExe = "python3.12.exe"
)

$ErrorActionPreference = "Stop"
$repoRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
$requirementsPath = Join-Path $repoRoot "tools\\t1\\requirements.txt"
$venvPath = Join-Path $repoRoot ".venv-tooling"
$venvPython = Join-Path $venvPath "Scripts\\python.exe"

function Resolve-PythonExecutable {
    param([string]$CommandName)

    $command = Get-Command $CommandName -ErrorAction SilentlyContinue
    if (-not $command) {
        throw "Unable to resolve '$CommandName'. Install Python 3.12 or pass -PythonExe with a valid interpreter path."
    }
    $candidate = $command.Source
    $probe = & $candidate -c "import sys; print(sys.executable)" 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "Resolved '$CommandName' to '$candidate', but it is not runnable. Install/fix Python 3.12 or pass -PythonExe with a valid interpreter path."
    }
    return ($probe | Select-Object -First 1).Trim()
}

$resolvedPython = Resolve-PythonExecutable -CommandName $PythonExe
if (-not (Test-Path -LiteralPath $venvPython)) {
    & $resolvedPython -m venv $venvPath
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to create .venv-tooling using '$resolvedPython'."
    }
}

& $venvPython -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) {
    throw "Failed to upgrade pip inside .venv-tooling."
}
& $venvPython -m pip install -r $requirementsPath
if ($LASTEXITCODE -ne 0) {
    throw "Failed to install T1 tooling requirements."
}

Write-Output "AiUE tooling environment ready at: $venvPath"
