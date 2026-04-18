param(
    [string]$SourceZip = "",
    [string]$SourceMesh = "",
    [string]$OutputRoot = "C:\AiUE\local\body_platform\provider_ready_source_handoffs\latest",
    [string]$FixtureId = "bodypaint_trial::lower_body_core_source_v1",
    [string]$BodyFamilyId = "bodypaint_trial",
    [string]$FixtureScope = "lower_body_core",
    [string[]]$SourceModuleId = @(),
    [string]$ExporterTool = "aiue_source_wrap",
    [string]$ExporterVersion = "0.1",
    [string]$FusionRecipeId = "",
    [string]$RigProfileId = "rig_profile::bodypaint_trial::pending",
    [string]$MaterialProfileId = "material_profile::bodypaint_trial::source_scan_v1",
    [string]$MeshOutputName = "lower_body_core_hi.fbx",
    [string]$LinearUnit = "",
    [string]$UpAxis = "",
    [string]$ForwardAxis = ""
)

$ErrorActionPreference = "Stop"
$repoRoot = [System.IO.Path]::GetFullPath($PSScriptRoot)
$venvPython = Join-Path $repoRoot ".venv-tooling\Scripts\python.exe"
$pythonExe = if (Test-Path -LiteralPath $venvPython) { $venvPython } else { "python3.12.exe" }
$scriptPath = Join-Path $repoRoot "workflows\pmx_pipeline\run_build_provider_ready_source_handoff_sample.py"

$arguments = @(
    $scriptPath,
    "--output-root", $OutputRoot,
    "--fixture-id", $FixtureId,
    "--body-family-id", $BodyFamilyId,
    "--fixture-scope", $FixtureScope,
    "--exporter-tool", $ExporterTool,
    "--exporter-version", $ExporterVersion,
    "--rig-profile-id", $RigProfileId,
    "--material-profile-id", $MaterialProfileId,
    "--mesh-output-name", $MeshOutputName
)
if ($SourceZip) { $arguments += @("--source-zip", $SourceZip) }
if ($SourceMesh) { $arguments += @("--source-mesh", $SourceMesh) }
if ($FusionRecipeId) { $arguments += @("--fusion-recipe-id", $FusionRecipeId) }
if ($LinearUnit) { $arguments += @("--linear-unit", $LinearUnit) }
if ($UpAxis) { $arguments += @("--up-axis", $UpAxis) }
if ($ForwardAxis) { $arguments += @("--forward-axis", $ForwardAxis) }
foreach ($item in $SourceModuleId) {
    if ($item) { $arguments += @("--source-module-id", $item) }
}

& $pythonExe @arguments
exit $LASTEXITCODE
