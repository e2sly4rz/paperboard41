// app.js
// Точка входа. Импортирует модули и связывает их с DOM.

import { loadGames } from './modules/data.js';
import { filterGames, sortGames } from './modules/filter.js';
import { readStateFromURL, writeStateToURL } from './modules/url.js';
import { renderGames } from './modules/render.js';
import { initThemeToggle } from './modules/theme.js';

const $ = (sel) => document.querySelector(sel);

const tbody        = $('#tbody');
const countEl      = $('#count');
const emptyEl      = $('#empty');
const searchInput  = $('#search');
const genreSel     = $('#filter-genre');
const diffChips    = $('#filter-difficulty');
const playersChips = $('#filter-players');
const accessChips  = $('#filter-access');
const resetBtn     = $('#reset');
const resetEmpty   = $('#reset-empty');
const thead        = $('.catalog-table thead');

let GAMES = [];
let state = {
  q: '', diff: 'any', genre: '', players: '0', access: 'all',
  sortKey: 'name', sortDir: 'asc', openId: null
};

// === Чипы ===
const chipValue = (container) =>
  container?.querySelector('.chip.is-active')?.dataset.value ?? null;

const setChipValue = (container, value) => {
  if (!container) return;
  container.querySelectorAll('.chip').forEach(chip => {
    chip.classList.toggle('is-active', chip.dataset.value === String(value));
  });
};

// === Рендер ===
function render() {
  const filtered = sortGames(filterGames(GAMES, {
    q: state.q.toLowerCase().trim(),
    diff: state.diff,
    genre: state.genre,
    players: parseInt(state.players, 10) || 0,
    access: state.access
  }), state.sortKey, state.sortDir);

  if (state.openId && !filtered.some(g => g.id === state.openId)) {
    state.openId = null;
  }

  renderGames(tbody, filtered, state);
  countEl.textContent = `Найдено: ${filtered.length} из ${GAMES.length}`;
  emptyEl.hidden = filtered.length !== 0;

  // Индикаторы сортировки
  document.querySelectorAll('.catalog-table th.sortable').forEach(th => {
    const key = th.dataset.sort;
    th.setAttribute(
      'aria-sort',
      key === state.sortKey
        ? (state.sortDir === 'asc' ? 'ascending' : 'descending')
        : 'none'
    );
  });

  writeStateToURL(state);
}

// === Раскрытие ===
function toggleRow(row) {
  const id = row.dataset.id;
  if (!id) return;
  if (row.getAttribute('aria-disabled') === 'true') return;

  if (state.openId === id) {
    state.openId = null;
    row.classList.remove('is-open');
    row.setAttribute('aria-expanded', 'false');
    const panel = row.nextElementSibling;
    if (panel && panel.classList.contains('expansion-row')) {
      panel.querySelector('.expansion-content')?.classList.remove('open');
    }
  } else {
    if (state.openId) {
      const prev = tbody.querySelector('.game-row.is-open');
      if (prev) {
        prev.classList.remove('is-open');
        prev.setAttribute('aria-expanded', 'false');
        const panel = prev.nextElementSibling;
        if (panel && panel.classList.contains('expansion-row')) {
          panel.querySelector('.expansion-content')?.classList.remove('open');
        }
      }
    }
    state.openId = id;
    row.classList.add('is-open');
    row.setAttribute('aria-expanded', 'true');
    const panel = row.nextElementSibling;
    if (panel && panel.classList.contains('expansion-row')) {
      panel.querySelector('.expansion-content')?.classList.add('open');
    }
  }
  writeStateToURL(state);
}

// === Сброс ===
function resetFilters() {
  state = {
    q: '', diff: 'any', genre: '', players: '0', access: 'all',
    sortKey: 'name', sortDir: 'asc', openId: null
  };
  searchInput.value = '';
  setChipValue(diffChips, 'any');
  genreSel.value = '';
  setChipValue(playersChips, '0');
  setChipValue(accessChips, 'all');
  render();
  searchInput.focus();
}

// === Инициализация ===
async function init() {
  initThemeToggle();

  try {
    GAMES = await loadGames();
  } catch (e) {
    countEl.textContent = 'Не удалось загрузить каталог: ' + e.message;
    console.error(e);
    return;
  }

  // Восстанавливаем состояние из URL
  const urlState = readStateFromURL();
  Object.assign(state, urlState);
  searchInput.value = state.q;
  setChipValue(diffChips, state.diff);
  genreSel.value = state.genre;
  setChipValue(playersChips, state.players);
  setChipValue(accessChips, state.access);

  // Жанры
  const genres = [...new Set(GAMES.map(g => g.genre).filter(Boolean))]
    .sort((a, b) => a.localeCompare(b, 'ru'));
  genres.forEach(g => {
    const opt = document.createElement('option');
    opt.value = g;
    opt.textContent = g;
    genreSel.appendChild(opt);
  });

  // Обработчики
  const debounce = (fn, ms = 150) => {
    let t;
    return (...args) => { clearTimeout(t); t = setTimeout(() => fn(...args), ms); };
  };

  searchInput.addEventListener('input', debounce(() => {
    state.q = searchInput.value;
    render();
  }));

  const filtersForm = $('#filters');
  filtersForm?.addEventListener('submit', (e) => {
    e.preventDefault();
    render();
    searchInput.blur();
  });

  genreSel.addEventListener('change', () => {
    state.genre = genreSel.value;
    render();
  });

  [diffChips, playersChips, accessChips].forEach(group => {
    group?.addEventListener('click', (e) => {
      const chip = e.target.closest('.chip');
      if (!chip) return;
      setChipValue(group, chip.dataset.value);
      if (group === diffChips)    state.diff = chip.dataset.value;
      if (group === playersChips) state.players = chip.dataset.value;
      if (group === accessChips)  state.access = chip.dataset.value;
      render();
    });
  });

  thead.addEventListener('click', (e) => {
    const th = e.target.closest('th.sortable');
    if (!th) return;
    const key = th.dataset.sort;
    if (state.sortKey === key) {
      state.sortDir = state.sortDir === 'asc' ? 'desc' : 'asc';
    } else {
      state.sortKey = key;
      state.sortDir = 'asc';
    }
    render();
  });

  tbody.addEventListener('click', (e) => {
    const row = e.target.closest('.game-row');
    if (row) toggleRow(row);
  });

  tbody.addEventListener('keydown', (e) => {
    if (e.key !== 'Enter' && e.key !== ' ') return;
    const row = e.target.closest('.game-row');
    if (!row) return;
    e.preventDefault();
    toggleRow(row);
  });

  resetBtn.addEventListener('click', resetFilters);
  resetEmpty.addEventListener('click', resetFilters);

  render();
}

init();