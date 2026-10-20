(function () {
  'use strict';
  const root = document.querySelector('.decision-center');
  if (!root) return;

  function readJson(id, fallback) {
    const node = document.getElementById(id);
    if (!node) return fallback;
    try { return JSON.parse(node.textContent) || fallback; } catch (error) { return fallback; }
  }

  const catalog = readJson('agro-catalog', {});
  const farm = readJson('agro-farms', { predios: [], plots: [] });
  const calculateUrl = root.dataset.calculateUrl;
  const isStaff = root.dataset.staff === '1';
  const crops = (catalog.cultivos || []).filter((crop) => crop.active !== false);
  const products = (catalog.insumos || []).filter((item) => item.usable !== false && item.active !== false);
  const allProducts = catalog.insumos || [];
  const problems = catalog.problemas || [];
  const categoryLabels = catalog.categoryLabels || {};
  const PHYTO = new Set(['herbicide', 'fungicide', 'insecticide']);
  const PHYTO_UNITS = ['kg/ha', 'g/ha', 'L/ha', 'mL/ha'];
  const params = new URLSearchParams(window.location.search);
  const lastResults = {};

  // ---------- utilidades ----------
  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined && text !== null) node.textContent = text;
    return node;
  }
  function fmt(value, digits) {
    const number = Number(value);
    if (!Number.isFinite(number)) return '—';
    return number.toLocaleString('es-CL', { maximumFractionDigits: digits === undefined ? 2 : digits });
  }
  function fmtDate(value) {
    if (!value) return '';
    const parts = String(value).split('-');
    return parts.length === 3 ? parts[2] + '/' + parts[1] + '/' + parts[0] : value;
  }
  function safeUrl(value) {
    if (!value) return '';
    try {
      const url = new URL(value, window.location.origin);
      return ['http:', 'https:'].includes(url.protocol) ? url.href : '';
    } catch (error) { return ''; }
  }
  function cropById(id) { return crops.find((crop) => String(crop.id) === String(id)) || null; }
  function plotById(id) { return (farm.plots || []).find((plot) => String(plot.id) === String(id)) || null; }
  function productById(id) { return allProducts.find((item) => String(item.id) === String(id)) || null; }
  function farmOf(plot) { return (farm.predios || []).find((item) => String(item.id) === String(plot.predio)) || null; }
  function isPhyto(item) { return PHYTO.has(item.category); }
  function belongsToCrop(item, crop) {
    if (!crop) return !item.cropId && !item.crop;
    return !item.cropId ? !item.crop || item.crop === crop.name : String(item.cropId) === String(crop.id);
  }
  function verifiedPhytoFor(item, crop) {
    return item.verifiedUse === true && crop && item.crop === crop.name &&
      Array.isArray(item.authorizedCrops) && item.authorizedCrops.includes(crop.name) &&
      PHYTO_UNITS.includes(item.unit);
  }
  function missingData(item, crop) {
    const missing = [];
    if (item.verificationStatus !== 'verified') missing.push('verificación del producto con fuente');
    if (item.dose === null || item.dose === undefined) missing.push('dosis por hectárea');
    else if (!item.doseVerified) missing.push('verificación de la dosis (fuente, URL y fecha)');
    if (!item.unit) missing.push('unidad de la dosis');
    if (isPhyto(item)) {
      if (!item.sagRegistration) missing.push('número de autorización SAG');
      if (!item.labelUrl) missing.push('etiqueta autorizada');
      if (!crop || !(item.authorizedCrops || []).includes(crop.name)) missing.push('cultivo autorizado en etiqueta');
      if (!(item.controlTargets || []).length) missing.push('objetivo de control');
    }
    return missing;
  }
  function csrfToken() {
    const input = document.querySelector('[name=csrfmiddlewaretoken]');
    return input ? input.value : '';
  }
  async function calculate(payload) {
    const response = await fetch(calculateUrl, {
      method: 'POST',
      credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken(), Accept: 'application/json' },
      body: JSON.stringify(payload),
    });
    if (!(response.headers.get('Content-Type') || '').includes('application/json')) {
      throw new Error(response.redirected ? 'Tu sesión expiró. Inicia sesión nuevamente.' : 'El servidor devolvió una respuesta inesperada.');
    }
    const data = await response.json();
    if (!response.ok || !data.ok) throw new Error(data.error || 'El servidor no pudo validar el cálculo.');
    return data;
  }
  function setOptions(select, items, placeholder) {
    const previous = select.value;
    select.replaceChildren();
    if (placeholder !== null) select.add(new Option(placeholder, ''));
    items.forEach((item) => {
      const option = new Option(item.label, item.value);
      if (item.disabled) option.disabled = true;
      select.add(option);
    });
    if ([...select.options].some((option) => option.value === previous && !option.disabled)) select.value = previous;
  }

  // ---------- pestañas ----------
  const tabs = [...document.querySelectorAll('.tool-tabs [data-tool]')];
  function showTool(name, focus) {
    if (!['llevar', 'alcanza', 'cosecha', 'ficha'].includes(name)) name = 'llevar';
    tabs.forEach((tab) => {
      const active = tab.dataset.tool === name;
      tab.classList.toggle('is-active', active);
      tab.setAttribute('aria-selected', String(active));
      tab.tabIndex = active ? 0 : -1;
    });
    document.querySelectorAll('.tool-panel').forEach((panel) => { panel.hidden = panel.id !== 'tool-' + name; });
    const next = new URLSearchParams(window.location.search);
    next.set('herramienta', name);
    window.history.replaceState(null, '', window.location.pathname + '?' + next.toString());
    if (focus) document.getElementById('tool-' + name).scrollIntoView({ behavior: 'smooth', block: 'start' });
  }
  tabs.forEach((tab) => tab.addEventListener('click', () => showTool(tab.dataset.tool)));

  const kindButtons = [...document.querySelectorAll('[data-kind]')];
  const llevarLayouts = [...document.querySelectorAll('#tool-llevar .tool-layout')];
  function showKind(kind) {
    kind = kind === 'insumos' ? 'insumos' : 'semillas';
    kindButtons.forEach((button) => {
      const active = button.dataset.kind === kind;
      button.classList.toggle('is-active', active);
      button.setAttribute('aria-pressed', String(active));
    });
    llevarLayouts[0].hidden = kind !== 'semillas';
    llevarLayouts[1].hidden = kind !== 'insumos';
    const next = new URLSearchParams(window.location.search);
    next.set('tipo', kind);
    window.history.replaceState(null, '', window.location.pathname + '?' + next.toString());
  }
  kindButtons.forEach((button) => button.addEventListener('click', () => showKind(button.dataset.kind)));

  // ---------- potrero y cultivo comunes ----------
  function selectedPlot(form) { return plotById(form.elements.plot.value); }
  function selectedCrop(form) { return cropById(form.elements.crop.value); }

  function setupPlotCrop(form, onChange) {
    const plotSelect = form.elements.plot;
    const cropSelect = form.elements.crop;
    setOptions(plotSelect, (farm.plots || []).map((plot) => ({
      value: String(plot.id),
      label: plot.farmName + ' · ' + plot.name + ' (' + fmt(plot.areaHa, 2) + ' ha)',
    })), (farm.plots || []).length ? 'Selecciona un potrero' : 'No tienes potreros registrados');
    setOptions(cropSelect, crops.map((crop) => ({ value: String(crop.id), label: crop.name })),
      crops.length ? 'Selecciona un cultivo' : 'Sin cultivos en el catálogo');
    const plotHelp = form.querySelector('[data-role=plot-help]');
    const cropHelp = form.querySelector('[data-role=crop-help]');
    function syncCropHelp() {
      const plot = selectedPlot(form);
      const crop = selectedCrop(form);
      if (!cropHelp) return;
      if (!crops.length) {
        cropHelp.textContent = 'El catálogo no tiene cultivos activos.' + (isStaff ? ' Regístralos desde la administración.' : ' Solicítalo al administrador.');
      } else if (plot && crop && plot.cropId && String(plot.cropId) !== String(crop.id)) {
        cropHelp.textContent = 'Simulación con otro cultivo: el registro del potrero (' + plot.crop + ') no se modifica.';
      } else if (plot && crop && !plot.cropId) {
        cropHelp.textContent = 'El potrero no tiene cultivo asignado; el cálculo no lo asigna.';
      } else {
        cropHelp.textContent = '';
      }
    }
    plotSelect.addEventListener('change', () => {
      const plot = selectedPlot(form);
      if (plot) {
        form.elements.area.value = Number(plot.areaHa.toFixed(4));
        form.elements.area.max = plot.areaHa;
        if (plot.cropId && cropById(plot.cropId)) cropSelect.value = String(plot.cropId);
        if (plotHelp) plotHelp.textContent = 'Superficie registrada: ' + fmt(plot.areaHa, 2) + ' ha · cultivo actual: ' + (plot.crop || 'sin asignar') + '.';
      } else if (plotHelp) {
        plotHelp.textContent = '';
      }
      syncCropHelp();
      onChange();
    });
    cropSelect.addEventListener('change', () => { syncCropHelp(); onChange(); });
    return syncCropHelp;
  }

  function validateBase(form) {
    const plot = selectedPlot(form);
    const area = Number(form.elements.area.value);
    if (!plot) return 'Selecciona un potrero registrado.';
    if (!(area > 0)) return 'La superficie debe ser mayor que 0.';
    if (area > plot.areaHa + 1e-9) return 'La superficie no puede superar las ' + fmt(plot.areaHa, 4) + ' ha registradas del potrero.';
    return '';
  }

  // ---------- resultados ----------
  function resultPanel(form) { return document.querySelector('[data-result-for="' + form.id + '"]'); }

  function emptyResult(panel, title, text) {
    panel.replaceChildren(el('p', 'result-kicker', title), el('p', 'muted', text));
  }

  function renderResult(form, spec) {
    const panel = resultPanel(form);
    panel.replaceChildren();
    panel.append(el('p', 'result-kicker', spec.kicker));
    const value = el('p', 'result-value');
    value.append(document.createTextNode(spec.value + ' '), el('span', '', spec.unit));
    panel.append(value);
    if (spec.secondary) panel.append(el('p', 'result-secondary', spec.secondary));
    if (spec.badge) panel.append(el('span', 'badge ' + (spec.badge.ok ? '' : 'amber'), spec.badge.text));
    const list = el('dl', 'result-facts');
    spec.rows.filter((row) => row[1] !== '' && row[1] !== null && row[1] !== undefined).forEach(([label, text]) => {
      list.append(el('dt', '', label), el('dd', '', text));
    });
    panel.append(list);
    if (spec.sourceUrl) {
      const url = safeUrl(spec.sourceUrl);
      if (url) {
        const link = el('a', 'text-link', 'Ver fuente técnica');
        link.href = url; link.target = '_blank'; link.rel = 'noopener noreferrer';
        panel.append(link);
      }
    }
    (spec.warnings || []).forEach((warning) => panel.append(el('p', 'result-warning', warning)));
    const actions = el('div', 'result-actions');
    const modify = el('button', 'button secondary', 'Modificar');
    modify.type = 'button';
    modify.addEventListener('click', () => {
      const first = form.querySelector('input:not([readonly]), select');
      if (first) first.focus();
      form.scrollIntoView({ behavior: 'smooth', block: 'start' });
    });
    const pdf = el('button', 'button secondary', 'Descargar PDF');
    pdf.type = 'button';
    pdf.addEventListener('click', () => downloadPdf(spec.pdfTitle || spec.kicker, pdfLines(spec)));
    actions.append(modify, pdf);
    if (spec.plan) {
      const plan = el('a', 'button secondary', 'Planificar como actividad');
      const query = new URLSearchParams();
      Object.entries(spec.plan).forEach(([key, value]) => { if (value !== '' && value !== null && value !== undefined) query.set(key, value); });
      plan.href = '/actividades/nueva/?' + query.toString();
      actions.append(plan);
    }
    if (spec.availability) {
      const avail = el('button', 'button', 'Consultar disponibilidad');
      avail.type = 'button';
      avail.addEventListener('click', () => goToAvailability(spec.availability));
      actions.append(avail);
    }
    panel.append(actions);
    panel.append(el('p', 'result-saved', 'Cálculo guardado en tu cuenta; también aparece en Reporte.'));
    lastResults[form.id] = spec;
  }

  function pdfLines(spec) {
    const lines = [spec.kicker + ': ' + spec.value + ' ' + spec.unit];
    if (spec.secondary) lines.push(spec.secondary);
    spec.rows.filter((row) => row[1]).forEach(([label, text]) => lines.push(label + ': ' + text));
    (spec.warnings || []).forEach((warning) => lines.push('Advertencia: ' + warning));
    return lines;
  }

  function downloadPdf(title, lines) {
    const today = new Date().toLocaleString('es-CL');
    const all = ['AgroAsesor · ' + title, 'Generado: ' + today, ''].concat(lines, ['',
      'Resultado orientativo. Verifica etiqueta, fuente técnica y condiciones del potrero antes de aplicar.']);
    const JsPdf = window.jspdf && window.jspdf.jsPDF;
    if (!JsPdf) {
      const win = window.open('', '_blank');
      if (!win) { alert('No se pudo generar el PDF. Revisa tu conexión e inténtalo nuevamente.'); return; }
      const doc = win.document;
      doc.title = 'AgroAsesor';
      all.forEach((line) => { const p = doc.createElement('p'); p.textContent = line; doc.body.append(p); });
      win.print();
      return;
    }
    const doc = new JsPdf({ unit: 'mm', format: 'a4' });
    let y = 18;
    doc.setFontSize(15); doc.text(all[0], 15, y); y += 8;
    doc.setFontSize(10);
    all.slice(1).forEach((line) => {
      doc.splitTextToSize(line, 180).forEach((chunk) => {
        if (y > 280) { doc.addPage(); y = 18; }
        doc.text(chunk, 15, y); y += 6;
      });
    });
    doc.save('agroasesor-' + title.toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '').replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '') + '.pdf');
  }

  function goToAvailability(info) {
    const form = document.getElementById('cover-form');
    form.elements.plot.value = info.plot || '';
    form.elements.plot.dispatchEvent(new Event('change'));
    if (info.crop) { form.elements.crop.value = info.crop; form.elements.crop.dispatchEvent(new Event('change')); }
    if (info.product) { form.elements.product.value = info.product; form.elements.product.dispatchEvent(new Event('change')); }
    if (info.area) form.elements.area.value = info.area;
    if (info.dose && !form.elements.dose.readOnly) form.elements.dose.value = info.dose;
    if (info.unit) form.elements.unit.value = info.unit;
    showTool('alcanza', true);
    form.elements.stock.focus({ preventScroll: true });
  }

  function techBox(box, item) {
    box.replaceChildren();
    if (!item) { box.hidden = true; return; }
    const statusText = {
      verified: 'Verificado con fuente', unverified: 'Información no verificada', restricted: 'Restringido', cancelled: 'Registro cancelado',
    }[item.verificationStatus] || 'Información no verificada';
    box.append(el('span', 'badge ' + (item.verificationStatus === 'verified' ? '' : 'amber'), statusText));
    const list = el('dl', 'tech-list');
    const add = (label, value) => { if (value !== null && value !== undefined && value !== '') list.append(el('dt', '', label), el('dd', '', String(value))); };
    add('Categoría', item.categoryLabel || item.type);
    add('Fabricante', item.manufacturer);
    add('Composición', item.nutrientComposition);
    add('Ingrediente activo', item.activeIngredient);
    add('Concentración', item.concentration);
    add('Variedad', item.seedVariety);
    add('Tipo de semilla', item.seedType);
    add('Germinación', item.germinationPct !== null && item.germinationPct !== undefined ? fmt(item.germinationPct) + ' %' : '');
    add('Pureza', item.purityPct !== null && item.purityPct !== undefined ? fmt(item.purityPct) + ' %' : '');
    add('Peso de mil semillas', item.thousandSeedWeightG ? fmt(item.thousandSeedWeightG) + ' g' : '');
    add('Dosis registrada', item.dose !== null && item.dose !== undefined ? fmt(item.dose, 3) + ' ' + (item.unit || '(sin unidad)') + (item.doseVerified ? ' · verificada' : ' · sin verificar') : 'No documentada');
    add('Presentación comercial', item.packageAmount && item.packageUnit ? fmt(item.packageAmount) + ' ' + item.packageUnit : '');
    add('Fuente', item.doseSource || item.sourceName);
    add('Verificado el', fmtDate(item.verifiedAt));
    box.append(list);
    const url = safeUrl(item.labelUrl || item.sourceUrl);
    if (url) {
      const link = el('a', 'text-link', item.labelUrl ? 'Ver etiqueta' : 'Ver ficha técnica');
      link.href = url; link.target = '_blank'; link.rel = 'noopener noreferrer';
      box.append(link);
    }
    box.hidden = false;
  }

  // ---------- CUÁNTO LLEVAR: semillas ----------
  const seedForm = document.getElementById('seed-form');
  (function setupSeeds() {
    const form = seedForm;
    const seedSelect = form.elements.seed;
    const doseHelp = form.querySelector('[data-role=dose-help]');
    const seedHelp = form.querySelector('[data-role=seed-help]');
    const tech = form.querySelector('[data-role=seed-tech]');
    const error = form.querySelector('[data-role=error]');

    function seedProducts(crop) {
      return products.filter((item) => item.category === 'seed' && crop && belongsToCrop(item, crop));
    }
    function refreshSeeds() {
      const crop = selectedCrop(form);
      const items = seedProducts(crop);
      const options = items.map((item) => ({
        value: 'p:' + item.id,
        label: item.name + (item.seedVariety ? ' · ' + item.seedVariety : '') +
          (item.doseVerified ? ' · ' + fmt(item.dose, 3) + ' ' + item.unit : ' · sin densidad verificada'),
      }));
      if (crop && crop.density !== null && crop.density !== undefined) {
        options.push({ value: 'crop', label: 'Densidad general del cultivo (catálogo)' + (crop.densitySource ? '' : ' · sin fuente') });
      }
      options.push({ value: 'manual', label: 'Ingreso manual (simulación)' });
      setOptions(seedSelect, options, crop ? 'Selecciona una semilla u opción' : 'Selecciona primero un cultivo');
      seedHelp.textContent = !crop ? '' : items.length
        ? items.length + ' semilla(s) registrada(s) para ' + crop.name + '.'
        : 'No hay semillas registradas para ' + crop.name + ' en el catálogo.';
      const requested = params.get('insumo');
      if (requested && [...seedSelect.options].some((option) => option.value === 'p:' + requested)) seedSelect.value = 'p:' + requested;
      else if (!seedSelect.value && items.length === 1) seedSelect.value = 'p:' + items[0].id;
      syncSeed();
    }
    function syncSeed() {
      const crop = selectedCrop(form);
      const value = seedSelect.value;
      const item = value.startsWith('p:') ? productById(value.slice(2)) : null;
      error.textContent = '';
      techBox(tech, item);
      if (item && item.doseVerified && item.dose) {
        form.elements.dose.value = item.dose;
        form.elements.unit.value = item.unit || 'kg/ha';
        doseHelp.textContent = 'Densidad documentada por: ' + (item.doseSource || item.sourceName) + '.';
      } else if (value === 'crop' && crop) {
        form.elements.dose.value = crop.density;
        form.elements.unit.value = (crop.unit || 'kg') + '/ha';
        doseHelp.textContent = crop.densitySource && crop.densityUrl
          ? 'Densidad general documentada: ' + crop.densitySource + (crop.densityVerifiedAt ? ' (verificada ' + fmtDate(crop.densityVerifiedAt) + ')' : '') + '.'
          : 'La densidad general del catálogo no tiene fuente: el resultado será una simulación.';
      } else {
        form.elements.dose.value = '';
        doseHelp.textContent = item
          ? 'Densidad no documentada para esta semilla (falta: ' + missingData(item, crop).join(', ') + '). Si ingresas un valor, el resultado será una simulación, no una recomendación.'
          : 'Ingresa la densidad de tu fuente técnica; el resultado se identificará como simulación.';
      }
      // Cálculo avanzado: precarga parámetros documentados de la semilla.
      const adv = form.elements;
      adv.plants_m2.value = item && item.targetPlantsM2 ? item.targetPlantsM2 : '';
      adv.tsw.value = item && item.thousandSeedWeightG ? item.thousandSeedWeightG : '';
      adv.germination.value = item && item.germinationPct ? item.germinationPct : '';
      adv.purity.value = item && item.purityPct ? item.purityPct : '';
      adv.adv_source.value = item && (item.targetPlantsM2 || item.thousandSeedWeightG) ? 'Ficha de semilla: ' + (item.sourceName || item.name) : '';
    }
    const syncHelp = setupPlotCrop(form, refreshSeeds);
    seedSelect.addEventListener('change', syncSeed);

    function context() {
      const plot = selectedPlot(form);
      const crop = selectedCrop(form);
      const value = seedSelect.value;
      const item = value.startsWith('p:') ? productById(value.slice(2)) : null;
      return { plot, crop, item, value };
    }

    form.addEventListener('submit', async (event) => {
      event.preventDefault();
      error.textContent = '';
      const { plot, crop, item } = context();
      const base = validateBase(form);
      if (base) { error.textContent = base; return; }
      if (!crop) { error.textContent = 'Selecciona un cultivo del catálogo.'; return; }
      if (!(Number(form.elements.dose.value) > 0)) { error.textContent = 'Ingresa una densidad mayor que 0.'; return; }
      const button = event.submitter; if (button) button.disabled = true;
      try {
        const data = await calculate({
          operation: 'dose', calculation_type: 'semillas', plot_id: plot.id, area: form.elements.area.value,
          dose: form.elements.dose.value, unit: form.elements.unit.value, crop: crop.name, product_id: item ? item.id : null,
        });
        const warnings = [];
        if (data.simulation) warnings.push('Simulación: la densidad usada no está documentada con una fuente verificada. No es una recomendación agronómica.');
        if (plot.cropId && String(plot.cropId) !== String(crop.id)) warnings.push('Calculado para un cultivo distinto al registrado en el potrero; el potrero no se modificó.');
        warnings.push('Ajusta la cantidad según el estado de la cama de siembra, la maquinaria y la recomendación técnica.');
        renderResult(form, {
          kicker: 'Semilla necesaria', pdfTitle: 'Cálculo de semillas', value: fmt(data.amount, 2), unit: data.unit,
          secondary: data.package ? 'Equivale a ' + data.package.count + ' envase(s) de ' + fmt(data.package.size) + ' ' + data.package.unit + ' (presentación registrada).' : '',
          badge: { ok: data.verified, text: data.verified ? 'Densidad documentada' : 'Simulación' },
          rows: [
            ['Potrero', plot.farmName + ' · ' + plot.name], ['Cultivo', crop.name], ['Semilla', item ? item.name : (seedSelect.value === 'crop' ? 'Densidad general del cultivo' : 'Ingreso manual')],
            ['Superficie calculada', fmt(data.area, 2) + ' ha'], ['Densidad', fmt(data.dose, 3) + ' ' + data.dose_unit],
            ['Fuente técnica', data.source || 'Sin fuente verificada'], ['Fecha de verificación', fmtDate(data.source_date)],
          ],
          sourceUrl: data.source_url, warnings,
          availability: { plot: plot.id, crop: crop.id, product: item ? item.id : '', area: data.area, dose: data.dose, unit: data.dose_unit },
          plan: { potrero: plot.id, tipo: 'siembra', insumo: item ? item.id : '', dosis: data.dose, unidad: data.dose_unit, superficie: data.area },
        });
      } catch (err) {
        error.textContent = err.message;
      } finally { if (button) button.disabled = false; }
    });

    form.querySelector('[data-action=advanced]').addEventListener('click', async () => {
      error.textContent = '';
      const { plot, crop, item } = context();
      const base = validateBase(form);
      if (base) { error.textContent = base; return; }
      const f = form.elements;
      if (![f.plants_m2, f.tsw, f.germination, f.purity].every((input) => Number(input.value) > 0)) {
        error.textContent = 'Completa plantas/m², peso de mil semillas, germinación y pureza con valores mayores que 0.'; return;
      }
      if (!f.adv_source.value.trim()) { error.textContent = 'Indica la fuente de los parámetros avanzados.'; return; }
      try {
        const data = await calculate({
          operation: 'seed_population', calculation_type: 'semillas', plot_id: plot.id, area: f.area.value, crop: crop ? crop.name : '',
          plants_m2: f.plants_m2.value, thousand_seed_weight_g: f.tsw.value, germination_pct: f.germination.value,
          purity_pct: f.purity.value, source: f.adv_source.value.trim(),
        });
        renderResult(form, {
          kicker: 'Semilla necesaria (cálculo avanzado)', pdfTitle: 'Cálculo avanzado de semillas', value: fmt(data.amount, 2), unit: data.unit,
          secondary: 'Equivale a ' + fmt(data.rate, 2) + ' kg/ha.',
          badge: { ok: false, text: 'Parámetros con fuente declarada' },
          rows: [
            ['Potrero', plot.farmName + ' · ' + plot.name], ['Cultivo', crop ? crop.name : ''], ['Semilla', item ? item.name : ''],
            ['Superficie calculada', fmt(f.area.value, 2) + ' ha'], ['Plantas objetivo', fmt(f.plants_m2.value) + ' por m²'],
            ['Peso de mil semillas', fmt(f.tsw.value) + ' g'], ['Germinación · pureza', fmt(f.germination.value) + ' % · ' + fmt(f.purity.value) + ' %'],
            ['Fuente declarada', data.source],
          ],
          warnings: ['Fórmula: plantas/m² × PMS ÷ (100 × germinación × pureza). No considera pérdidas de establecimiento salvo que las incluyas en la población objetivo.'],
          availability: { plot: plot.id, crop: crop ? crop.id : '', product: item ? item.id : '', area: f.area.value, dose: data.rate, unit: 'kg/ha' },
        });
      } catch (err) { error.textContent = err.message; }
    });
    emptyResult(resultPanel(form), 'Resultado', 'Selecciona potrero, cultivo y semilla, y presiona «Calcular ahora». El resultado aparecerá aquí.');
    syncHelp();
  })();

  // ---------- CUÁNTO LLEVAR: fertilizantes e insumos ----------
  const inputForm = document.getElementById('input-form');
  (function setupInputs() {
    const form = inputForm;
    const f = form.elements;
    const tech = form.querySelector('[data-role=product-tech]');
    const doseHelp = form.querySelector('[data-role=dose-help]');
    const error = form.querySelector('[data-role=error]');
    const targetField = form.querySelector('[data-role=target-field]');
    const nutrientBox = form.querySelector('[data-role=nutrient]');

    function cropProducts(crop) {
      return products.filter((item) => item.category !== 'seed' && belongsToCrop(item, crop));
    }
    function refreshCategories() {
      const crop = selectedCrop(form);
      const items = crop ? cropProducts(crop) : [];
      const keys = ['fertilizer', 'herbicide', 'fungicide', 'insecticide', 'other'];
      setOptions(f.category, keys.map((key) => {
        const count = items.filter((item) => item.category === key).length;
        return { value: key, label: (categoryLabels[key] || key) + ' (' + count + ')' };
      }), null);
      const requested = productById(params.get('insumo'));
      if (requested && requested.category !== 'seed' && !f.category.dataset.touched) f.category.value = requested.category;
      refreshProducts();
    }
    function refreshProducts() {
      const crop = selectedCrop(form);
      const category = f.category.value;
      const items = crop ? cropProducts(crop).filter((item) => item.category === category) : [];
      const options = items.map((item) => {
        if (PHYTO.has(category) && !verifiedPhytoFor(item, crop)) {
          return { value: item.id, label: item.name + ' · sin uso verificado (no calculable)', disabled: true };
        }
        return { value: item.id, label: item.name + (item.doseVerified ? ' · ' + fmt(item.dose, 3) + ' ' + item.unit : ' · dosis no verificada') };
      });
      if (!PHYTO.has(category)) options.push({ value: 'manual', label: 'Otro producto (simulación manual)' });
      setOptions(f.product, options, !crop ? 'Selecciona primero un cultivo' : items.length ? 'Selecciona un producto' : 'Sin productos de esta categoría para el cultivo');
      const requested = params.get('insumo');
      if (requested && [...f.product.options].some((option) => option.value === requested && !option.disabled)) f.product.value = requested;
      syncProduct();
    }
    function syncProduct() {
      const crop = selectedCrop(form);
      const item = productById(f.product.value);
      error.textContent = '';
      techBox(tech, item);
      const phyto = item && isPhyto(item);
      targetField.hidden = !phyto;
      f.dose.readOnly = Boolean(phyto);
      f.unit.disabled = Boolean(phyto);
      if (phyto) {
        setOptions(f.target, (item.controlTargets || []).map((target) => ({ value: target, label: target })), 'Selecciona el objetivo de control');
      }
      if (item && item.doseVerified && item.dose) {
        f.dose.value = item.dose;
        if ([...f.unit.options].some((option) => option.value === item.unit)) f.unit.value = item.unit;
        doseHelp.textContent = (phyto ? 'Dosis de etiqueta verificada (no editable): ' : 'Dosis documentada: ') + (item.doseSource || item.sourceName) + '.';
      } else {
        f.dose.value = '';
        doseHelp.textContent = item
          ? 'No hay dosis verificada. Falta: ' + missingData(item, crop).join(', ') + '. Si ingresas una dosis, el resultado será una simulación.'
          : f.product.value === 'manual' ? 'Ingresa la dosis de tu fuente técnica; el resultado se identificará como simulación.' : '';
      }
      const canNutrient = item && item.category === 'fertilizer' && item.verified && item.unit === 'kg/ha' && item.nutrientComposition;
      nutrientBox.hidden = !canNutrient;
      if (canNutrient) {
        setOptions(f.nutrient, [['N', item.nitrogenPct], ['P2O5', item.phosphorusP2o5Pct], ['K2O', item.potassiumK2oPct]]
          .filter(([, pct]) => pct > 0).map(([key, pct]) => ({ value: key, label: key + ' (' + fmt(pct) + ' %)' })), null);
      }
    }
    const syncHelp = setupPlotCrop(form, refreshCategories);
    f.category.addEventListener('change', () => { f.category.dataset.touched = '1'; refreshProducts(); });
    f.product.addEventListener('change', syncProduct);

    form.addEventListener('submit', async (event) => {
      event.preventDefault();
      error.textContent = '';
      const plot = selectedPlot(form);
      const crop = selectedCrop(form);
      const item = productById(f.product.value);
      const base = validateBase(form);
      if (base) { error.textContent = base; return; }
      if (!crop) { error.textContent = 'Selecciona un cultivo del catálogo.'; return; }
      if (!item && f.product.value !== 'manual') { error.textContent = 'Selecciona un producto o la opción de simulación manual.'; return; }
      if (item && isPhyto(item) && !f.target.value) { error.textContent = 'Selecciona el objetivo de control autorizado.'; return; }
      if (!(Number(f.dose.value) > 0)) { error.textContent = 'Ingresa una dosis mayor que 0.'; return; }
      const button = event.submitter; if (button) button.disabled = true;
      try {
        const phyto = item && isPhyto(item);
        const data = await calculate({
          operation: 'dose', calculation_type: phyto ? 'proteccion' : 'insumos', plot_id: plot.id, area: f.area.value,
          dose: f.dose.value, unit: phyto ? item.unit : f.unit.value, crop: crop.name, product_id: item ? item.id : null,
          target: phyto ? f.target.value : '',
        });
        const warnings = [];
        if (data.simulation) warnings.push('Simulación: la dosis no está documentada con una fuente verificada. No es una recomendación de aplicación.');
        if (phyto) warnings.push('Respeta la etiqueta autorizada: período de carencia, reingreso, equipo de protección y condiciones de aplicación.');
        warnings.push('La dosis adecuada depende de análisis de suelo, estado del cultivo y recomendación técnica.');
        renderResult(form, {
          kicker: 'Cantidad requerida', pdfTitle: 'Cálculo de insumo', value: fmt(data.amount, 2), unit: data.unit,
          secondary: data.package ? 'Equivale a ' + data.package.count + ' envase(s) de ' + fmt(data.package.size) + ' ' + data.package.unit + ' (presentación registrada).' : '',
          badge: { ok: data.verified, text: data.verified ? 'Dosis documentada' : 'Simulación' },
          rows: [
            ['Potrero', plot.farmName + ' · ' + plot.name], ['Cultivo', crop.name],
            ['Producto', item ? item.name + ' (' + item.categoryLabel + ')' : 'Producto manual'],
            ['Composición', item ? item.nutrientComposition || item.activeIngredient : ''],
            ['Objetivo de control', phyto ? f.target.value : ''],
            ['Superficie calculada', fmt(data.area, 2) + ' ha'], ['Dosis', fmt(data.dose, 3) + ' ' + data.dose_unit],
            ['Fuente técnica', data.source || 'Sin fuente verificada'], ['Fecha de verificación', fmtDate(data.source_date)],
          ],
          sourceUrl: data.source_url, warnings,
          availability: { plot: plot.id, crop: crop.id, product: item ? item.id : '', area: data.area, dose: data.dose, unit: data.dose_unit },
          plan: { potrero: plot.id, tipo: phyto ? 'control_fitosanitario' : 'fertilizacion', insumo: item ? item.id : '', dosis: data.dose, unidad: data.dose_unit, superficie: data.area, objetivo: phyto ? f.target.value : '' },
        });
      } catch (err) { error.textContent = err.message; } finally { if (button) button.disabled = false; }
    });

    form.querySelector('[data-action=nutrient]').addEventListener('click', async () => {
      error.textContent = '';
      const plot = selectedPlot(form);
      const crop = selectedCrop(form);
      const item = productById(f.product.value);
      const base = validateBase(form);
      if (base) { error.textContent = base; return; }
      if (!(Number(f.need.value) > 0) || !f.need_source.value.trim()) { error.textContent = 'Indica la necesidad del nutriente y su fuente.'; return; }
      try {
        const data = await calculate({
          operation: 'fertilizer_nutrition', calculation_type: 'insumos', plot_id: plot.id, area: f.area.value,
          crop: crop ? crop.name : '', product_id: item.id, nutrient: f.nutrient.value, need_per_ha: f.need.value, need_source: f.need_source.value.trim(),
        });
        renderResult(form, {
          kicker: 'Fertilizante requerido (por nutriente)', pdfTitle: 'Cálculo por nutriente', value: fmt(data.amount, 2), unit: data.unit,
          secondary: fmt(data.dose, 2) + ' kg de producto/ha para aportar ' + fmt(data.nutrientNeedPerHa) + ' kg/ha de ' + data.nutrient + '.',
          badge: { ok: true, text: 'Composición verificada' },
          rows: [
            ['Potrero', plot.farmName + ' · ' + plot.name], ['Cultivo', crop ? crop.name : ''], ['Producto', data.product],
            ['Nutriente', data.nutrient + ' (' + fmt(data.nutrientPct) + ' %)'], ['Nutriente aportado', fmt(data.nutrientApplied, 2) + ' kg'],
            ['Superficie calculada', fmt(f.area.value, 2) + ' ha'], ['Fuente de la necesidad', data.nutrientSource], ['Fuente del producto', data.productSource],
          ],
          warnings: ['La necesidad nutricional debe provenir de un análisis de suelo o una recomendación técnica.'],
          availability: { plot: plot.id, crop: crop ? crop.id : '', product: item.id, area: f.area.value, dose: data.dose, unit: 'kg/ha' },
        });
      } catch (err) { error.textContent = err.message; }
    });
    emptyResult(resultPanel(form), 'Resultado', 'Elige categoría y producto. Solo se habilitan productos fitosanitarios con uso verificado para el cultivo.');
    syncHelp();
  })();

  // ---------- SI ALCANZA ----------
  (function setupCoverage() {
    const form = document.getElementById('cover-form');
    const f = form.elements;
    const error = form.querySelector('[data-role=error]');
    const productHelp = form.querySelector('[data-role=product-help]');
    const doseHelp = form.querySelector('[data-role=dose-help]');
    const targetField = form.querySelector('[data-role=target-field]');
    function refresh() {
      const crop = selectedCrop(form);
      const items = crop ? products.filter((item) => belongsToCrop(item, crop) || (!item.cropId && !item.crop)) : [];
      const options = items.map((item) => (isPhyto(item) && !verifiedPhytoFor(item, crop))
        ? { value: item.id, label: item.categoryLabel + ' · ' + item.name + ' · sin uso verificado', disabled: true }
        : { value: item.id, label: item.categoryLabel + ' · ' + item.name });
      options.push({ value: 'manual', label: 'Producto no registrado (simulación)' });
      setOptions(f.product, options, crop ? 'Selecciona un producto' : 'Selecciona primero un cultivo');
      sync();
    }
    function sync() {
      const crop = selectedCrop(form);
      const item = productById(f.product.value);
      const phyto = item && isPhyto(item);
      targetField.hidden = !phyto;
      if (phyto) setOptions(f.target, (item.controlTargets || []).map((t) => ({ value: t, label: t })), 'Selecciona el objetivo');
      f.dose.readOnly = Boolean(phyto);
      f.unit.disabled = Boolean(phyto);
      if (item && item.doseVerified && item.dose) {
        f.dose.value = item.dose;
        if ([...f.unit.options].some((o) => o.value === item.unit)) f.unit.value = item.unit;
        doseHelp.textContent = 'Dosis documentada: ' + (item.doseSource || item.sourceName) + '.';
      } else if (item) {
        doseHelp.textContent = 'Sin dosis verificada (falta: ' + missingData(item, crop).join(', ') + '). Lo que ingreses será una simulación.';
      } else {
        doseHelp.textContent = '';
      }
      productHelp.textContent = item ? 'Registrado en catálogo; la cantidad disponible la indicas tú (no hay inventario registrado).' : '';
    }
    const syncHelp = setupPlotCrop(form, refresh);
    f.product.addEventListener('change', sync);
    form.addEventListener('submit', async (event) => {
      event.preventDefault();
      error.textContent = '';
      const plot = selectedPlot(form);
      const crop = selectedCrop(form);
      const item = productById(f.product.value);
      const base = validateBase(form);
      if (base) { error.textContent = base; return; }
      if (!crop) { error.textContent = 'Selecciona un cultivo.'; return; }
      if (!item && f.product.value !== 'manual') { error.textContent = 'Selecciona un producto.'; return; }
      if (f.stock.value === '' || Number(f.stock.value) < 0) { error.textContent = 'La cantidad disponible debe ser 0 o mayor.'; return; }
      if (!(Number(f.dose.value) > 0)) { error.textContent = 'Ingresa una dosis o requerimiento mayor que 0.'; return; }
      const phyto = item && isPhyto(item);
      if (phyto && !f.target.value) { error.textContent = 'Selecciona el objetivo de control.'; return; }
      const button = event.submitter; if (button) button.disabled = true;
      try {
        const unit = phyto ? item.unit : f.unit.value;
        const data = await calculate({
          operation: 'coverage', calculation_type: phyto ? 'proteccion' : 'coverage', plot_id: plot.id, area: f.area.value,
          dose: f.dose.value, unit, stock: f.stock.value, crop: crop.name, product_id: item ? item.id : null, target: phyto ? f.target.value : '',
        });
        const enough = data.missingQty <= 0;
        const difference = data.stock - data.needed;
        renderResult(form, {
          kicker: enough ? 'Te alcanza' : 'No te alcanza', pdfTitle: 'Disponibilidad de insumo',
          value: fmt(data.percent, 0) + ' %', unit: 'de la superficie cubierta',
          secondary: enough ? 'Sobran ' + fmt(data.surplus, 2) + ' ' + data.unit + '.' : 'Faltan ' + fmt(data.missingQty, 2) + ' ' + data.unit + ' para cubrir ' + fmt(data.missingHa, 2) + ' ha.',
          badge: { ok: data.verified, text: data.verified ? 'Dosis documentada' : 'Simulación' },
          rows: [
            ['Potrero', plot.farmName + ' · ' + plot.name], ['Cultivo', crop.name], ['Producto', item ? item.name : 'Producto manual'],
            ['Cantidad necesaria', fmt(data.needed, 2) + ' ' + data.unit], ['Cantidad disponible (indicada)', fmt(data.stock, 2) + ' ' + data.unit],
            ['Diferencia', (difference >= 0 ? '+' : '') + fmt(difference, 2) + ' ' + data.unit],
            ['Superficie que se puede cubrir', fmt(data.coveredHa, 2) + ' de ' + fmt(data.area, 2) + ' ha'],
            ['Dosis', fmt(data.dose, 3) + ' ' + data.dose_unit], ['Fuente técnica', data.source || 'Sin fuente verificada'],
          ],
          sourceUrl: data.source_url,
          warnings: ['Simulación de disponibilidad: no se descontó ninguna existencia ni se registró inventario.'].concat(data.simulation ? ['La dosis usada no está documentada con fuente verificada.'] : []),
        });
      } catch (err) { error.textContent = err.message; } finally { if (button) button.disabled = false; }
    });
    emptyResult(resultPanel(form), 'Resultado', 'Indica cuánto producto tienes y comprueba qué superficie alcanzas a cubrir.');
    syncHelp();
  })();

  // ---------- COSECHA ----------
  (function setupYield() {
    const form = document.getElementById('yield-form');
    const f = form.elements;
    const error = form.querySelector('[data-role=error]');
    const rateHelp = form.querySelector('[data-role=rate-help]');
    const datalist = document.getElementById('yield-varieties');
    let reference = null;
    function findReference() {
      const plot = selectedPlot(form);
      const crop = selectedCrop(form);
      if (!plot || !crop || !plot.zoneId) return null;
      const refs = (catalog.regionalYieldReferences || []).filter((ref) => String(ref.cropId) === String(crop.id) && String(ref.zoneId) === String(plot.zoneId));
      const variety = (f.variety.value || '').trim().toLocaleLowerCase('es');
      return refs.find((ref) => variety && ref.variety.toLocaleLowerCase('es') === variety) || refs.find((ref) => !ref.variety) || null;
    }
    function sync() {
      const plot = selectedPlot(form);
      const crop = selectedCrop(form);
      datalist.replaceChildren();
      ((catalog.varieties || {})[crop ? crop.id : ''] || []).forEach((v) => datalist.append(new Option(v, v)));
      if (plot && crop && plot.cropId && String(plot.cropId) === String(crop.id) && plot.variety && !f.variety.dataset.touched) f.variety.value = plot.variety;
      reference = findReference();
      f.rate.readOnly = Boolean(reference);
      f.source.readOnly = Boolean(reference);
      if (reference) {
        f.rate.value = reference.rate;
        f.source.value = reference.source + ' · ' + reference.document;
        rateHelp.textContent = 'Referencia verificada para ' + reference.zone + (reference.variety ? ' · ' + reference.variety : '') + ' (consultada ' + fmtDate(reference.verifiedAt) + ').';
      } else {
        const general = crop ? (catalog.yieldReferences || {})[crop.name] : null;
        if (!f.rate.dataset.touched) f.rate.value = '';
        if (!f.source.dataset.touched) f.source.value = '';
        rateHelp.textContent = !plot || !plot.zoneId
          ? 'El predio no tiene zona agrícola: ingresa tu rendimiento esperado y su origen.'
          : general && general.rate
            ? 'Sin referencia regional verificada. El catálogo registra ' + fmt(general.rate) + ' ton/ha como dato general' + (general.source ? ' (' + general.source + ')' : ' sin fuente') + '; úsalo solo si aplica a tu caso.'
            : 'Sin referencia verificada: ingresa un rendimiento esperado y su origen.';
      }
    }
    const syncHelp = setupPlotCrop(form, sync);
    f.variety.addEventListener('change', () => { f.variety.dataset.touched = '1'; sync(); });
    f.rate.addEventListener('input', () => { f.rate.dataset.touched = '1'; });
    f.source.addEventListener('input', () => { f.source.dataset.touched = '1'; });
    form.addEventListener('submit', async (event) => {
      event.preventDefault();
      error.textContent = '';
      const plot = selectedPlot(form);
      const crop = selectedCrop(form);
      const base = validateBase(form);
      if (base) { error.textContent = base; return; }
      if (!crop) { error.textContent = 'Selecciona un cultivo.'; return; }
      if (!reference && !(Number(f.rate.value) > 0)) { error.textContent = 'Ingresa un rendimiento esperado mayor que 0.'; return; }
      if (!reference && !f.source.value.trim()) { error.textContent = 'Indica el origen del rendimiento.'; return; }
      const button = event.submitter; if (button) button.disabled = true;
      try {
        const data = await calculate({
          operation: 'yield', calculation_type: 'rendimiento', plot_id: plot.id, area: f.area.value, crop: crop.name,
          variety: f.variety.value.trim(), rate: f.rate.value, source: f.source.value.trim(),
        });
        renderResult(form, {
          kicker: 'Producción estimada', pdfTitle: 'Estimación de cosecha', value: fmt(data.production, 2), unit: 'ton',
          secondary: fmt(data.rate, 2) + ' ton/ha × ' + fmt(f.area.value, 2) + ' ha',
          badge: { ok: data.source_verified, text: data.source_verified ? 'Referencia regional verificada' : 'Rendimiento ingresado por ti' },
          rows: [
            ['Potrero', plot.farmName + ' · ' + plot.name], ['Cultivo', crop.name], ['Variedad', f.variety.value.trim() || 'No indicada'],
            ['Superficie', fmt(f.area.value, 2) + ' ha'], ['Rendimiento usado', fmt(data.rate, 2) + ' ton/ha'],
            ['Origen del dato', data.source], ['Fecha de consulta', fmtDate(data.source_date)],
          ],
          sourceUrl: data.source_url,
          warnings: ['Estimación, no predicción: no considera clima de la temporada, suelo, manejo, sanidad ni pérdidas de cosecha.'],
        });
      } catch (err) { error.textContent = err.message; } finally { if (button) button.disabled = false; }
    });
    emptyResult(resultPanel(form), 'Resultado', 'La estimación multiplica superficie por rendimiento esperado e indica de dónde proviene ese rendimiento.');
    syncHelp();
  })();

  // ---------- FICHA DE INSUMO (4 pasos) ----------
  const ficha = { step: 0, crop: '', problem: '', category: '', product: '' };
  const fichaSteps = document.getElementById('ficha-steps');
  const fichaBody = document.getElementById('ficha-body');
  const fichaContext = document.getElementById('ficha-context');
  const STEP_LABELS = ['Cultivo', 'Problema agrícola', 'Tipo de insumo', 'Ficha del producto'];
  const PROBLEM_TYPES = [['pest', 'Plagas'], ['disease', 'Enfermedades'], ['weed', 'Malezas'], ['nutrition', 'Problemas nutricionales'], ['other', 'Otros problemas']];
  const STEP_HELP = [
    'Elige un cultivo registrado en el catálogo. Solo se muestran cultivos activos.',
    'Elige el problema documentado para el cultivo. También puedes ver todos los insumos del cultivo sin filtrar por problema.',
    'Se muestran solo categorías con productos registrados para el cultivo y el problema elegidos.',
    'Selecciona un producto para ver su ficha. Las dosis solo se usan en cálculos cuando están verificadas.',
  ];

  function fichaProducts() {
    const crop = cropById(ficha.crop);
    return allProducts.filter((item) => item.active !== false && crop && belongsToCrop(item, crop) &&
      (!ficha.problem || ficha.problem === '*' || (item.problemIds || []).includes(String(ficha.problem))));
  }

  function choiceButton(label, detail, onClick, disabled) {
    const button = el('button', 'choice-card');
    button.type = 'button';
    button.append(el('strong', '', label));
    if (detail) button.append(el('span', '', detail));
    if (disabled) button.disabled = true;
    else button.addEventListener('click', onClick);
    return button;
  }

  function renderFichaSteps() {
    fichaSteps.replaceChildren();
    STEP_LABELS.forEach((label, index) => {
      const item = el('li', index === ficha.step ? 'is-active' : index < ficha.step ? 'is-complete' : '');
      const button = el('button', '', '');
      button.type = 'button';
      button.append(el('span', 'step-number', String(index + 1)), document.createTextNode(' ' + label));
      button.disabled = index > ficha.step;
      if (index === ficha.step) button.setAttribute('aria-current', 'step');
      button.addEventListener('click', () => { ficha.step = index; renderFicha(); });
      item.append(button);
      fichaSteps.append(item);
    });
  }

  function renderFichaContext() {
    fichaContext.replaceChildren();
    fichaContext.append(el('p', 'result-kicker', 'Paso ' + (ficha.step + 1) + ' de 4 · ' + STEP_LABELS[ficha.step]));
    fichaContext.append(el('p', 'muted', STEP_HELP[ficha.step]));
    const crop = cropById(ficha.crop);
    if (!crop) {
      fichaContext.append(el('p', 'muted', crops.length ? 'Aún no eliges un cultivo.' : 'El catálogo no tiene cultivos registrados.'));
      return;
    }
    fichaContext.append(el('h3', '', crop.name));
    if (crop.description) fichaContext.append(el('p', '', crop.description));
    const list = el('dl', 'result-facts');
    const add = (label, value) => list.append(el('dt', '', label), el('dd', '', value));
    add('Densidad de siembra', crop.density !== null && crop.density !== undefined ? fmt(crop.density) + ' ' + (crop.unit || 'kg') + '/ha' + (crop.densitySource ? ' · ' + crop.densitySource : ' · sin fuente') : 'No documentada');
    const cropProblems = problems.filter((problem) => (problem.cropIds || []).includes(String(crop.id)));
    add('Problemas documentados', cropProblems.length ? cropProblems.map((p) => p.name).join(', ') : 'Ninguno registrado');
    add('Productos en catálogo', String(allProducts.filter((item) => belongsToCrop(item, crop)).length));
    fichaContext.append(list);
    const problem = problems.find((p) => String(p.id) === String(ficha.problem));
    if (problem) {
      fichaContext.append(el('h4', '', problem.typeLabel + ': ' + problem.name));
      if (problem.symptoms) fichaContext.append(el('p', '', 'Síntomas: ' + problem.symptoms));
      if (problem.description) fichaContext.append(el('p', '', problem.description));
      const url = safeUrl(problem.sourceUrl);
      if (problem.sourceName || url) {
        const p = el('p', 'muted', 'Fuente: ' + (problem.sourceName || ''));
        if (url) { const a = el('a', 'text-link', ' ver documento'); a.href = url; a.target = '_blank'; a.rel = 'noopener noreferrer'; p.append(a); }
        fichaContext.append(p);
      }
    }
    const sources = [...new Set(fichaProducts().map((item) => item.sourceName).filter(Boolean))];
    if (sources.length) fichaContext.append(el('p', 'muted', 'Fuentes técnicas disponibles: ' + sources.join(' · ')));
    fichaContext.append(el('p', 'result-warning', 'La ficha no reemplaza la etiqueta autorizada ni la asesoría de un profesional.'));
  }

  function renderFicha() {
    renderFichaSteps();
    renderFichaContext();
    fichaBody.replaceChildren();
    const crop = cropById(ficha.crop);
    if (ficha.step === 0) {
      fichaBody.append(el('h2', '', '¿Qué cultivo quieres consultar?'));
      if (!crops.length) {
        fichaBody.append(el('p', 'muted', 'No hay cultivos registrados en el catálogo. ' + (isStaff ? 'Regístralos desde la administración.' : 'Solicita al administrador que cargue el catálogo.')));
        return;
      }
      const grid = el('div', 'choice-grid');
      crops.forEach((item) => {
        const count = allProducts.filter((product) => belongsToCrop(product, item)).length;
        grid.append(choiceButton(item.name, count + ' insumo(s) registrados', () => {
          Object.assign(ficha, { crop: String(item.id), problem: '', category: '', product: '', step: 1 });
          renderFicha();
        }));
      });
      fichaBody.append(grid);
      return;
    }
    if (ficha.step === 1) {
      fichaBody.append(el('h2', '', 'Problema agrícola en ' + crop.name));
      const cropProblems = problems.filter((problem) => (problem.cropIds || []).includes(String(crop.id)));
      if (!cropProblems.length) fichaBody.append(el('p', 'muted', 'No hay problemas documentados para este cultivo en el catálogo.'));
      PROBLEM_TYPES.forEach(([type, label]) => {
        const group = cropProblems.filter((problem) => problem.type === type);
        if (!group.length) return;
        fichaBody.append(el('h3', 'choice-group-title', label));
        const grid = el('div', 'choice-grid');
        group.forEach((problem) => {
          const count = allProducts.filter((item) => belongsToCrop(item, crop) && (item.problemIds || []).includes(String(problem.id))).length;
          grid.append(choiceButton(problem.name, count ? count + ' producto(s) documentado(s)' : 'Sin productos documentados', () => {
            Object.assign(ficha, { problem: String(problem.id), category: '', product: '', step: 2 });
            renderFicha();
          }, count === 0));
        });
        fichaBody.append(grid);
      });
      const all = choiceButton('Ver todos los insumos de ' + crop.name, 'Sin filtrar por problema', () => {
        Object.assign(ficha, { problem: '*', category: '', product: '', step: 2 });
        renderFicha();
      });
      all.classList.add('choice-secondary');
      fichaBody.append(all);
      return;
    }
    if (ficha.step === 2) {
      fichaBody.append(el('h2', '', 'Tipo de insumo'));
      const items = fichaProducts();
      const keys = [...new Set(items.map((item) => item.category))];
      if (!keys.length) {
        fichaBody.append(el('p', 'muted', 'No hay productos documentados para esta combinación.'));
        return;
      }
      const grid = el('div', 'choice-grid');
      keys.forEach((key) => {
        const count = items.filter((item) => item.category === key).length;
        grid.append(choiceButton(categoryLabels[key] || key, count + ' producto(s)', () => {
          Object.assign(ficha, { category: key, product: '', step: 3 });
          renderFicha();
        }));
      });
      fichaBody.append(grid);
      return;
    }
    const items = fichaProducts().filter((item) => item.category === ficha.category);
    fichaBody.append(el('h2', '', (categoryLabels[ficha.category] || 'Productos') + ' para ' + crop.name));
    const list = el('div', 'product-picker');
    items.forEach((item) => {
      const button = el('button', 'product-pick' + (String(item.id) === String(ficha.product) ? ' is-selected' : ''));
      button.type = 'button';
      button.append(el('strong', '', item.name));
      const status = isPhyto(item) ? (verifiedPhytoFor(item, crop) ? 'Uso verificado' : 'Sin uso verificado') : (item.verified ? 'Verificado' : 'Sin verificar');
      button.append(el('span', 'badge ' + (status.startsWith('Sin') ? 'amber' : ''), status));
      button.addEventListener('click', () => { ficha.product = String(item.id); renderFicha(); });
      list.append(button);
    });
    fichaBody.append(list);
    const item = productById(ficha.product);
    if (item) fichaBody.append(productSheet(item, crop));
    const nav = el('div', 'result-actions');
    const back = el('button', 'button secondary', 'Volver al paso anterior');
    back.type = 'button';
    back.addEventListener('click', () => { ficha.step = 2; renderFicha(); });
    const restart = el('button', 'button secondary', 'Iniciar nueva consulta');
    restart.type = 'button';
    restart.addEventListener('click', () => { Object.assign(ficha, { step: 0, crop: '', problem: '', category: '', product: '' }); renderFicha(); });
    nav.append(back, restart);
    fichaBody.append(nav);
  }

  function productSheet(item, crop) {
    const card = el('article', 'product-sheet');
    const phyto = isPhyto(item);
    const usable = phyto ? verifiedPhytoFor(item, crop) : item.doseVerified === true;
    card.append(el('h3', '', item.name));
    const statusText = { verified: 'Verificado con fuente', restricted: 'Restringido', cancelled: 'Registro cancelado' }[item.verificationStatus] || 'Información no verificada';
    card.append(el('span', 'badge ' + (item.verificationStatus === 'verified' ? '' : 'amber'), statusText));
    card.append(el('p', 'muted', 'El estado refleja lo registrado por el administrador del catálogo; no es una consulta en línea al SAG.'));
    const list = el('dl', 'sheet-list');
    const rows = [
      ['Nombre comercial', item.name], ['Categoría', item.categoryLabel], ['Fabricante', item.manufacturer],
      ['Ingrediente activo o composición', item.activeIngredient || item.nutrientComposition], ['Concentración', item.concentration],
      ['Formulación', item.formulation], ['Cultivo', item.crop || 'Sin cultivo asociado'],
      ['Uso documentado', (item.problems || []).join(', ') || (item.controlTargets || []).join(', ')],
      ['Cultivos autorizados', (item.authorizedCrops || []).join(', ')], ['Objetivos de control', (item.controlTargets || []).join(', ')],
      ['Dosis' + (phyto ? ' autorizada' : ''), item.dose !== null && item.dose !== undefined ? fmt(item.dose, 3) + ' ' + (item.unit || '') + (item.doseVerified ? ' (verificada)' : ' (sin verificar)') : 'No documentada'],
      ['Dosis máxima', item.maxDose ? fmt(item.maxDose, 3) + ' ' + item.maxDoseUnit : ''],
      ['Modo de aplicación (etiqueta)', item.applicationMode], ['Restricciones', item.restrictions],
      ['Período de carencia', item.preharvestInterval], ['Tiempo de reingreso', item.reentryInterval],
      ['Precauciones ambientales', item.environmentalPrecautions], ['Advertencia para polinizadores', item.pollinatorWarning],
      ['Autorización SAG', item.sagRegistration], ['Presentación', item.packageAmount && item.packageUnit ? fmt(item.packageAmount) + ' ' + item.packageUnit : ''],
      ['Fuente técnica', item.sourceName], ['Fuente de la dosis', item.doseSource], ['Fecha de verificación', fmtDate(item.verifiedAt)],
      ['Vigencia', item.validFrom || item.validUntil ? (fmtDate(item.validFrom) || 'sin inicio') + ' – ' + (fmtDate(item.validUntil) || 'sin término') : ''],
    ];
    rows.forEach(([label, value]) => { if (value) list.append(el('dt', '', label), el('dd', '', value)); });
    card.append(list);
    const links = el('p', 'sheet-links');
    [['Etiqueta', item.labelUrl], ['Hoja de seguridad', item.safetySheetUrl], ['Fuente técnica', item.sourceUrl]].forEach(([label, href]) => {
      const url = safeUrl(href);
      if (url) { const a = el('a', 'text-link', label); a.href = url; a.target = '_blank'; a.rel = 'noopener noreferrer'; links.append(a); }
    });
    if (links.childNodes.length) card.append(links);
    if (!usable) {
      card.append(el('p', 'result-warning', 'Información no verificada para cálculo. Falta: ' + missingData(item, crop).join(', ') +
        '. No se habilitan cálculos de aplicación con dosis no confirmadas.'));
    }
    const actions = el('div', 'result-actions');
    const pdf = el('button', 'button secondary', 'Descargar ficha PDF');
    pdf.type = 'button';
    pdf.addEventListener('click', () => {
      const lines = rows.filter(([, value]) => value).map(([label, value]) => label + ': ' + value);
      lines.unshift('Estado: ' + statusText);
      if (!usable) lines.push('Advertencia: información no verificada para cálculo.');
      downloadPdf('Ficha de insumo ' + item.name, lines);
    });
    const toCalc = el('button', 'button', 'Llevar a «Cuánto llevar»');
    toCalc.type = 'button';
    toCalc.addEventListener('click', () => sendToCalculator(item, crop));
    const avail = el('button', 'button secondary', 'Consultar disponibilidad');
    avail.type = 'button';
    avail.addEventListener('click', () => {
      const plot = params.get('plot') && plotById(params.get('plot')) ? params.get('plot') : '';
      goToAvailability({ plot, crop: crop.id, product: phyto && !usable ? '' : item.id });
    });
    actions.append(pdf, toCalc, avail);
    card.append(actions);
    return card;
  }

  function sendToCalculator(item, crop) {
    const plotId = params.get('plot') && plotById(params.get('plot')) ? params.get('plot') : '';
    showTool('llevar', true);
    if (item.category === 'seed') {
      showKind('semillas');
      const f = seedForm.elements;
      if (plotId) { f.plot.value = plotId; f.plot.dispatchEvent(new Event('change')); }
      f.crop.value = String(crop.id); f.crop.dispatchEvent(new Event('change'));
      if ([...f.seed.options].some((o) => o.value === 'p:' + item.id)) { f.seed.value = 'p:' + item.id; f.seed.dispatchEvent(new Event('change')); }
    } else {
      showKind('insumos');
      const f = inputForm.elements;
      if (plotId) { f.plot.value = plotId; f.plot.dispatchEvent(new Event('change')); }
      f.crop.value = String(crop.id); f.crop.dispatchEvent(new Event('change'));
      f.category.value = item.category; f.category.dataset.touched = '1'; f.category.dispatchEvent(new Event('change'));
      const option = [...f.product.options].find((o) => o.value === String(item.id));
      if (option && !option.disabled) { f.product.value = String(item.id); f.product.dispatchEvent(new Event('change')); }
      else {
        const error = inputForm.querySelector('[data-role=error]');
        error.textContent = 'El producto no tiene un uso verificado para calcular: se conservó el cultivo, pero no se asumió ninguna dosis.';
      }
    }
  }

  // ---------- estado inicial desde la URL ----------
  function applyInitialSelection() {
    const plotId = params.get('plot');
    const cropId = params.get('crop');
    [seedForm, inputForm, document.getElementById('cover-form'), document.getElementById('yield-form')].forEach((form) => {
      if (plotId && plotById(plotId)) { form.elements.plot.value = plotId; form.elements.plot.dispatchEvent(new Event('change')); }
      if (cropId && cropById(cropId)) { form.elements.crop.value = cropId; form.elements.crop.dispatchEvent(new Event('change')); }
    });
    const requested = productById(params.get('insumo'));
    if (cropId && cropById(cropId)) {
      ficha.crop = cropId;
      ficha.step = 1;
      if (requested && belongsToCrop(requested, cropById(cropId))) {
        Object.assign(ficha, { problem: '*', category: requested.category, product: String(requested.id), step: 3 });
      }
    }
    renderFicha();
    const tool = params.get('herramienta') || (params.get('modo') === 'ficha' ? 'ficha' : 'llevar');
    showKind(params.get('tipo') || (requested && requested.category !== 'seed' ? 'insumos' : 'semillas'));
    if (tool === 'llevar' && requested) {
      if (requested.category === 'seed' && cropId) seedForm.elements.seed.dispatchEvent(new Event('change'));
    }
    showTool(tool);
  }
  applyInitialSelection();
})();
