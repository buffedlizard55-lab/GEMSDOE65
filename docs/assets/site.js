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
const feedURL = 'https://api.github.com/repos/buffedlizard55-lab/GEMSDOE65/contents/docs/data/feed.json?ref=arena%2Ff09c3103-gemsdoe65';
function validateFeed(data) {
  if (!data || !Number.isFinite(Date.parse(data.checked_at)) || data.organizer_verified !== false || data.training_rerun !== false || data.submission_slots_used !== 0) throw new Error('Invalid metadata scope');
  for (const key of ['checked', 'changed', 'unavailable']) {
    if (!Number.isInteger(data[key]) || data[key] < 0) throw new Error('Invalid metadata count');
  }
  return data;
}
async function fetchJSON(url) {
  const response = await fetch(url, { cache: 'no-cache', signal: AbortSignal.timeout(7000) });
  if (!response.ok) throw new Error('Feed unavailable');
  return response.json();
}
async function loadFeed() {
  try {
    // One small public GitHub request, not one request per source and never an organizer request.
    // Session caching avoids wasting the anonymous API allowance while navigating the site.
    let cached;
    try { cached = JSON.parse(sessionStorage.getItem('gems65-source-feed')); } catch (_) { /* storage optional */ }
    if (cached && Date.now() >= cached.saved && Date.now() - cached.saved < 600000) return { data: validateFeed(cached.data), remote: true };
    const envelope = await fetchJSON(feedURL);
    if (envelope.encoding !== 'base64' || typeof envelope.content !== 'string') throw new Error('Invalid GitHub content');
    const bytes = Uint8Array.from(atob(envelope.content.replace(/\s/g, '')), c => c.charCodeAt(0));
    const data = validateFeed(JSON.parse(new TextDecoder().decode(bytes)));
    try { sessionStorage.setItem('gems65-source-feed', JSON.stringify({ saved: Date.now(), data })); } catch (_) { /* storage optional */ }
    return { data, remote: true };
  } catch (_) {
    return { data: validateFeed(await fetchJSON('data/feed.json')), remote: false };
  }
}
if (feed) {
  loadFeed().then(({ data, remote }) => {
    const stamp = new Date(data.checked_at);
    const age = Date.now() - stamp.getTime();
    const state = age > 48 * 3600 * 1000 ? 'STALE SNAPSHOT' : age < -300000 ? 'TIMESTAMP REQUIRES REVIEW' : remote ? 'GITHUB METADATA SNAPSHOT' : 'LOCAL FALLBACK SNAPSHOT';
    feed.dataset.state = age > 48 * 3600 * 1000 || !remote || data.unavailable ? 'caution' : 'current';
    feed.textContent = `${state} · ${stamp.toISOString().replace('T', ' ').slice(0, 19)} UTC · ${data.checked} repositories checked · ${data.changed} changed since scientific review · ${data.unavailable} unavailable. No leaderboard or score verification.${remote ? '' : ' Remote freshness could not be checked.'}`;
  }).catch(() => {
    feed.textContent = 'Feed could not be loaded. The dated scientific review remains available below; do not assume it is current.';
  });
}
