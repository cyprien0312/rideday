const tbody = document.querySelector("#events tbody");
const rows = () => [...tbody.querySelectorAll("tr")];
const stateSel = document.querySelector("#state");
const statusSel = document.querySelector("#status");
const qInput = document.querySelector("#q");
const countEl = document.querySelector("#count");

// populate the state dropdown from the data actually present
[...new Set(rows().map((r) => r.dataset.state).filter(Boolean))].sort()
  .forEach((s) => stateSel.add(new Option(s, s)));

function applyFilter() {
  const q = qInput.value.trim().toLowerCase();
  const st = stateSel.value;
  const status = statusSel.value;
  let shown = 0;
  rows().forEach((r) => {
    const ok =
      (!q || r.dataset.track.includes(q)) &&
      (!st || r.dataset.state === st) &&
      (!status || r.dataset.status === status);
    r.style.display = ok ? "" : "none";
    if (ok) shown++;
  });
  countEl.textContent = `${shown} 场`;
}

qInput.addEventListener("input", applyFilter);
stateSel.addEventListener("change", applyFilter);
statusSel.addEventListener("change", applyFilter);

// column sorting
const asc = {};
const headers = document.querySelectorAll("th[data-sort]");
headers.forEach((th) =>
  th.addEventListener("click", () => {
    const key = th.dataset.sort;
    asc[key] = !asc[key];
    const val = (r) =>
      key === "price" ? parseFloat(r.dataset.price)
      : key === "rain" ? parseFloat(r.dataset.rain)
      : key === "date" ? r.dataset.date
      : r.dataset[key];
    rows()
      .sort((a, b) => {
        const av = val(a), bv = val(b);
        return (av > bv ? 1 : av < bv ? -1 : 0) * (asc[key] ? 1 : -1);
      })
      .forEach((r) => tbody.appendChild(r));
    // reflect sort state in the header chevron (Action Blue arrow)
    headers.forEach((h) => h.removeAttribute("data-dir"));
    th.setAttribute("data-dir", asc[key] ? "asc" : "desc");
  })
);

// manual refresh (server mode only; absent on the static GitHub Pages build)
const refreshBtn = document.querySelector("#refresh");
if (refreshBtn) {
  refreshBtn.addEventListener("click", async (e) => {
    const btn = e.target;
    btn.disabled = true;
    btn.textContent = "抓取中…";
    try {
      await fetch("/api/refresh", { method: "POST" });
    } finally {
      location.reload();
    }
  });
}

applyFilter();
