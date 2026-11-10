// .github/scripts/validate-games.js
// Валидатор каталога. Запускается в CI на каждый push.
// Падает с exit code 1, если есть ошибки.

const fs = require('fs');
const path = require('path');
const vm = require('vm');

const GAMES_FILE = path.resolve('catalog/games.js');
const COVERS_DIR = path.resolve('catalog/covers_webp');

if (!fs.existsSync(GAMES_FILE)) {
  console.error(`✗ Файл не найден: ${GAMES_FILE}`);
  process.exit(1);
}

// Загружаем games.js в песочницу, чтобы получить window.GAMES
const code = fs.readFileSync(GAMES_FILE, 'utf8');
const sandbox = { window: {} };
vm.createContext(sandbox);
vm.runInContext(code, sandbox);

const GAMES = sandbox.window.GAMES;
if (!Array.isArray(GAMES) || GAMES.length === 0) {
  console.error('✗ window.GAMES не массив или пуст');
  process.exit(1);
}

const errors = [];
const warnings = [];
const names = new Set();
const ids   = new Set();
const bggIds = new Set();

const coverFiles = fs.existsSync(COVERS_DIR)
  ? new Set(fs.readdirSync(COVERS_DIR))
  : new Set();

GAMES.forEach((g, i) => {
  const label = `#${i} «${g.name || '?'}»`;
  const err = (m) => errors.push(`${label}: ${m}`);
  const warn = (m) => warnings.push(`${label}: ${m}`);

  if (typeof g.name !== 'string' || !g.name) err('нет name');
  if (names.has(g.name)) err('дубликат name');
  names.add(g.name);

  if (g.id === undefined) warn('нет id (будет сгенерирован)');
  else {
    if (ids.has(g.id)) err(`дубликат id «${g.id}»`);
    ids.add(g.id);
  }

  if (typeof g.difficulty !== 'number' || g.difficulty < 0.5 || g.difficulty > 5 || (g.difficulty * 2) % 1 !== 0)
    err(`difficulty=${g.difficulty} (должно быть 0.5…5 с шагом 0.5)`);

  if (!Number.isInteger(g.minPlayers) || !Number.isInteger(g.maxPlayers))
    err(`игроки ${g.minPlayers}–${g.maxPlayers} (должны быть целыми)`);
  else if (g.minPlayers > g.maxPlayers)
    err(`minPlayers=${g.minPlayers} > maxPlayers=${g.maxPlayers}`);

  if (typeof g.special !== 'boolean') err('special не boolean');
  if (!Array.isArray(g.expansions)) err('expansions не массив');
  if (typeof g.description !== 'string') err('description не строка');

  if (g.bggId !== undefined) {
    if (!Number.isInteger(g.bggId)) err(`bggId=${g.bggId} (должен быть числом)`);
    else if (bggIds.has(g.bggId)) err(`дубликат bggId ${g.bggId}`);
    else bggIds.add(g.bggId);

    // Проверяем, что обложка существует
    if (coverFiles.size > 0 && !coverFiles.has(`${g.bggId}.webp`)) {
      warn(`нет обложки covers_webp/${g.bggId}.webp`);
    }
  }

  // Длина описания (мягкое предупреждение)
  if (typeof g.description === 'string' && g.description.length > 350) {
    warn(`description > 350 символов (${g.description.length})`);
  }
});

// Вывод
if (warnings.length) {
  console.warn('\n⚠️  Предупреждения:');
  warnings.forEach(w => console.warn('  ' + w));
}

if (errors.length) {
  console.error('\n❌ Ошибки:');
  errors.forEach(e => console.error('  ' + e));
  console.error(`\nВсего ошибок: ${errors.length}`);
  process.exit(1);
}

console.log(`\n✅ Валидация пройдена: ${GAMES.length} игр, ${ids.size} id, ${bggIds.size} bggId`);
if (warnings.length) console.log(`   (предупреждений: ${warnings.length} — не блокируют деплой)`);