// convert-to-json.js
// Одноразовый скрипт: games.js → games.json
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const SRC = path.resolve('games.js');
const DST = path.resolve('games.json');

const code = fs.readFileSync(SRC, 'utf8');
const sandbox = { window: {} };
vm.createContext(sandbox);
vm.runInContext(code, sandbox);

const GAMES = sandbox.window.GAMES;
if (!Array.isArray(GAMES)) {
  console.error('window.GAMES не найден');
  process.exit(1);
}

// Сортируем по name для стабильного diff
const sorted = [...GAMES].sort((a, b) => a.name.localeCompare(b.name, 'ru'));

const data = {
  version: 3,
  updated: new Date().toISOString().slice(0, 10),
  games: sorted
};

fs.writeFileSync(DST, JSON.stringify(data, null, 2) + '\n', 'utf8');
console.log(`✅ Готово: ${sorted.length} игр → ${DST}`);