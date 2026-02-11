(function () {
  const root = document.getElementById("tt-dash");
  if (!root) return;

  const endpoint = root.dataset.endpoint;
  const days = parseInt(root.dataset.days || "14", 10);

  const chartsData = JSON.parse(document.getElementById("tt-dash-charts")?.textContent || "{}");
  const alertsData = JSON.parse(document.getElementById("tt-dash-alerts")?.textContent || "{}");

  let chartAsistencia = null;
  let chartHoras = null;
  let chartKpi = null;

  

  function updateCards(cards){
    if(!cards) return;
    document.querySelectorAll('[data-tt-card]').forEach((el)=>{
      const key = el.dataset.ttCard;
      if(!key) return;
      if(Object.prototype.hasOwnProperty.call(cards, key)){
        const v = cards[key];
        el.textContent = (v === null || v === undefined) ? '0' : String(v);
      }
    });
  }
function fmtPct(v) {
    if (v === null || v === undefined || Number.isNaN(v)) return "—";
    return `${parseFloat(v).toFixed(2)}%`;
  }

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
    renderTable("tt-alert-abs", a.pendientes_ausencia, (r) => (
      `<tr>
        <td><p class="text-sm mb-0">${r.empleado}</p></td>
        <td><p class="text-sm mb-0">${r.tipo}</p></td>
        <td><p class="text-sm mb-0">${r.desde}</p></td>
        <td><p class="text-sm mb-0">${r.hasta}</p></td>
      </tr>`
    ));

    renderTable("tt-alert-tardy", a.top_tardanzas, (r) => (
      `<tr>
        <td><p class="text-sm mb-0">${r.empleado}</p></td>
        <td><p class="text-sm mb-0">${r.fecha}</p></td>
        <td><span class="badge bg-gradient-warning">${r.min}</span></td>
      </tr>`
    ));

    renderTable("tt-alert-inc", a.incompletas_hoy, (r) => (
      `<tr>
        <td><p class="text-sm mb-0">${r.empleado}</p></td>
        <td><p class="text-sm mb-0">${r.entrada}</p></td>
        <td><p class="text-sm mb-0">${r.salida}</p></td>
      </tr>`
    ));

    renderTable("tt-alert-kpi", a.kpis_rojo, (r) => (
      `<tr>
        <td><p class="text-sm mb-0">${r.empleado}</p></td>
        <td><p class="text-sm mb-0">${r.kpi}</p></td>
        <td><span class="badge bg-gradient-danger">${fmtPct(r.pct)}</span></td>
      </tr>`
    ));
  }

  function buildCharts(payload) {
    const c = payload.charts || {};

    const ctxA = document.getElementById("tt-chart-asistencia");
    const ctxH = document.getElementById("tt-chart-horas");
    const ctxK = document.getElementById("tt-chart-kpi");

    if (ctxA) {
      if (chartAsistencia) chartAsistencia.destroy();
      chartAsistencia = new Chart(ctxA, {
        type: "line",
        data: {
          labels: c.labels || [],
          datasets: [
            { label: "Presentes", data: c.presentes || [], tension: 0.4 },
            { label: "Tardanzas", data: c.tardanzas || [], tension: 0.4 },
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

    if (ctxH) {
      if (chartHoras) chartHoras.destroy();
      chartHoras = new Chart(ctxH, {
        type: "bar",
        data: {
          labels: c.labels || [],
          datasets: [
            { label: "Horas trabajadas", data: c.horas || [] },
            { label: "Horas extra", data: c.horas_extra || [] },
          ],
        },
        options: {
          responsive: true,
          plugins: { legend: { display: true } },
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
      updateCards(payload.cards || {});
      buildCharts(payload);
      renderAlerts(payload);
    } catch (e) {
      console.error(e);
      alert("No se pudo actualizar el dashboard.");
    } finally {
      if (btn) btn.disabled = false;
    }
  }

  // Inicial
  buildCharts({ charts: chartsData });
  renderAlerts({ alerts: alertsData });

  document.getElementById("tt-refresh")?.addEventListener("click", refresh);
})();
