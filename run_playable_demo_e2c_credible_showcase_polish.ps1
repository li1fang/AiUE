param(
    [Parameter(Mandatory = $true)]
    [string]$WorkspaceConfig,
    [string]$SessionManifestPath,
    [string]$E2BReportPath,
    [string]$DV2ReportPath,
    [string]$CuratedReviewReportPath,
    [string]$ReviewNavigationReportPath,
    [string]$ReviewReplayReportPath,
    [string]$ReviewHistoryReportPath,
    [string]$ReviewCompareReportPath,
    [string]$ReviewCompareBrowseReportPath,
    [string]$OutputRoot,
    [string]$LatestReportPath,
    [string]$LatestPolishStatePath
)

$ErrorActionPreference = "Stop"

$arguments = @("--workspace-config", $WorkspaceConfig)

if ($SessionManifestPath) { $arguments += @("--session-manifest-path", $SessionManifestPath) }
if ($E2BReportPath) { $arguments += @("--e2b-report-path", $E2BReportPath) }
if ($DV2ReportPath) { $arguments += @("--dv2-report-path", $DV2ReportPath) }
if ($CuratedReviewReportPath) { $arguments += @("--curated-review-report-path", $CuratedReviewReportPath) }
if ($ReviewNavigationReportPath) { $arguments += @("--review-navigation-report-path", $ReviewNavigationReportPath) }
if ($ReviewReplayReportPath) { $arguments += @("--review-replay-report-path", $ReviewReplayReportPath) }
if ($ReviewHistoryReportPath) { $arguments += @("--review-history-report-path", $ReviewHistoryReportPath) }
if ($ReviewCompareReportPath) { $arguments += @("--review-compare-report-path", $ReviewCompareReportPath) }
if ($ReviewCompareBrowseReportPath) { $arguments += @("--review-compare-browse-report-path", $ReviewCompareBrowseReportPath) }
if ($OutputRoot) { $arguments += @("--output-root", $OutputRoot) }
if ($LatestReportPath) { $arguments += @("--latest-report-path", $LatestReportPath) }
if ($LatestPolishStatePath) { $arguments += @("--latest-polish-state-path", $LatestPolishStatePath) }

python C:\AiUE\workflows\pmx_pipeline\run_playable_demo_e2c_credible_showcase_polish.py @arguments
