/* Calculadora de semillas. La cuenta la hace el servidor (/calculos/ejecutar/): aquí solo se muestran los datos,
   así hay una única lógica de cálculo. «Guardar en historial» es la misma llamada sin la marca de vista previa. */
(function () {
  'use strict';
  const dataNode = document.getElementById('semillas-data');
  if (!dataNode || !document.getElementById('cs-farm')) return;

  const data = JSON.parse(dataNode.textContent);
  const farms = JSON.parse(document.getElementById('agro-farms').textContent);
  const mapsNode = document.getElementById('maps-config');
  const mapsConfig = mapsNode ? JSON.parse(mapsNode.textContent) : {};
  const $ = (id) => document.getElementById(id);
  const nf = new Intl.NumberFormat('es-CL', { maximumFractionDigits: 2 });
  const nf4 = new Intl.NumberFormat('es-CL', { maximumFractionDigits: 4 });
  const money = new Intl.NumberFormat('es-CL', { style: 'currency', currency: 'CLP', maximumFractionDigits: 0 });

  const state = { plot: null, crop: null, ref: null, timer: null, token: 0, result: null, saved: false, tab: 'siembra' };

  function el(tag, attrs, children) {
    const node = document.createElement(tag);
    Object.entries(attrs || {}).forEach(([key, value]) => {
      if (key === 'text') node.textContent = value;
      else if (key === 'class') node.className = value;
      else node.setAttribute(key, value);
    });
    (children || []).forEach((child) => child && node.appendChild(child));
    return node;
  }
  function icons() { if (window.lucide) window.lucide.createIcons(); }
  function option(value, label, selected) {
    const node = el('option', { value: String(value), text: label });
    if (selected) node.selected = true;
    return node;
  }
  function areaText(ha) { return nf4.format(ha) + ' ha (' + nf.format(ha * 10000) + ' m²)'; }

  /* ---------- Terreno ---------- */
  function fillFarms() {
    const select = $('cs-farm');
    select.replaceChildren(...farms.predios.filter((f) => farms.plots.some((p) => p.predio === f.id)).map((f) => option(f.id, f.name)));
  }
  function fillPlots(farmId) {
    $('cs-plot').replaceChildren(...farms.plots.filter((p) => p.predio === farmId).map((p) => option(p.id, p.name + ' · ' + nf4.format(p.areaHa) + ' ha')));
  }
  function facts(plot) {
    const rows = [
      ['Potrero', plot.name], ['Predio', plot.farmName], ['Superficie', areaText(plot.areaHa)],
      ['Cultivo actual', plot.crop || 'Sin cultivo asignado'], ['Variedad', plot.variety || 'No registrada'],
    ];
    $('cs-facts').replaceChildren(...rows.map(([k, v]) => el('div', {}, [el('dt', { text: k }), el('dd', { text: v })])));
  }

  /* ---------- Mapa (Leaflet si carga; si no, dibujo SVG propio del perímetro) ---------- */
  let map = null; let layerGroup = null;
  function ringOf(plot) {
    let ring = [];
    const g = plot.geojson && (plot.geojson.geometry || plot.geojson);
    if (g && g.type === 'Polygon' && Array.isArray(g.coordinates)) ring = g.coordinates[0] || [];
    else if (Array.isArray(plot.coordinates)) ring = plot.coordinates;
    return ring.filter((p) => Array.isArray(p) && p.length >= 2 && isFinite(p[0]) && isFinite(p[1])).map((p) => [Number(p[0]), Number(p[1])]);
  }
  function svgFallback(points) {
    const ns = 'http://www.w3.org/2000/svg';
    const svg = document.createElementNS(ns, 'svg');
    svg.setAttribute('class', 'cs-fallback'); svg.setAttribute('viewBox', '0 0 400 230'); svg.setAttribute('preserveAspectRatio', 'xMidYMid meet');
    const bg = document.createElementNS(ns, 'rect'); bg.setAttribute('width', '400'); bg.setAttribute('height', '230'); bg.setAttribute('fill', '#dfe8da'); svg.appendChild(bg);
    if (points.length >= 3) {
      const lat0 = points.reduce((s, p) => s + p[1], 0) / points.length;
      const k = Math.cos(lat0 * Math.PI / 180);
      const xs = points.map((p) => p[0] * k); const ys = points.map((p) => -p[1]);
      const minX = Math.min(...xs); const maxX = Math.max(...xs); const minY = Math.min(...ys); const maxY = Math.max(...ys);
      const scale = Math.min(340 / (maxX - minX || 1), 180 / (maxY - minY || 1));
      const ox = (400 - (maxX - minX) * scale) / 2; const oy = (230 - (maxY - minY) * scale) / 2;
      const poly = document.createElementNS(ns, 'polygon');
      poly.setAttribute('points', xs.map((x, i) => ((x - minX) * scale + ox).toFixed(1) + ',' + ((ys[i] - minY) * scale + oy).toFixed(1)).join(' '));
      poly.setAttribute('fill', 'rgba(47,138,82,0.35)'); poly.setAttribute('stroke', '#1d6a43'); poly.setAttribute('stroke-width', '3');
      svg.appendChild(poly);
    } else {
      const t = document.createElementNS(ns, 'text'); t.setAttribute('x', '200'); t.setAttribute('y', '120'); t.setAttribute('text-anchor', 'middle'); t.setAttribute('fill', '#5d6b62');
      t.textContent = 'Sin perímetro dibujado'; svg.appendChild(t);
    }
    return svg;
  }
  function drawMap(plot) {
    const box = $('cs-map'); const points = ringOf(plot);
    const note = $('cs-map-note');
    if (points.length < 3) {
      note.textContent = 'Este potrero no tiene perímetro dibujado: se usa su superficie registrada. Puedes dibujarlo en Mis predios.';
    } else {
      note.textContent = 'La superficie sale del potrero seleccionado; el mapa solo muestra su perímetro.';
    }
    const chip = $('cs-map-chip'); chip.hidden = false; chip.replaceChildren(el('strong', { text: plot.name }), el('span', { text: nf4.format(plot.areaHa) + ' ha' }));
    if (!window.L || points.length < 3) {
      if (map) { map.remove(); map = null; layerGroup = null; }
      box.replaceChildren(svgFallback(points));
      return;
    }
    try {
      if (!map) {
        box.replaceChildren();
        map = window.L.map(box, { zoomControl: true, attributionControl: true });
        window.L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {
          attribution: '&copy; Esri, Maxar, Earthstar Geographics', maxZoom: 19,
        }).addTo(map);
        layerGroup = window.L.layerGroup().addTo(map);
      }
      layerGroup.clearLayers();
      const latlngs = points.map((p) => [p[1], p[0]]);
      const polygon = window.L.polygon(latlngs, { color: '#7fe3a0', weight: 3, fillColor: '#2f8a52', fillOpacity: 0.35 }).addTo(layerGroup);
      map.fitBounds(polygon.getBounds(), { padding: [20, 20] });
      setTimeout(() => map && map.invalidateSize(), 150);
    } catch (error) {
      box.replaceChildren(svgFallback(points));
    }
  }

  /* ---------- Cultivo, referencia y dosis ---------- */
  function cropById(id) { return data.crops.find((c) => String(c.id) === String(id)) || null; }
  function fillCrops(selectedId) {
    $('cs-crop').replaceChildren(option('', 'Elige un cultivo', !selectedId), ...data.crops.map((c) => option(c.id, c.name, String(c.id) === String(selectedId))));
  }
  function fillRefs() {
    const select = $('cs-ref'); const crop = state.crop;
    if (!crop) { select.replaceChildren(option('', 'Primero elige un cultivo')); select.disabled = true; return; }
    select.disabled = false;
    const options = crop.references.map((r) => option('ref:' + r.id, r.fuente.organismo + ' · ' + r.sistema));
    if (crop.density !== null) options.push(option('db', 'Densidad registrada del cultivo' + (crop.densityBacked ? ' (con fuente)' : ' (sin fuente verificada)')));
    options.push(option('manual', 'Otra: escribo mi propia dosis'));
    select.replaceChildren(...options);
  }
  function currentRef() {
    const value = $('cs-ref').value;
    if (!state.crop || !value.startsWith('ref:')) return null;
    return state.crop.references.find((r) => 'ref:' + r.id === value) || null;
  }
  function applyRef(resetDose) {
    const ref = currentRef(); state.ref = ref;
    const slider = $('cs-slider'); const unit = $('cs-dose-unit'); const link = $('cs-ref-link'); const card = $('cs-refcard');
    const mode = $('cs-ref').value;
    unit.textContent = ref ? 'kg/ha' : (state.crop ? state.crop.unit : 'kg/ha');
    if (ref) {
      const mid = Math.round(((ref.min + ref.max) / 2) * 10) / 10;
      slider.min = ref.min; slider.max = ref.max; slider.step = (ref.max - ref.min) >= 20 ? 1 : 0.5; slider.hidden = false;
      $('cs-range').hidden = false; $('cs-range-min').textContent = nf.format(ref.min); $('cs-range-max').textContent = nf.format(ref.max);
      if (resetDose) $('cs-dose').value = mid;
      $('cs-dose-help').textContent = 'Valor inicial: punto medio del rango de referencia. Ajústalo según tu variedad, suelo y calidad de semilla.';
      link.hidden = false; link.href = ref.fuente.url; link.lastElementChild.textContent = 'Ver ficha técnica (' + ref.fuente.organismo + ')';
      card.hidden = false;
      card.replaceChildren(
        el('strong', { text: state.crop.name + ' · ' + ref.sistema }),
        el('p', { text: 'Dosis recomendada: ' + nf.format(ref.min) + ' – ' + nf.format(ref.max) + ' kg/ha' }),
        el('p', {}, [el('span', { class: 'cs-badge' + (ref.estado === 'cotejada_con_fuente' ? '' : ' is-pending'), text: ref.estado_etiqueta })]),
        el('p', { class: 'cs-help', text: ref.nota })
      );
    } else {
      slider.hidden = true; $('cs-range').hidden = true; link.hidden = true; card.hidden = true;
      if (resetDose) $('cs-dose').value = mode === 'db' && state.crop && state.crop.density !== null ? state.crop.density : '';
      $('cs-dose-help').textContent = mode === 'db'
        ? (state.crop.densityBacked ? 'Densidad registrada con fuente: ' + state.crop.densitySource + '.' : 'Esta densidad no tiene una fuente verificada: el resultado se marca como simulación.')
        : 'Escribe la dosis que usarás; el resultado queda marcado como simulación.';
    }
    syncSlider();
  }
  function syncSlider() {
    const ref = state.ref; const dose = parseFloat($('cs-dose').value);
    const help = $('cs-dose-help');
    if (ref && isFinite(dose)) {
      $('cs-slider').value = Math.min(Math.max(dose, ref.min), ref.max);
      help.classList.toggle('is-warn', dose < ref.min || dose > ref.max);
      if (dose < ref.min || dose > ref.max) help.textContent = 'Esta dosis queda fuera del rango de referencia (' + nf.format(ref.min) + ' – ' + nf.format(ref.max) + ' kg/ha). Puedes calcularla, pero consulta a un ingeniero agrónomo.';
    } else { help.classList.remove('is-warn'); }
  }

  /* ---------- Cálculo (servidor) ---------- */
  function csrf() { const input = document.querySelector('[name=csrfmiddlewaretoken]'); return input ? input.value : ''; }
  function payload(preview) {
    const unit = $('cs-dose-unit').textContent;
    const body = {
      operation: 'dose', calculation_type: 'semillas', plot_id: state.plot.id, area: String(state.plot.areaHa),
      crop: state.crop.name, dose: $('cs-dose').value, unit, preview,
    };
    if ($('cs-bag').value) body.bag_kg = $('cs-bag').value;
    if ($('cs-bag').value && $('cs-price').value) body.bag_price_clp = $('cs-price').value;
    return body;
  }
  function ready() { return state.plot && state.crop && parseFloat($('cs-dose').value) > 0; }
  function showError(message) { const box = $('cs-error'); box.hidden = !message; box.textContent = message || ''; }
  function clearResult() {
    state.result = null;
    ['cs-total', 'cs-bags', 'cs-cover', 'cs-cost'].forEach((id) => { $(id).textContent = '—'; });
    ['cs-bags-note', 'cs-cover-note'].forEach((id) => { $(id).textContent = ''; });
    $('cs-total-for').textContent = state.plot ? 'Elige un cultivo y una dosis.' : 'Elige un potrero y una dosis.';
    $('cs-leftover').hidden = true; $('cs-origin').hidden = true; $('cs-save').disabled = true;
  }
  function render(result) {
    state.result = result;
    $('cs-total').textContent = nf.format(result.amount) + ' ' + result.unit;
    $('cs-total-for').textContent = 'para ' + nf4.format(result.area) + ' hectáreas';
    $('cs-cover').textContent = nf4.format(result.area) + ' ha';
    $('cs-cover-note').textContent = '(' + nf.format(result.area * 10000) + ' m²)';
    const bag = result.user_bag;
    if (bag) {
      $('cs-bags').textContent = nf.format(bag.count);
      $('cs-bags-note').textContent = 'sacos de ' + nf.format(bag.size) + ' kg';
      $('cs-leftover').hidden = false;
      $('cs-leftover').textContent = 'Sobrante teórico: ' + nf.format(bag.leftover) + ' kg (los sacos se compran enteros).';
      $('cs-cost').textContent = bag.total_cost_clp !== undefined ? money.format(bag.total_cost_clp) : '—';
    } else {
      $('cs-bags').textContent = '—'; $('cs-bags-note').textContent = result.unit === 'kg' ? 'Indica el tamaño del saco' : 'solo para dosis en kg/ha';
      $('cs-leftover').hidden = true; $('cs-cost').textContent = '—';
    }
    const origin = $('cs-origin'); origin.hidden = false;
    const dose = parseFloat($('cs-dose').value); const ref = state.ref;
    if (ref && dose >= ref.min && dose <= ref.max) {
      origin.textContent = 'Dosis dentro del rango de referencia ' + ref.fuente.organismo + ' (' + ref.estado_etiqueta.toLowerCase() + ').' +
        (result.simulation ? ' En el historial queda marcada como simulación mientras la referencia no esté cotejada.' : '');
    } else {
      origin.textContent = 'Origen de la dosis: ' + result.origin_label + (result.simulation ? ' · Resultado marcado como simulación.' : '.');
    }
    $('cs-save').disabled = false;
  }
  async function send(preview) {
    const token = ++state.token;
    const response = await fetch(data.calculateUrl, {
      method: 'POST', credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf(), Accept: 'application/json' },
      body: JSON.stringify(payload(preview)),
    });
    let body = {};
    try { body = await response.json(); } catch (error) { body = {}; }
    return { ok: response.ok, body, stale: token !== state.token };
  }
  function schedule() {
    state.saved = false; $('cs-saved').hidden = true;
    clearTimeout(state.timer);
    steps();
    if (!ready()) { clearResult(); showError(''); return; }
    state.timer = setTimeout(async () => {
      try {
        const { ok, body, stale } = await send(true);
        if (stale) return;
        if (ok && body.ok) { showError(''); render(body); } else { clearResult(); showError(body.error || 'No se pudo calcular.'); }
      } catch (error) { clearResult(); showError('No se pudo conectar con el servidor. Revisa tu conexión e inténtalo de nuevo.'); }
      steps();
    }, 250);
  }
  async function save() {
    if (!ready()) return;
    const button = $('cs-save'); button.disabled = true;
    try {
      const { ok, body } = await send(false);
      if (ok && body.ok) {
        state.saved = true; showError(''); render(body); button.disabled = true;
        const saved = $('cs-saved'); saved.hidden = false;
        saved.replaceChildren(document.createTextNode('Cálculo guardado en tu historial. '), el('a', { href: data.historyUrl, text: 'Ver en Reportes' }));
      } else { showError(body.error || 'No se pudo guardar.'); button.disabled = false; }
    } catch (error) { showError('No se pudo guardar por un problema de conexión. Inténtalo de nuevo.'); button.disabled = false; }
  }

  /* ---------- Pasos y panel técnico ---------- */
  function steps() {
    const done = [!!state.plot, ready(), !!state.result, !!state.result];
    const current = done.findIndex((d) => !d);
    document.querySelectorAll('#cs-steps li').forEach((li, i) => {
      li.classList.toggle('is-done', done[i] && i !== 3);
      li.classList.toggle('is-current', i === (current === -1 ? 3 : current));
    });
  }
  function infoItem(icon, title, text, extra) {
    return el('div', { class: 'cs-item' }, [el('i', { 'data-lucide': icon }), el('div', {}, [el('strong', { text: title }), el('small', { text }), extra])]);
  }
  function renderInfo() {
    const panel = $('cs-tabpanel'); const source = $('cs-source');
    const crop = state.crop; const ref = state.ref;
    const sheet = crop && state.plot ? crop.sheets.find((s) => s.zone === state.plot.zoneName) : null;
    const none = (text) => el('p', { class: 'cs-nodata', text });
    source.hidden = true;
    if (!crop) { panel.replaceChildren(none('Elige un cultivo para ver su información técnica.')); return; }
    if (state.tab === 'siembra') {
      const items = [];
      items.push(infoItem('calendar-days', 'Época de siembra', sheet && sheet.sowingWindow ? sheet.sowingWindow + ' · zona ' + sheet.zone : 'Sin dato verificado para tu zona'));
      items.push(infoItem('wheat', 'Dosis recomendada', ref ? nf.format(ref.min) + ' – ' + nf.format(ref.max) + ' kg/ha (' + ref.fuente.organismo + ')' : (crop.density !== null ? nf.format(crop.density) + ' ' + crop.unit + ' (densidad registrada)' : 'Sin dosis de referencia: escribe la tuya')));
      items.push(infoItem('ruler', 'Profundidad de siembra', sheet && sheet.depth ? sheet.depth : 'Sin dato verificado'));
      const list = el('ul', {}, ['Usar semilla certificada', 'Verificar la humedad del suelo', 'Ajustar la dosis según la preparación del terreno'].map((t) => el('li', { text: t })));
      items.push(infoItem('lightbulb', 'Buenas prácticas generales', '', list));
      panel.replaceChildren(...items);
      if (ref) {
        source.hidden = false;
        const when = ref.estado === 'cotejada_con_fuente' && ref.fecha_consulta ? 'Consultada el ' + ref.fecha_consulta : 'Fuente citada, pendiente de cotejo con el documento';
        source.replaceChildren(el('strong', { text: 'Fuente oficial' }), el('br'), document.createTextNode(ref.fuente.titulo), el('br'), el('a', { href: ref.fuente.url, target: '_blank', rel: 'noopener noreferrer', text: ref.fuente.organismo + ' · abrir documento' }), el('br'), el('small', { text: when }));
      }
    } else if (state.tab === 'manejo') {
      panel.replaceChildren(sheet && sheet.management ? infoItem('clipboard-list', 'Manejo', sheet.management) : none('Sin información de manejo verificada para este cultivo y tu zona.'));
    } else if (state.tab === 'suelo') {
      panel.replaceChildren(sheet && sheet.soil ? infoItem('layers', 'Requerimientos de suelo', sheet.soil) : none('Sin información de suelo verificada para este cultivo y tu zona. AgroAsesor aún no registra el tipo de suelo de tus potreros.'));
    } else {
      const value = sheet && sheet.yield !== null ? nf.format(sheet.yield) + ' ton/ha · zona ' + sheet.zone : (crop.yield !== null ? nf.format(crop.yield) + ' ton/ha (rendimiento registrado, referencial)' : '');
      panel.replaceChildren(value ? infoItem('chart-column', 'Rendimiento', value) : none('Sin rendimiento verificado para este cultivo.'));
    }
    icons();
  }

  /* ---------- Eventos ---------- */
  function selectPlot(plotId, remember) {
    const plot = farms.plots.find((p) => p.id === String(plotId));
    if (!plot) return;
    state.plot = plot;
    $('cs-farm').value = plot.predio; fillPlots(plot.predio); $('cs-plot').value = plot.id;
    if (remember && window.AgroSel) window.AgroSel.set(plot.id);
    facts(plot); drawMap(plot);
    state.crop = cropById(plot.cropId); fillCrops(plot.cropId); fillRefs(); applyRef(true);
    $('cs-price').value = '';
    renderInfo(); schedule();
  }
  function clearAll() {
    $('cs-bag').value = ''; $('cs-price').value = ''; showError(''); $('cs-saved').hidden = true;
    if (state.plot) selectPlot(state.plot.id, false);
  }

  fillFarms();
  $('cs-farm').addEventListener('change', () => { fillPlots($('cs-farm').value); const first = $('cs-plot').value; if (first) selectPlot(first, true); });
  $('cs-plot').addEventListener('change', () => selectPlot($('cs-plot').value, true));
  $('cs-change-plot').addEventListener('click', () => { $('cs-plot').focus(); $('cs-plot').scrollIntoView({ block: 'center', behavior: 'smooth' }); });
  $('cs-crop').addEventListener('change', () => { state.crop = cropById($('cs-crop').value); fillRefs(); applyRef(true); renderInfo(); schedule(); });
  $('cs-ref').addEventListener('change', () => { applyRef(true); renderInfo(); schedule(); });
  $('cs-dose').addEventListener('input', () => { syncSlider(); schedule(); });
  $('cs-slider').addEventListener('input', () => { $('cs-dose').value = $('cs-slider').value; syncSlider(); schedule(); });
  ['cs-bag', 'cs-price'].forEach((id) => $(id).addEventListener('input', schedule));
  $('cs-clear').addEventListener('click', clearAll);
  $('cs-save').addEventListener('click', save);
  document.querySelectorAll('.cs-tabs button').forEach((button) => button.addEventListener('click', () => {
    state.tab = button.dataset.tab;
    document.querySelectorAll('.cs-tabs button').forEach((b) => { const on = b === button; b.classList.toggle('is-active', on); b.setAttribute('aria-selected', String(on)); });
    renderInfo();
  }));

  const wanted = new URLSearchParams(window.location.search).get('plot') || (window.AgroSel && window.AgroSel.get());
  const initial = farms.plots.find((p) => p.id === String(wanted)) || farms.plots[0];
  if (initial) selectPlot(initial.id, false);
  steps(); icons();
})();
