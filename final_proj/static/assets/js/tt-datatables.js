/*
  TalentTrack - Simple-DataTables initializer
  - Adds search, sorting and pagination to list tables
  - Safe no-op if a page doesn't have any matching tables

  Usage:
    <table data-tt-datatable="1" ...>
    Optional:
      data-tt-perpage="10"
      data-tt-nosort-col="5,6" (0-based)
      th[data-tt-nosort] to disable sorting by column
*/

(function () {
  function ready(fn) {
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', fn);
    } else {
      fn();
    }
  }

  function parseCsvInts(v) {
    if (!v) return [];
    return String(v)
      .split(',')
      .map(s => s.trim())
      .filter(Boolean)
      .map(n => Number(n))
      .filter(n => Number.isFinite(n));
  }

  function getNoSortIndexes(table) {
    const nosort = new Set(parseCsvInts(table.getAttribute('data-tt-nosort-col')));
    const ths = table.querySelectorAll('thead th');
    ths.forEach((th, idx) => {
      if (th.hasAttribute('data-tt-nosort')) nosort.add(idx);
    });
    return Array.from(nosort);
  }

  function initTable(table) {
    if (!window.simpleDatatables || !window.simpleDatatables.DataTable) return;
    if (table.__ttDataTable) return; // prevent double init

    const perPage = Number(table.getAttribute('data-tt-perpage') || 10);
    const noSortIdx = getNoSortIndexes(table);

    const columns = noSortIdx.map(i => ({ select: i, sortable: false }));

    // eslint-disable-next-line no-undef
    const dt = new simpleDatatables.DataTable(table, {
      searchable: true,
      fixedHeight: false,
      perPage: Number.isFinite(perPage) ? perPage : 10,
      perPageSelect: [10, 25, 50, 100],
      columns,
      labels: {
        placeholder: 'Buscar…',
        perPage: '{select} por página',
        noRows: 'No hay registros',
        info: 'Mostrando {start}–{end} de {rows} registros'
      }
    });

    table.__ttDataTable = dt;
  }

  ready(function () {
    const tables = document.querySelectorAll('table[data-tt-datatable="1"]');
    if (!tables.length) return;
    tables.forEach(initTable);
  });
})();
