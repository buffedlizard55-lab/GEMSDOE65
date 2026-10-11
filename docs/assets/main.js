(() => {
  const status = document.getElementById("feed-status");
  const body = document.getElementById("leaderboard-body");
  if (!status || !body) return;

  const source = "https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/";
  const decimal = /^(?:0(?:\.\d+)?|1(?:\.0+)?)$/;

  fetch("data/leaderboard.json", { cache: "no-store" })
    .then((response) => {
      if (!response.ok) throw new Error(`Feed request returned ${response.status}`);
      return response.json();
    })
    .then((feed) => {
      if (!Array.isArray(feed.rows) || !feed.rows.length) throw new Error("Feed has no leaderboard rows");
      if (!String(feed.evidence_label || "").includes("PUBLIC-LEADERBOARD-OBSERVATION")) {
        throw new Error("Feed is missing its evidence label");
      }
      if (feed.source_url && feed.source_url !== source) {
        throw new Error("Feed source URL differs from the official leaderboard");
      }

      const selected = feed.rows.slice(0, 10);
      const reference = feed.rows.find((row) => row.participant === "extradr19");
      if (reference && !selected.some((row) => row.rank === reference.rank)) selected.push(reference);
      for (const row of selected) {
        if (!Number.isInteger(row.rank) || typeof row.participant !== "string" || !decimal.test(String(row.public_dti))) {
          throw new Error("Feed contains an invalid row; not displaying unvalidated data");
        }
      }

      const fragment = document.createDocumentFragment();
      for (const row of selected) {
        const tr = document.createElement("tr");
        const values = [String(row.rank), row.participant, String(row.public_dti)];
        values.forEach((value, index) => {
          const td = document.createElement("td");
          td.textContent = value;
          if (index === 2) td.className = "score";
          tr.appendChild(td);
        });
        fragment.appendChild(tr);
      }
      body.replaceChildren(fragment);

      const retrieved = feed.retrieved_at_utc || "unknown date";
      if (feed.refresh_status === "refreshed") {
        status.className = "callout";
        status.textContent = `Live public-page snapshot refreshed ${retrieved}. ${feed.evidence_label}`;
      } else if (feed.refresh_status === "stale") {
        status.className = "callout warning";
        status.textContent = `Live refresh failed; showing the last validated snapshot from ${retrieved}. ${feed.refresh_warning || "Check the official page for current values."} ${feed.evidence_label}`;
      } else {
        status.className = "callout warning";
        status.textContent = `Stored public leaderboard snapshot from ${retrieved}; scheduled live refresh has not yet been confirmed. ${feed.evidence_label}`;
      }
    })
    .catch((error) => {
      status.className = "callout warning";
      status.textContent = `Stored official snapshot could not be validated: ${error.message}. Check the official source directly: ${source}`;
      body.replaceChildren();
      const row = document.createElement("tr");
      const cell = document.createElement("td");
      cell.colSpan = 3;
      cell.textContent = "No validated leaderboard data could be rendered.";
      row.appendChild(cell);
      body.appendChild(row);
    });
})();
