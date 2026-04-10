param(
    [Parameter(Mandatory = $true)]
    [string]$BeforePath,
    [Parameter(Mandatory = $true)]
    [string]$AfterPath,
    [int]$SampleWidth = 160,
    [int]$SampleHeight = 90,
    [int]$HistogramBins = 32,
    [double]$CropX = -1,
    [double]$CropY = -1,
    [double]$CropWidth = -1,
    [double]$CropHeight = -1,
    [string]$MaskPath = ""
)

$ErrorActionPreference = "Stop"

function Get-RepoRoot {
    return [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
}

function Invoke-LegacyEngine {
    $legacyScript = Join-Path $PSScriptRoot "compare_image_motion_legacy.ps1"
    $legacyArgs = @(
        "-BeforePath", $BeforePath,
        "-AfterPath", $AfterPath,
        "-SampleWidth", $SampleWidth,
        "-SampleHeight", $SampleHeight,
        "-HistogramBins", $HistogramBins,
        "-CropX", $CropX,
        "-CropY", $CropY,
        "-CropWidth", $CropWidth,
        "-CropHeight", $CropHeight
    )
    if ($MaskPath) {
        throw "MaskPath requires the T1 Python tooling environment (.venv-tooling)."
    }
    & powershell -NoProfile -ExecutionPolicy Bypass -File $legacyScript @legacyArgs
    if ($LASTEXITCODE -ne 0) {
        throw "compare_image_motion legacy engine failed."
    }
}

$repoRoot = Get-RepoRoot
$toolingPython = Join-Path $repoRoot ".venv-tooling\\Scripts\\python.exe"
$cliScript = Join-Path $repoRoot "tools\\t1\\python\\compare_image_motion_cli.py"
if (-not (Test-Path -LiteralPath $toolingPython) -or -not (Test-Path -LiteralPath $cliScript)) {
    Invoke-LegacyEngine
    return
}

$pythonArgs = @(
    $cliScript,
    "--before-path", $BeforePath,
    "--after-path", $AfterPath,
    "--sample-width", $SampleWidth,
    "--sample-height", $SampleHeight,
    "--histogram-bins", $HistogramBins,
    "--crop-x", $CropX,
    "--crop-y", $CropY,
    "--crop-width", $CropWidth,
    "--crop-height", $CropHeight
)
if ($MaskPath) {
    $pythonArgs += @("--mask-path", $MaskPath)
}

$stdout = & $toolingPython @pythonArgs 2>&1
if ($LASTEXITCODE -ne 0) {
    throw ($stdout | Out-String).Trim()
}
$stdout | Write-Output
