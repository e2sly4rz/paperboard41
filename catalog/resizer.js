// resizer.js
// Конвертирует PNG/JPG/JPEG из covers/ в WebP 200×200 в covers_webp/
// Требует: npm install sharp

const sharp = require("sharp");
const fs = require("fs");
const path = require("path");

const SRC = "covers";
const DST = "covers_webp";
const SIZE = 200;
const QUALITY = 82;

if (!fs.existsSync(SRC)) {
  console.error(`Ошибка: папка '${SRC}' не найдена.`);
  process.exit(1);
}

fs.mkdirSync(DST, { recursive: true });

// jpe?g — jpg и jpeg, i — регистронезависимо
const EXT = /\.(png|jpe?g)$/i;
const files = fs.readdirSync(SRC).filter(f => EXT.test(f));

if (files.length === 0) {
  console.log(`В папке '${SRC}' нет PNG/JPG/JPEG.`);
  process.exit(0);
}

console.log(`Найдено файлов: ${files.length}`);

(async () => {
  let done = 0, failed = 0;

  for (const f of files) {
    const base = path.basename(f, path.extname(f));
    const src = path.join(SRC, f);
    const dst = path.join(DST, `${base}.webp`);

    try {
      await sharp(src)
        .resize(SIZE, SIZE, { fit: "cover", position: "centre" })
        .webp({ quality: QUALITY, effort: 6 })
        .toFile(dst);
      done++;
      console.log(`  ✓ ${f}`);
    } catch (e) {
      failed++;
      console.error(`  ✗ ${f}: ${e.message}`);
      // Чистим возможный битый выход
      if (fs.existsSync(dst)) fs.unlinkSync(dst);
    }

    if (done % 25 === 0 && done > 0) {
      console.log(`  ... ${done}/${files.length}`);
    }
  }

  console.log(`\nГотово: ${done} → ${DST}/, ошибок: ${failed}`);
})();