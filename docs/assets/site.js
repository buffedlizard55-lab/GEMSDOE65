'use strict';
const filter = document.querySelector('[data-filter]');
if (filter) {
  const rows = [...document.querySelectorAll('[data-search]')];
  const count = document.querySelector('[data-result-count]');
  filter.addEventListener('input', () => {
    const term = filter.value.trim().toLowerCase();
    let visible = 0;
    for (const row of rows) {
      row.hidden = !row.dataset.search.toLowerCase().includes(term);
      if (!row.hidden) visible += 1;
    }
    if (count) count.textContent = `${visible} of ${rows.length} sources shown`;
  });
}
const feed = document.querySelector('[data-feed-status]');
if (feed) {
  fetch('data/feed.json', { cache: 'no-cache' }).then(response => {
    if (!response.ok) throw new Error('Feed unavailable');
    return response.json();
  }).then(data => {
    const stamp = new Date(data.checked_at);
    if (Number.isNaN(stamp.getTime())) throw new Error('Invalid timestamp');
    const age = Date.now() - stamp.getTime();
    const state = age > 48 * 3600 * 1000 ? 'STALE SNAPSHOT' : age < -300000 ? 'TIMESTAMP REQUIRES REVIEW' : 'METADATA SNAPSHOT';
    feed.textContent = `${state} · ${stamp.toISOString().replace('T', ' ').slice(0, 19)} UTC · ${data.checked} repositories checked · ${data.changed} changed since scientific review · ${data.unavailable} unavailable. No leaderboard or score verification.`;
  }).catch(() => {
    feed.textContent = 'Feed could not be loaded. The dated scientific review remains available below; do not assume it is current.';
  });
}
