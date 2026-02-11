(function () {
  const root = document.getElementById("tt-dash");
  if (!root) return;

  const endpoint = root.dataset.endpoint;
  const days = parseInt(root.dataset.days || "14", 10);
  const empresaId = root.dataset.empresa || "";

  const chartsData = JSON.parse(document.getElementById("tt-dash-charts")?.textContent || "{}");
  const alertsData = JSON.parse(document.getElementById("tt-dash-alerts")?.textContent || "{}");
  const empresasData = JSON.parse(document.getElementById("tt-dash-empresas")?.textContent || "[]");

  let chartAsistencia = null;
  let chartHoras = null;
  let chartKpi = null;
  let chartEmpresas = null;

  

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

  function renderTable(tbodyId, rows, renderRow, emptyCols) {
    const tbody = document.getElementById(tbodyId);
    if (!tbody) return;
    if (!rows || !rows.length) {
      tbody.innerHTML = `<tr><td class="text-sm text-secondary" colspan="${emptyCols || 10}">Sin datos</td></tr>`;
      return;
    }
    tbody.innerHTML = rows.map(renderRow).join("");
  }

  function renderEmpresaAlerts(rows) {
    const ul = document.getElementById("tt-alert-empresas");
    if (!ul) return;
    if (!rows || !rows.length) {
      ul.innerHTML = `<li class="list-group-item text-sm text-secondary">Sin alertas por empresa</li>`;
      return;
    }
    ul.innerHTML = rows.map((r) => {
      const badge = r.nivel === "danger" ? "bg-gradient-danger" : (r.nivel === "warning" ? "bg-gradient-warning" : "bg-gradient-info");
      return `
        <li class="list-group-item d-flex justify-content-between align-items-start">
          <div class="me-2">
            <div class="text-sm fw-bold">${r.titulo}</div>
            <div class="text-xs text-secondary">${r.detalle}</div>
          </div>
          <span class="badge ${badge}">${r.nivel}</span>
        </li>
      `;
    }).join("");
  }

  function renderEmpresasTable(rows) {
    renderTable(
      "tt-empresas-resumen",
      rows,
      (r) => {
        const link = r.empresa_id ? `<a href="?empresa=${encodeURIComponent(r.empresa_id)}&days=${days}">${r.empresa}</a>` : r.empresa;
        const presBadge = r.tasa_presentismo >= 90 ? "bg-gradient-success" : (r.tasa_presentismo >= 75 ? "bg-gradient-warning" : "bg-gradient-danger");
        return `
          <tr>
            <td class="text-sm">${link}</td>
            <td class="text-sm">${r.empleados || 0}</td>
            <td class="text-sm">${r.presentes || 0}</td>
            <td class="text-sm"><span class="badge ${presBadge}">${fmtPct(r.tasa_presentismo)}</span></td>
            <td class="text-sm">${r.tardanzas || 0}</td>
            <td class="text-sm">${r.pendientes_ausencia || 0}</td>
            <td class="text-sm">${r.kpi_rojo || 0}</td>
          </tr>
        `;
      },
      7
    );
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
    ), 4);

    renderTable("tt-alert-tardy", a.top_tardanzas, (r) => (
      `<tr>
        <td><p class="text-sm mb-0">${r.empleado}</p></td>
        <td><p class="text-sm mb-0">${r.fecha}</p></td>
        <td><span class="badge bg-gradient-warning">${r.min}</span></td>
      </tr>`
    ), 3);

    renderTable("tt-alert-inc", a.incompletas_hoy, (r) => (
      `<tr>
        <td><p class="text-sm mb-0">${r.empleado}</p></td>
        <td><p class="text-sm mb-0">${r.entrada}</p></td>
        <td><p class="text-sm mb-0">${r.salida}</p></td>
      </tr>`
    ), 3);

    renderTable("tt-alert-kpi", a.kpis_rojo, (r) => (
      `<tr>
        <td><p class="text-sm mb-0">${r.empleado}</p></td>
        <td><p class="text-sm mb-0">${r.kpi}</p></td>
        <td><span class="badge bg-gradient-danger">${fmtPct(r.pct)}</span></td>
      </tr>`
    ), 3);

    renderEmpresaAlerts(a.alertas_empresa || []);
  }

  function buildCharts(payload, empresasRows) {
    const c = payload.charts || {};

    const ctxA = document.getElementById("tt-chart-asistencia");
    const ctxH = document.getElementById("tt-chart-horas");
    const ctxK = document.getElementById("tt-chart-kpi");
    const ctxE = document.getElementById("tt-chart-empresas");

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

    if (ctxE) {
      if (chartEmpresas) chartEmpresas.destroy();

      const rows = [...(empresasRows || [])]
        .filter((r) => (r.empleados || 0) > 0)
        .sort((a, b) => (b.tasa_presentismo || 0) - (a.tasa_presentismo || 0))
        .slice(0, 10);

      chartEmpresas = new Chart(ctxE, {
        type: "bar",
        data: {
          labels: rows.map((r) => r.empresa),
          datasets: [{ label: "Presentismo hoy (%)", data: rows.map((r) => r.tasa_presentismo || 0) }],
        },
        options: {
          responsive: true,
          plugins: { legend: { display: true } },
          scales: { y: { beginAtZero: true, max: 100 } },
        },
      });
    }
  }

  async function refresh() {
    const btn = document.getElementById("tt-refresh");
    if (btn) btn.disabled = true;
    try {
      const params = new URLSearchParams({ days: String(days) });
      if (empresaId) params.set("empresa", empresaId);

      const url = `${endpoint}?${params.toString()}`;
      const res = await fetch(url, { credentials: "same-origin" });
      if (!res.ok) throw new Error("No se pudo cargar el dashboard");
      const payload = await res.json();

      buildCharts(payload, payload.empresas_rows || []);
      renderEmpresasTable(payload.empresas_rows || []);
      renderAlerts(payload);
    } catch (e) {
      console.error(e);
      alert("No se pudo actualizar el dashboard.");
    } finally {
      if (btn) btn.disabled = false;
    }
  }

  // Inicial
  buildCharts({ charts: chartsData }, empresasData);
  renderEmpresasTable(empresasData);
  renderAlerts({ alerts: alertsData });

  document.getElementById("tt-refresh")?.addEventListener("click", refresh);
})();
