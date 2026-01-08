(function () {
  const root = document.getElementById("tt-dash");
  if (!root) return;

  const endpoint = root.dataset.endpoint;
  const days = parseInt(root.dataset.days || "14", 10);

  let chartHoras = null;
  let chartKpi = null;

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
    renderTable("tt-alert-misabs", a.mis_ausencias, (r) => (
      `<tr>
        <td><p class="text-sm mb-0">${r.tipo}</p></td>
        <td><span class="badge bg-gradient-info">${r.estado}</span></td>
        <td><p class="text-sm mb-0">${r.desde}</p></td>
        <td><p class="text-sm mb-0">${r.hasta}</p></td>
      </tr>`
    ));

    renderTable("tt-alert-inc", a.incompletas, (r) => (
      `<tr>
        <td><p class="text-sm mb-0">${r.fecha}</p></td>
        <td><p class="text-sm mb-0">${r.entrada}</p></td>
        <td><p class="text-sm mb-0">${r.salida}</p></td>
      </tr>`
    ));

    renderTable("tt-alert-kpirojo", a.kpis_rojo, (r) => (
      `<tr>
        <td><p class="text-sm mb-0">${r.kpi}</p></td>
        <td><span class="badge bg-gradient-danger">${(r.pct === null || r.pct === undefined) ? "—" : (parseFloat(r.pct).toFixed(2) + "%")}</span></td>
      </tr>`
    ));
  }

  function buildCharts(payload) {
    const c = payload.charts || {};
    const ctxH = document.getElementById("tt-chart-horas");
    const ctxK = document.getElementById("tt-chart-kpi");

    if (ctxH) {
      if (chartHoras) chartHoras.destroy();
      chartHoras = new Chart(ctxH, {
        type: "line",
        data: {
          labels: c.labels || [],
          datasets: [
            { label: "Horas", data: c.horas || [], tension: 0.4 },
            { label: "Extra", data: c.horas_extra || [], tension: 0.4 },
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

    if (ctxK) {
      if (chartKpi) chartKpi.destroy();
      const sem = c.kpi_semaforo || { verde: 0, amarillo: 0, rojo: 0 };
      chartKpi = new Chart(ctxK, {
        type: "doughnut",
        data: {
          labels: ["Verde", "Amarillo", "Rojo"],
          datasets: [{ data: [sem.verde || 0, sem.amarillo || 0, sem.rojo || 0] }],
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
  // inicial (data ya está renderizada por SSR, pero queremos poblar tablas)
  renderAlerts({ alerts: JSON.parse(document.getElementById("tt-dash-alerts")?.textContent || "{}")} );
  buildCharts({ charts: JSON.parse(document.getElementById("tt-dash-charts")?.textContent || "{}")} );
})();
