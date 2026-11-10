// modules/render.js
// Рендер таблицы и карточек.

import { makeScale, esc } from './filter.js';

export function renderGames(tbody, filtered, state) {
  tbody.innerHTML = filtered.map((game, i) => {
    const players = game.minPlayers === game.maxPlayers
      ? String(game.minPlayers)
      : `${game.minPlayers}\u2013${game.maxPlayers}`;

    const access = game.special ? '\uD83D\uDD12' : '';
    const hasDesc = game.description && game.description.trim();
    const hasExp  = game.expansions && game.expansions.length > 0;
    const hasData = hasDesc || hasExp;
    const isOpen  = game.id === state.openId;

    const coverHtml = game.bggId
      ? `<img class="cover-img"
              src="covers_webp/${game.bggId}.webp"
              alt="" loading="lazy" decoding="async"
              width="32" height="32"
              onerror="this.style.display='none';this.nextElementSibling.style.display='flex';">
         <span class="cover-fallback" style="display:none" aria-hidden="true">${esc(game.name[0])}</span>`
      : `<span class="cover-fallback" aria-hidden="true">${esc(game.name[0])}</span>`;

    let panel = '';
    if (hasData) {
      const descHtml = hasDesc
        ? `<div class="expansion-desc">${esc(game.description)}</div>`
        : '';
      const expHtml = hasExp
        ? `<ul>${game.expansions.map(e => `<li>${esc(e)}</li>`).join('')}</ul>`
        : `<div class="no-exp">Дополнений нет в наличии</div>`;

      const bigCover = game.bggId
        ? `<img class="cover-large"
                src="covers_webp/${game.bggId}.webp"
                alt="" loading="lazy" decoding="async"
                width="120" height="120"
                onerror="this.style.display='none';this.parentElement.classList.add('no-cover');">`
        : '';

      const bggLink = game.bggId
        ? `<a class="bgg-link"
              href="https://boardgamegeek.com/boardgame/${game.bggId}"
              target="_blank" rel="noopener noreferrer"
              title="Открыть на BoardGameGeek">🎲 BoardGameGeek</a>`
        : '';

      panel = `
        <tr class="expansion-row" data-exp-for="${esc(game.id)}">
          <td colspan="7">
            <div class="expansion-content ${isOpen ? 'open' : ''}" id="exp-${i}">
              <div class="expansion-body ${bigCover ? 'has-cover' : 'no-cover'}">
                ${bigCover}
                <div class="expansion-text">
                  ${descHtml}
                  <strong>Дополнения:</strong><br>
                  ${expHtml}
                  ${bggLink ? `<div class="bgg-row">${bggLink}</div>` : ''}
                </div>
              </div>
            </div>
          </td>
        </tr>`;
    }

    const rowAttrs = hasData
      ? `tabindex="0" role="button" aria-expanded="${isOpen}" aria-controls="exp-${i}"`
      : `aria-disabled="true"`;

    return `
      <tr class="game-row ${isOpen ? 'is-open' : ''}"
          data-index="${i}"
          data-id="${esc(game.id)}"
          ${rowAttrs}>
        <td class="col-num">${i + 1}</td>
        <td class="col-name">
          <div class="name-flex">
            <span class="cover-wrap">${coverHtml}</span>
            <span class="name-text">${esc(game.name)}</span>
          </div>
        </td>
        <td class="col-scale">${makeScale(game.difficulty)}</td>
        <td class="col-players">${players}</td>
        <td class="col-time">${esc(game.time)}</td>
        <td class="col-genre">${esc(game.genre)}</td>
        <td class="col-access">${access}</td>
      </tr>
      ${panel}`;
  }).join('');
}