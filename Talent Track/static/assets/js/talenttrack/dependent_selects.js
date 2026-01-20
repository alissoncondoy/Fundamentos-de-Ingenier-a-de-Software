(function () {
  const cfg = document.querySelector('[data-tt-dependent-selects]');
  if (!cfg) return;

  const urls = {
    unidades: cfg.getAttribute('data-unidades-url'),
    puestos: cfg.getAttribute('data-puestos-url'),
    empleados: cfg.getAttribute('data-empleados-url'),
    managers: cfg.getAttribute('data-managers-url') || cfg.getAttribute('data-empleados-url'),
    roles: cfg.getAttribute('data-roles-url')
  };

  const empresaSel = document.querySelector('select[name="empresa"]');
  const unidadSel = document.querySelector('select[name="unidad"]');
  const puestoSel = document.querySelector('select[name="puesto"]');
  const managerSel = document.querySelector('select[name="manager"]');
  const empleadoSel = document.querySelector('select[name="empleado"]');
  const rolSel = document.querySelector('select[name="rol"]');

  // --- Autocompletado tipo Select2 (Choices.js) ---
  const hasChoices = typeof window.Choices !== 'undefined';
  const choicesMap = new WeakMap();

  function getOrCreateChoices(selectEl) {
    if (!hasChoices || !selectEl) return null;
    if (choicesMap.has(selectEl)) return choicesMap.get(selectEl);

    const inst = new Choices(selectEl, {
      shouldSort: false,
      searchEnabled: true,
      searchChoices: false, // nosotros cargamos remoto
      placeholder: true,
      placeholderValue: 'Busque y seleccione…',
      itemSelectText: '',
      allowHTML: false,
    });
    choicesMap.set(selectEl, inst);
    return inst;
  }

  function setChoicesOptions(selectEl, results, placeholderText) {
    const ch = getOrCreateChoices(selectEl);
    if (!selectEl) return;
    if (!ch) {
      fillSelect(selectEl, results, placeholderText);
      return;
    }

    // preserva valor actual
    const current = selectEl.value;
    ch.clearChoices();
    // placeholder
    ch.setChoices([{ value: '', label: placeholderText || 'Seleccione…', selected: !current }], 'value', 'label', false);
    ch.setChoices(
      (results || []).map(r => ({ value: r.id, label: r.text, selected: current && String(r.id) === String(current) })),
      'value',
      'label',
      false
    );
  }

  function debounce(fn, ms) {
    let t;
    return (...args) => {
      clearTimeout(t);
      t = setTimeout(() => fn(...args), ms);
    };
  }

  const remoteSearch = debounce(async (selectEl, url, empresaId, term, placeholderText) => {
    if (!selectEl || !url) return;
    if (!empresaId) return;
    // evita peticiones muy ruidosas
    const q = (term || '').trim();
    if (q.length > 0 && q.length < 2) return;
    try {
      const results = await fetchOptions(url, empresaId, q || null);
      setChoicesOptions(selectEl, results, placeholderText);
    } catch (e) {
      console.error(e);
    }
  }, 300);

  function enableRemoteSearch(selectEl, url, placeholderText) {
    if (!selectEl || !hasChoices) return;
    getOrCreateChoices(selectEl);

    // Choices dispara evento 'search' en el select original
    selectEl.addEventListener('search', (event) => {
      const term = event?.detail?.value || '';
      const empresaId = empresaSel ? empresaSel.value : '';
      remoteSearch(selectEl, url, empresaId, term, placeholderText);
    });
  }

  function setDisabled(el, disabled) {
    if (!el) return;
    el.disabled = !!disabled;
    if (disabled) el.classList.add('opacity-7');
    else el.classList.remove('opacity-7');
  }

  function clearOptions(selectEl, placeholderText) {
    if (!selectEl) return;
    while (selectEl.firstChild) selectEl.removeChild(selectEl.firstChild);
    const opt = document.createElement('option');
    opt.value = '';
    opt.textContent = placeholderText || 'Seleccione...';
    selectEl.appendChild(opt);
  }

  async function fetchOptions(url, empresaId, q) {
    if (!url) return [];
    const u = new URL(url, window.location.origin);
    if (empresaId) u.searchParams.set('empresa', empresaId);
    if (q) u.searchParams.set('q', q);
    const res = await fetch(u.toString(), { headers: { 'X-Requested-With': 'XMLHttpRequest' } });
    if (!res.ok) throw new Error('No se pudieron cargar opciones');
    const data = await res.json();
    return data.results || [];
  }

  function fillSelect(selectEl, results, placeholderText, keepValue) {
    if (!selectEl) return;
    const prev = keepValue !== undefined ? keepValue : selectEl.value;
    clearOptions(selectEl, placeholderText);
    results.forEach(r => {
      const opt = document.createElement('option');
      opt.value = r.id;
      opt.textContent = r.text;
      if (prev && r.id === prev) opt.selected = true;
      selectEl.appendChild(opt);
    });
  }

  async function reloadDependent() {
    const empresaId = empresaSel ? empresaSel.value : '';
    // Si no hay empresa, deshabilitamos dependientes
    const deps = [unidadSel, puestoSel, managerSel, empleadoSel, rolSel].filter(Boolean);
    if (!empresaId) {
      deps.forEach(el => {
        clearOptions(el, 'Seleccione empresa primero…');
        setDisabled(el, true);
      });
      return;
    }

    // Cargamos en paralelo
    try {
      if (unidadSel) setDisabled(unidadSel, true);
      if (puestoSel) setDisabled(puestoSel, true);
      if (managerSel) setDisabled(managerSel, true);
      if (empleadoSel) setDisabled(empleadoSel, true);
      if (rolSel) setDisabled(rolSel, true);

      const tasks = [];
      if (unidadSel) tasks.push(fetchOptions(urls.unidades, empresaId));
      else tasks.push(Promise.resolve([]));
      if (puestoSel) tasks.push(fetchOptions(urls.puestos, empresaId));
      else tasks.push(Promise.resolve([]));
      // managers y empleados (carga inicial corta; luego autocompletado remoto)
      if (managerSel) tasks.push(fetchOptions(urls.managers, empresaId));
      else tasks.push(Promise.resolve([]));
      if (empleadoSel) tasks.push(fetchOptions(urls.empleados, empresaId));
      else tasks.push(Promise.resolve([]));
      if (rolSel) tasks.push(fetchOptions(urls.roles, empresaId));
      else tasks.push(Promise.resolve([]));

      const [unidades, puestos, managers, empleados, roles] = await Promise.all(tasks);

      if (unidadSel) {
        fillSelect(unidadSel, unidades, 'Seleccione unidad…');
        setDisabled(unidadSel, false);
      }
      if (puestoSel) {
        fillSelect(puestoSel, puestos, 'Seleccione puesto…');
        setDisabled(puestoSel, false);
      }
      if (managerSel) {
        setChoicesOptions(managerSel, managers, 'Seleccione manager…');
        setDisabled(managerSel, false);
        enableRemoteSearch(managerSel, urls.managers, 'Seleccione manager…');
      }
      if (empleadoSel) {
        setChoicesOptions(empleadoSel, empleados, 'Seleccione empleado…');
        setDisabled(empleadoSel, false);
        enableRemoteSearch(empleadoSel, urls.empleados, 'Seleccione empleado…');
      }
      if (rolSel) {
        fillSelect(rolSel, roles, 'Seleccione rol…');
        setDisabled(rolSel, false);
      }
    } catch (err) {
      console.error(err);
      const deps2 = [unidadSel, puestoSel, managerSel, empleadoSel, rolSel].filter(Boolean);
      deps2.forEach(el => {
        clearOptions(el, 'Error cargando opciones');
        setDisabled(el, true);
      });
    }
  }

  // Hook change empresa
  if (empresaSel) {
    empresaSel.addEventListener('change', reloadDependent);
  }

  // Inicial: si hay empresa preseleccionada, carga; si no, bloquea dependientes
  reloadDependent();
})();