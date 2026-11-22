#!/usr/bin/env bash
# resizer.sh
# Конвертирует PNG/JPG/JPEG/WebP из covers/ в WebP 200x200 в covers_webp/
# Не-квадратные изображения дополняются до квадрата ПРОЗРАЧНЫМ фоном.
# Пропускает файлы, которые уже есть в covers_webp/.
# Требует: ImageMagick 7 (команда `magick`)

set -euo pipefail

SRC="covers"
DST="covers_webp"

mkdir -p "$DST"

# find + -iname — регистронезависимо (.png, .PNG, .jpg, .JPG, .jpeg, .JPEG, .webp, .WEBP)
count=0
skipped=0
failed=0

while IFS= read -r -d '' f; do
  base=$(basename "$f")
  name="${base%.*}"          # отрезаем любое расширение
  out="$DST/${name}.webp"

  # Пропускаем, если уже сконвертирован
  if [ -e "$out" ]; then
    skipped=$((skipped + 1))
    printf '  SKIP %s (already exists)\n' "$base"
    continue
  fi

  # >  = вписать в 200x200, сохранив пропорции (без обрезки)
  # -background none + -extent = добить до квадрата ПРОЗРАЧНЫМ
  if magick "$f" \
      -resize "200x200>" \
      -gravity center \
      -background none \
      -extent "200x200" \
      -strip \
      -quality 82 \
      "$out" 2>/dev/null; then
    count=$((count + 1))
    printf '  OK %s\n' "$base"
  else
    failed=$((failed + 1))
    printf '  FAIL %s\n' "$base"
    [ -e "$out" ] && rm -f "$out"
  fi

  if [ "$count" -gt 0 ] && [ $((count % 25)) -eq 0 ]; then
    printf '  ... %d / %d\n' "$count" "$(find "$SRC" -maxdepth 1 -type f \( \
      -iname '*.png' -o -iname '*.jpg' -o -iname '*.jpeg' -o -iname '*.webp' \
    \) | wc -l)"
  fi
done < <(find "$SRC" -maxdepth 1 -type f \( \
  -iname '*.png' -o -iname '*.jpg' -o -iname '*.jpeg' -o -iname '*.webp' \
\) -print0)

echo
echo "Done: converted $count, skipped $skipped, errors $failed -> $DST"