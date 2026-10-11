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
  const zones = (state.zonas || []).map((zone) => typeof zone === 'string' ? zone : zone.name).filter(Boolean);
  populate(document.getElementById('zone'), zones, (name) => name, 'Sin zona seleccionada');

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
    syncYieldReference();
  }

  function syncYieldReference() {
    const reference = window.AGRO_CATALOG?.yieldReferences?.[cropSelect.value];
    const documented = reference && reference.rate && reference.source && reference.url && reference.verifiedAt;
    yieldInput.value = documented ? reference.rate : '';
    yieldSourceInput.value = documented ? reference.source : '';
    document.getElementById('yield-source-help').textContent = documented
      ? 'Referencia del catálogo: ' + reference.source + ' · verificada ' + reference.verifiedAt + '.'
      : 'No se ha registrado un rendimiento documentado para este cultivo. Ingresa un valor respaldado por tu fuente.';
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
        plot_id: plot.id,
        crop,
        area,
        rate,
        source: yieldSource
      });
    } catch (requestError) {
      errorBox.textContent = requestError.message;
      return false;
    }
    const variety = document.getElementById('variety').value.trim();
    const zone = document.getElementById('zone').value;
    const season = document.getElementById('season').value;
    const reference = window.AGRO_CATALOG?.yieldReferences?.[cropSelect.value];
    const isDocumented = Boolean(reference && reference.rate === rate && reference.source && reference.url && reference.verifiedAt);
    const sourceSummary = yieldSource || (isDocumented ? reference.source + ' · ' + reference.verifiedAt : 'Ingresado por usuario; sin fuente documentada');
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
