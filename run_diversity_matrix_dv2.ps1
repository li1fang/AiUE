param(
    [Parameter(Mandatory = $true)]
    [string]$WorkspaceConfig,
    [string]$PythonExe = "python3.12.exe",
    [string]$SessionManifestPath = "",
    [string]$Dv1ReportPath = "",
    [string]$OutputRoot = "",
    [string]$LatestReportPath = "",
    [string]$ClothingStaticMeshAsset = "",
    [string]$FxNiagaraSystemAsset = ""
)

$ErrorActionPreference = "Stop"
$repoRoot = [System.IO.Path]::GetFullPath($PSScriptRoot)
$scriptPath = Join-Path $repoRoot "workflows\pmx_pipeline\run_diversity_matrix_dv2.py"

$args = @(
    $scriptPath,
    "--workspace-config", $WorkspaceConfig
)
if ($SessionManifestPath) {
    $args += @("--session-manifest-path", $SessionManifestPath)
}
if ($Dv1ReportPath) {
    $args += @("--dv1-report-path", $Dv1ReportPath)
}
if ($OutputRoot) {
    $args += @("--output-root", $OutputRoot)
}
if ($LatestReportPath) {
    $args += @("--latest-report-path", $LatestReportPath)
}
if ($ClothingStaticMeshAsset) {
    $args += @("--clothing-static-mesh-asset", $ClothingStaticMeshAsset)
}
if ($FxNiagaraSystemAsset) {
    $args += @("--fx-niagara-system-asset", $FxNiagaraSystemAsset)
}

& $PythonExe @args
exit $LASTEXITCODE
