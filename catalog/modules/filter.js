// modules/filter.js
// Чистые функции фильтрации и сортировки.
// Не зависят от DOM — можно тестировать в Node.

export function parseTime(s) {
  if (!s) return { min: 0, max: 0 };
  const nums = String(s).match(/\d+/g);
  if (!nums) return { min: 0, max: 0 };
  const n = nums.map(Number);
  return n.length === 1
    ? { min: n[0], max: n[0] }
    : { min: Math.min(...n), max: Math.max(...n) };
}

export function filterGames(games, filters) {
  const { q, diff, genre, players, access } = filters;

  let dMin = 0, dMax = 5;
  if (diff && diff !== 'any') {
    const [lo, hi] = diff.split('-').map(Number);
    dMin = lo; dMax = hi;
  }

  return games.filter(game => {
    if (q) {
      const haystack = [
        game.name,
        ...(game.expansions || [])
      ].join(' ').toLowerCase();
      if (!haystack.includes(q)) return false;
    }
    if (game.difficulty < dMin || game.difficulty > dMax) return false;
    if (genre && game.genre !== genre) return false;
    if (players > 0 && !(game.minPlayers <= players && game.maxPlayers >= players)) return false;
    if (access === 'yes' && !game.special) return false;
    if (access === 'no' && game.special) return false;
    return true;
  });
}

export function sortGames(games, sortKey, sortDir) {
  const dir = sortDir === 'asc' ? 1 : -1;

  const cmp = (a, b) => {
    let va, vb;
    switch (sortKey) {
      case 'difficulty':
        va = a.difficulty; vb = b.difficulty; break;
      case 'players':
        va = a.minPlayers * 1000 + a.maxPlayers;
        vb = b.minPlayers * 1000 + b.maxPlayers; break;
      case 'time': {
        const ta = parseTime(a.time), tb = parseTime(b.time);
        va = ta.min * 10000 + ta.max;
        vb = tb.min * 10000 + tb.max; break;
      }
      case 'genre':
        va = a.genre || '\uffff';
        vb = b.genre || '\uffff'; break;
      case 'access':
        va = a.special ? 0 : 1;
        vb = b.special ? 0 : 1; break;
      default:
        va = a.name; vb = b.name;
    }
    let r = typeof va === 'string'
      ? va.localeCompare(vb, 'ru')
      : va - vb;
    if (r === 0) r = a.name.localeCompare(b.name, 'ru');
    return r * dir;
  };

  return [...games].sort(cmp);
}

export function makeScale(score) {
  const filled = Math.max(0, Math.min(9, Math.round(score * 2)));
  return '[' + '\u2588'.repeat(filled) + '\u2591'.repeat(9 - filled) + ']';
}

export function esc(s) {
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}