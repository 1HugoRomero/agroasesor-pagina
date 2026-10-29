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
  // «potrero» es el nombre público del parámetro; «plot» se mantiene por compatibilidad con enlaces anteriores.
  if (!params.has('plot') && params.has('potrero')) params.set('plot', params.get('potrero'));
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
    root.dataset.tool = name;
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

  document.querySelectorAll('[data-go-tool]').forEach((link) => link.addEventListener('click', (event) => {
    event.preventDefault();
    showTool(link.dataset.goTool);
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }));

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
        else if (!plot.cropId) cropSelect.value = '';  // no se arrastra el cultivo del potrero anterior
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
    const top = el('div', 'calc-result-top');
    top.append(el('p', 'result-kicker', spec.kicker));
    if (spec.badge) top.append(el('span', 'badge ' + (spec.badge.ok ? '' : 'amber'), spec.badge.text));
    panel.append(top);
    const value = el('p', 'result-value');
    value.append(el('strong', '', spec.value), el('span', '', spec.unit));
    panel.append(value);
    if (spec.bar !== undefined) {
      const track = el('div', 'cover-bar');
      track.setAttribute('role', 'progressbar');
      track.setAttribute('aria-valuemin', '0'); track.setAttribute('aria-valuemax', '100');
      const pct = Math.max(0, Math.min(100, Number(spec.bar) || 0));
      track.setAttribute('aria-valuenow', String(Math.round(pct)));
      const fill = el('span', 'cover-bar-fill' + (pct >= 100 ? ' is-full' : ''));
      fill.style.width = pct + '%';
      track.append(fill);
      panel.append(track);
    }
    if (spec.figures) {
      const grid = el('div', 'cover-figures');
      spec.figures.forEach(([label, text, tone]) => {
        const cell = el('div', 'cover-figure' + (tone ? ' is-' + tone : ''));
        cell.append(el('span', '', label), el('strong', '', text));
        grid.append(cell);
      });
      panel.append(grid);
    }
    if (spec.message) panel.append(el('p', 'cover-message' + (spec.messageTone ? ' is-' + spec.messageTone : ''), spec.message));
    const rows = spec.rows.filter((row) => row[1] !== '' && row[1] !== null && row[1] !== undefined);
    const list = el('dl', 'calc-ctx');
    rows.forEach(([label, text]) => { list.append(el('dt', '', label), el('dd', '', text)); });
    panel.append(list);
    if (spec.secondary) {
      const box = el('div', 'formula-box');
      box.append(el('p', 'formula-line', spec.formulaTitle || 'Resumen'), el('p', '', spec.secondary));
      panel.append(box);
    }
    if (spec.sourceUrl) {
      const url = safeUrl(spec.sourceUrl);
      if (url) {
        const source = el('p', 'calc-source');
        const link = el('a', 'text-link', 'Ver fuente técnica');
        link.href = url; link.target = '_blank'; link.rel = 'noopener noreferrer';
        source.append(link);
        panel.append(source);
      }
    }
    (spec.warnings || []).forEach((warning) => panel.append(el('p', 'alert', warning)));
    panel.append(el('p', 'callout', 'Cálculo guardado en tu cuenta; también aparece en Reporte.'));
    const actions = el('div', 'calc-result-actions');
    const pdf = el('button', 'btn-secondary-agro btn-sm', 'Descargar PDF');
    pdf.type = 'button';
    pdf.addEventListener('click', () => downloadPdf(spec.pdfTitle || spec.kicker, pdfLines(spec)));
    actions.append(pdf);
    const report = el('a', 'btn-secondary-agro btn-sm', 'Ver en Reportes');
    report.href = '/reportes/?tipo=calculos';
    actions.append(report);
    if (spec.plan) {
      const plan = el('a', 'btn-secondary-agro btn-sm', 'Planificar como actividad');
      const query = new URLSearchParams();
      Object.entries(spec.plan).forEach(([key, val]) => { if (val !== '' && val !== null && val !== undefined) query.set(key, val); });
      plan.href = '/actividades/nueva/?' + query.toString();
      actions.append(plan);
    }
    if (spec.availability) {
      const avail = el('button', 'btn-ghost-agro btn-sm', 'Ir a «¿Me alcanza?»');
      avail.type = 'button';
      avail.addEventListener('click', () => goToAvailability(spec.availability));
      actions.append(avail);
    }
    panel.append(actions);
    lastResults[form.id] = spec;
    // La capa guiada (tool-flow.js) marca el paso final y el estado como completados.
    form.dispatchEvent(new CustomEvent('flow:result', { detail: { simulation: spec.badge ? !spec.badge.ok : false } }));
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
    form.dispatchEvent(new CustomEvent('flow:refresh'));
    showTool('alcanza', true);
    form.elements.stock.focus({ preventScroll: true });
  }

  // «Cuánto llevar» (semillas, insumos y cálculos avanzados) vive en calc-panel.js,
  // con el diseño de la calculadora de AgroAsesor. Aquí solo se le envían datos desde la ficha.

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
        const surplus = Math.max(0, data.stock - data.needed);
        const shortfall = Math.max(0, data.needed - data.stock);
        const unitText = data.unit;
        renderResult(form, {
          kicker: enough ? 'Cantidad suficiente' : 'Cantidad insuficiente', pdfTitle: 'Disponibilidad de insumo', formulaTitle: 'Cantidad necesaria = superficie × dosis',
          value: fmt(Math.min(100, Math.max(0, data.percent)), 0) + ' %', unit: 'de la superficie cubierta',
          bar: data.percent,
          figures: [
            ['Necesario', fmt(data.needed, 2) + ' ' + unitText],
            ['Disponible', fmt(data.stock, 2) + ' ' + unitText],
            enough ? ['Sobrante', fmt(surplus, 2) + ' ' + unitText, 'ok'] : ['Faltante', fmt(shortfall, 2) + ' ' + unitText, 'warn'],
          ],
          message: enough
            ? (surplus > 1e-9 ? 'Tu cantidad disponible supera lo necesario.' : 'Cantidad suficiente: te alcanza justo para toda la superficie.')
            : 'Con lo que tienes cubres ' + fmt(data.coveredHa, 2) + ' de ' + fmt(data.area, 2) + ' ha; te faltan ' + fmt(shortfall, 2) + ' ' + unitText + ' para cubrir ' + fmt(data.missingHa, 2) + ' ha.',
          messageTone: enough ? 'ok' : 'warn',
          badge: { ok: data.verified, text: data.verified ? 'Dosis documentada' : (data.origin === 'catalog' ? 'Dato de catálogo' : (data.adjusted ? 'Ajustado manualmente' : 'Simulación')) },
          rows: [
            ['Potrero', plot.farmName + ' · ' + plot.name], ['Cultivo', crop.name], ['Producto', item ? item.name : 'Producto manual'],
                        ['Superficie que se puede cubrir', fmt(data.coveredHa, 2) + ' de ' + fmt(data.area, 2) + ' ha'], ['Superficie sin cubrir', data.missingHa > 1e-9 ? fmt(data.missingHa, 2) + ' ha' : ''],
            ['Dosis', fmt(data.dose, 3) + ' ' + data.dose_unit], ['Fuente técnica', data.source || ''],
          ],
          sourceUrl: data.source_url,
          warnings: (data.above_max ? ['⚠ Dosis superior a la referencia registrada (' + fmt(data.max_dose, 3) + ' ' + data.max_unit + ').'] : []).concat(['Simulación de disponibilidad: no se descontó ninguna existencia ni se registró inventario.']).concat(data.simulation ? ['La dosis usada no está documentada con fuente verificada.'] : []),
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
          kicker: 'Producción estimada', pdfTitle: 'Estimación de cosecha', formulaTitle: 'Producción = rendimiento × superficie', value: fmt(data.production, 2), unit: 'ton',
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

  // ---------- FICHA DE INSUMO (4 pasos, mismo diseño guiado que «Cuánto llevar») ----------
  const ficha = { step: 0, crop: '', problem: '', category: '', product: '' };
  const fichaSteps = document.getElementById('ficha-steps');
  const fichaContext = document.getElementById('ficha-context');
  const fichaSheet = document.getElementById('ficha-sheet');
  const fichaStatus = document.getElementById('ficha-status');
  const fichaHint = document.getElementById('ficha-hint');
  const flow = window.AgroToolFlow;
  const STEP_LABELS = ['Cultivo', 'Problema agrícola', 'Tipo de insumo', 'Ficha del producto'];
  const STEP_HEADS = [
    ['Selecciona un cultivo', 'Del catálogo activo de AgroAsesor.'],
    ['¿Qué problema quieres atender?', 'Documentado para el cultivo. También puedes ver todos sus insumos.'],
    ['Elige el tipo de insumo', 'Solo categorías con productos registrados para esa combinación.'],
    ['Elige un producto', 'Selecciona uno para ver su ficha técnica.'],
  ];
  const PROBLEM_TYPES = [['pest', 'Plagas'], ['disease', 'Enfermedades'], ['weed', 'Malezas'], ['nutrition', 'Problemas nutricionales'], ['other', 'Otros problemas']];
  const PROBLEM_ICONS = { pest: '🐛', disease: '🍂', weed: '🌿', nutrition: '🧪', other: '📋' };
  const CATEGORY_ICONS = { seed: '🌱', fertilizer: '🧪', herbicide: '🌿', fungicide: '🍄', insecticide: '🐛', other: '📦' };
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
  function productCount(crop) { return allProducts.filter((item) => item.active !== false && belongsToCrop(item, crop)).length; }

  // Tarjeta seleccionable (misma apariencia que en «Cuánto llevar»).
  function optionButton(icon, title, subs, onClick, options) {
    const opts = options || {};
    const button = el('button', 'calc-opt');
    button.type = 'button';
    button.setAttribute('aria-pressed', String(Boolean(opts.pressed)));
    const copy = el('span', 'calc-opt-copy');
    copy.append(el('strong', '', title));
    (subs || []).filter(Boolean).forEach((sub) => copy.append(el('small', '', sub)));
    if (opts.badge) copy.append(el('span', 'badge ' + (opts.badge.ok ? '' : 'amber'), opts.badge.text));
    button.append(Object.assign(el('span', 'calc-opt-ico', icon), { ariaHidden: 'true' }), copy);
    if (opts.disabled) button.disabled = true;
    else button.addEventListener('click', onClick);
    return button;
  }
  function chosenCard(icon, title, sub, step) {
    const change = el('button', 'btn-ghost-agro btn-sm', 'Cambiar');
    change.type = 'button';
    change.addEventListener('click', () => { ficha.step = step; renderFicha(); });
    const copy = el('div', 'calc-chosen-copy');
    copy.append(el('strong', '', title), el('small', '', sub));
    const card = el('div', 'calc-chosen');
    card.append(el('span', 'calc-chosen-ico', icon), copy, change);
    return card;
  }
  function advance(patch) { Object.assign(ficha, patch); renderFicha(); }

  function fichaStepContent(index) {
    const crop = cropById(ficha.crop);
    const problem = problems.find((item) => String(item.id) === String(ficha.problem));
    const current = index === ficha.step;
    if (index === 0) {
      if (!current && crop) return [chosenCard(flow.emoji(crop), crop.name, productCount(crop) + ' insumo(s) registrados', 0)];
      if (!crops.length) return [flow.emptyCard('🌱', 'No hay cultivos activos en el catálogo', 'Sin cultivos no se puede consultar, y AgroAsesor no inventa datos. ' + (isStaff ? 'Regístralos desde la administración.' : 'Solicita al administrador que cargue el catálogo.'))];
      const host = el('div', 'calc-picker');
      const picker = flow.createPicker(flow.cropPickerConfig({
        host, items: () => flow.sortCrops(crops), selected: () => null,
        pick: (id) => advance({ crop: String(id), problem: '', category: '', product: '', step: 1 }),
        option: (item) => ({ icon: flow.emoji(item), title: item.name, subs: [flow.shortGroup(item), productCount(item) + ' insumo(s) registrados'] }),
      }));
      picker.render();
      return [host];
    }
    if (!crop) return [];
    if (index === 1) {
      if (!current) return [chosenCard(problem ? PROBLEM_ICONS[problem.type] || '📋' : '🗂️', problem ? problem.name : 'Todos los insumos de ' + crop.name, problem ? problem.typeLabel : 'Sin filtrar por problema', 1)];
      const nodes = [];
      const cropProblems = problems.filter((item) => (item.cropIds || []).includes(String(crop.id)));
      if (!cropProblems.length) nodes.push(el('p', 'muted', 'No hay problemas documentados para este cultivo en el catálogo.'));
      PROBLEM_TYPES.forEach(([type, label]) => {
        const group = cropProblems.filter((item) => item.type === type);
        if (!group.length) return;
        nodes.push(el('p', 'flow-group-title', label));
        const grid = el('div', 'calc-opts');
        group.forEach((item) => {
          const count = allProducts.filter((product) => belongsToCrop(product, crop) && (product.problemIds || []).includes(String(item.id))).length;
          grid.append(optionButton(PROBLEM_ICONS[type] || '📋', item.name, [count ? count + ' producto(s) documentado(s)' : 'Sin productos documentados'],
            () => advance({ problem: String(item.id), category: '', product: '', step: 2 }), { disabled: count === 0, pressed: String(item.id) === String(ficha.problem) }));
        });
        nodes.push(grid);
      });
      const all = el('button', 'calc-chip', 'Ver todos los insumos de ' + crop.name);
      all.type = 'button';
      all.addEventListener('click', () => advance({ problem: '*', category: '', product: '', step: 2 }));
      const allWrap = el('div', 'flow-restart');
      allWrap.append(all);
      nodes.push(allWrap);
      return nodes;
    }
    if (index === 2) {
      if (ficha.step < 2) return [];
      const items = fichaProducts();
      const keys = [...new Set(items.map((item) => item.category))];
      if (!current) return [chosenCard(CATEGORY_ICONS[ficha.category] || '📦', categoryLabels[ficha.category] || 'Insumos', items.filter((item) => item.category === ficha.category).length + ' producto(s)', 2)];
      if (!keys.length) return [el('p', 'muted', 'No hay productos documentados para esta combinación.')];
      const grid = el('div', 'calc-opts');
      keys.forEach((key) => {
        const count = items.filter((item) => item.category === key).length;
        grid.append(optionButton(CATEGORY_ICONS[key] || '📦', categoryLabels[key] || key, [count + ' producto(s)'],
          () => advance({ category: key, product: '', step: 3 }), { pressed: key === ficha.category }));
      });
      return [grid];
    }
    if (ficha.step < 3) return [];
    const items = fichaProducts().filter((item) => item.category === ficha.category);
    if (!items.length) return [el('p', 'muted', 'No hay productos para esta combinación.')];
    const list = el('div', 'calc-opts calc-opts-list');
    items.forEach((item) => {
      const status = isPhyto(item) ? (verifiedPhytoFor(item, crop) ? 'Uso verificado' : 'Sin uso verificado') : (item.verified ? 'Verificado' : 'Sin verificar');
      list.append(optionButton(CATEGORY_ICONS[item.category] || '📦', item.name, [item.categoryLabel],
        () => { ficha.product = String(item.id); renderFicha(); }, { pressed: String(item.id) === String(ficha.product), badge: { ok: !status.startsWith('Sin'), text: status } }));
    });
    return [list];
  }

  function renderFichaSteps() {
    fichaSteps.replaceChildren();
    STEP_HEADS.forEach(([title, text], index) => {
      const locked = index > ficha.step;
      const done = index < ficha.step || (index === 3 && Boolean(ficha.product));
      const li = el('li', 'calc-step' + (done ? ' is-done' : '') + (index === ficha.step ? ' is-current' : '') + (locked ? ' is-locked' : ''));
      li.dataset.step = ['crop', 'problem', 'category', 'product'][index];
      const num = el('span', 'calc-step-num', String(index + 1));
      num.setAttribute('aria-hidden', 'true');
      const body = el('div', 'calc-step-body');
      const head = el('div', 'calc-step-head');
      head.append(el('h3', '', title), el('p', '', text));
      body.append(head);
      if (locked) { body.setAttribute('inert', ''); body.setAttribute('aria-disabled', 'true'); }
      else fichaStepContent(index).forEach((node) => body.append(node));
      li.append(num, body);
      fichaSteps.append(li);
    });
  }

  function renderFichaContext() {
    fichaContext.replaceChildren(el('h2', '', 'Tu consulta'));
    const crop = cropById(ficha.crop);
    if (!crop) {
      fichaContext.append(el('p', 'muted', crops.length ? 'Aún no eliges un cultivo. Al elegirlo verás aquí sus datos del catálogo.' : 'El catálogo no tiene cultivos registrados.'));
      return;
    }
    const cropProblems = problems.filter((item) => (item.cropIds || []).includes(String(crop.id)));
    const hasDensity = crop.density !== null && crop.density !== undefined;
    const card = el('div', 'calc-mini');
    const headRow = el('div', 'calc-crop-head');
    const headCopy = el('div');
    headCopy.append(el('h3', '', crop.name));
    if (crop.group) headCopy.append(el('span', 'badge', crop.group));
    headRow.append(Object.assign(el('span', 'calc-crop-emoji', flow.emoji(crop)), { ariaHidden: 'true' }), headCopy);
    card.append(headRow);
    if (crop.description) card.append(el('p', 'calc-crop-desc', crop.description));
    const metrics = el('div', 'metric-grid calc-metrics');
    [['Densidad de siembra', hasDensity ? fmt(crop.density) + ' ' + (crop.unit || 'kg') + '/ha' : 'Sin dato'],
      ['Productos en catálogo', String(productCount(crop))],
      ['Problemas documentados', String(cropProblems.length)]].forEach(([label, text]) => {
      const box = el('div', 'metric');
      box.append(el('span', '', label), el('strong', '', text));
      metrics.append(box);
    });
    card.append(metrics);
    if (hasDensity) card.append(el('p', 'calc-source-note', 'Densidad: ' + (crop.densitySource || 'sin fuente registrada') + '.'));
    fichaContext.append(card);
    const problem = problems.find((item) => String(item.id) === String(ficha.problem));
    if (problem) {
      const box = el('div', 'calc-mini');
      box.append(el('p', 'calc-mini-kicker', problem.typeLabel), el('h3', '', problem.name));
      if (problem.symptoms) box.append(el('p', '', 'Síntomas: ' + problem.symptoms));
      if (problem.description) box.append(el('p', '', problem.description));
      const url = safeUrl(problem.sourceUrl);
      if (problem.sourceName || url) {
        const p = el('p', 'muted', 'Fuente: ' + (problem.sourceName || ''));
        if (url) { const a = el('a', 'text-link', ' ver documento'); a.href = url; a.target = '_blank'; a.rel = 'noopener noreferrer'; p.append(a); }
        box.append(p);
      }
      fichaContext.append(box);
    }
    const sources = [...new Set(fichaProducts().map((item) => item.sourceName).filter(Boolean))];
    if (sources.length) fichaContext.append(el('p', 'muted', 'Fuentes técnicas disponibles: ' + sources.join(' · ')));
    fichaContext.append(el('p', 'alert', 'La ficha no reemplaza la etiqueta autorizada ni la asesoría de un profesional.'));
    if (ficha.step > 0) {
      const restart = el('button', 'btn-ghost-agro btn-sm', 'Iniciar nueva consulta');
      restart.type = 'button';
      restart.addEventListener('click', () => advance({ step: 0, crop: '', problem: '', category: '', product: '' }));
      fichaContext.append(restart);
    }
  }

  function renderFichaSheet() {
    const crop = cropById(ficha.crop);
    const item = productById(ficha.product);
    fichaSheet.replaceChildren();
    if (crop && item && ficha.step === 3) {
      const status = { verified: 'Verificado con fuente', restricted: 'Restringido', cancelled: 'Registro cancelado' }[item.verificationStatus] || 'Información no verificada';
      const top = el('div', 'calc-result-top');
      top.append(el('p', 'result-kicker', 'Ficha del producto'), el('span', 'badge ' + (item.verificationStatus === 'verified' ? '' : 'amber'), status));
      fichaSheet.append(top, productSheet(item, crop));
      return;
    }
    const items = [
      { label: 'Cultivo', ok: Boolean(crop), hint: 'Selecciona un cultivo' },
      { label: 'Problema agrícola', ok: Boolean(ficha.problem), hint: 'Elige un problema o «ver todos los insumos»' },
      { label: 'Tipo de insumo', ok: Boolean(ficha.category), hint: 'Elige el tipo de insumo' },
      { label: 'Producto', ok: Boolean(ficha.product), hint: 'Selecciona un producto' },
    ];
    flow.pendingResult(fichaSheet, {
      kicker: 'Ficha del producto', title: 'Aún falta elegir el producto',
      text: 'Cuando elijas un producto verás aquí su ficha técnica: dosis, usos, restricciones y fuentes.', items, ready: false,
    });
  }

  function renderFicha() {
    renderFichaSteps();
    renderFichaContext();
    renderFichaSheet();
    const done = ficha.step === 3 && Boolean(ficha.product);
    fichaStatus.dataset.state = !crops.length ? 'blocked' : done ? 'done' : 'pending';
    fichaStatus.querySelector('.calc-status-text').textContent = !crops.length ? 'El catálogo no tiene cultivos'
      : done ? 'Ficha lista' : 'Paso ' + (ficha.step + 1) + ' de 4 · ' + STEP_LABELS[ficha.step];
    fichaHint.textContent = STEP_HELP[ficha.step];
  }

  function productSheet(item, crop) {
    const card = el('article', 'product-sheet');
    const phyto = isPhyto(item);
    const usable = phyto ? verifiedPhytoFor(item, crop) : item.doseVerified === true;
    card.append(el('h3', '', item.name));
    const statusText = { verified: 'Verificado con fuente', restricted: 'Restringido', cancelled: 'Registro cancelado' }[item.verificationStatus] || 'Información no verificada';
    card.append(el('p', 'muted', 'El estado refleja lo registrado por el administrador del catálogo; no es una consulta en línea al SAG.'));
    const list = el('dl', 'sheet-list');
    const rows = [
      ['Nombre comercial', item.name], ['Categoría', item.categoryLabel], ['Fabricante', item.manufacturer],
      ['Ingrediente activo o composición', item.activeIngredient || item.nutrientComposition], ['Concentración', item.concentration],
      ['Formulación', item.formulation], ['Cultivo', item.crop || ''],
      ['Uso documentado', (item.problems || []).join(', ') || (item.controlTargets || []).join(', ')],
      ['Cultivos autorizados', (item.authorizedCrops || []).join(', ')], ['Objetivos de control', (item.controlTargets || []).join(', ')],
      ['Dosis' + (phyto ? ' autorizada' : ''), item.dose !== null && item.dose !== undefined ? fmt(item.dose, 3) + ' ' + (item.unit || '') + (item.doseVerified ? ' (verificada)' : ' (sin verificar)') : ''],
      ['Origen del dato', item.doseVerified ? 'Documentado' : (item.dose !== null && item.dose !== undefined ? 'De catálogo (sin respaldo completo)' : '')],
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
      card.append(el('p', 'alert', 'Información no verificada para cálculo. Falta: ' + missingData(item, crop).join(', ') +
        '. No se habilitan cálculos de aplicación con dosis no confirmadas.'));
    }
    const actions = el('div', 'calc-result-actions');
    const pdf = el('button', 'btn-secondary-agro btn-sm', 'Descargar ficha PDF');
    pdf.type = 'button';
    pdf.addEventListener('click', () => {
      const lines = rows.filter(([, value]) => value).map(([label, value]) => label + ': ' + value);
      lines.unshift('Estado: ' + statusText);
      if (!usable) lines.push('Advertencia: información no verificada para cálculo.');
      downloadPdf('Ficha de insumo ' + item.name, lines);
    });
    const toCalc = el('button', 'btn-primary-agro btn-sm', 'Llevar a «Cuánto llevar»');
    toCalc.type = 'button';
    toCalc.addEventListener('click', () => sendToCalculator(item, crop));
    const avail = el('button', 'btn-secondary-agro btn-sm', 'Ir a «¿Me alcanza?»');
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
    if (!window.AgroCalculator) return;
    const result = window.AgroCalculator.prefill({
      mode: item.category === 'seed' ? 'semillas' : 'insumos',
      plot: plotId,
      crop: crop.id,
      product: item.id,
    });
    if (!result.product) {
      window.AgroCalculator.showError('El producto no está habilitado para calcular (falta un uso verificado o su vigencia): se conservó el cultivo, pero no se asumió ninguna dosis.');
    }
  }

  // ---------- estado inicial desde la URL ----------
  function applyInitialSelection() {
    const plotId = params.get('plot');
    const cropId = params.get('crop');
    [document.getElementById('cover-form'), document.getElementById('yield-form')].forEach((form) => {
      if (plotId && plotById(plotId)) { form.elements.plot.value = plotId; form.elements.plot.dispatchEvent(new Event('change')); }
      if (cropId && cropById(cropId)) { form.elements.crop.value = cropId; form.elements.crop.dispatchEvent(new Event('change')); }
      form.dispatchEvent(new CustomEvent('flow:refresh'));
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
    showTool(tool);
  }
  // ---------- línea de contexto: dónde estás (Predio › Potrero › Cultivo › Herramienta) ----------
  const ctxLine = document.getElementById('ctx-line');
  function renderContextLine() {
    if (!ctxLine) return;
    const tool = root.dataset.tool || 'llevar';
    const field = (id) => { const node = document.getElementById(id); return node ? node.value : ''; };
    const formValue = (formId, name) => { const form = document.getElementById(formId); return form && form.elements[name] ? form.elements[name].value : ''; };
    let plotId = '';
    let cropId = '';
    let label = '';
    if (tool === 'llevar') {
      plotId = field('calc-plot');
      cropId = field('calc-crop');
      const active = document.querySelector('#calc-modes [data-mode].is-active');
      label = active && active.dataset.mode === 'insumos' ? 'Calcular insumos' : 'Calcular semillas';
    } else if (tool === 'alcanza') {
      plotId = formValue('cover-form', 'plot'); cropId = formValue('cover-form', 'crop'); label = 'Ver si alcanza';
    } else if (tool === 'cosecha') {
      plotId = formValue('yield-form', 'plot'); cropId = formValue('yield-form', 'crop'); label = 'Estimar cosecha';
    } else {
      plotId = params.get('plot') || ''; cropId = ficha.crop || ''; label = 'Ficha de insumo';
    }
    const plot = plotId ? plotById(plotId) : null;
    const crop = cropId ? cropById(cropId) : null;
    const owner = plot ? farmOf(plot) : null;
    const crumbs = [];
    if (owner) crumbs.push({ text: owner.name, href: owner.detailUrl });
    if (plot) crumbs.push({ text: plot.name, href: plot.detailUrl });
    if (crop) crumbs.push({ text: crop.name });
    crumbs.push({ text: label, current: true });
    ctxLine.replaceChildren();
    crumbs.forEach((crumb, index) => {
      if (index) ctxLine.append(el('span', 'ctx-sep', '›'));
      if (crumb.href) {
        const link = el('a', 'ctx-crumb', crumb.text);
        link.href = crumb.href;
        ctxLine.append(link);
      } else {
        const node = el('span', crumb.current ? 'ctx-crumb is-current' : 'ctx-crumb', crumb.text);
        if (crumb.current) node.setAttribute('aria-current', 'page');
        ctxLine.append(node);
      }
    });
    if (!plot && tool !== 'ficha') ctxLine.append(el('span', 'ctx-hint', 'Elige un potrero para continuar'));
  }
  // Los selectores y botones de los flujos cambian el estado; se vuelve a leer después de que ellos actualizan.
  ['change', 'click', 'flow:refresh', 'input'].forEach((name) => document.addEventListener(name, () => window.setTimeout(renderContextLine, 0), true));
  renderContextLine();

  window.AgroDecisiones = { showTool, goToAvailability };
  applyInitialSelection();
})();
