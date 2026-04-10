param(
    [string]$WorkspaceConfig = "C:\AiUE\local\pipeline_workspace.local.json",
    [string]$R2ReportPath,
    [string]$OutputRoot,
    [string]$LatestReportPath,
    [string]$FxSlotName = "fx",
    [string]$FxAssetPath,
    [string]$FxAttachSocketName,
    [double]$TrackedFxMinCoverage = 0.03,
    [double]$CropHistogramL1Threshold = 0.0025,
    [double]$CropMeanAbsPixelDeltaThreshold = 0.001,
    [double]$FullFrameHistogramL1Threshold = 0.001,
    [double]$FullFrameMeanAbsPixelDeltaThreshold = 0.00035,
    [double]$NiagaraDesiredAgeSeconds = 0.08,
    [double]$NiagaraSeekDeltaSeconds = (1.0 / 60.0),
    [int]$NiagaraAdvanceStepCount = 4,
    [double]$NiagaraAdvanceStepDeltaSeconds = (1.0 / 60.0),
    [string]$SceneCaptureSource = "SCS_FINAL_COLOR_HDR",
    [int]$SceneCaptureWarmupCount = 4,
    [double]$SceneCaptureWarmupDelaySeconds = 0.08
)

$ErrorActionPreference = "Stop"
$pythonExe = "C:\Program Files\Epic Games\UE_5.7\Engine\Binaries\ThirdParty\Python3\Win64\python.exe"
$scriptPath = Join-Path $PSScriptRoot "workflows\pmx_pipeline\run_live_fx_visual_quality_r3.py"

$arguments = @(
    $scriptPath,
    "--workspace-config",
    $WorkspaceConfig,
    "--fx-slot-name",
    $FxSlotName,
    "--niagara-desired-age-seconds",
    $NiagaraDesiredAgeSeconds,
    "--niagara-seek-delta-seconds",
    $NiagaraSeekDeltaSeconds,
    "--niagara-advance-step-count",
    $NiagaraAdvanceStepCount,
    "--niagara-advance-step-delta-seconds",
    $NiagaraAdvanceStepDeltaSeconds,
    "--scene-capture-warmup-count",
    $SceneCaptureWarmupCount,
    "--scene-capture-warmup-delay-seconds",
    $SceneCaptureWarmupDelaySeconds,
    "--tracked-fx-min-coverage",
    $TrackedFxMinCoverage,
    "--crop-histogram-l1-threshold",
    $CropHistogramL1Threshold,
    "--crop-mean-abs-pixel-delta-threshold",
    $CropMeanAbsPixelDeltaThreshold,
    "--full-frame-histogram-l1-threshold",
    $FullFrameHistogramL1Threshold,
    "--full-frame-mean-abs-pixel-delta-threshold",
    $FullFrameMeanAbsPixelDeltaThreshold
)
if ($R2ReportPath) { $arguments += @("--r2-report-path", $R2ReportPath) }
if ($OutputRoot) { $arguments += @("--output-root", $OutputRoot) }
if ($LatestReportPath) { $arguments += @("--latest-report-path", $LatestReportPath) }
if ($FxAssetPath) { $arguments += @("--fx-asset-path", $FxAssetPath) }
if ($FxAttachSocketName) { $arguments += @("--fx-attach-socket-name", $FxAttachSocketName) }
if ($SceneCaptureSource) { $arguments += @("--scene-capture-source", $SceneCaptureSource) }

& $pythonExe @arguments
exit $LASTEXITCODE
