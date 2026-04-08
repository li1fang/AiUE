param(
    [string]$OutputRoot,
    [switch]$FailOnLeaks
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$runId = (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssZ")
$bundleRootBase = if ($OutputRoot) { [System.IO.Path]::GetFullPath($OutputRoot) } else { Join-Path $repoRoot "Saved\open_source_bundle" }
$bundleRoot = Join-Path $bundleRootBase $runId
$reportPath = Join-Path $bundleRoot "open_source_readiness_report.json"
$includeRoots = @(
    ".github",
    "docs",
    "schemas",
    "core",
    "adapters",
    "workflows",
    "labs",
    "examples",
    "tools",
    ".gitignore",
    "README.md",
    "WHITEPAPER.md",
    "ROADMAP.md",
    "GOVERNANCE.md",
    "CONTRIBUTING.md",
    "CODE_OF_CONDUCT.md",
    "SECURITY.md",
    "SUPPORT.md",
    "CHANGELOG.md",
    "LICENSE",
    "aiue.ps1",
    "run_alpha_triplines.ps1"
)

function Copy-IncludeItem {
    param([string]$RelativePath)
    $sourcePath = Join-Path $repoRoot $RelativePath
    if (-not (Test-Path -LiteralPath $sourcePath)) { return @() }
    $copied = @()
    if ((Get-Item -LiteralPath $sourcePath).PSIsContainer) {
        Get-ChildItem -LiteralPath $sourcePath -Recurse -File | Where-Object {
            $_.FullName -notmatch '\\__pycache__\\' -and
            $_.Extension -ne '.pyc'
        } | ForEach-Object {
            $relative = $_.FullName.Substring($repoRoot.Length).TrimStart('\')
            $destination = Join-Path $bundleRoot $relative
            $destinationDir = Split-Path -Parent $destination
            if (-not (Test-Path -LiteralPath $destinationDir)) { New-Item -ItemType Directory -Path $destinationDir -Force | Out-Null }
            Copy-Item -LiteralPath $_.FullName -Destination $destination -Force
            $copied += $destination
        }
    } else {
        $destination = Join-Path $bundleRoot $RelativePath
        $destinationDir = Split-Path -Parent $destination
        if (-not (Test-Path -LiteralPath $destinationDir)) { New-Item -ItemType Directory -Path $destinationDir -Force | Out-Null }
        Copy-Item -LiteralPath $sourcePath -Destination $destination -Force
        $copied += $destination
    }
    return $copied
}

function Find-PatternHits {
    param([string[]]$Paths, [string[]]$Patterns)
    $hits = @()
    foreach ($path in $Paths) {
        if (-not (Test-Path -LiteralPath $path)) { continue }
        $item = Get-Item -LiteralPath $path
        if ($item.PSIsContainer) { continue }
        $matches = Select-String -LiteralPath $path -Pattern $Patterns
        foreach ($match in $matches) {
            $hits += [PSCustomObject]@{ path = $path; line_number = $match.LineNumber; line = $match.Line.Trim() }
        }
    }
    return $hits
}

$hostLeakPatterns = @(
    ("Documents\\Unreal Projects\\" + "test1"),
    ("test1" + ".uproject")
)

New-Item -ItemType Directory -Path $bundleRoot -Force | Out-Null
$copiedFiles = @()
foreach ($relativePath in $includeRoots) { $copiedFiles += Copy-IncludeItem -RelativePath $relativePath }
$report = [ordered]@{
    generated_at_utc = ([datetime]::UtcNow.ToString("s") + "Z")
    bundle_root = $bundleRoot
    included_files = $copiedFiles
    private_path_hits = Find-PatternHits -Paths $copiedFiles -Patterns @("C:\\Users\\")
    host_naming_hits = Find-PatternHits -Paths $copiedFiles -Patterns $hostLeakPatterns
}
$report.ready_for_public_export = (@($report.private_path_hits).Count -eq 0 -and @($report.host_naming_hits).Count -eq 0)
$json = $report | ConvertTo-Json -Depth 8
[System.IO.File]::WriteAllText($reportPath, $json + [Environment]::NewLine, [System.Text.UTF8Encoding]::new($false))
Write-Host "AiUE open-source bundle exported to: $bundleRoot"
Write-Host "Readiness report written to: $reportPath"
if ($FailOnLeaks -and -not $report.ready_for_public_export) {
    throw "AiUE open-source bundle audit failed."
}
