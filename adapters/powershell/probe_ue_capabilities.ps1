param(
    [string]$WorkspaceConfig,
    [ValidateSet("dual", "all", "cmd_nullrhi", "cmd_rendered", "editor_rendered")]
    [string]$Mode = "dual",
    [string]$RunId
)

$ErrorActionPreference = "Stop"
$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$wrapper = Join-Path $scriptRoot "auto_ue_cli.ps1"
$arguments = @(
    "-NoProfile",
    "-ExecutionPolicy",
    "Bypass",
    "-File",
    $wrapper,
    "-Operation",
    "probe",
    "-WorkspaceConfig",
    $WorkspaceConfig,
    "-Mode",
    $Mode
)
if ($RunId) { $arguments += @("-RunId", $RunId) }
& powershell @arguments
exit $LASTEXITCODE
