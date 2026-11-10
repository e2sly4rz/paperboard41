// modules/data.js
// Загрузка и кэширование данных каталога.

let cache = null;

export async function loadGames() {
  if (cache) return cache;

  const res = await fetch('games.json', { cache: 'no-cache' });
  if (!res.ok) throw new Error(`Не удалось загрузить games.json: ${res.status}`);

  const data = await res.json();
  if (!Array.isArray(data.games)) throw new Error('games.json: нет поля games');

  cache = data.games;
  return cache;
}

export function clearCache() {
  cache = null;
}