const $ = (id) => document.getElementById(id);
const fmt = new Intl.NumberFormat(undefined, { style: "currency", currency: "USD" });

const PALETTE = ["#4f46e5", "#06b6d4", "#f59e0b", "#ef4444", "#10b981", "#8b5cf6", "#ec4899", "#84cc16", "#f97316", "#64748b"];
let categoryChart, monthChart;

function filters() {
  const p = new URLSearchParams();
  if ($("start").value) p.set("start", $("start").value);
  if ($("end").value) p.set("end", $("end").value);
  return p;
}

function showStatus(msg, isError = false) {
  const el = $("status");
  el.textContent = msg;
  el.classList.toggle("error", isError);
  el.hidden = false;
  clearTimeout(showStatus.timer);
  showStatus.timer = setTimeout(() => (el.hidden = true), 6000);
}

async function api(path, opts) {
  const res = await fetch(path, opts);
  const body = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(body.detail || res.statusText);
  return body;
}

function renderSummary(s) {
  $("total-expenses").textContent = fmt.format(s.expenses);
  $("total-income").textContent = fmt.format(s.income);
  const net = $("total-net");
  net.textContent = fmt.format(s.net);
  net.className = "value " + (s.net < 0 ? "expense" : "income");
  $("total-count").textContent = s.count;

  const select = $("category");
  const current = select.value;
  const cats = s.by_category.map((c) => c.category).sort();
  select.innerHTML = '<option value="">All</option>' + cats.map((c) => `<option>${escapeHtml(c)}</option>`).join("");
  if (cats.includes(current)) select.value = current;

  categoryChart?.destroy();
  categoryChart = new Chart($("category-chart"), {
    type: "doughnut",
    data: {
      labels: s.by_category.map((c) => c.category),
      datasets: [{ data: s.by_category.map((c) => c.total), backgroundColor: PALETTE }],
    },
    options: { plugins: { legend: { position: "right" } } },
  });

  monthChart?.destroy();
  monthChart = new Chart($("month-chart"), {
    type: "bar",
    data: {
      labels: s.by_month.map((m) => m.month),
      datasets: [
        { label: "Expenses", data: s.by_month.map((m) => m.expenses), backgroundColor: "#ef4444" },
        { label: "Income", data: s.by_month.map((m) => m.income), backgroundColor: "#10b981" },
      ],
    },
    options: { scales: { y: { beginAtZero: true } } },
  });
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
}

function renderTransactions(data) {
  const tbody = $("transactions").querySelector("tbody");
  tbody.innerHTML = data.items
    .map(
      (t) => `<tr>
        <td>${t.date}</td>
        <td>${escapeHtml(t.payee)}</td>
        <td><span class="badge">${escapeHtml(t.category)}</span></td>
        <td>${t.tags.map((tag) => `<span class="badge tag">${escapeHtml(tag)}</span>`).join(" ")}</td>
        <td class="muted">${escapeHtml(t.notes)}</td>
        <td class="num ${t.amount < 0 ? "expense" : "income"}">${fmt.format(t.amount)}</td>
      </tr>`
    )
    .join("");
  $("table-count").textContent = data.total ? `(${data.items.length} of ${data.total})` : "";
  $("empty").hidden = data.total > 0;
}

async function refresh() {
  const p = filters();
  const summary = await api(`/api/summary?${p}`);
  renderSummary(summary);
  if ($("category").value) p.set("category", $("category").value);
  renderTransactions(await api(`/api/transactions?${p}`));
}

$("csv-file").addEventListener("change", (e) => {
  $("file-name").textContent = e.target.files[0]?.name || "Choose CSV…";
});

$("import-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const file = $("csv-file").files[0];
  if (!file) return;
  const btn = $("import-btn");
  btn.disabled = true;
  try {
    const fd = new FormData();
    fd.append("file", file);
    const r = await api("/api/import", { method: "POST", body: fd });
    showStatus(`Imported ${r.imported} transaction(s)` + (r.skipped_duplicates ? `, skipped ${r.skipped_duplicates} duplicate(s)` : ""));
    $("import-form").reset();
    $("file-name").textContent = "Choose CSV…";
    await refresh();
  } catch (err) {
    showStatus(`Import failed: ${err.message}`, true);
  } finally {
    btn.disabled = false;
  }
});

$("clear-btn").addEventListener("click", async () => {
  if (!confirm("Delete all transactions?")) return;
  await api("/api/transactions", { method: "DELETE" });
  showStatus("All transactions deleted");
  refresh();
});

["start", "end", "category"].forEach((id) => $(id).addEventListener("change", refresh));
$("reset-filters").addEventListener("click", () => {
  ["start", "end", "category"].forEach((id) => ($(id).value = ""));
  refresh();
});

refresh().catch((err) => showStatus(err.message, true));
