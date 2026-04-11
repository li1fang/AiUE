param(
    [string]$VerificationRoot = "",
    [string]$GateId = "",
    [string]$ReportName = "",
    [string]$Reason = "historical_archive"
)

$ErrorActionPreference = "Stop"

$repoRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
if (-not $VerificationRoot) {
    $VerificationRoot = Join-Path $repoRoot "Saved\\verification"
}

$verificationRootPath = [System.IO.Path]::GetFullPath($VerificationRoot)
if (-not (Test-Path -LiteralPath $verificationRootPath -PathType Container)) {
    throw "Verification root not found: $verificationRootPath"
}

if ([string]::IsNullOrWhiteSpace($GateId) -and [string]::IsNullOrWhiteSpace($ReportName)) {
    throw "Specify either -GateId or -ReportName."
}

function Resolve-ReportPath {
    param(
        [string]$RootPath,
        [string]$RequestedGateId,
        [string]$RequestedReportName
    )

    if (-not [string]::IsNullOrWhiteSpace($RequestedReportName)) {
        $candidate = Join-Path $RootPath $RequestedReportName
        if (-not (Test-Path -LiteralPath $candidate -PathType Leaf)) {
            throw "Report file not found: $candidate"
        }
        return [System.IO.Path]::GetFullPath($candidate)
    }

    $matches = @()
    $pattern = '"gate_id"\s*:\s*"' + [regex]::Escape($RequestedGateId) + '"'
    foreach ($candidate in Get-ChildItem -Path $RootPath -Filter "latest_*report.json" -File) {
        $match = Select-String -Path $candidate.FullName -Pattern $pattern -SimpleMatch:$false -Quiet
        if ($match) {
            $matches += $candidate.FullName
        }
    }

    if ($matches.Count -eq 0) {
        throw "No latest report found for gate_id '$RequestedGateId'."
    }
    if ($matches.Count -gt 1) {
        throw "Multiple latest reports matched gate_id '$RequestedGateId': $($matches -join ', ')"
    }
    return [System.IO.Path]::GetFullPath($matches[0])
}

$sourcePath = Resolve-ReportPath -RootPath $verificationRootPath -RequestedGateId $GateId -RequestedReportName $ReportName
if (-not $sourcePath.StartsWith($verificationRootPath, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Resolved source path is outside the verification root: $sourcePath"
}

$archiveRoot = Join-Path $verificationRootPath "archived_latest"
$archiveStamp = [DateTime]::UtcNow.ToString("yyyyMMddTHHmmssZ")
$archiveRunRoot = Join-Path $archiveRoot $archiveStamp
$destinationPath = Join-Path $archiveRunRoot ([System.IO.Path]::GetFileName($sourcePath))
$indexPath = Join-Path $archiveRoot "archive_index.json"

New-Item -ItemType Directory -Force -Path $archiveRunRoot | Out-Null
Move-Item -LiteralPath $sourcePath -Destination $destinationPath

$payload = $null
try {
    $payload = Get-Content -Raw -LiteralPath $destinationPath -Encoding utf8 | ConvertFrom-Json
} catch {
    $payload = $null
}

$archiveEntry = [ordered]@{
    archived_at_utc = [DateTime]::UtcNow.ToString("o")
    reason = $Reason
    gate_id = [string]$(if ($payload) { $payload.gate_id } else { "" })
    status = [string]$(if ($payload) { $payload.status } else { "" })
    report_name = [System.IO.Path]::GetFileName($destinationPath)
    original_path = $sourcePath
    archived_path = $destinationPath
}

$existingIndex = @()
if (Test-Path -LiteralPath $indexPath -PathType Leaf) {
    try {
        $rawIndex = Get-Content -Raw -LiteralPath $indexPath -Encoding utf8 | ConvertFrom-Json
        if ($rawIndex -is [System.Collections.IEnumerable] -and -not ($rawIndex -is [string])) {
            foreach ($item in $rawIndex) {
                $existingIndex += $item
            }
        } elseif ($null -ne $rawIndex) {
            $existingIndex += $rawIndex
        }
    } catch {
        $existingIndex = @()
    }
}
$existingIndex += $archiveEntry
$archiveJson = @($existingIndex) | ConvertTo-Json -Depth 6
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText($indexPath, $archiveJson, $utf8NoBom)

Write-Host "Archived latest report:"
Write-Host "  gate_id: $($archiveEntry.gate_id)"
Write-Host "  report_name: $($archiveEntry.report_name)"
Write-Host "  archived_path: $($archiveEntry.archived_path)"
Write-Host "  archive_index: $indexPath"
