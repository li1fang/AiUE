param(
    [string[]]$ProjectRoots = @(
        "C:\Users\garro\Documents\Unreal Projects\UEIntroProject",
        "C:\Users\garro\Documents\Unreal Projects\AiUEdemo"
    )
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$sourcePluginRoot = Join-Path $repoRoot "tools\unreal_plugins\AiUEPmxRuntime"
if (-not (Test-Path -LiteralPath $sourcePluginRoot)) {
    throw "Source plugin root not found: $sourcePluginRoot"
}

foreach ($projectRoot in $ProjectRoots) {
    if (-not (Test-Path -LiteralPath $projectRoot)) {
        throw "Project root not found: $projectRoot"
    }
    $pluginsRoot = Join-Path $projectRoot "Plugins"
    $targetPluginRoot = Join-Path $pluginsRoot "AiUEPmxRuntime"
    if (Test-Path -LiteralPath $targetPluginRoot) {
        Remove-Item -LiteralPath $targetPluginRoot -Recurse -Force
    }
    New-Item -ItemType Directory -Path $pluginsRoot -Force | Out-Null
    Copy-Item -LiteralPath $sourcePluginRoot -Destination $targetPluginRoot -Recurse -Force
}
