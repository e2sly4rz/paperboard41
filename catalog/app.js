// app.js
(function () {
  "use strict";

  const GAMES = window.GAMES || [];

  // === Утилиты ===
  const $  = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];
  const debounce = (fn, ms = 180) => {
    let t;
    return (...args) => {
      clearTimeout(t);
      t = setTimeout(() => fn(...args), ms);
    };
  };

  const makeScale = (score) => {
    const filled = Math.max(0, Math.min(9, Math.round(score * 2)));
    return "[" + "\u2588".repeat(filled) + "\u2591".repeat(9 - filled) + "]";
  };

  const esc = (s) => String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");

  const parseTime = (s) => {
    if (!s) return { min: 0, max: 0 };
    const nums = String(s).match(/\d+/g);
    if (!nums) return { min: 0, max: 0 };
    const n = nums.map(Number);
    return n.length === 1
      ? { min: n[0], max: n[0] }
      : { min: Math.min(...n), max: Math.max(...n) };
  };

  const bggUrl = (game) => {
    if (game.bggId) return `https://boardgamegeek.com/boardgame/${game.bggId}`;
    return `https://www.google.com/search?q=${encodeURIComponent('site:boardgamegeek.com ' + game.name)}`;
  };

  // === Переключатель темы ===
  (function initThemeToggle() {
    const btn = document.getElementById("theme-toggle");
    if (!btn) return;

    const root = document.documentElement;
    const icon = btn.querySelector(".theme-icon");

    const apply = (theme) => {
      root.dataset.theme = theme;
      try { localStorage.setItem("theme", theme); } catch (e) {}
      if (icon) icon.textContent = theme === "dark" ? "☀️" : "🌙";
      btn.setAttribute("aria-label",
        theme === "dark" ? "Включить светлую тему" : "Включить тёмную тему");
    };

    const current = root.dataset.theme || "light";
    if (icon) icon.textContent = current === "dark" ? "☀️" : "🌙";
    btn.setAttribute("aria-label",
      current === "dark" ? "Включить светлую тему" : "Включить тёмную тему");

    btn.addEventListener("click", () => {
      const next = root.dataset.theme === "dark" ? "light" : "dark";
      apply(next);
    });

    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    mq.addEventListener?.("change", (e) => {
      let saved = null;
      try { saved = localStorage.getItem("theme"); } catch (err) {}
      if (!saved) apply(e.matches ? "dark" : "light");
    });
  })();

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
  const thead        = $(".catalog-table thead");

  // === Жанры ===
  const genres = [...new Set(GAMES.map(g => g.genre).filter(Boolean))]
    .sort((a, b) => a.localeCompare(b, "ru"));
  genres.forEach(g => {
    const opt = document.createElement("option");
    opt.value = g;
    opt.textContent = g;
    genreSel.appendChild(opt);
  });

  // === Состояние ===
  let openName = null;
  let sortKey  = "name";
  let sortDir  = "asc";

  // === URL ⇄ состояние ===
  const SORT_KEYS = ["name", "num", "difficulty", "players", "time", "genre", "access"];

  function readStateFromURL() {
    const params = new URLSearchParams(location.search);
    searchInput.value = params.get("q") || "";
    diffSelect.value  = params.get("diff")  || "any";
    genreSel.value    = params.get("genre") || "";
    playersSel.value  = params.get("p")     || "0";
    accessSel.value   = params.get("a")     || "all";

    const s = params.get("sort");
    if (s) {
      const [k, d] = s.split(":");
      if (SORT_KEYS.includes(k)) sortKey = k;
      if (d === "asc" || d === "desc") sortDir = d;
    }

    openName = params.get("open") || null;
  }

  function writeStateToURL() {
    const params = new URLSearchParams();
    if (searchInput.value.trim()) params.set("q", searchInput.value.trim());
    if (diffSelect.value !== "any") params.set("diff", diffSelect.value);
    if (genreSel.value)             params.set("genre", genreSel.value);
    if (playersSel.value !== "0")   params.set("p", playersSel.value);
    if (accessSel.value !== "all")  params.set("a", accessSel.value);
    if (sortKey !== "name" || sortDir !== "asc") {
      params.set("sort", `${sortKey}:${sortDir}`);
    }
    if (openName) params.set("open", openName);

    const qs = params.toString();
    const url = qs ? `?${qs}` : location.pathname;
    history.replaceState(null, "", url);
  }

  // === Сортировка ===
  function sortGames(list) {
    const dir = sortDir === "asc" ? 1 : -1;

    const cmp = (a, b) => {
      let va, vb;
      switch (sortKey) {
        case "difficulty":
          va = a.difficulty; vb = b.difficulty;
          break;
        case "players":
          va = a.minPlayers * 1000 + a.maxPlayers;
          vb = b.minPlayers * 1000 + b.maxPlayers;
          break;
        case "time": {
          const ta = parseTime(a.time), tb = parseTime(b.time);
          va = ta.min * 10000 + ta.max;
          vb = tb.min * 10000 + tb.max;
          break;
        }
        case "genre":
          va = a.genre || "\uffff";
          vb = b.genre || "\uffff";
          break;
        case "access":
          va = a.special ? 0 : 1;
          vb = b.special ? 0 : 1;
          break;
        case "name":
        case "num":
        default:
          va = a.name; vb = b.name;
      }

      let r;
      if (typeof va === "string") r = va.localeCompare(vb, "ru");
      else r = va - vb;
      if (r === 0) r = a.name.localeCompare(b.name, "ru");
      return r * dir;
    };

    return [...list].sort(cmp);
  }

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

    const filtered = GAMES.filter(game => {
      if (q) {
        // Жанр из поиска убран: ищем только по названию и дополнениям
        const haystack = [
          game.name,
          ...(game.expansions || [])
        ].join(" ").toLowerCase();
        if (!haystack.includes(q)) return false;
      }
      if (game.difficulty < dMin || game.difficulty > dMax) return false;
      if (g && game.genre !== g) return false;
      if (p > 0 && !(game.minPlayers <= p && game.maxPlayers >= p)) return false;
      if (a === "yes" && !game.special) return false;
      if (a === "no"  &&  game.special) return false;
      return true;
    });

    return sortGames(filtered);
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

      const bgg = `<a class="bgg-link"
                     href="${bggUrl(game)}"
                     target="_blank" rel="noopener noreferrer"
                     title="Открыть на BoardGameGeek"
                     aria-label="BoardGameGeek: ${esc(game.name)}"
                     data-bgg>🎲</a>`;

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
          <td class="col-name">${esc(game.name)}${bgg}</td>
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

    updateSortIndicators();
    writeStateToURL();
  }

  function updateSortIndicators() {
    $$(".catalog-table th.sortable").forEach(th => {
      const key = th.dataset.sort;
      th.setAttribute(
        "aria-sort",
        key === sortKey ? (sortDir === "asc" ? "ascending" : "descending") : "none"
      );
    });
  }

  // === Клик по заголовку ===
  thead.addEventListener("click", (e) => {
    const th = e.target.closest("th.sortable");
    if (!th) return;
    const key = th.dataset.sort;

    if (sortKey === key) {
      sortDir = sortDir === "asc" ? "desc" : "asc";
    } else {
      sortKey = key;
      sortDir = "asc";
    }
    render();
  });

  // === Раскрытие ===
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
    writeStateToURL();
  }

  tbody.addEventListener("click", (e) => {
    if (e.target.closest("[data-bgg]")) return;
    const row = e.target.closest(".game-row");
    if (row) toggleRow(row);
  });

  tbody.addEventListener("keydown", (e) => {
    if (e.key !== "Enter" && e.key !== " ") return;
    if (e.target.closest("[data-bgg]")) return;
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
    sortKey = "name";
    sortDir = "asc";
    openName = null;
    render();
    searchInput.focus();
  }
  resetBtn.addEventListener("click", resetFilters);
  resetEmpty.addEventListener("click", resetFilters);

  // === Старт ===
  if (GAMES.length === 0) {
    countEl.textContent = "Не удалось загрузить каталог (games.js).";
    return;
  }
  readStateFromURL();
  render();
})();