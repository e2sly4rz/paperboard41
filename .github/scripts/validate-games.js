// .github/scripts/validate-games.js
// Валидатор каталога. Запускается в CI на каждый push.
// Читает catalog/games.json, проверяет структуру и целостность.
// Падает с exit code 1, если есть ошибки.

const fs = require('fs');
const path = require('path');

const GAMES_FILE = path.resolve('catalog/games.json');
const COVERS_DIR = path.resolve('catalog/covers_webp');

if (!fs.existsSync(GAMES_FILE)) {
  console.error(`✗ Файл не найден: ${GAMES_FILE}`);
  process.exit(1);
}

let data;
try {
  data = JSON.parse(fs.readFileSync(GAMES_FILE, 'utf8'));
} catch (e) {
  console.error(`✗ games.json невалидный JSON: ${e.message}`);
  process.exit(1);
}

if (!Array.isArray(data.games) || data.games.length === 0) {
  console.error('✗ games.json: нет массива games или он пуст');
  process.exit(1);
}

const GAMES = data.games;

const errors = [];
const warnings = [];
const names  = new Set();
const ids    = new Set();
const bggIds = new Set();

const coverFiles = fs.existsSync(COVERS_DIR)
  ? new Set(fs.readdirSync(COVERS_DIR))
  : new Set();

if (coverFiles.size === 0) {
  warnings.push(`Папка ${COVERS_DIR} не найдена или пуста — проверка обложек пропущена`);
}

GAMES.forEach((g, i) => {
  const label = `#${i} «${g.name || '?'}»`;
  const err  = (m) => errors.push(`${label}: ${m}`);
  const warn = (m) => warnings.push(`${label}: ${m}`);

  // name
  if (typeof g.name !== 'string' || !g.name.trim()) err('нет name');
  else {
    if (names.has(g.name)) err('дубликат name');
    names.add(g.name);
  }

  // id
  if (g.id === undefined || g.id === null || g.id === '') {
    warn('нет id (URL будет нестабильным)');
  } else {
    if (typeof g.id !== 'string' && typeof g.id !== 'number') {
      err(`id=${g.id} (должен быть строкой или числом)`);
    } else {
      const idStr = String(g.id);
      if (ids.has(idStr)) err(`дубликат id «${idStr}»`);
      ids.add(idStr);
    }
  }

  // difficulty
  if (typeof g.difficulty !== 'number' ||
      g.difficulty < 0.5 || g.difficulty > 5 ||
      (g.difficulty * 2) % 1 !== 0) {
    err(`difficulty=${g.difficulty} (должно быть 0.5…5 с шагом 0.5)`);
  }

  // players
  if (!Number.isInteger(g.minPlayers) || !Number.isInteger(g.maxPlayers)) {
    err(`игроки ${g.minPlayers}–${g.maxPlayers} (должны быть целыми)`);
  } else if (g.minPlayers > g.maxPlayers) {
    err(`minPlayers=${g.minPlayers} > maxPlayers=${g.maxPlayers}`);
  } else if (g.minPlayers < 1) {
    err(`minPlayers=${g.minPlayers} (должно быть ≥ 1)`);
  }

  // special
  if (typeof g.special !== 'boolean') err('special не boolean');

  // expansions
  if (!Array.isArray(g.expansions)) err('expansions не массив');

  // description
  if (typeof g.description !== 'string') err('description не строка');
  else if (g.description.length > 350) {
    warn(`description > 350 символов (${g.description.length})`);
  }

  // bggId
  if (g.bggId !== undefined && g.bggId !== null) {
    if (!Number.isInteger(g.bggId)) {
      err(`bggId=${g.bggId} (должен быть целым числом)`);
    } else {
      if (bggIds.has(g.bggId)) err(`дубликат bggId ${g.bggId}`);
      bggIds.add(g.bggId);

      // Проверка наличия обложки
      if (coverFiles.size > 0 && !coverFiles.has(`${g.bggId}.webp`)) {
        warn(`нет обложки covers_webp/${g.bggId}.webp`);
      }
    }
  }
});

// === Вывод ===
console.log(`Проверено игр: ${GAMES.length}`);
console.log(`Уникальных id: ${ids.size}`);
console.log(`Уникальных bggId: ${bggIds.size}`);
console.log(`Файлов обложек: ${coverFiles.size}`);
console.log('');

if (warnings.length) {
  console.warn('⚠️  Предупреждения:');
  warnings.forEach(w => console.warn('  ' + w));
  console.warn('');
}

if (errors.length) {
  console.error('❌ Ошибки:');
  errors.forEach(e => console.error('  ' + e));
  console.error(`\nВсего ошибок: ${errors.length}`);
  process.exit(1);
}

console.log(`✅ Валидация пройдена: ${GAMES.length} игр`);
if (warnings.length) {
  console.log(`   (предупреждений: ${warnings.length} — не блокируют деплой)`);
}