#!/usr/bin/env bash
# resizer.sh
# Конвертирует PNG/JPG/JPEG из covers/ в WebP 100×100 в covers_webp/
# Требует: ImageMagick 7 (команда `magick`)

set -euo pipefail

SRC="covers"
DST="covers_webp"

mkdir -p "$DST"

# find + -iname — регистронезависимо (.png, .PNG, .jpg, .JPG, .jpeg, .JPEG)
count=0
skipped=0

while IFS= read -r -d '' f; do
  base=$(basename "$f")
  name="${base%.*}"          # отрезаем любое расширение

  if magick "$f" \
      -resize 200x200^ \
      -gravity center \
      -extent 200x200 \
      -strip \
      -quality 82 \
      "$DST/${name}.webp" 2>/dev/null; then
    count=$((count + 1))
    printf '  ✓ %s\n' "$base"
  else
    skipped=$((skipped + 1))
    printf '  ✗ %s (ошибка конвертации)\n' "$base"
  fi
done < <(find "$SRC" -maxdepth 1 -type f \( \
  -iname '*.png' -o -iname '*.jpg' -o -iname '*.jpeg' \
\) -print0)

echo
echo "Готово: $count файлов → $DST/, пропущено/ошибок: $skipped"