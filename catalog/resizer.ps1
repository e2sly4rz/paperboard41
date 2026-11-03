# resizer.ps1
# Converts PNG/JPG/JPEG from covers\ to WebP 200x200 in covers_webp\
# Non-square images are padded to square with TRANSPARENT background.

$ErrorActionPreference = "Stop"

$SRC = "covers"
$DST = "covers_webp"

if (-not (Get-Command magick -ErrorAction SilentlyContinue)) {
    Write-Host "ERROR: ImageMagick ('magick') not found in PATH." -ForegroundColor Red
    Write-Host "Install: https://imagemagick.org/script/download.php#windows" -ForegroundColor Yellow
    exit 1
}

if (-not (Test-Path $SRC)) {
    Write-Host "ERROR: folder '$SRC' not found." -ForegroundColor Red
    exit 1
}

New-Item -ItemType Directory -Force -Path $DST | Out-Null

$files = Get-ChildItem -Path $SRC -File |
    Where-Object { $_.Extension -match '^\.(png|jpe?g)$' }

if ($files.Count -eq 0) {
    Write-Host "No PNG/JPG/JPEG files in '$SRC'." -ForegroundColor Yellow
    exit 0
}

Write-Host "Found files: $($files.Count)"

$count = 0
$failed = 0

foreach ($f in $files) {
    $name = [System.IO.Path]::GetFileNameWithoutExtension($f.Name)
    $out  = Join-Path $DST "$name.webp"

    # >  = fit inside 200x200 keeping aspect (no crop)
    # -background none + -extent = pad to square with TRANSPARENT
    & magick $f.FullName `
        -resize "200x200>" `
        -gravity center `
        -background none `
        -extent "200x200" `
        -strip `
        -quality 82 `
        $out 2>$null

    if ($LASTEXITCODE -eq 0 -and (Test-Path $out)) {
        $count++
        Write-Host "  OK $($f.Name)"
    } else {
        $failed++
        Write-Host "  FAIL $($f.Name)" -ForegroundColor Red
        if (Test-Path $out) { Remove-Item $out -Force }
    }

    if ($count -gt 0 -and $count % 25 -eq 0) {
        Write-Host "  ... $count / $($files.Count)"
    }
}

Write-Host ""
Write-Host "Done: $count files -> $DST, errors: $failed"