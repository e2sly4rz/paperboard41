# из корня репозитория
mkdir -p covers_webp
for f in covers/*.png; do
  base=$(basename "$f" .png)
  magick "$f" \
    -resize 100x100^ \
    -gravity center \
    -extent 100x100 \
    -strip \
    -quality 82 \
    "covers_webp/${base}.webp"
done