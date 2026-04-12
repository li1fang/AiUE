param(
    [Parameter(Mandatory = $true)]
    [string]$WorkspaceConfig,
    [string]$SessionManifestPath,
    [string]$CandidateManifestPath,
    [string]$E2CReportPath,
    [string]$DV2ReportPath,
    [string]$DynamicBalanceReportPath,
    [string]$OutputRoot,
    [string]$LatestReportPath,
    [string]$LatestProviderStatePath,
    [string]$LatestProviderContextPath,
    [string]$LatestCandidateManifestPath
)

$ErrorActionPreference = "Stop"
$arguments = @("--workspace-config", $WorkspaceConfig)

if ($SessionManifestPath) { $arguments += @("--session-manifest-path", $SessionManifestPath) }
if ($CandidateManifestPath) { $arguments += @("--candidate-manifest-path", $CandidateManifestPath) }
if ($E2CReportPath) { $arguments += @("--e2c-report-path", $E2CReportPath) }
if ($DV2ReportPath) { $arguments += @("--dv2-report-path", $DV2ReportPath) }
if ($DynamicBalanceReportPath) { $arguments += @("--dynamic-balance-report-path", $DynamicBalanceReportPath) }
if ($OutputRoot) { $arguments += @("--output-root", $OutputRoot) }
if ($LatestReportPath) { $arguments += @("--latest-report-path", $LatestReportPath) }
if ($LatestProviderStatePath) { $arguments += @("--latest-provider-state-path", $LatestProviderStatePath) }
if ($LatestProviderContextPath) { $arguments += @("--latest-provider-context-path", $LatestProviderContextPath) }
if ($LatestCandidateManifestPath) { $arguments += @("--latest-candidate-manifest-path", $LatestCandidateManifestPath) }

python C:\AiUE\workflows\pmx_pipeline\run_action_candidate_provider_a1.py @arguments
exit $LASTEXITCODE
