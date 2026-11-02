// app.js
(function () {
  "use strict";

  const GAMES = window.GAMES || [];

  // === Утилиты ===
  const $ = (sel) => document.querySelector(sel);
  const debounce = (fn, ms = 180) => {
    let t;
    return (...args) => {
      clearTimeout(t);
      t = setTimeout(() => fn(...args), ms);
    };
  };

  // Шкала сложности: 9 символов, 0.5 = 1 клетка
  const makeScale = (score) => {
    const filled = Math.max(0, Math.min(9, Math.round(score * 2)));
    return "[" + "\u2588".repeat(filled) + "\u2591".repeat(9 - filled) + "]";
  };

  // Безопасное экранирование HTML
  const esc = (s) => String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");

  // === DOM ===
  const tbody        = $("#tbody");
  const countEl      = $("#count");
  const emptyEl      = $("#empty");
  const searchInput  = $("#search");
  const diffSelect   = $("#filter-difficulty");
  const genreSel     = $("#filter-genre");
  const playersSel   = $("#filter-players");
  const accessSel    = $("#filter-access");
  const resetBtn     = $("#reset");
  const resetEmpty   = $("#reset-empty");

  // === Заполняем жанры (без пустых) ===
  const genres = [...new Set(GAMES.map(g => g.genre).filter(Boolean))]
    .sort((a, b) => a.localeCompare(b, "ru"));
  genres.forEach(g => {
    const opt = document.createElement("option");
    opt.value = g;
    opt.textContent = g;
    genreSel.appendChild(opt);
  });

  // === Состояние: какая игра раскрыта (по имени, а не по индексу) ===
  let openName = null;

  // === Фильтрация ===
  function getFiltered() {
    const q  = searchInput.value.toLowerCase().trim();
    const d  = diffSelect.value;
    const g  = genreSel.value;
    const p  = parseInt(playersSel.value, 10) || 0;
    const a  = accessSel.value;

    let dMin = 0, dMax = 5;
    if (d !== "any") {
      const [lo, hi] = d.split("-").map(Number);
      dMin = lo; dMax = hi;
    }

    return GAMES.filter(game => {
      // Поиск: имя, жанр, дополнения
      if (q) {
        const haystack = [
          game.name,
          game.genre,
          ...(game.expansions || [])
        ].join(" ").toLowerCase();
        if (!haystack.includes(q)) return false;
      }

      // Сложность — диапазон
      if (game.difficulty < dMin || game.difficulty > dMax) return false;

      // Жанр
      if (g && game.genre !== g) return false;

      // Игроки: игра поддерживает N игроков
      if (p > 0 && !(game.minPlayers <= p && game.maxPlayers >= p)) return false;

      // Доступ
      if (a === "yes" && !game.special) return false;
      if (a === "no"  &&  game.special) return false;

      return true;
    }).sort((a, b) => a.name.localeCompare(b.name, "ru"));
  }

  // === Рендер ===
  function render() {
    const filtered = getFiltered();

    if (openName && !filtered.some(g => g.name === openName)) {
      openName = null;
    }

    tbody.innerHTML = filtered.map((game, i) => {
      const players = game.minPlayers === game.maxPlayers
        ? String(game.minPlayers)
        : `${game.minPlayers}\u2013${game.maxPlayers}`;

      const access  = game.special ? "\uD83D\uDD12" : "";
      const hasDesc = game.description && game.description.trim();
      const hasExp  = game.expansions && game.expansions.length > 0;
      const hasData = hasDesc || hasExp;

      const isOpen = game.name === openName;

      let panel = "";
      if (hasData) {
        const descHtml = hasDesc
          ? `<div class="expansion-desc">${esc(game.description)}</div>`
          : "";
        const expHtml = hasExp
          ? `<ul>${game.expansions.map(e => `<li>${esc(e)}</li>`).join("")}</ul>`
          : `<div class="no-exp">Дополнений нет в наличии</div>`;

        panel = `
          <tr class="expansion-row" data-exp-for="${esc(game.name)}">
            <td colspan="7">
              <div class="expansion-content ${isOpen ? "open" : ""}" id="exp-${i}">
                ${descHtml}
                <strong>Дополнения:</strong><br>
                ${expHtml}
              </div>
            </td>
          </tr>`;
      }

      const rowAttrs = hasData
        ? `tabindex="0" role="button" aria-expanded="${isOpen}" aria-controls="exp-${i}"`
        : `aria-disabled="true"`;

      return `
        <tr class="game-row ${isOpen ? "is-open" : ""}"
            data-index="${i}"
            data-name="${esc(game.name)}"
            ${rowAttrs}>
          <td class="col-num">${i + 1}</td>
          <td class="col-name">${esc(game.name)}</td>
          <td class="col-scale">${makeScale(game.difficulty)}</td>
          <td class="col-players">${players}</td>
          <td class="col-time">${esc(game.time)}</td>
          <td class="col-genre">${esc(game.genre)}</td>
          <td class="col-access">${access}</td>
        </tr>
        ${panel}`;
    }).join("");

    countEl.textContent = `Найдено: ${filtered.length} из ${GAMES.length}`;
    emptyEl.hidden = filtered.length !== 0;
  }

  // === Раскрытие/закрытие ===
  function toggleRow(row) {
    const name = row.dataset.name;
    if (!name) return;
    if (row.getAttribute("aria-disabled") === "true") return;

    if (openName === name) {
      openName = null;
      row.classList.remove("is-open");
      row.setAttribute("aria-expanded", "false");
      const panel = row.nextElementSibling;
      if (panel && panel.classList.contains("expansion-row")) {
        panel.querySelector(".expansion-content")?.classList.remove("open");
      }
    } else {
      if (openName) {
        const prev = tbody.querySelector(".game-row.is-open");
        if (prev) {
          prev.classList.remove("is-open");
          prev.setAttribute("aria-expanded", "false");
          const panel = prev.nextElementSibling;
          if (panel && panel.classList.contains("expansion-row")) {
            panel.querySelector(".expansion-content")?.classList.remove("open");
          }
        }
      }
      openName = name;
      row.classList.add("is-open");
      row.setAttribute("aria-expanded", "true");
      const panel = row.nextElementSibling;
      if (panel && panel.classList.contains("expansion-row")) {
        panel.querySelector(".expansion-content")?.classList.add("open");
      }
    }
  }

  tbody.addEventListener("click", (e) => {
    const row = e.target.closest(".game-row");
    if (row) toggleRow(row);
  });

  tbody.addEventListener("keydown", (e) => {
    if (e.key !== "Enter" && e.key !== " ") return;
    const row = e.target.closest(".game-row");
    if (!row) return;
    e.preventDefault();
    toggleRow(row);
  });

  // === Фильтры ===
  const onFilterChange = debounce(render, 150);

  searchInput.addEventListener("input", onFilterChange);
  diffSelect.addEventListener("change", render);
  genreSel.addEventListener("change", render);
  playersSel.addEventListener("change", render);
  accessSel.addEventListener("change", render);

  // === Сброс ===
  function resetFilters() {
    searchInput.value = "";
    diffSelect.value = "any";
    genreSel.value = "";
    playersSel.value = "0";
    accessSel.value = "all";
    openName = null;
    render();
    searchInput.focus();
  }

  resetBtn.addEventListener("click", resetFilters);
  resetEmpty.addEventListener("click", resetFilters);

  // === Первый рендер ===
  if (GAMES.length === 0) {
    countEl.textContent = "Не удалось загрузить каталог (games.js).";
    return;
  }
  render();
})();