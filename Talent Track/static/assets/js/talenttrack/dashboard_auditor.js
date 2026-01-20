(function () {
  const root = document.getElementById("tt-dash");
  if (!root) return;

  const endpoint = root.dataset.endpoint;
  const days = parseInt(root.dataset.days || "14", 10);

  let chartAnom = null;
  let chartMfa = null;

  function renderTable(tbodyId, rows, renderRow) {
    const tbody = document.getElementById(tbodyId);
    if (!tbody) return;
    if (!rows || !rows.length) {
      tbody.innerHTML = `<tr><td class="text-sm text-secondary" colspan="10">Sin datos</td></tr>`;
      return;
    }
    tbody.innerHTML = rows.map(renderRow).join("");
  }

  function renderAlerts(payload) {
    const a = payload.alerts || {};
    renderTable("tt-alert-topfuera", a.top_fuera_geocerca, (r) => (
      `<tr>
        <td><p class="text-sm mb-0">${r.empleado}</p></td>
        <td><span class="badge bg-gradient-warning">${r.eventos}</span></td>
      </tr>`
    ));

    renderTable("tt-alert-abssin", a.abs_sin_soporte, (r) => (
      `<tr>
        <td><p class="text-sm mb-0">${r.empleado}</p></td>
        <td><p class="text-sm mb-0">${r.tipo}</p></td>
        <td><p class="text-sm mb-0">${r.desde}</p></td>
        <td><p class="text-sm mb-0">${r.hasta}</p></td>
      </tr>`
    ));

    renderTable("tt-alert-evnogps", a.eventos_sin_gps, (r) => (
      `<tr>
        <td><p class="text-sm mb-0">${r.empleado}</p></td>
        <td><p class="text-sm mb-0">${r.fecha}</p></td>
        <td><p class="text-sm mb-0">${r.tipo}</p></td>
      </tr>`
    ));
  }

  function buildCharts(payload) {
    const c = payload.charts || {};
    const ctxA = document.getElementById("tt-chart-anom");
    const ctxM = document.getElementById("tt-chart-mfa");

    if (ctxA) {
      if (chartAnom) chartAnom.destroy();
      chartAnom = new Chart(ctxA, {
        type: "line",
        data: {
          labels: c.labels || [],
          datasets: [
            { label: "Fuera geocerca", data: c.fuera_geocerca || [], tension: 0.4 },
            { label: "Sin GPS", data: c.sin_gps || [], tension: 0.4 },
          ],
        },
        options: {
          responsive: true,
          plugins: { legend: { display: true } },
          interaction: { intersect: false, mode: "index" },
          scales: { y: { beginAtZero: true } },
        },
      });
    }

    if (ctxM) {
      if (chartMfa) chartMfa.destroy();
      const m = c.mfa || { on: 0, off: 0 };
      chartMfa = new Chart(ctxM, {
        type: "doughnut",
        data: {
          labels: ["MFA activado", "MFA desactivado"],
          datasets: [{ data: [m.on || 0, m.off || 0] }],
        },
        options: { responsive: true, plugins: { legend: { position: "bottom" } } },
      });
    }
  }

  async function refresh() {
    const url = `${endpoint}?days=${days}`;
    const btn = document.getElementById("tt-refresh");
    if (btn) btn.disabled = true;
    try {
      const res = await fetch(url, { credentials: "same-origin" });
      if (!res.ok) throw new Error("No se pudo cargar el dashboard");
      const payload = await res.json();
      buildCharts(payload);
      renderAlerts(payload);
    } catch (e) {
      console.error(e);
      alert("No se pudo actualizar el dashboard.");
    } finally {
      if (btn) btn.disabled = false;
    }
  }

  document.getElementById("tt-refresh")?.addEventListener("click", refresh);
  renderAlerts({ alerts: JSON.parse(document.getElementById("tt-dash-alerts")?.textContent || "{}") });
  buildCharts({ charts: JSON.parse(document.getElementById("tt-dash-charts")?.textContent || "{}") });
})();
