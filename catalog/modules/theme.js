// modules/theme.js
// Переключатель темы.

export function initThemeToggle() {
  const btn = document.getElementById('theme-toggle');
  if (!btn) return;

  const root = document.documentElement;
  const icon = btn.querySelector('.theme-icon');

  const apply = (theme) => {
    root.dataset.theme = theme;
    try { localStorage.setItem('theme', theme); } catch (e) {}
    if (icon) icon.textContent = theme === 'dark' ? '☀️' : '🌙';
    btn.setAttribute('aria-label',
      theme === 'dark' ? 'Включить светлую тему' : 'Включить тёмную тему');
  };

  const current = root.dataset.theme || 'light';
  if (icon) icon.textContent = current === 'dark' ? '☀️' : '🌙';

  btn.addEventListener('click', () => {
    apply(root.dataset.theme === 'dark' ? 'light' : 'dark');
  });

  const mq = window.matchMedia('(prefers-color-scheme: dark)');
  mq.addEventListener?.('change', (e) => {
    let saved = null;
    try { saved = localStorage.getItem('theme'); } catch (err) {}
    if (!saved) apply(e.matches ? 'dark' : 'light');
  });
}