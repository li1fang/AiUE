param(
    [string]$WorkspaceConfig = "C:\AiUE\local\pipeline_workspace.local.json",
    [string]$C2Report = "",
    [string]$OutputPath = "",
    [string]$LatestOutputPath = ""
)

$ErrorActionPreference = "Stop"
$repoRoot = [System.IO.Path]::GetFullPath($PSScriptRoot)
$venvPython = Join-Path $repoRoot ".venv-tooling\Scripts\python.exe"
$pythonExe = if (Test-Path -LiteralPath $venvPython) { $venvPython } else { "python3.12.exe" }
$scriptPath = Join-Path $repoRoot "workflows\pmx_pipeline\run_resolve_converted_model_provider_v0.py"

$arguments = @(
    $scriptPath,
    "--workspace-config",
    $WorkspaceConfig
)
if ($C2Report) { $arguments += @("--c2-report", $C2Report) }
if ($OutputPath) { $arguments += @("--output-path", $OutputPath) }
if ($LatestOutputPath) { $arguments += @("--latest-output-path", $LatestOutputPath) }

& $pythonExe @arguments
exit $LASTEXITCODE
