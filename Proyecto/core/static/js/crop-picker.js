/* Selector visual de cultivos de AgroAsesor.
 *
 * Mejora progresiva: toma un <select> de cultivos (que sigue siendo la fuente de verdad del formulario)
 * y lo presenta como tarjetas seleccionables con filtros por categoría, buscador, cultivos frecuentes,
 * ficha del cultivo y un paso siguiente. No define ninguna lista de cultivos: usa solo las opciones del
 * <select> (que vienen de la base de datos) y los datos reales del catálogo (#agro-catalog) y de
 * #agro-crop-picker (frecuentes y ventanas con fuente verificada).
 *
 * Para sumar más datos a la ficha (requerimiento hídrico, suelo, etc.) basta con enviarlos en el
 * catálogo y agregar una fila a FACT_FIELDS: la ficha solo muestra lo que existe.
 */
(function () {
  'use strict';

  // Solo iconografía (no son datos): palabra normalizada del nombre → emoji. Lo demás usa el de su categoría.
  const CROP_EMOJI = {
    maiz: '🌽', trigo: '🌾', avena: '🌱', cebada: '🌾', arroz: '🌾', centeno: '🌾',
    poroto: '🫘', lenteja: '🫘', garbanzo: '🫘', haba: '🫘', arveja: '🌱', lupino: '🫘',
    tomate: '🍅', cebolla: '🧅', lechuga: '🥬', repollo: '🥬', zapallo: '🎃', zanahoria: '🥕',
    ajo: '🧄', pimenton: '🫑', sandia: '🍉', melon: '🍈', choclo: '🌽', frutilla: '🍓',
    papa: '🥔', remolacha: '🌱', camote: '🍠',
    alfalfa: '🌿', trebol: '🍀', ballica: '🌿',
    vid: '🍇', uva: '🍇', palto: '🥑', cerezo: '🍒', manzano: '🍎', nogal: '🌰', arandano: '🫐',
    olivo: '🫒', limonero: '🍋', naranjo: '🍊', kiwi: '🥝', durazno: '🍑', peral: '🍐', ciruelo: '🍑',
    raps: '🌼', maravilla: '🌻',
  };
  const CATEGORY_EMOJI = {
    cereales: '🌾', leguminosas: '🫘', hortalizas: '🥬', tuberculos: '🥔',
    forrajes: '🌿', frutales: '🍎', industriales: '🌻', otros: '🌱',
  };
  const FLOW_STEPS = [
    ['predio', 'Predio'], ['potrero', 'Potrero'], ['cultivo', 'Cultivo'], ['siembra', 'Siembra'],
    ['planificacion', 'Planificación'], ['labores', 'Labores'], ['historial', 'Historial'],
  ];

  const norm = (text) => String(text || '').normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase().trim();

  function emojiFor(name, categoryKey) {
    const words = norm(name).replace(/[^a-z\s]/g, ' ').split(/\s+/).filter(Boolean);
    for (const word of words) if (CROP_EMOJI[word]) return CROP_EMOJI[word];
    return CATEGORY_EMOJI[categoryKey] || '🌱';
  }

  function readJson(id) {
    const node = document.getElementById(id);
    if (!node) return null;
    try { return JSON.parse(node.textContent); } catch (error) { return null; }
  }

  function h(tag, attrs, ...kids) {
    const node = document.createElement(tag);
    Object.entries(attrs || {}).forEach(([key, value]) => {
      if (value === false || value == null) return;
      if (key === 'class') node.className = value;
      else node.setAttribute(key, value === true ? '' : value);
    });
    kids.flat().forEach((kid) => {
      if (kid === null || kid === undefined || kid === false) return;
      node.append(kid instanceof Node ? kid : document.createTextNode(String(kid)));
    });
    return node;
  }

  function searchIcon() {
    const ns = 'http://www.w3.org/2000/svg';
    const svg = document.createElementNS(ns, 'svg');
    ['viewBox:0 0 24 24', 'width:16', 'height:16', 'aria-hidden:true', 'fill:none', 'stroke:currentColor', 'stroke-width:2', 'stroke-linecap:round']
      .forEach((pair) => { const [name, value] = pair.split(':'); svg.setAttribute(name, value); });
    const circle = document.createElementNS(ns, 'circle');
    ['cx:11', 'cy:11', 'r:7'].forEach((pair) => { const [name, value] = pair.split(':'); circle.setAttribute(name, value); });
    const path = document.createElementNS(ns, 'path');
    path.setAttribute('d', 'm20 20-3.5-3.5');
    svg.append(circle, path);
    return svg;
  }

  function cropsFromSelect(select) {
    const crops = [];
    select.querySelectorAll('option').forEach((option) => {
      if (!option.value) return;
      const group = option.parentElement && option.parentElement.tagName === 'OPTGROUP' ? option.parentElement.label : 'Otros cultivos';
      crops.push({ id: String(option.value), name: option.textContent.trim(), group });
    });
    return crops;
  }

  const fmtNumber = (value) => Number(value).toLocaleString('es-CL', { maximumFractionDigits: 3 });

  // Filas de la ficha. Cada una devuelve un texto (o lista de textos) solo cuando el dato existe.
  const FACT_FIELDS = [
    { key: 'category', label: 'Categoría', get: (crop) => crop.short || crop.group },
    { key: 'type', label: 'Tipo de cultivo', get: (crop) => crop.detail && crop.detail.type },
    { key: 'family', label: 'Familia botánica', get: (crop) => crop.detail && crop.detail.family },
    { key: 'sowing', label: 'Siembra recomendada', get: (crop) => windowLines(crop, 'sowing') },
    { key: 'harvest', label: 'Cosecha', get: (crop) => windowLines(crop, 'harvest') },
    { key: 'cycle', label: 'Ciclo aproximado', get: (crop) => windowLines(crop, 'cycleDays', (value) => value + ' días') },
    {
      key: 'density', label: 'Densidad de siembra',
      get: (crop) => (crop.cat.density != null ? fmtNumber(crop.cat.density) + ' ' + (crop.cat.unit || 'kg') + '/ha' : ''),
    },
    {
      key: 'yield', label: 'Rendimiento de referencia',
      get: (crop) => (crop.cat.yield != null ? fmtNumber(crop.cat.yield) + ' t/ha' : ''),
    },
    {
      key: 'varieties', label: 'Variedades en el catálogo',
      get: (crop) => {
        const list = crop.varieties || [];
        if (!list.length) return '';
        return list.slice(0, 3).join(', ') + (list.length > 3 ? ' y ' + (list.length - 3) + ' más' : '');
      },
    },
    {
      key: 'description', label: 'Descripción',
      get: (crop) => {
        const text = (crop.cat.description || '').trim();
        return text && norm(text) !== norm(crop.group) ? text : '';
      },
    },
  ];

  function windowLines(crop, field, format) {
    const windows = (crop.detail && crop.detail.windows) || [];
    const lines = windows
      .filter((item) => item[field])
      .map((item) => {
        const value = format ? format(item[field]) : item[field];
        const label = [item.zone, item.variety].filter(Boolean).join(' · ');
        return label ? label + ': ' + value : value;
      });
    return lines;
  }

  function mount(host, options) {
    options = options || {};
    const select = options.select;
    if (!host || !select) return null;
    const hints = readJson('agro-crop-picker') || {};
    const catalog = readJson('agro-catalog') || {};
    const catalogById = new Map((catalog.cultivos || []).map((item) => [String(item.id), item]));
    const groupMeta = new Map((hints.groups || []).map((item) => [item.name, item]));
    const varieties = catalog.varieties || {};

    const groupOrder = (hints.groups || []).map((item) => item.name);
    const crops = cropsFromSelect(select).sort((a, b) => {
      const byGroup = (groupOrder.indexOf(a.group) + 1 || 99) - (groupOrder.indexOf(b.group) + 1 || 99);
      return byGroup || a.name.localeCompare(b.name, 'es');
    }).map((crop) => {
      const meta = groupMeta.get(crop.group) || {};
      const key = meta.key || 'otros';
      return {
        ...crop,
        key,
        short: meta.short || crop.group,
        emoji: emojiFor(crop.name, key),
        cat: catalogById.get(crop.id) || {},
        detail: (hints.details || {})[crop.id] || null,
        varieties: varieties[crop.id] || [],
      };
    });
    if (!crops.length) return null;
    const byId = new Map(crops.map((crop) => [crop.id, crop]));

    const state = { value: '', mode: 'choose', filter: 'all', query: '' };
    let context = typeof options.context === 'function' ? options.context : () => options.context || {};

    host.replaceChildren();
    host.classList.add('crop-picker');
    const question = options.question || '¿Qué quieres plantar en este potrero?';

    // ---- Esqueleto ----
    const rail = options.rail ? h('ol', { class: 'flow-rail', 'aria-label': 'Flujo de planificación' }) : null;
    const link = h('div', { class: 'crop-link' });
    const live = h('p', { class: 'crop-sr', 'aria-live': 'polite' });
    const searchInput = h('input', {
      type: 'search', class: 'crop-search-input', placeholder: 'Buscar cultivo...', autocomplete: 'off',
      'aria-label': 'Buscar cultivo', 'aria-controls': 'crop-grid-' + (select.id || 'x'),
    });
    const search = h('label', { class: 'crop-search' }, searchIcon(), searchInput);
    const filters = h('div', { class: 'crop-filters', role: 'group', 'aria-label': 'Filtrar por categoría' });
    const frequent = h('div', { class: 'crop-frequent' });
    const grid = h('div', { class: 'crop-grid', role: 'radiogroup', 'aria-label': 'Cultivos disponibles', id: 'crop-grid-' + (select.id || 'x') });
    const clearButton = h('button', { type: 'button', class: 'btn-secondary-agro btn-sm' }, 'Limpiar filtros');
    const empty = h('div', { class: 'crop-empty', hidden: true },
      h('span', { class: 'crop-empty-ico', 'aria-hidden': 'true' }, '🌱'),
      h('strong', {}, 'Ningún cultivo coincide con tu búsqueda'),
      h('p', {}, 'Prueba con otro nombre o muestra todas las categorías.'),
      clearButton);
    const choose = h('div', { class: 'crop-choose' },
      h('h3', { class: 'crop-question' }, question),
      h('div', { class: 'crop-toolbar' }, search, filters),
      frequent,
      h('div', { class: 'crop-divider', 'aria-hidden': 'true' }),
      grid, empty);
    const sheet = h('section', { class: 'crop-sheet', hidden: true, 'aria-live': 'polite', 'aria-label': 'Ficha del cultivo' });
    host.append(...[rail, link, choose, sheet, live].filter(Boolean));

    // ---- Tarjetas ----
    const cards = new Map();
    crops.forEach((crop) => {
      const card = h('button', {
        type: 'button', class: 'crop-card cat-' + crop.key, role: 'radio', 'aria-checked': 'false',
        tabindex: '-1', 'data-crop-id': crop.id, title: crop.name + ' · ' + crop.short,
      },
      h('span', { class: 'crop-card-badge', 'aria-hidden': 'true' }, crop.emoji),
      h('span', { class: 'crop-card-name' }, crop.name),
      h('span', { class: 'crop-card-cat' }, crop.short),
      h('span', { class: 'crop-card-check', 'aria-hidden': 'true' }, '✓'));
      cards.set(crop.id, card);
      grid.append(card);
    });

    // ---- Filtros por categoría (solo las que existen en el catálogo) ----
    const present = [];
    crops.forEach((crop) => { if (!present.some((item) => item.key === crop.key)) present.push({ key: crop.key, short: crop.short }); });
    const order = (hints.groups || []).map((item) => item.key);
    present.sort((a, b) => order.indexOf(a.key) - order.indexOf(b.key));
    const filterButtons = new Map();
    [{ key: 'all', short: 'Todos', count: crops.length }, ...present.map((item) => ({
      ...item, count: crops.filter((crop) => crop.key === item.key).length,
    }))].forEach((item) => {
      const button = h('button', { type: 'button', class: 'crop-filter', 'aria-pressed': item.key === 'all' ? 'true' : 'false', 'data-filter': item.key },
        item.short, h('small', {}, String(item.count)));
      filterButtons.set(item.key, button);
      filters.append(button);
    });
    filters.hidden = present.length < 2;

    // ---- Frecuentes / sugeridos ----
    const frequentCrops = (hints.frequent || []).map((id) => byId.get(String(id))).filter(Boolean).slice(0, 5);
    if (frequentCrops.length) {
      const used = hints.frequentBasis === 'used';
      frequent.append(
        h('div', { class: 'crop-frequent-head' },
          h('strong', {}, used ? 'Cultivos frecuentes' : 'Cultivos sugeridos'),
          h('span', {}, used ? 'Los que ya usaste en tus potreros' : 'Opciones comunes del catálogo')),
        h('div', { class: 'crop-frequent-list' }, frequentCrops.map((crop) => h('button', {
          type: 'button', class: 'crop-quick cat-' + crop.key, 'data-quick-crop': crop.id, 'aria-pressed': 'false',
        }, h('span', { 'aria-hidden': 'true' }, crop.emoji), crop.name))));
    } else {
      frequent.hidden = true;
    }

    // ---- Render ----
    const currentCrop = () => byId.get(state.value) || null;

    function renderRail() {
      if (!rail) return;
      const current = state.mode === 'chosen' && state.value ? 'siembra' : 'cultivo';
      const currentIndex = FLOW_STEPS.findIndex((step) => step[0] === current);
      rail.replaceChildren(...FLOW_STEPS.map(([key, label], index) => h('li', {
        class: index < currentIndex ? 'is-done' : index === currentIndex ? 'is-current' : '',
        'aria-current': index === currentIndex ? 'step' : false,
      }, h('span', { class: 'flow-dot', 'aria-hidden': 'true' }, index < currentIndex ? '✓' : String(index + 1)), h('span', { class: 'flow-label' }, label))));
    }

    function renderLink() {
      const ctx = context() || {};
      const crop = currentCrop();
      const plotName = ctx.plot || 'Este potrero';
      const cropSide = h('div', { class: 'crop-link-crop' + (crop ? ' is-set cat-' + crop.key : '') },
        h('small', {}, 'Cultivo seleccionado'),
        crop
          ? h('strong', {}, h('span', { class: 'crop-link-emoji', 'aria-hidden': 'true' }, crop.emoji), crop.name)
          : h('strong', { class: 'is-empty' }, 'Aún sin elegir'));
      if (crop && state.mode === 'chosen') {
        const change = h('button', { type: 'button', class: 'crop-change' }, 'Cambiar cultivo');
        change.addEventListener('click', reopen);
        cropSide.append(change);
      }
      link.replaceChildren(
        h('div', { class: 'crop-link-plot' },
          h('small', {}, 'Potrero seleccionado'),
          h('strong', {}, h('span', { 'aria-hidden': 'true' }, '📍 '), plotName),
          ctx.area ? h('span', {}, ctx.area) : null),
        h('span', { class: 'crop-link-arrow', 'aria-hidden': 'true' }),
        cropSide);
    }

    function factsFor(crop) {
      const rows = [];
      FACT_FIELDS.forEach((field) => {
        const value = field.get(crop);
        const list = (Array.isArray(value) ? value : [value]).filter(Boolean);
        if (list.length) rows.push({ field, list });
      });
      return rows;
    }

    function renderSheet() {
      const crop = currentCrop();
      sheet.hidden = !crop;
      if (!crop) { sheet.replaceChildren(); return; }
      const ctx = context() || {};
      const rows = factsFor(crop);
      sheet.className = 'crop-sheet cat-' + crop.key;
      const head = h('header', { class: 'crop-sheet-head' },
        h('span', { class: 'crop-sheet-badge', 'aria-hidden': 'true' }, crop.emoji),
        h('div', {},
          h('strong', { class: 'crop-sheet-name' }, crop.name),
          h('span', { class: 'crop-tag' }, crop.short)));
      const status = h('p', { class: 'crop-sheet-state' },
        h('span', { 'aria-hidden': 'true' }, '✓'),
        ' Estado: ', h('strong', {}, 'Seleccionado para este potrero'));
      const facts = h('dl', { class: 'crop-facts' }, rows.map(({ field, list }) => h('div', { class: 'crop-fact', 'data-fact': field.key },
        h('dt', {}, field.label), h('dd', {}, list.map((line) => h('span', {}, line))))));
      const note = rows.length <= 1
        ? h('p', { class: 'crop-sheet-note' }, 'Aún no hay más datos de este cultivo en el catálogo. Cuando se carguen (período de siembra, ciclo, rendimiento…) aparecerán aquí.')
        : null;
      const parts = [head, status, facts, note];
      if (state.mode === 'choose') {
        const next = h('button', { type: 'button', class: 'btn-primary-agro crop-continue' }, 'Continuar planificación');
        next.addEventListener('click', goNext);
        parts.push(h('div', { class: 'crop-sheet-actions' }, next));
      } else if (options.nextTarget) {
        const go = h('button', { type: 'button', class: 'btn-secondary-agro btn-sm' }, 'Ir a la fecha de siembra');
        go.addEventListener('click', focusNextTarget);
        parts.push(h('div', { class: 'crop-next' },
          h('span', { class: 'crop-next-ico', 'aria-hidden': 'true' }, '📅'),
          h('div', {}, h('strong', {}, '¿Cuándo quieres sembrar?'), h('p', {}, 'Es el siguiente paso de la planificación de este potrero.')),
          go));
      }
      sheet.replaceChildren(...parts.filter(Boolean));
    }

    function visibleCards() {
      return crops.filter((crop) => !cards.get(crop.id).hidden).map((crop) => cards.get(crop.id));
    }

    function applyFilter() {
      const query = norm(state.query);
      let shown = 0;
      crops.forEach((crop) => {
        const matchesFilter = state.filter === 'all' || crop.key === state.filter;
        const matchesQuery = !query || norm(crop.name).includes(query) || norm(crop.short).includes(query) || norm(crop.group).includes(query);
        const visible = matchesFilter && matchesQuery;
        cards.get(crop.id).hidden = !visible;
        if (visible) shown += 1;
      });
      filterButtons.forEach((button, key) => button.setAttribute('aria-pressed', key === state.filter ? 'true' : 'false'));
      empty.hidden = shown > 0;
      grid.hidden = shown === 0;
      frequent.hidden = !frequentCrops.length || state.filter !== 'all' || Boolean(query);
      live.textContent = shown === 1 ? '1 cultivo' : shown + ' cultivos';
      syncTabindex();
    }

    function syncTabindex() {
      const visible = visibleCards();
      const selected = visible.find((card) => card.getAttribute('aria-checked') === 'true');
      const focusable = selected || visible[0];
      cards.forEach((card) => card.setAttribute('tabindex', card === focusable ? '0' : '-1'));
    }

    function applyValue() {
      cards.forEach((card, id) => card.setAttribute('aria-checked', id === state.value ? 'true' : 'false'));
      host.querySelectorAll('[data-quick-crop]').forEach((button) => button.setAttribute('aria-pressed', button.dataset.quickCrop === state.value ? 'true' : 'false'));
      syncTabindex();
    }

    function applyMode() {
      host.dataset.mode = state.mode;
      choose.hidden = state.mode === 'chosen' && Boolean(state.value);
      renderRail();
    }

    function renderAll() {
      applyValue();
      applyMode();
      renderLink();
      renderSheet();
    }

    // ---- Acciones ----
    function setValue(id, fromUser) {
      const next = id && byId.has(String(id)) ? String(id) : '';
      const changed = select.value !== next;
      state.value = next;
      if (changed) {
        select.value = next;
        select.dispatchEvent(new Event('change', { bubbles: true }));
      }
      if (!next) state.mode = 'choose';
      renderAll();
      if (fromUser && next) {
        live.textContent = byId.get(next).name + ' seleccionado';
        sheet.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
      }
    }

    function goNext() {
      if (!state.value) return;
      state.mode = 'chosen';
      renderAll();
      if (typeof options.onContinue === 'function') options.onContinue(currentCrop());
    }

    function reopen() {
      state.mode = 'choose';
      renderAll();
      if (typeof options.onReopen === 'function') options.onReopen();
      const selected = cards.get(state.value);
      if (selected) selected.focus();
    }

    function focusNextTarget() {
      const target = options.nextTarget ? document.querySelector(options.nextTarget) : null;
      if (!target) return;
      target.scrollIntoView({ behavior: 'smooth', block: 'center' });
      target.focus({ preventScroll: true });
    }

    function reset() {
      state.filter = 'all';
      state.query = '';
      searchInput.value = '';
      state.mode = 'choose';
      state.value = '';
      select.value = '';
      select.dispatchEvent(new Event('change', { bubbles: true }));
      applyFilter();
      renderAll();
    }

    // ---- Eventos ----
    grid.addEventListener('click', (event) => {
      const card = event.target.closest('.crop-card');
      if (card) setValue(card.dataset.cropId, true);
    });
    frequent.addEventListener('click', (event) => {
      const quick = event.target.closest('[data-quick-crop]');
      if (!quick) return;
      setValue(quick.dataset.quickCrop, true);
      const card = cards.get(quick.dataset.quickCrop);
      if (card && !card.hidden) card.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
    });
    filters.addEventListener('click', (event) => {
      const button = event.target.closest('[data-filter]');
      if (!button) return;
      state.filter = button.dataset.filter;
      applyFilter();
    });
    searchInput.addEventListener('input', () => { state.query = searchInput.value; applyFilter(); });
    searchInput.addEventListener('keydown', (event) => {
      if (event.key !== 'Enter') return;
      event.preventDefault();
      const visible = visibleCards();
      if (visible.length === 1) setValue(visible[0].dataset.cropId, true);
    });
    clearButton.addEventListener('click', () => {
      state.filter = 'all';
      state.query = '';
      searchInput.value = '';
      applyFilter();
      searchInput.focus();
    });
    grid.addEventListener('keydown', (event) => {
      const keys = ['ArrowRight', 'ArrowLeft', 'ArrowDown', 'ArrowUp', 'Home', 'End'];
      if (!keys.includes(event.key)) return;
      const visible = visibleCards();
      const index = visible.indexOf(document.activeElement);
      if (index === -1) return;
      event.preventDefault();
      let target = visible[index];
      if (event.key === 'ArrowRight') target = visible[Math.min(index + 1, visible.length - 1)];
      else if (event.key === 'ArrowLeft') target = visible[Math.max(index - 1, 0)];
      else if (event.key === 'Home') target = visible[0];
      else if (event.key === 'End') target = visible[visible.length - 1];
      else {
        const current = visible[index];
        const down = event.key === 'ArrowDown';
        const candidates = visible.filter((card) => (down ? card.offsetTop > current.offsetTop + 4 : card.offsetTop < current.offsetTop - 4));
        if (candidates.length) {
          const row = down ? Math.min(...candidates.map((card) => card.offsetTop)) : Math.max(...candidates.map((card) => card.offsetTop));
          target = candidates.filter((card) => card.offsetTop === row)
            .sort((a, b) => Math.abs(a.offsetLeft - current.offsetLeft) - Math.abs(b.offsetLeft - current.offsetLeft))[0];
        }
      }
      cards.forEach((card) => card.setAttribute('tabindex', card === target ? '0' : '-1'));
      target.focus();
    });
    // Si otro script cambia el <select>, la interfaz se mantiene sincronizada.
    select.addEventListener('change', () => {
      if (select.value !== state.value) {
        state.value = byId.has(select.value) ? select.value : '';
        if (!state.value) state.mode = 'choose';
        renderAll();
      }
    });

    state.value = byId.has(select.value) ? select.value : '';
    state.mode = state.value && !options.startChoosing ? 'chosen' : 'choose';
    applyFilter();
    renderAll();

    const api = {
      getValue: () => state.value,
      setValue: (id) => setValue(id, false),
      reset,
      refresh: renderAll,
      setContext(next) { context = typeof next === 'function' ? next : () => next || {}; renderLink(); renderSheet(); },
      focus() { searchInput.focus({ preventScroll: true }); },
    };
    host._cropPicker = api;
    return api;
  }

  // Formularios de potrero y de temporada: se mejora el <select name="cultivo"> existente.
  function autoMount() {
    document.querySelectorAll('#terrain-form select[name="cultivo"], .activity-form-card form select[name="cultivo"]').forEach((select) => {
      if (select.dataset.cropPicker) return;
      const form = select.closest('form');
      const field = select.closest('.field') || select.parentElement;
      const host = h('div', { class: 'crop-picker-host' });
      const nameInput = form.querySelector('[name="nombre"]');
      const areaInput = form.querySelector('[name="superficie_ha"]');
      const plotName = form.dataset.cropPlot || '';
      const plotArea = form.dataset.cropArea || '';
      const context = () => {
        const typed = nameInput ? nameInput.value.trim() : '';
        const area = areaInput && areaInput.value ? Number(areaInput.value.replace(',', '.')) : NaN;
        return {
          plot: plotName || typed || 'Nuevo potrero',
          area: plotArea || (Number.isFinite(area) && area > 0 ? area.toLocaleString('es-CL', { maximumFractionDigits: 2 }) + ' ha' : ''),
        };
      };
      field.parentNode.insertBefore(host, field);
      field.classList.add('crop-field-enhanced');
      const nextTarget = form.querySelector('[name="fecha_siembra"]') ? '#' + form.querySelector('[name="fecha_siembra"]').id : '';
      const picker = mount(host, { select, context, nextTarget });
      if (!picker) { host.remove(); field.classList.remove('crop-field-enhanced'); return; }
      select.dataset.cropPicker = '1';
      [nameInput, areaInput].forEach((input) => input && input.addEventListener('input', () => picker.setContext(context)));
    });
  }

  window.AgroCropPicker = { mount, autoMount, emojiFor };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', autoMount);
  else autoMount();
})();
