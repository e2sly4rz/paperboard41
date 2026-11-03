# resizer.ps1
# Конвертирует PNG/JPG/JPEG из covers\ в WebP 200×200 в covers_webp\
# Требует: ImageMagick 7 (команда `magick` в PATH)

$ErrorActionPreference = "Stop"

$SRC = "covers"
$DST = "covers_webp"

# --- Проверка ImageMagick ---
if (-not (Get-Command magick -ErrorAction SilentlyContinue)) {
    Write-Host "Ошибка: ImageMagick (команда 'magick') не найден в PATH." -ForegroundColor Red
    Write-Host "Установите ImageMagick 7: https://imagemagick.org/script/download.php#windows" -ForegroundColor Yellow
    Write-Host "При установке отметьте 'Add application directory to your system path'." -ForegroundColor Yellow
    exit 1
}

# --- Проверка исходной папки ---
if (-not (Test-Path $SRC)) {
    Write-Host "Ошибка: папка '$SRC' не найдена." -ForegroundColor Red
    exit 1
}

New-Item -ItemType Directory -Force -Path $DST | Out-Null

# Регистронезависимый поиск .png / .jpg / .jpeg
$files = Get-ChildItem -Path $SRC -File |
    Where-Object { $_.Extension -match '^\.(png|jpe?g)$' }

if ($files.Count -eq 0) {
    Write-Host "В папке '$SRC' нет PNG/JPG/JPEG." -ForegroundColor Yellow
    exit 0
}

Write-Host "Найдено файлов: $($files.Count)"

$count = 0
$failed = 0

foreach ($f in $files) {
    $name = [System.IO.Path]::GetFileNameWithoutExtension($f.Name)
    $out  = Join-Path $DST "$name.webp"

    # Вызов ImageMagick через оператор & (без склейки в строку)
    # '>' вместо '^' — безопасно на Windows, тот же смысл "обрезать до квадрата"
    & magick $f.FullName `
        -resize "200x200>" `
        -gravity center `
        -extent "200x200" `
        -strip `
        -quality 82 `
        $out 2>$null

    if ($LASTEXITCODE -eq 0 -and (Test-Path $out)) {
        $count++
        Write-Host "  ✓ $($f.Name)"
    } else {
        $failed++
        Write-Host "  ✗ $($f.Name) (ошибка конвертации)" -ForegroundColor Red
        if (Test-Path $out) { Remove-Item $out -Force }
    }

    if ($count -gt 0 -and $count % 25 -eq 0) {
        Write-Host "  ... $count / $($files.Count)"
    }
}

Write-Host ""
Write-Host "Готово: $count файлов → $DST, ошибок: $failed"