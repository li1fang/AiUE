param(
    [Parameter(Position = 0)]
    [ValidateSet("probe", "run", "lab", "policy")]
    [string]$Verb,
    [Parameter(Position = 1)]
    [string]$Subcommand,
    [string]$WorkspaceConfig,
    [ValidateSet("dual", "all", "cmd_nullrhi", "cmd_rendered", "editor_rendered")]
    [string]$Mode = "dual",
    [string]$Command,
    [string]$ActionSpec,
    [string]$ParamsJson,
    [string]$ParamsPath,
    [string]$OutputPath,
    [string]$RunId,
    [int]$PostExitFinalizeWaitSeconds,
    [switch]$AllowDestructive,
    [switch]$DryRun,
    [ValidateSet("capture")]
    [string]$LabName,
    [string]$Focus,
    [string]$SuiteName = "weapon_split",
    [int]$ExperimentLimit,
    [string]$PackageId,
    [string]$CapabilitiesPath,
    [string]$LabReportPath,
    [string]$PreferredCaptureMode = "editor_rendered"
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$forwardedParamsPath = $null

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

function Get-WorkspacePython {
    param([string]$ConfigPath)
    if (-not $ConfigPath) { throw "AiUE requires -WorkspaceConfig for this operation" }
    $resolvedConfig = [System.IO.Path]::GetFullPath($ConfigPath)
    $raw = Get-Content -LiteralPath $resolvedConfig -Raw -Encoding UTF8 | ConvertFrom-Json
    $configDirectory = Split-Path -Parent $resolvedConfig
    $projectRoot = Split-Path -Parent $configDirectory
    $pythonPath = Resolve-WorkspacePathValue -Value $raw.paths.blender_python_exe -ProjectRoot $projectRoot -ConfigDirectory $configDirectory
    if (-not $pythonPath -or -not (Test-Path -LiteralPath $pythonPath)) { throw "Workspace config is missing a valid paths.blender_python_exe" }
    return $pythonPath
}

switch ($Verb) {
    "probe" {
        $scriptPath = Join-Path $repoRoot "adapters\powershell\probe_ue_capabilities.ps1"
        $psArgs = @(
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            $scriptPath,
            "-WorkspaceConfig",
            $WorkspaceConfig,
            "-Mode",
            $Mode
        )
        if ($RunId) { $psArgs += @("-RunId", $RunId) }
        & powershell @psArgs
        exit $LASTEXITCODE
    }
    "run" {
        $args = @("-Operation", $Verb, "-WorkspaceConfig", $WorkspaceConfig, "-Mode", $Mode)
        if ($Command) { $args += @("-Command", $Command) }
        if ($ActionSpec) { $args += @("-ActionSpec", $ActionSpec) }
        if ($ParamsPath) {
            $forwardedParamsPath = [System.IO.Path]::GetFullPath($ParamsPath)
            $args += @("-ParamsPath", $forwardedParamsPath)
        } elseif ($ParamsJson) {
            $paramsDir = Join-Path $repoRoot "Saved\cli_params"
            New-Item -ItemType Directory -Path $paramsDir -Force | Out-Null
            $forwardedParamsPath = Join-Path $paramsDir ("params_" + [guid]::NewGuid().ToString("N") + ".json")
            Set-Content -LiteralPath $forwardedParamsPath -Value $ParamsJson -Encoding UTF8
            $args += @("-ParamsPath", $forwardedParamsPath)
        }
        if ($OutputPath) { $args += @("-OutputPath", $OutputPath) }
        if ($RunId) { $args += @("-RunId", $RunId) }
        if ($PSBoundParameters.ContainsKey("PostExitFinalizeWaitSeconds")) { $args += @("-PostExitFinalizeWaitSeconds", [string]$PostExitFinalizeWaitSeconds) }
        if ($AllowDestructive) { $args += "-AllowDestructive" }
        if ($DryRun) { $args += "-DryRun" }
        $scriptPath = Join-Path $repoRoot "adapters\powershell\auto_ue_cli.ps1"
        $psArgs = @(
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            $scriptPath
        ) + $args
        try {
            & powershell @psArgs
            exit $LASTEXITCODE
        }
        finally {
            if ($ParamsJson -and $forwardedParamsPath -and (Test-Path -LiteralPath $forwardedParamsPath)) {
                Remove-Item -LiteralPath $forwardedParamsPath -Force -ErrorAction SilentlyContinue
            }
        }
    }
    "lab" {
        if (-not $LabName -and $Subcommand -eq "capture") { $LabName = "capture" }
        if ($LabName -ne "capture") { throw "Only -LabName capture is supported in this AiUE build." }
        $python = Get-WorkspacePython -ConfigPath $WorkspaceConfig
        $scriptPath = Join-Path $repoRoot "labs\capture\run_capture_lab.py"
        $args = @($scriptPath, "--workspace-config", $WorkspaceConfig, "--suite", $SuiteName)
        if ($OutputPath) { $args += @("--output-root", $OutputPath) }
        if ($ExperimentLimit) { $args += @("--experiment-limit", [string]$ExperimentLimit) }
        if ($PackageId) { $args += @("--package-id", $PackageId) }
        if ($Focus) { $args += @("--focus", $Focus) }
        & $python @args
        exit $LASTEXITCODE
    }
    "policy" {
        if (-not $Subcommand) { $Subcommand = "recommend-capture" }
        if ($Subcommand -ne "recommend-capture") { throw "Only policy recommend-capture is supported in this AiUE build." }
        $python = Get-WorkspacePython -ConfigPath $WorkspaceConfig
        $scriptPath = Join-Path $repoRoot "core\python\aiue_core\policy.py"
        if (-not $OutputPath) { $OutputPath = Join-Path $repoRoot "Saved\policy\recommended_capture_policy.json" }
        $args = @($scriptPath, "--output", $OutputPath, "--preferred-capture-mode", $PreferredCaptureMode)
        if ($CapabilitiesPath) { $args += @("--capabilities", $CapabilitiesPath) }
        if ($LabReportPath) { $args += @("--lab-report", $LabReportPath) }
        & $python @args
        exit $LASTEXITCODE
    }
}
