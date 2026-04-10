param(
    [Parameter(Mandatory = $true)]
    [string]$BeforePath,
    [Parameter(Mandatory = $true)]
    [string]$AfterPath,
    [int]$SampleWidth = 160,
    [int]$SampleHeight = 90,
    [int]$HistogramBins = 32,
    [double]$CropX = -1,
    [double]$CropY = -1,
    [double]$CropWidth = -1,
    [double]$CropHeight = -1
)

$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Drawing

function Resolve-CropRectangle {
    param(
        [System.Drawing.Bitmap]$Bitmap,
        [double]$X,
        [double]$Y,
        [double]$Width,
        [double]$Height
    )

    $fullRect = New-Object System.Drawing.Rectangle(0, 0, $Bitmap.Width, $Bitmap.Height)
    if ($Width -le 1 -or $Height -le 1) {
        return $fullRect
    }
    $x0 = [Math]::Max(0, [int][Math]::Floor($X))
    $y0 = [Math]::Max(0, [int][Math]::Floor($Y))
    $x1 = [Math]::Min($Bitmap.Width, [int][Math]::Ceiling($X + $Width))
    $y1 = [Math]::Min($Bitmap.Height, [int][Math]::Ceiling($Y + $Height))
    if ($x1 -le $x0 -or $y1 -le $y0) {
        return $fullRect
    }
    return New-Object System.Drawing.Rectangle($x0, $y0, ($x1 - $x0), ($y1 - $y0))
}

function Get-ScaledBitmap {
    param(
        [string]$Path,
        [int]$Width,
        [int]$Height,
        [double]$RequestedCropX,
        [double]$RequestedCropY,
        [double]$RequestedCropWidth,
        [double]$RequestedCropHeight
    )

    $source = [System.Drawing.Bitmap]::FromFile($Path)
    try {
        $sourceRect = Resolve-CropRectangle -Bitmap $source -X $RequestedCropX -Y $RequestedCropY -Width $RequestedCropWidth -Height $RequestedCropHeight
        $scaled = New-Object System.Drawing.Bitmap($Width, $Height)
        $graphics = [System.Drawing.Graphics]::FromImage($scaled)
        try {
            $graphics.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
            $graphics.DrawImage(
                $source,
                (New-Object System.Drawing.Rectangle(0, 0, $Width, $Height)),
                $sourceRect,
                [System.Drawing.GraphicsUnit]::Pixel
            )
        }
        finally {
            $graphics.Dispose()
        }
        return @{
            bitmap = $scaled
            crop_rect = @{
                x = $sourceRect.X
                y = $sourceRect.Y
                width = $sourceRect.Width
                height = $sourceRect.Height
            }
            original_width = $source.Width
            original_height = $source.Height
        }
    }
    finally {
        $source.Dispose()
    }
}

$beforeResolved = [System.IO.Path]::GetFullPath($BeforePath)
$afterResolved = [System.IO.Path]::GetFullPath($AfterPath)
if (-not (Test-Path -LiteralPath $beforeResolved)) { throw "Before image missing: $beforeResolved" }
if (-not (Test-Path -LiteralPath $afterResolved)) { throw "After image missing: $afterResolved" }

$beforeScaled = Get-ScaledBitmap -Path $beforeResolved -Width $SampleWidth -Height $SampleHeight -RequestedCropX $CropX -RequestedCropY $CropY -RequestedCropWidth $CropWidth -RequestedCropHeight $CropHeight
$afterScaled = Get-ScaledBitmap -Path $afterResolved -Width $SampleWidth -Height $SampleHeight -RequestedCropX $CropX -RequestedCropY $CropY -RequestedCropWidth $CropWidth -RequestedCropHeight $CropHeight
$beforeBitmap = $beforeScaled.bitmap
$afterBitmap = $afterScaled.bitmap

try {
    $binCount = [Math]::Max(4, $HistogramBins)
    $histBefore = New-Object 'double[]' $binCount
    $histAfter = New-Object 'double[]' $binCount
    $sumBefore = 0.0
    $sumAfter = 0.0
    $sumAbsDelta = 0.0
    $pixelCount = $SampleWidth * $SampleHeight
    $binWidth = 256.0 / [double]$binCount

    for ($y = 0; $y -lt $SampleHeight; $y++) {
        for ($x = 0; $x -lt $SampleWidth; $x++) {
            $beforeColor = $beforeBitmap.GetPixel($x, $y)
            $afterColor = $afterBitmap.GetPixel($x, $y)

            $beforeLuma = [int][Math]::Round((0.299 * $beforeColor.R) + (0.587 * $beforeColor.G) + (0.114 * $beforeColor.B))
            $afterLuma = [int][Math]::Round((0.299 * $afterColor.R) + (0.587 * $afterColor.G) + (0.114 * $afterColor.B))

            $beforeBin = [Math]::Min($binCount - 1, [int][Math]::Floor($beforeLuma / $binWidth))
            $afterBin = [Math]::Min($binCount - 1, [int][Math]::Floor($afterLuma / $binWidth))
            $histBefore[$beforeBin] += 1.0
            $histAfter[$afterBin] += 1.0

            $sumBefore += $beforeLuma
            $sumAfter += $afterLuma
            $sumAbsDelta += [Math]::Abs($afterLuma - $beforeLuma)
        }
    }

    $histogramL1 = 0.0
    for ($index = 0; $index -lt $binCount; $index++) {
        $normalizedBefore = $histBefore[$index] / [double]$pixelCount
        $normalizedAfter = $histAfter[$index] / [double]$pixelCount
        $histogramL1 += [Math]::Abs($normalizedBefore - $normalizedAfter)
    }

    $result = @{
        before_path = $beforeResolved
        after_path = $afterResolved
        crop_rect = $beforeScaled.crop_rect
        original_width = $beforeScaled.original_width
        original_height = $beforeScaled.original_height
        sample_width = $SampleWidth
        sample_height = $SampleHeight
        pixel_count = $pixelCount
        histogram_bins = $binCount
        histogram_l1 = [double]$histogramL1
        mean_abs_pixel_delta = [double]($sumAbsDelta / ([double]$pixelCount * 255.0))
        mean_luma_before = [double]($sumBefore / [double]$pixelCount)
        mean_luma_after = [double]($sumAfter / [double]$pixelCount)
    }

    $result | ConvertTo-Json -Compress
}
finally {
    $beforeBitmap.Dispose()
    $afterBitmap.Dispose()
}
