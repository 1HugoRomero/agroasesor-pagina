(function () {
  const userId = JSON.parse(document.getElementById('agro-user-id').textContent);
  const KEY = 'agroasesor-local-v2-' + userId;
  const farmData = JSON.parse(document.getElementById('agro-farms').textContent);

  function clone(value) {
    return JSON.parse(JSON.stringify(value));
  }

  function readServerCatalog() {
    const node = document.getElementById('agro-catalog');
    if (!node) return null;
    try {
      const data = JSON.parse(node.textContent);
      if (data && data.fromDb) return data;
    } catch (error) {
      console.warn('No se pudo leer el catálogo de la base de datos.', error);
    }
    return null;
  }

  function applyCatalog(state, catalog) {
    if (!catalog || !catalog.fromDb) return state;
    if (catalog.cultivos) state.cultivos = catalog.cultivos;
    if (catalog.zonas) state.zonas = catalog.zonas;
    if (catalog.insumos) state.insumos = catalog.insumos;
    if (catalog.problemas) state.problemas = catalog.problemas;
    window.AGRO_MOCK.cultivos = (catalog.cultivos || []).filter((item) => item.active !== false).map((item) => item.name);
    if (catalog.zonas) window.AGRO_MOCK.zonas = catalog.zonas.map((item) => item.name);
    if (catalog.insumos) window.AGRO_MOCK.insumos = catalog.insumos;
    if (catalog.semillas) window.AGRO_MOCK.semillas = catalog.semillas;
    if (catalog.yields) window.AGRO_MOCK.yields = catalog.yields;
    window.AGRO_CATALOG = catalog;
    return state;
  }

  function seed() {
    return {
      predios: clone(farmData.predios),
      plots: clone(farmData.plots),
      cultivos: clone(window.AGRO_MOCK.cultivos).map((name, i) => ({ id: 'c' + i, name, active: true })),
      variedades: [
        { id: 'v1', name: 'Híbrido demo', active: true },
        { id: 'v2', name: 'Industrial demo', active: true },
        { id: 'v3', name: 'Demo invierno', active: true }
      ],
      zonas: clone(window.AGRO_MOCK.zonas).map((name, i) => ({ id: 'z' + i, name, active: true })),
      insumos: clone(window.AGRO_MOCK.insumos),
      problemas: clone(window.AGRO_MOCK.problemas),
      calendario: clone(window.AGRO_MOCK.calendario).map((item, i) => ({ id: 'cal' + i, active: true, ...item })),
      results: {}
    };
  }

  function load() {
    const fresh = seed();
    try {
      const stored = JSON.parse(localStorage.getItem(KEY));
      if (stored && stored.plots && stored.predios) {
        fresh.results = stored.results || {};
      }
    } catch (error) {
      console.warn('No se pudo leer el estado local.', error);
    }
    applyCatalog(fresh, readServerCatalog());
    return fresh;
  }

  function save(state) {
    try {
      localStorage.setItem(KEY, JSON.stringify({
        predios: state.predios,
        plots: state.plots,
        results: state.results || {}
      }));
    } catch (error) {
      console.warn('No se pudo guardar el estado local.', error);
    }
  }

  function fmt(value, digits) {
    const number = Number(value);
    if (!Number.isFinite(number)) return '—';
    return number.toLocaleString('es-CL', { maximumFractionDigits: digits ?? 2, minimumFractionDigits: 0 });
  }

  function positive(value) {
    const number = Number(String(value).replace(',', '.'));
    return Number.isFinite(number) && number > 0 ? number : null;
  }

  function nonNegative(value) {
    const number = Number(String(value).replace(',', '.'));
    return Number.isFinite(number) && number >= 0 ? number : null;
  }

  function calculateDose(areaHa, dose) {
    const area = positive(areaHa);
    const d = positive(dose);
    if (area === null || d === null) return { ok: false, error: 'Ingresa superficie y dosis mayores a 0.' };
    return { ok: true, amount: area * d, formula: area + ' × ' + d + ' = ' + (area * d) };
  }

  function calculateCoverage(areaHa, dose, available) {
    const area = positive(areaHa);
    const d = positive(dose);
    const stock = nonNegative(available);
    if (area === null || d === null || stock === null) {
      return { ok: false, error: 'Revisa superficie, dosis y cantidad disponible.' };
    }
    const needed = area * d;
    const coveredHa = Math.min(area, stock / d);
    const percent = (coveredHa / area) * 100;
    const missingHa = Math.max(0, area - coveredHa);
    const missingQty = Math.max(0, needed - stock);
    const surplus = Math.max(0, stock - needed);
    return { ok: true, needed, coveredHa, percent, missingHa, missingQty, surplus };
  }

  function predictYield(crop, areaHa, yieldPerHa) {
    const area = positive(areaHa);
    const rate = yieldPerHa === undefined
      ? window.AGRO_MOCK.yields[crop]
      : positive(yieldPerHa);
    if (area === null) return { ok: false, error: 'La superficie debe ser mayor a 0.' };
    if (!rate) return { ok: false, error: 'Selecciona un cultivo.' };
    return { ok: true, rate, production: rate * area, confidence: 'Media (datos de referencia, no un modelo real).' };
  }

  function sameId(left, right) {
    return String(left) === String(right);
  }

  async function calculateOnServer(url, payload) {
    const token = document.querySelector('input[name="csrfmiddlewaretoken"]')?.value;
    if (!token) throw new Error('No se encontró el token de seguridad. Recarga la página e inténtalo nuevamente.');
    const response = await fetch(url, {
      method: 'POST',
      credentials: 'same-origin',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': token,
        'Accept': 'application/json'
      },
      body: JSON.stringify(payload)
    });
    if (!response.headers.get('Content-Type')?.includes('application/json')) {
      throw new Error(response.redirected
        ? 'Tu sesión expiró. Inicia sesión nuevamente para calcular.'
        : 'El servidor devolvió una respuesta inesperada. Inténtalo nuevamente.');
    }
    const data = await response.json();
    if (!response.ok || !data.ok) throw new Error(data.error || 'El servidor no pudo validar el cálculo.');
    return data;
  }

  const api = {
    escape: (value) => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])),
    getState: load,
    saveState: save,
    catalogFromDb: () => Boolean(readServerCatalog()),
    getPredios: () => load().predios,
    getPlots: (predioId) => load().plots.filter((plot) => !predioId || plot.predio === predioId),
    getCultivos: () => load().cultivos.filter((item) => item.active !== false).map((item) => item.name || item),
    getSemilla(crop) {
      return (window.AGRO_MOCK.semillas || []).find((item) => item.crop === crop) || null;
    },
    getInsumos: (onlyActive) => load().insumos.filter((item) => !onlyActive || item.active),
    getProblemas: () => load().problemas.filter((item) => item.active !== false),
    calculateCoverage,
    calculateDose,
    predictYield,
    calculateOnServer,
    fmt,
    positive,
    nonNegative,
    sameId,
    updatePlot(id, values) {
      const state = load();
      state.plots = state.plots.map((plot) => plot.id === id ? { ...plot, ...values } : plot);
      save(state);
      return state.plots.find((plot) => plot.id === id);
    },
    addPlot(plot) {
      const state = load();
      state.plots.push(plot);
      save(state);
      return plot;
    },
    removePlot(id) {
      const state = load();
      state.plots = state.plots.filter((plot) => plot.id !== id && plot.parentId !== id);
      save(state);
    },
    addPredio(predio) {
      const state = load();
      state.predios.push(predio);
      save(state);
      return predio;
    },
    saveResult(key, value) {
      const state = load();
      state.results[key] = value;
      save(state);
    },
    getResult(key) {
      return load().results[key];
    },
    replaceCatalog(section, items) {
      const state = load();
      state[section] = items;
      save(state);
    }
  };

  window.AgroService = api;
})();
