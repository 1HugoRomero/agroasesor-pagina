(function () {
  'use strict';
  const months = ['ENE', 'FEB', 'MAR', 'ABR', 'MAY', 'JUN', 'JUL', 'AGO', 'SEP', 'OCT', 'NOV', 'DIC'];
  const monthNames = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre'];
  const phaseLabels = {
    sow: 'Ventana de siembra',
    grow: 'Crecimiento referencial',
    harvest: 'Ventana de cosecha',
    none: 'Fuera de las ventanas documentadas',
  };
  const PHYTO = new Set(['herbicide', 'fungicide', 'insecticide']);

  function readJson(id, fallback) {
    const node = document.getElementById(id);
    if (!node) return fallback;
    try { return JSON.parse(node.textContent); } catch (error) { return fallback; }
  }

  const references = readJson('calendar-references', []);
  let plots = readJson('calendar-plots', []);
  const varietyIndex = readJson('calendar-variety-index', []);
  const catalog = readJson('agro-catalog', {});
  const cropFilter = document.getElementById('crop-filter');
  const varietyFilter = document.getElementById('variety-filter');
  const zoneFilter = document.getElementById('zone');
  const yearFilter = document.getElementById('year');
  const plotFilter = document.getElementById('calendar-plot');
  const table = document.getElementById('cal-table');
  const detail = document.getElementById('cal-detail');
  const empty = document.getElementById('calendar-empty');
  const yearNote = document.getElementById('calendar-year-note');
  const realNote = document.getElementById('calendar-real-note');
  let selectedReferenceId = null;
  let activeTab = 'general';

  function element(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined && text !== null) node.textContent = text;
    return node;
  }

  function safeUrl(value) {
    if (!value) return '';
    try {
      const url = new URL(value, window.location.origin);
      return ['http:', 'https:'].includes(url.protocol) ? url.href : '';
    } catch (error) { return ''; }
  }

  function parseDate(value) {
    if (!value) return null;
    const [year, month, day] = value.split('-').map(Number);
    return year && month && day ? { year, month, day } : null;
  }

  function formatDate(value) {
    const date = parseDate(value);
    return date ? String(date.day).padStart(2, '0') + '/' + String(date.month).padStart(2, '0') + '/' + date.year : 'Sin fecha';
  }

  function ordinal(month, day) {
    return month && day ? month * 32 + day : null;
  }

  function hasWindow(reference, prefix) {
    return Boolean(reference[prefix + 'StartMonth'] && reference[prefix + 'StartDay'] && reference[prefix + 'EndMonth'] && reference[prefix + 'EndDay']);
  }

  function monthInWindow(month, reference, prefix) {
    if (!hasWindow(reference, prefix)) return false;
    const start = ordinal(reference[prefix + 'StartMonth'], reference[prefix + 'StartDay']);
    const end = ordinal(reference[prefix + 'EndMonth'], reference[prefix + 'EndDay']);
    const first = month * 32 + 1;
    const last = month * 32 + 31;
    if (start <= end) return first <= end && last >= start;
    return last >= start || first <= end;
  }

  function crossesYear(reference) {
    if (!hasWindow(reference, 'sowing') || !hasWindow(reference, 'harvest')) return false;
    return ordinal(reference.harvestStartMonth, reference.harvestStartDay) < ordinal(reference.sowingStartMonth, reference.sowingStartDay) ||
      ordinal(reference.sowingEndMonth, reference.sowingEndDay) < ordinal(reference.sowingStartMonth, reference.sowingStartDay);
  }

  function phase(reference, monthIndex) {
    const month = monthIndex + 1;
    if (monthInWindow(month, reference, 'sowing')) return 'sow';
    if (monthInWindow(month, reference, 'harvest')) return 'harvest';
    if (!hasWindow(reference, 'sowing') || !hasWindow(reference, 'harvest')) return 'none';
    // Meses entre el fin de la siembra y el inicio de la cosecha (con salto de año).
    let cursor = reference.sowingEndMonth % 12;
    for (let count = 0; count < 12; count += 1) {
      if (cursor === reference.harvestStartMonth - 1) return 'none';
      if (cursor === monthIndex) return 'grow';
      cursor = (cursor + 1) % 12;
    }
    return 'none';
  }

  function verified(reference) {
    return reference.sourceVerified && reference.status === 'verified';
  }

  function visibleReferences() {
    return references.filter((reference) => {
      if (!verified(reference)) return false;
      if (zoneFilter.value && String(reference.zoneId) !== zoneFilter.value) return false;
      if (cropFilter.value && String(reference.cropId) !== cropFilter.value) return false;
      if (varietyFilter.value !== '*' && (reference.variety || '') !== varietyFilter.value) return false;
      return true;
    });
  }

  function varietiesFor(cropId, zoneId) {
    return [...new Set(varietyIndex
      .filter((item) => String(item.cropId) === String(cropId) && (!zoneId || String(item.zoneId) === String(zoneId)))
      .map((item) => item.variety))].sort((a, b) => a.localeCompare(b, 'es'));
  }

  function updateFilterVarieties(selectedValue) {
    const previous = selectedValue === undefined ? varietyFilter.value : selectedValue;
    const choices = cropFilter.value ? varietiesFor(cropFilter.value, zoneFilter.value) : [];
    varietyFilter.replaceChildren(new Option('Todas las variedades', '*'), new Option('Solo referencia general', ''));
    choices.forEach((variety) => varietyFilter.add(new Option(variety, variety)));
    varietyFilter.value = previous === '' || choices.includes(previous) ? previous : '*';
  }

  function updateEvaluatorVarieties(form, preferred) {
    const select = form.elements.variety;
    const previous = preferred === undefined ? select.value : preferred;
    const choices = form.elements.crop_id.value ? varietiesFor(form.elements.crop_id.value, form.elements.zone_id.value) : [];
    select.replaceChildren(new Option('Referencia general', ''));
    choices.forEach((variety) => select.add(new Option(variety, variety)));
    if (previous && !choices.includes(previous)) {
      // Variedad registrada por el agricultor sin referencia: se conserva para que el
      // servidor informe que no hay ventana específica y use la general si existe.
      select.add(new Option(previous + ' (sin referencia propia)', previous));
    }
    select.value = previous || '';
  }

  function selectedPlot() {
    return plotFilter ? plots.find((plot) => String(plot.id) === plotFilter.value) || null : null;
  }

  function plotSeason(plot) {
    if (!plot) return null;
    return (plot.seasons || [])[0] || null;
  }

  function plotDates(plot) {
    const season = plotSeason(plot);
    return {
      crop: season ? season.crop : plot.crop,
      variety: season ? season.variety : plot.variety,
      sowing: season ? season.sowingDate : plot.sowingDate,
      harvest: season ? season.harvestDate : plot.harvestDate,
      season: season ? season.season : '',
      status: season ? season.statusLabel : plot.status,
    };
  }

  function realPhase(dates, monthIndex, year) {
    const sowing = parseDate(dates.sowing);
    const harvest = parseDate(dates.harvest);
    const key = year * 12 + monthIndex;
    const sowingKey = sowing ? sowing.year * 12 + sowing.month - 1 : null;
    const harvestKey = harvest ? harvest.year * 12 + harvest.month - 1 : null;
    if (sowingKey === key) return 'real-sow';
    if (harvestKey === key) return 'real-harvest';
    if (sowingKey !== null && harvestKey !== null && key > sowingKey && key < harvestKey) return 'real-grow';
    return '';
  }

  function addTabSection(container, heading, value, emptyText) {
    const section = element('div', 'calendar-detail-section');
    section.append(element('h4', '', heading));
    if (value === null || value === undefined || value === '' || (Array.isArray(value) && !value.length)) {
      section.append(element('p', 'muted', emptyText || 'Sin información documentada en la fuente registrada.'));
    } else if (Array.isArray(value)) {
      const list = element('ul');
      value.forEach((item) => list.append(element('li', '', item)));
      section.append(list);
    } else {
      section.append(element('p', '', value));
    }
    container.append(section);
  }

  function formatWindow(reference, prefix) {
    if (!hasWindow(reference, prefix)) return 'Sin información';
    return reference[prefix + 'StartDay'] + ' de ' + monthNames[reference[prefix + 'StartMonth'] - 1] + ' – ' +
      reference[prefix + 'EndDay'] + ' de ' + monthNames[reference[prefix + 'EndMonth'] - 1];
  }

  function cropCatalog(reference) {
    return (catalog.cultivos || []).find((crop) => String(crop.id) === String(reference.cropId)) || null;
  }

  function productsFor(reference) {
    return (catalog.insumos || []).filter((item) =>
      item.usable !== false && item.active !== false &&
      (String(item.cropId) === String(reference.cropId) || item.crop === reference.crop));
  }

  function productLink(item) {
    const link = element('a', 'text-link', item.name);
    link.href = '/decisiones/?herramienta=ficha&crop=' + encodeURIComponent(item.cropId || '') + '&insumo=' + encodeURIComponent(item.id);
    return link;
  }

  function renderProducts(container, reference) {
    const crop = cropCatalog(reference);
    const seedSection = element('div', 'calendar-detail-section');
    seedSection.append(element('h4', '', 'Densidad de siembra del catálogo'));
    if (crop && crop.density !== null && crop.density !== undefined && crop.densitySource && crop.densityUrl) {
      seedSection.append(element('p', '', crop.density + ' ' + (crop.unit || 'kg') + '/ha · Fuente: ' + crop.densitySource +
        (crop.densityVerifiedAt ? ' (verificada ' + crop.densityVerifiedAt + ')' : '')));
    } else {
      seedSection.append(element('p', 'muted', 'No hay una densidad de siembra verificada con fuente para este cultivo.'));
    }
    container.append(seedSection);

    const groups = [
      ['seed', 'Semillas disponibles en el catálogo'],
      ['fertilizer', 'Fertilizantes relacionados'],
      ['phyto', 'Productos fitosanitarios con uso verificado'],
      ['other', 'Otros insumos'],
    ];
    const products = productsFor(reference);
    groups.forEach(([key, title]) => {
      const items = products.filter((item) => key === 'phyto'
        ? PHYTO.has(item.category) && item.verifiedUse === true
        : item.category === key);
      const section = element('div', 'calendar-detail-section');
      section.append(element('h4', '', title));
      if (!items.length) {
        section.append(element('p', 'muted', key === 'phyto'
          ? 'No hay productos con autorización, etiqueta, cultivo, objetivo y dosis verificados para este cultivo.'
          : 'No hay registros en el catálogo para este cultivo.'));
      } else {
        const list = element('ul', 'calendar-product-list');
        items.forEach((item) => {
          const row = element('li');
          row.append(productLink(item));
          row.append(element('span', 'badge' + (item.verified ? '' : ' amber'), item.verified ? 'Verificado' : 'Sin verificar'));
          const label = safeUrl(item.labelUrl || item.sourceUrl);
          if (label) {
            const doc = element('a', 'text-link', item.labelUrl ? 'Etiqueta' : 'Ficha técnica');
            doc.href = label; doc.target = '_blank'; doc.rel = 'noopener noreferrer';
            row.append(doc);
          }
          list.append(row);
        });
        section.append(list);
      }
      container.append(section);
    });
  }

  const TABS = [
    ['general', 'General'], ['sowing', 'Siembra'], ['growth', 'Desarrollo'],
    ['harvest', 'Cosecha'], ['health', 'Sanidad'], ['products', 'Productos'], ['sources', 'Fuentes'],
  ];

  function renderTab(panel, reference) {
    panel.replaceChildren();
    const crop = cropCatalog(reference);
    const allVarieties = varietiesFor(reference.cropId, reference.zoneId);
    if (activeTab === 'general') {
      addTabSection(panel, 'Nombre común', reference.crop);
      addTabSection(panel, 'Nombre científico', reference.scientificName);
      addTabSection(panel, 'Familia botánica', reference.botanicalFamily);
      addTabSection(panel, 'Tipo de cultivo', reference.cropType);
      addTabSection(panel, 'Variedades con referencia en esta zona', allVarieties, 'Solo existe referencia general del cultivo.');
      addTabSection(panel, 'Zona agrícola de referencia', reference.zone + (reference.referenceYear ? ' · año ' + reference.referenceYear : ' · ventana recurrente anual'));
      if (crop && crop.description) addTabSection(panel, 'Descripción del catálogo', crop.description);
    } else if (activeTab === 'sowing') {
      addTabSection(panel, 'Ventana referencial de siembra', formatWindow(reference, 'sowing'));
      addTabSection(panel, 'Condiciones de establecimiento', reference.sowingConditions);
      addTabSection(panel, 'Requerimientos relevantes', reference.requirements);
      const density = crop && crop.density !== null && crop.density !== undefined && crop.densitySource
        ? crop.density + ' ' + (crop.unit || 'kg') + '/ha · ' + crop.densitySource : '';
      addTabSection(panel, 'Densidad de siembra verificada', density, 'Sin densidad verificada en el catálogo.');
      addTabSection(panel, 'Profundidad de siembra', reference.sowingDepth);
    } else if (activeTab === 'growth') {
      addTabSection(panel, 'Duración referencial del ciclo', reference.cycleDays ? reference.cycleDays + ' días' : '');
      addTabSection(panel, 'Etapas fenológicas', reference.phenologicalStages);
      addTabSection(panel, 'Condiciones para el crecimiento', reference.growthConditions);
      addTabSection(panel, 'Manejo agronómico general', reference.management);
    } else if (activeTab === 'harvest') {
      addTabSection(panel, 'Ventana de cosecha', formatWindow(reference, 'harvest'));
      addTabSection(panel, 'Duración referencial del ciclo', reference.cycleDays ? reference.cycleDays + ' días' : '');
      addTabSection(panel, 'Indicadores de madurez', reference.maturityIndicators);
      addTabSection(panel, 'Consideraciones de cosecha', reference.harvestConsiderations);
      if (reference.yieldTonHa) addTabSection(panel, 'Rendimiento referencial documentado', reference.yieldTonHa + ' ton/ha');
      panel.append(element('p', 'calendar-disclaimer', 'La ventana estacional de cosecha no indica la madurez real del cultivo; confírmala con los indicadores observados en terreno.'));
    } else if (activeTab === 'health') {
      addTabSection(panel, 'Plagas relacionadas', reference.pests);
      addTabSection(panel, 'Enfermedades frecuentes', reference.diseases);
      addTabSection(panel, 'Malezas relevantes', reference.weeds);
      const problems = (catalog.problemas || []).filter((item) => (item.cropIds || []).includes(String(reference.cropId)));
      addTabSection(panel, 'Problemas documentados en el catálogo', problems.map((item) =>
        (item.typeLabel ? item.typeLabel + ': ' : '') + item.name + (item.symptoms ? ' — ' + item.symptoms : '')), 'No hay problemas agrícolas asociados a este cultivo en el catálogo.');
      addTabSection(panel, 'Manejo integrado documentado', reference.integratedManagement);
    } else if (activeTab === 'products') {
      renderProducts(panel, reference);
    } else if (activeTab === 'sources') {
      const source = element('div', 'calendar-source');
      const rows = [
        ['Institución', reference.sourceInstitution],
        ['Documento', reference.sourceDocument],
        ['Fecha de consulta', reference.sourceDate ? formatDate(reference.sourceDate) : ''],
        ['Región o contexto', reference.zone + (reference.variety ? ' · variedad ' + reference.variety : ' · referencia general')],
        ['Estado', verified(reference) ? 'Verificada con fuente' : 'Sin verificar'],
      ];
      const list = element('dl', 'calendar-source-list');
      rows.forEach(([label, value]) => {
        list.append(element('dt', '', label), element('dd', '', value || 'No registrado'));
      });
      source.append(list);
      const url = safeUrl(reference.sourceUrl);
      if (url) {
        const link = element('a', 'text-link', 'Abrir documento original');
        link.href = url; link.target = '_blank'; link.rel = 'noopener noreferrer';
        source.append(link);
      }
      panel.append(source);
    }
  }

  function showDetail(reference) {
    detail.replaceChildren();
    if (!reference) {
      detail.append(element('h2', '', 'Ficha agronómica'));
      detail.append(element('p', 'muted', references.length
        ? 'Selecciona un cultivo y una zona con una referencia verificada para ver su ficha.'
        : 'No hay referencias verificadas cargadas. La ficha se completará cuando el administrador registre fuentes oficiales.'));
      return;
    }
    selectedReferenceId = reference.id;
    const header = element('div', 'cal-detail-head');
    header.append(element('h2', '', reference.crop + (reference.variety ? ' · ' + reference.variety : '')));
    header.append(element('p', 'calendar-scientific', [reference.scientificName, reference.zone].filter(Boolean).join(' · ')));
    detail.append(header);
    const metrics = element('div', 'cal-metrics');
    [['Siembra', formatWindow(reference, 'sowing')], ['Cosecha', formatWindow(reference, 'harvest')],
      ['Ciclo', reference.cycleDays ? reference.cycleDays + ' días' : 'No documentado']].forEach(([label, value]) => {
      const metric = element('div', 'metric');
      metric.append(element('span', '', label), element('strong', '', value));
      metrics.append(metric);
    });
    detail.append(metrics);
    if (crossesYear(reference)) {
      detail.append(element('p', 'calendar-cross-year', 'Ciclo entre años: la cosecha de una siembra de ' + yearFilter.value + ' ocurre en ' + (Number(yearFilter.value) + 1) + '.'));
    }
    const tabList = element('div', 'cal-tabs');
    tabList.setAttribute('role', 'tablist');
    const panel = element('div', 'cal-tab-panel');
    panel.setAttribute('role', 'tabpanel');
    panel.id = 'cal-tab-panel';
    TABS.forEach(([key, label]) => {
      const button = element('button', 'cal-tab' + (key === activeTab ? ' is-active' : ''), label);
      button.type = 'button';
      button.setAttribute('role', 'tab');
      button.setAttribute('aria-selected', String(key === activeTab));
      button.setAttribute('aria-controls', 'cal-tab-panel');
      button.addEventListener('click', () => {
        activeTab = key;
        tabList.querySelectorAll('.cal-tab').forEach((item) => {
          const selected = item === button;
          item.classList.toggle('is-active', selected);
          item.setAttribute('aria-selected', String(selected));
        });
        renderTab(panel, reference);
      });
      tabList.append(button);
    });
    detail.append(tabList, panel);
    renderTab(panel, reference);
    detail.append(element('p', 'calendar-disclaimer', 'Información orientativa de la fuente indicada; no evalúa suelo, clima ni condiciones observadas en tu predio.'));
    table.querySelectorAll('tbody tr[data-reference-id]').forEach((row) => {
      row.classList.toggle('is-selected', row.dataset.referenceId === String(reference.id));
    });
  }

  function render() {
    const rows = visibleReferences();
    const year = Number(yearFilter.value);
    table.replaceChildren();
    const thead = element('thead');
    const header = element('tr');
    header.append(element('th', '', 'Cultivo / variedad'));
    months.forEach((month) => header.append(element('th', '', month)));
    thead.append(header);
    table.append(thead);
    const tbody = element('tbody');
    rows.forEach((reference) => {
      const row = element('tr');
      row.dataset.referenceId = String(reference.id);
      const labelCell = element('th');
      const button = element('button', 'calendar-row-button', reference.crop + (reference.variety ? ' · ' + reference.variety : ' · general'));
      button.type = 'button';
      button.addEventListener('click', () => showDetail(reference));
      labelCell.append(button);
      if (reference.referenceYear) labelCell.append(element('small', 'cal-row-year', 'Año ' + reference.referenceYear));
      row.append(labelCell);
      const wraps = crossesYear(reference);
      months.forEach((month, index) => {
        const cell = element('td');
        const key = phase(reference, index);
        const marker = element('span', 'cell ' + key);
        let title = month + ': ' + phaseLabels[key];
        if (wraps && key === 'harvest' && reference.harvestStartMonth < reference.sowingStartMonth) {
          marker.classList.add('next-year');
          title += ' (corresponde a siembras del año anterior o continúa al año siguiente)';
        }
        marker.title = title;
        marker.setAttribute('aria-label', title);
        cell.append(marker);
        row.append(cell);
      });
      tbody.append(row);
    });

    const plot = selectedPlot();
    realNote.hidden = true;
    if (plot) {
      const dates = plotDates(plot);
      const row = element('tr', 'cal-real-row');
      const labelCell = element('th');
      labelCell.append(element('strong', '', 'Tu registro · ' + plot.name));
      labelCell.append(element('small', 'cal-row-year', (dates.crop || 'Sin cultivo') + (dates.season ? ' · ' + dates.season : '')));
      row.append(labelCell);
      months.forEach((month, index) => {
        const cell = element('td');
        const key = realPhase(dates, index, year);
        const marker = element('span', 'cell real-cell ' + (key || 'none'));
        marker.title = month + ': ' + ({ 'real-sow': 'Siembra registrada', 'real-grow': 'Cultivo en terreno (registro)', 'real-harvest': 'Cosecha prevista registrada' }[key] || 'Sin registro');
        cell.append(marker);
        row.append(cell);
      });
      tbody.append(row);
      realNote.replaceChildren(
        element('strong', '', 'Datos registrados por ti (no provienen del calendario): '),
        document.createTextNode((dates.crop || 'Sin cultivo asignado') + (dates.variety ? ' · ' + dates.variety : '') +
          ' · siembra ' + formatDate(dates.sowing) + ' · cosecha prevista ' + formatDate(dates.harvest) +
          (dates.status ? ' · ' + dates.status : '') + '.'),
      );
      if (!dates.sowing && !dates.harvest) {
        realNote.append(element('span', 'muted', ' Aún no registras fechas para este potrero; puedes hacerlo con el evaluador de abajo.'));
      }
      realNote.hidden = false;
    }
    table.append(tbody);
    empty.hidden = rows.length > 0;
    empty.replaceChildren(element('p', '', references.length
      ? 'No hay referencias verificadas para esta combinación de zona, cultivo y variedad. Las ventanas solo se muestran cuando tienen fuente verificada.'
      : 'Aún no hay referencias agronómicas verificadas para ' + yearFilter.value + '. No se muestran ventanas de demostración como si fueran datos reales.'));
    yearNote.textContent = 'Año de referencia: ' + yearFilter.value + '. Las referencias de un año específico tienen prioridad; las ventanas sin año son recurrentes y no representan un calendario registrado por ti.';
    const keep = rows.find((reference) => reference.id === selectedReferenceId);
    showDetail(keep || rows[0] || null);
    syncUrl();
  }

  function syncUrl() {
    const params = new URLSearchParams(window.location.search);
    [['zone', zoneFilter.value], ['crop', cropFilter.value], ['variety', varietyFilter.value], ['year', yearFilter.value],
      ['potrero', plotFilter ? plotFilter.value : '']].forEach(([key, value]) => {
      if (value) params.set(key, value); else params.delete(key);
    });
    window.history.replaceState(null, '', window.location.pathname + '?' + params.toString());
  }

  // ----- Evaluadores -----
  const savePanel = document.getElementById('calendar-save');
  const savePlot = document.getElementById('save-plot');
  const saveSowing = document.getElementById('save-sowing');
  const saveHarvest = document.getElementById('save-harvest');
  const saveStatus = document.getElementById('save-status');
  const saveContext = document.getElementById('save-context');
  let lastEvaluation = null;

  function showEvaluationResult(container, result, isError) {
    container.replaceChildren();
    container.hidden = false;
    container.className = 'evaluation-result' + (isError ? ' is-error' : ' result-' + result.status);
    if (isError) {
      container.append(element('p', '', result));
      return;
    }
    container.append(element('strong', 'evaluation-status status-' + result.status, result.status_label));
    container.append(element('p', '', result.explanation));
    const facts = element('dl', 'evaluation-facts');
    const addFact = (label, value) => { if (value !== null && value !== undefined && value !== '') facts.append(element('dt', '', label), element('dd', '', value)); };
    if (result.sowing_date) addFact('Fecha de siembra', formatDate(result.sowing_date));
    addFact(result.sowing_date ? 'Fecha de cosecha propuesta' : 'Fecha propuesta', formatDate(result.proposed_date));
    if (result.elapsed_days !== undefined && result.elapsed_days !== null) addFact('Días previstos', result.elapsed_days + ' días');
    if (result.sowing_date) addFact('Duración referencial', result.expected_cycle_days ? result.expected_cycle_days + ' días' : 'No documentada');
    if (result.cycle_difference_days !== undefined && result.cycle_difference_days !== null) {
      addFact('Diferencia con el ciclo', (result.cycle_difference_days > 0 ? '+' : '') + result.cycle_difference_days + ' días');
    }
    if (result.reference_context) {
      addFact('Referencia aplicada', result.reference_context.crop + ' · ' + result.reference_context.zone + ' · ' + result.reference_context.variety +
        (result.reference_context.year ? ' · año ' + result.reference_context.year : ' · ventana recurrente'));
    }
    container.append(facts);
    if (result.source) {
      const source = element('p', 'evaluation-source');
      source.append(document.createTextNode('Fuente: ' + result.source.institution + ' · ' + result.source.document + ' · consultada ' + formatDate(result.source.consulted_at) + ' · '));
      const url = safeUrl(result.source.url);
      if (url) {
        const link = element('a', '', 'ver documento');
        link.href = url; link.target = '_blank'; link.rel = 'noopener noreferrer';
        source.append(link);
      }
      container.append(source);
    } else {
      container.append(element('p', 'evaluation-source', 'Fuente: no hay una referencia verificada aplicable.'));
    }
    container.append(element('p', 'evaluation-limits', 'Factores no evaluados: ' + result.factors_not_evaluated.join('; ') + '.'));
    container.append(element('p', 'calendar-disclaimer', result.disclaimer));
  }

  function populateSavePlots(preferred) {
    if (!savePlot) return;
    savePlot.replaceChildren(new Option('Selecciona un potrero', ''));
    plots.forEach((plot) => savePlot.add(new Option(plot.farm + ' · ' + plot.name + (plot.crop ? ' · ' + plot.crop : ''), String(plot.id))));
    if (preferred) savePlot.value = String(preferred);
  }

  function refreshSaveMode() {
    if (!savePanel || !lastEvaluation) return;
    const plot = plots.find((item) => String(item.id) === savePlot.value);
    const season = plotSeason(plot);
    const sameCrop = Boolean(season && String(season.cropId) === String(lastEvaluation.cropId));
    const updateRadio = savePanel.querySelector('[name="save-mode"][value="update_dates"]');
    const newRadio = savePanel.querySelector('[name="save-mode"][value="new"]');
    updateRadio.disabled = !sameCrop;
    if (!sameCrop) newRadio.checked = true;
    saveContext.textContent = !plot ? 'Selecciona el potrero donde registrar las fechas.'
      : sameCrop
        ? 'Temporada actual: ' + season.crop + (season.season ? ' · ' + season.season : '') + ' (' + season.statusLabel + ').'
        : season
          ? 'La temporada actual del potrero es de ' + season.crop + '. Se creará una temporada nueva de ' + lastEvaluation.cropName + ' y la anterior se conservará en el historial.'
          : 'El potrero aún no tiene temporadas. Se creará la primera temporada de ' + lastEvaluation.cropName + '.';
  }

  function openSavePanel(form, data) {
    if (!savePanel || !plots.length) return;
    const crop = form.elements.crop_id;
    lastEvaluation = {
      cropId: data.get('crop_id'),
      cropName: crop.options[crop.selectedIndex] ? crop.options[crop.selectedIndex].text : '',
      variety: data.get('variety') || '',
    };
    const picker = document.getElementById('plot-picker');
    populateSavePlots((picker && picker.value) || (plotFilter && plotFilter.value) || savePlot.value);
    if (form.dataset.evaluation === 'sowing') {
      saveSowing.value = data.get('proposed_date') || '';
    } else {
      saveSowing.value = data.get('sowing_date') || '';
      saveHarvest.value = data.get('proposed_date') || '';
    }
    saveStatus.textContent = '';
    savePanel.hidden = false;
    refreshSaveMode();
  }

  async function postJson(url, payload, token) {
    const response = await fetch(url, {
      method: 'POST',
      credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': token, Accept: 'application/json' },
      body: JSON.stringify(payload),
    });
    if (!(response.headers.get('Content-Type') || '').includes('application/json')) {
      throw new Error('Tu sesión expiró o el servidor no respondió. Recarga la página.');
    }
    const data = await response.json();
    if (!response.ok || data.ok === false || data.error) throw new Error(data.error || 'No se pudo completar la acción.');
    return data;
  }

  function csrfToken() {
    const input = document.querySelector('[name=csrfmiddlewaretoken]');
    return input ? input.value : '';
  }

  document.querySelectorAll('.calendar-evaluator').forEach((form) => {
    form.elements.crop_id.addEventListener('change', () => updateEvaluatorVarieties(form));
    form.elements.zone_id.addEventListener('change', () => updateEvaluatorVarieties(form));
    form.addEventListener('submit', async (event) => {
      event.preventDefault();
      const output = form.querySelector('.evaluation-result');
      const data = new FormData(form);
      const payload = {
        evaluation: form.dataset.evaluation,
        crop_id: data.get('crop_id'),
        zone_id: data.get('zone_id'),
        variety: data.get('variety'),
        proposed_date: data.get('proposed_date'),
        sowing_date: data.get('sowing_date'),
      };
      const button = form.querySelector('button[type=submit]');
      button.disabled = true;
      try {
        const response = await fetch(form.dataset.endpoint, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken() },
          body: JSON.stringify(payload),
          credentials: 'same-origin',
        });
        const result = await response.json();
        if (!response.ok) throw new Error(result.error || 'No se pudo evaluar la fecha.');
        showEvaluationResult(output, result, false);
        openSavePanel(form, data);
      } catch (error) {
        showEvaluationResult(output, error.message || 'No se pudo conectar con el evaluador.', true);
      } finally {
        button.disabled = false;
      }
    });
  });

  if (savePanel) {
    savePlot.addEventListener('change', refreshSaveMode);
    document.getElementById('save-dates').addEventListener('click', async () => {
      const plot = plots.find((item) => String(item.id) === savePlot.value);
      if (!plot || !lastEvaluation) {
        saveStatus.textContent = 'Selecciona un potrero y evalúa una fecha primero.';
        return;
      }
      if (!saveSowing.value && !saveHarvest.value) {
        saveStatus.textContent = 'Indica al menos una fecha para registrar.';
        return;
      }
      const mode = savePanel.querySelector('[name="save-mode"]:checked').value;
      const season = plotSeason(plot);
      const now = new Date();
      const today = now.getFullYear() + '-' + String(now.getMonth() + 1).padStart(2, '0') + '-' + String(now.getDate()).padStart(2, '0');
      const button = document.getElementById('save-dates');
      button.disabled = true;
      saveStatus.textContent = 'Guardando…';
      try {
        const data = await postJson(plot.assignUrl, {
          mode,
          season_id: mode === 'update_dates' && season ? season.id : null,
          crop_id: lastEvaluation.cropId,
          variety: lastEvaluation.variety,
          sowing_date: saveSowing.value || null,
          harvest_date: saveHarvest.value || null,
          status: mode === 'update_dates' && season ? season.status : (saveSowing.value && saveSowing.value <= today ? 'sown' : 'planned'),
          notes: 'Fechas registradas desde el calendario agronómico.',
        }, csrfToken());
        const updated = data.plot;
        plots = plots.map((item) => String(item.id) === String(plot.id) ? {
          ...item,
          crop: updated.crop,
          cropId: updated.cropId,
          variety: updated.variety,
          sowingDate: updated.sowing,
          harvestDate: updated.harvest,
          seasons: updated.seasons,
          status: updated.status,
        } : item);
        saveStatus.textContent = data.message;
        if (plotFilter) plotFilter.value = String(plot.id);
        render();
        refreshSaveMode();
      } catch (error) {
        saveStatus.textContent = error.message;
      } finally {
        button.disabled = false;
      }
    });
  }

  // ----- Potreros -----
  const plotPicker = document.getElementById('plot-picker');
  if (plotPicker) {
    const seasonPicker = document.getElementById('season-picker');
    function applyPlot(plot, season) {
      document.querySelectorAll('.calendar-evaluator').forEach((form) => {
        const cropId = season ? season.cropId : plot.cropId;
        const variety = season ? season.variety : plot.variety;
        if (cropId) form.elements.crop_id.value = String(cropId);
        if (plot.zoneId) form.elements.zone_id.value = String(plot.zoneId);
        updateEvaluatorVarieties(form, variety || '');
        const sowingDate = season ? season.sowingDate : plot.sowingDate;
        const harvestDate = season ? season.harvestDate : plot.harvestDate;
        if (form.dataset.evaluation === 'sowing' && sowingDate) form.elements.proposed_date.value = sowingDate;
        if (form.dataset.evaluation === 'harvest') {
          if (sowingDate) form.elements.sowing_date.value = sowingDate;
          if (harvestDate) form.elements.proposed_date.value = harvestDate;
        }
      });
    }
    plotPicker.addEventListener('change', () => {
      const plot = plots.find((item) => String(item.id) === plotPicker.value);
      seasonPicker.replaceChildren(new Option('Usar datos actuales del potrero', ''));
      if (!plot) { seasonPicker.disabled = true; return; }
      (plot.seasons || []).forEach((season) => {
        seasonPicker.add(new Option((season.season ? season.season + ' · ' : '') + season.crop +
          (season.variety ? ' · ' + season.variety : '') + ' · ' + season.statusLabel, String(season.id)));
      });
      seasonPicker.disabled = false;
      applyPlot(plot, null);
      if (!plot.zoneId) {
        document.querySelectorAll('.calendar-evaluator .evaluation-result').forEach((box) => {
          box.hidden = false;
          box.className = 'evaluation-result';
          box.replaceChildren(element('p', '', 'El predio de este potrero no tiene zona agrícola asignada; selecciónala manualmente o edítala en el predio.'));
        });
      }
    });
    seasonPicker.addEventListener('change', () => {
      const plot = plots.find((item) => String(item.id) === plotPicker.value);
      if (!plot) return;
      applyPlot(plot, (plot.seasons || []).find((item) => String(item.id) === seasonPicker.value) || null);
    });
  }

  // ----- Filtros -----
  cropFilter.addEventListener('change', () => { updateFilterVarieties(); render(); });
  varietyFilter.addEventListener('change', render);
  zoneFilter.addEventListener('change', () => { updateFilterVarieties(); render(); });
  yearFilter.addEventListener('change', () => {
    syncUrl();
    // El año cambia qué referencias aplican: se consulta nuevamente al servidor.
    document.getElementById('calendar-filters').submit();
  });
  if (plotFilter) {
    plotFilter.addEventListener('change', () => {
      const plot = selectedPlot();
      if (plot) {
        const dates = plotDates(plot);
        const season = plotSeason(plot);
        const cropId = season ? season.cropId : plot.cropId;
        if (cropId) cropFilter.value = String(cropId);
        if (plot.zoneId) zoneFilter.value = String(plot.zoneId);
        updateFilterVarieties(dates.variety && varietiesFor(cropFilter.value, zoneFilter.value).includes(dates.variety) ? dates.variety : '*');
      }
      render();
    });
  }

  updateFilterVarieties(varietyFilter.dataset.selected || '*');
  populateSavePlots();
  if (plotFilter && plotFilter.value) plotFilter.dispatchEvent(new Event('change'));
  else render();
})();
