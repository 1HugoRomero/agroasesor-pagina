(function () {
  const params = new URLSearchParams(location.search);
  const state = AgroService.getState();
  const plotSelect = document.getElementById('plot');
  const cropSelect = document.getElementById('crop');
  const areaInput = document.getElementById('area');
  const yieldInput = document.getElementById('yield-rate');
  const yieldSourceInput = document.getElementById('yield-source');
  const flow = document.querySelector('[data-decision-flow]');
  const errorBox = document.getElementById('predict-error');

  function populate(select, values, label, placeholder) {
    select.replaceChildren(new Option(placeholder, ''));
    values.forEach((value) => select.add(new Option(label(value), value.id ?? value)));
  }

  populate(plotSelect, state.plots, (plot) => {
    const predio = state.predios.find((item) => item.id === plot.predio);
    return (predio ? predio.name + ' · ' : '') + plot.name;
  }, 'Selecciona un potrero');
  populate(cropSelect, AgroService.getCultivos(), (name) => name, 'Selecciona un cultivo');
  const zones = (state.zonas || []).map((zone) => typeof zone === 'string'
    ? {id:zone, name:zone}
    : zone).filter((zone) => zone && zone.name);
  const zoneSelect = document.getElementById('zone');
  populate(zoneSelect, zones, (zone) => zone.name, 'Sin zona seleccionada');

  function selectedPlot() {
    return state.plots.find((item) => item.id === plotSelect.value);
  }

  function syncPlot() {
    const plot = selectedPlot();
    errorBox.textContent = '';
    if (!plot) {
      areaInput.value = '';
      document.getElementById('variety').value = '';
      return;
    }
    if (plot.crop && Array.from(cropSelect.options).some((option) => option.value === plot.crop)) {
      cropSelect.value = plot.crop;
    } else {
      cropSelect.value = '';
    }
    areaInput.value = plot.areaHa || '';
    areaInput.max = plot.areaHa || '';
    areaInput.readOnly = true;
    document.querySelector('[name="surface-scope"][value="total"]').checked = true;
    document.getElementById('variety').value = plot.variety || '';
    if (plot.zoneId && Array.from(zoneSelect.options).some((option) => option.value === String(plot.zoneId))) {
      zoneSelect.value = String(plot.zoneId);
    }
    syncYieldReference();
  }

  function syncYieldReference() {
    const plot = selectedPlot();
    const candidates = (window.AGRO_CATALOG?.regionalYieldReferences || []).filter((item) =>
      item.crop === cropSelect.value && plot && String(item.zoneId) === String(plot.zoneId));
    const variety = document.getElementById('variety').value.trim();
    const reference = candidates.find((item) =>
      item.variety && item.variety.toLocaleLowerCase('es-CL') === variety.toLocaleLowerCase('es-CL'))
      || candidates.find((item) => !item.variety);
    const documented = Boolean(reference);
    yieldInput.value = documented ? reference.rate : '';
    yieldSourceInput.value = documented ? reference.source : '';
    document.getElementById('yield-source-help').textContent = documented
      ? 'Referencia verificada para ' + reference.zone + (reference.variety ? ' · ' + reference.variety : '') +
        ': ' + reference.source + ' · ' + reference.verifiedAt + '. El servidor utilizará esta tasa.'
      : 'No hay rendimiento verificado para la zona y variedad del potrero. Ingresa un valor con su fuente técnica.';
  }

  async function estimate(save) {
    const plot = selectedPlot();
    const crop = cropSelect.value;
    const area = AgroService.positive(areaInput.value);
    const rate = AgroService.positive(yieldInput.value);
    errorBox.textContent = '';
    if (!plot || !crop || area === null || rate === null) {
      errorBox.textContent = 'Selecciona potrero y cultivo, e ingresa superficie y rendimiento mayores a 0.';
      return false;
    }
    if (area > plot.areaHa) {
      errorBox.textContent = 'La superficie no puede superar las ' + AgroService.fmt(plot.areaHa, 3) + ' ha registradas en el potrero.';
      return false;
    }

    let result;
    const yieldSource = yieldSourceInput.value.trim();
    try {
      result = await AgroService.calculateOnServer(flow.dataset.calculateUrl, {
        operation: 'yield',
        calculation_type: 'rendimiento',
        plot_id: plot.id,
        crop,
        area,
        rate,
        source: yieldSource,
        variety: document.getElementById('variety').value.trim()
      });
    } catch (requestError) {
      errorBox.textContent = requestError.message;
      return false;
    }
    const variety = document.getElementById('variety').value.trim();
    const zone = zones.find((item) => String(item.id) === zoneSelect.value)?.name || '';
    const season = document.getElementById('season').value;
    const isDocumented = result.source_verified === true;
    const sourceSummary = result.source + (result.source_date ? ' · ' + result.source_date : '');
    if (save) AgroService.saveResult('predictor', {
      crop, area, plot: plot.name, variety, zone, season, yieldSource: sourceSummary,
      yieldVerified: isDocumented, ...result, date: new Date().toISOString()
    });
    document.getElementById('predict-result').innerHTML =
      '<p class="result-kicker">Producción de referencia · ' + AgroService.escape(crop) + '</p>' +
      '<p class="decision-result-value">' + AgroService.fmt(result.production, 1) + ' t</p>' +
      '<div class="decision-result-summary">' +
      '<div class="metric"><span>Rendimiento de referencia</span><strong>' + AgroService.fmt(result.rate, 1) + ' ton/ha</strong></div>' +
      '<div class="metric"><span>Superficie utilizada</span><strong>' + AgroService.fmt(area, 2) + ' ha</strong></div>' +
      '<div class="metric"><span>Potrero</span><strong>' + AgroService.escape(plot.name) + '</strong></div>' +
      '<div class="metric"><span>Temporada</span><strong>' + AgroService.escape(season) + '</strong></div>' +
      (variety ? '<div class="metric"><span>Variedad</span><strong>' + AgroService.escape(variety) + '</strong></div>' : '') +
      (zone ? '<div class="metric"><span>Zona</span><strong>' + AgroService.escape(zone) + '</strong></div>' : '') +
      '</div><p class="muted">Estimación matemática: rendimiento registrado × superficie. No incorpora clima, suelo ni manejo real.</p>' +
      '<p class="muted">Fuente del rendimiento: ' + AgroService.escape(sourceSummary) + '</p>' +
      '<p class="alert decision-safety">' + AgroService.escape(window.AGRO_MOCK.disclaimer) + '</p>';
    return true;
  }

  if (params.get('plot')) plotSelect.value = params.get('plot');
  plotSelect.addEventListener('change', syncPlot);
  cropSelect.addEventListener('change', syncYieldReference);
  zoneSelect.addEventListener('change', syncYieldReference);
  document.getElementById('variety').addEventListener('input', syncYieldReference);
  document.querySelectorAll('[name="surface-scope"]').forEach((radio) => {
    radio.addEventListener('change', () => {
      const fullArea = radio.value === 'total' && radio.checked;
      areaInput.readOnly = fullArea;
      if (fullArea) areaInput.value = selectedPlot()?.areaHa || '';
      else areaInput.focus();
    });
  });
  document.getElementById('predict-form').addEventListener('submit', async (event) => {
    event.preventDefault();
    const submitButton = event.submitter;
    if (submitButton) submitButton.disabled = true;
    try {
      if (await estimate(true)) {
        flow.dispatchEvent(new CustomEvent('decision:show-step', { detail: { step: 3 } }));
      }
    } finally {
      if (submitButton) submitButton.disabled = false;
    }
  });
  flow.addEventListener('decision:new', () => {
    syncPlot();
    document.getElementById('predict-result').replaceChildren();
    errorBox.textContent = '';
  });
  syncPlot();
})();
