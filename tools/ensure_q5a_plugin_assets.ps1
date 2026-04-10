param(
    [string]$WorkspaceConfig = "C:\AiUE\local\pipeline_workspace.local.json"
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$syncScript = Join-Path $repoRoot "tools\sync_aiue_pmx_runtime.ps1"
$assetScript = Join-Path $repoRoot "tools\unreal\create_q5a_plugin_assets.py"
if (-not (Test-Path -LiteralPath $WorkspaceConfig)) {
    throw "Workspace config not found: $WorkspaceConfig"
}
if (-not (Test-Path -LiteralPath $syncScript)) {
    throw "Plugin sync script not found: $syncScript"
}
if (-not (Test-Path -LiteralPath $assetScript)) {
    throw "Q5A asset creation script not found: $assetScript"
}

$workspace = Get-Content -LiteralPath $WorkspaceConfig -Raw -Encoding UTF8 | ConvertFrom-Json
$editorCmd = [string]$workspace.paths.unreal_editor_cmd
$engineRoot = Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $editorCmd))
$buildBat = Join-Path $engineRoot "Build\BatchFiles\Build.bat"
$kernelProjectRoot = [string]$workspace.hosts.kernel.project_root
$demoProjectRoot = [string]$workspace.hosts.demo.project_root
$demoProjectFile = Get-ChildItem -Path $demoProjectRoot -Filter *.uproject | Select-Object -First 1 -ExpandProperty FullName
$kernelProjectFile = Get-ChildItem -Path $kernelProjectRoot -Filter *.uproject | Select-Object -First 1 -ExpandProperty FullName
$demoPluginContent = Join-Path $demoProjectRoot "Plugins\AiUEPmxRuntime\Content"
$repoPluginContent = Join-Path $repoRoot "tools\unreal_plugins\AiUEPmxRuntime\Content"

if (-not (Test-Path -LiteralPath $editorCmd)) {
    throw "UnrealEditor-Cmd.exe not found: $editorCmd"
}
if (-not (Test-Path -LiteralPath $buildBat)) {
    throw "Unreal Build.bat not found: $buildBat"
}
if (-not (Test-Path -LiteralPath $demoProjectFile)) {
    throw "Demo project not found: $demoProjectFile"
}
if (-not (Test-Path -LiteralPath $kernelProjectFile)) {
    throw "Kernel project not found: $kernelProjectFile"
}

function Invoke-BuildEditorTarget {
    param(
        [Parameter(Mandatory = $true)][string]$ProjectFile
    )
    $targetName = ([System.IO.Path]::GetFileNameWithoutExtension($ProjectFile)) + "Editor"
    & $buildBat $targetName Win64 Development $ProjectFile -WaitMutex -NoHotReloadFromIDE
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to build editor target: $targetName"
    }
}

& powershell -NoProfile -ExecutionPolicy Bypass -File $syncScript
if ($LASTEXITCODE -ne 0) {
    throw "Initial AiUEPmxRuntime sync failed."
}

Invoke-BuildEditorTarget -ProjectFile $demoProjectFile

$cmdVariants = @(
    @($demoProjectFile, "-Unattended", "-NullRHI", "-ExecutePythonScript=$assetScript"),
    @($demoProjectFile, "-Unattended", "-NullRHI", "-run=pythonscript", "-script=$assetScript")
)
$generated = $false
foreach ($variant in $cmdVariants) {
    & $editorCmd @variant
    if ($LASTEXITCODE -eq 0) {
        $generated = $true
        break
    }
}
if (-not $generated) {
    throw "Q5A plugin asset generation failed through UnrealEditor-Cmd."
}

if (-not (Test-Path -LiteralPath $demoPluginContent)) {
    throw "Demo plugin content directory missing after generation: $demoPluginContent"
}
if (Test-Path -LiteralPath $repoPluginContent) {
    Remove-Item -LiteralPath $repoPluginContent -Recurse -Force
}
Copy-Item -LiteralPath $demoPluginContent -Destination $repoPluginContent -Recurse -Force

& powershell -NoProfile -ExecutionPolicy Bypass -File $syncScript
if ($LASTEXITCODE -ne 0) {
    throw "Final AiUEPmxRuntime sync failed."
}

Invoke-BuildEditorTarget -ProjectFile $demoProjectFile
Invoke-BuildEditorTarget -ProjectFile $kernelProjectFile
