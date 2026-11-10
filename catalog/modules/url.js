// modules/url.js
// Синхронизация состояния с URL.

const SORT_KEYS = ['name', 'difficulty', 'players', 'time', 'genre', 'access'];

export function readStateFromURL() {
  const params = new URLSearchParams(location.search);
  return {
    q:      params.get('q')     || '',
    diff:   params.get('diff')  || 'any',
    genre:  params.get('genre') || '',
    players: params.get('p')    || '0',
    access: params.get('a')     || 'all',
    sortKey: (() => {
      const s = params.get('sort');
      if (!s) return 'name';
      const [k] = s.split(':');
      return SORT_KEYS.includes(k) ? k : 'name';
    })(),
    sortDir: (() => {
      const s = params.get('sort');
      if (!s) return 'asc';
      const [, d] = s.split(':');
      return d === 'desc' ? 'desc' : 'asc';
    })(),
    openId: params.get('game') || null
  };
}

export function writeStateToURL(state) {
  const params = new URLSearchParams();
  if (state.q.trim())                 params.set('q', state.q.trim());
  if (state.diff !== 'any')           params.set('diff', state.diff);
  if (state.genre)                    params.set('genre', state.genre);
  if (state.players !== '0')          params.set('p', state.players);
  if (state.access !== 'all')         params.set('a', state.access);
  if (state.sortKey !== 'name' || state.sortDir !== 'asc') {
    params.set('sort', `${state.sortKey}:${state.sortDir}`);
  }
  if (state.openId)                   params.set('game', state.openId);

  const qs = params.toString();
  const url = qs ? `?${qs}` : location.pathname;
  history.replaceState(null, '', url);
}