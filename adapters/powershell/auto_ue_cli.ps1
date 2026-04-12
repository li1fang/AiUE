param(
    [Parameter(Position = 0)]
    [ValidateSet("probe", "run")]
    [string]$Operation = "run",
    [string]$WorkspaceConfig,
    [ValidateSet("dual", "all", "cmd_nullrhi", "cmd_rendered", "editor_rendered")]
    [string]$Mode = "dual",
    [string]$Command,
    [string]$ActionSpec,
    [string]$ParamsJson,
    [string]$ParamsPath,
    [string]$OutputPath,
    [string]$RunId,
    [string]$HostKey,
    [int]$PostExitFinalizeWaitSeconds,
    [switch]$AllowDestructive,
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"

function Resolve-WorkspacePathValue {
    param([AllowNull()]$Value, [string]$ProjectRoot, [string]$ConfigDirectory)
    if ($null -eq $Value) { return $null }
    $text = [string]$Value
    if ([string]::IsNullOrWhiteSpace($text)) { return $text }
    if ($text.StartsWith("/Game/")) { return $text }
    $expanded = $text.Replace('${project_root}', $ProjectRoot).Replace('${config_dir}', $ConfigDirectory).Replace('${workspace_dir}', $ConfigDirectory)
    if ([System.IO.Path]::IsPathRooted($expanded)) { return [System.IO.Path]::GetFullPath($expanded) }
    return [System.IO.Path]::GetFullPath((Join-Path $ConfigDirectory $expanded))
}

function Get-HostProjectRoot {
    param([string]$ConfigPath, [string]$CommandId, [string]$RequestedHostKey)
    if (-not $ConfigPath) { throw "AiUE wrapper requires -WorkspaceConfig" }
    $resolvedConfig = [System.IO.Path]::GetFullPath($ConfigPath)
    $raw = Get-Content -LiteralPath $resolvedConfig -Raw -Encoding UTF8 | ConvertFrom-Json
    $configDirectory = Split-Path -Parent $resolvedConfig
    $projectRoot = Split-Path -Parent $configDirectory
    $defaultRoutes = @{
        "import-package" = "kernel"
        "build-equipment-registry" = "kernel"
        "refresh-assets" = "kernel"
        "inspect-host" = "kernel"
        "inspect-host-visual" = "kernel"
        "inspect-visible-conflict" = "demo"
        "inspect-slot-runtime" = "kernel"
        "composition-validation" = "kernel"
        "validate-package" = "kernel"
        "load-level" = "demo"
        "stage-capture" = "demo"
        "run-scene-sweep" = "demo"
        "action-preview" = "demo"
        "animation-preview" = "demo"
        "retarget-preflight" = "demo"
        "retarget-bootstrap" = "demo"
        "retarget-author-chains" = "demo"
        "demo-gate" = "demo"
    }
    if ($raw.default_host_routes) {
        foreach ($property in $raw.default_host_routes.PSObject.Properties) {
            $defaultRoutes[$property.Name] = [string]$property.Value
        }
    }
    $resolvedHostKey = if ($RequestedHostKey) { [string]$RequestedHostKey } elseif ($CommandId -and $defaultRoutes.ContainsKey($CommandId)) { [string]$defaultRoutes[$CommandId] } elseif ($raw.hosts.kernel) { "kernel" } else { "" }
    $hostRoot = $null
    if ($resolvedHostKey -and $raw.hosts -and $raw.hosts.$resolvedHostKey) {
        $hostRoot = Resolve-WorkspacePathValue -Value $raw.hosts.$resolvedHostKey.project_root -ProjectRoot $projectRoot -ConfigDirectory $configDirectory
    }
    if (-not $hostRoot) {
        $hostRoot = Resolve-WorkspacePathValue -Value $raw.paths.unreal_project_root -ProjectRoot $projectRoot -ConfigDirectory $configDirectory
    }
    if (-not $hostRoot) { throw "Workspace config is missing a resolvable host project root" }
    return @{
        ProjectRoot = $hostRoot
        HostKey = $resolvedHostKey
    }
}

$hostSelection = Get-HostProjectRoot -ConfigPath $WorkspaceConfig -CommandId $Command -RequestedHostKey $HostKey
$hostProjectRoot = $hostSelection.ProjectRoot
$hostWrapper = Join-Path $hostProjectRoot "auto_ue_cli.ps1"
if (-not (Test-Path -LiteralPath $hostWrapper)) { throw "Host auto_ue_cli wrapper not found: $hostWrapper" }

$arguments = @($Operation)
if ($WorkspaceConfig) { $arguments += @("-WorkspaceConfig", $WorkspaceConfig) }
if ($Mode) { $arguments += @("-Mode", $Mode) }
if ($Command) { $arguments += @("-Command", $Command) }
if ($hostSelection.HostKey) { $arguments += @("-HostKey", $hostSelection.HostKey) }
if ($ActionSpec) { $arguments += @("-ActionSpec", $ActionSpec) }
if ($ParamsJson) { $arguments += @("-ParamsJson", $ParamsJson) }
if ($ParamsPath) { $arguments += @("-ParamsPath", $ParamsPath) }
if ($OutputPath) { $arguments += @("-OutputPath", $OutputPath) }
if ($RunId) { $arguments += @("-RunId", $RunId) }
if ($PSBoundParameters.ContainsKey("PostExitFinalizeWaitSeconds")) { $arguments += @("-PostExitFinalizeWaitSeconds", [string]$PostExitFinalizeWaitSeconds) }
if ($AllowDestructive) { $arguments += "-AllowDestructive" }
if ($DryRun) { $arguments += "-DryRun" }
$psArguments = @(
    "-NoProfile",
    "-ExecutionPolicy",
    "Bypass",
    "-File",
    $hostWrapper
) + $arguments
& powershell @psArguments
exit $LASTEXITCODE
