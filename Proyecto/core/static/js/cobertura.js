(function () {
  const params = new URLSearchParams(location.search);
  const state = AgroService.getState();
  const plotSelect = document.getElementById('plot');
  const cropSelect = document.getElementById('crop');
  const insumoSelect = document.getElementById('insumo');
  const targetSelect = document.getElementById('target');
  const targetField = document.getElementById('target-field');
  const areaInput = document.getElementById('area');
  const doseInput = document.getElementById('dose');
  const stockInput = document.getElementById('stock');
  const flow = document.querySelector('[data-decision-flow]');

  function populate(select, values, label, placeholder) {
    select.replaceChildren(new Option(placeholder, ''));
    values.forEach((item) => select.add(new Option(label(item), item.id)));
  }

  populate(plotSelect, state.plots, (plot) => {
    const predio = state.predios.find((item) => item.id === plot.predio);
    return (predio ? predio.name + ' · ' : '') + plot.name + ' · ' + AgroService.fmt(plot.areaHa, 2) + ' ha';
  }, 'Selecciona un potrero');
  populate(cropSelect, AgroService.getCultivos(), (name) => name, 'Selecciona un cultivo');
  const pesticideTypes = new Set(['herbicida', 'fungicida', 'insecticida', 'acaricida', 'plaguicida']);
  const isPesticide = (item) => pesticideTypes.has(String(item.type || '').toLocaleLowerCase('es-CL'));
  let availableInsumos = [];
  populate(insumoSelect, availableInsumos, (item) => item.name + ' · ' + item.type, 'Selecciona un insumo');

  function refreshInsumos() {
    const previous = insumoSelect.value;
    availableInsumos = AgroService.getInsumos(true).filter((item) => {
      return (!isPesticide(item) || (
        item.verifiedUse === true &&
        Array.isArray(item.authorizedCrops) &&
        item.authorizedCrops.includes(cropSelect.value) &&
        Array.isArray(item.controlTargets) &&
        item.controlTargets.length > 0
      )) && (!item.crop || item.crop === cropSelect.value);
    });
    populate(insumoSelect, availableInsumos, (item) => item.name + ' · ' + item.type, 'Selecciona un insumo');
    if (availableInsumos.some((item) => String(item.id) === previous)) insumoSelect.value = previous;
    syncInsumo();
  }

  function selectedPlot() {
    return state.plots.find((item) => item.id === plotSelect.value);
  }

  function selectedInsumo() {
    return availableInsumos.find((item) => AgroService.sameId(item.id, insumoSelect.value));
  }

  function syncPlot() {
    const plot = selectedPlot();
    if (!plot) {
      areaInput.value = '';
      document.getElementById('plot-help').textContent = 'Selecciona un potrero con superficie registrada.';
      return;
    }
    areaInput.value = plot.areaHa || '';
    areaInput.max = plot.areaHa || '';
    areaInput.readOnly = true;
    document.querySelector('[name="surface-scope"][value="total"]').checked = true;
    document.querySelector('[name="surface-scope"][value="total"]').checked = true;
    if (plot.crop && Array.from(cropSelect.options).some((option) => option.value === plot.crop)) {
      cropSelect.value = plot.crop;
    } else {
      cropSelect.value = '';
    }
    document.getElementById('plot-help').textContent =
      plot.name + ': ' + AgroService.fmt(plot.areaHa, 3) + ' ha registradas.';
    refreshInsumos();
  }

  function syncInsumo() {
    const insumo = selectedInsumo();
    doseInput.value = insumo?.dose ?? '';
    document.getElementById('stock-unit').textContent = String(insumo?.unit || '').replace(/\/ha$/i, '') || 'registrada';
    const verifiedPesticide = Boolean(insumo && isPesticide(insumo) && insumo.verifiedUse === true);
    doseInput.readOnly = verifiedPesticide;
    document.getElementById('insumo-help').textContent = insumo?.dose && insumo.doseVerified
      ? 'Dosis documentada del catálogo: ' + AgroService.fmt(insumo.dose) + ' ' + insumo.unit + '.'
      : 'El catálogo no tiene una dosis registrada para este insumo.';
    targetField.hidden = !isPesticide(insumo || {});
    targetSelect.required = isPesticide(insumo || {});
    const targets = insumo?.verifiedUse && Array.isArray(insumo.controlTargets) ? insumo.controlTargets : [];
    const previousTarget = targetSelect.value;
    targetSelect.replaceChildren(new Option('Selecciona un objetivo', ''));
    targets.forEach((target) => targetSelect.add(new Option(target, target)));
    if (targets.includes(previousTarget)) targetSelect.value = previousTarget;
  }

  async function renderResult(save) {
    const plot = selectedPlot();
    const insumo = selectedInsumo();
    const area = AgroService.positive(areaInput.value);
    const dose = AgroService.positive(doseInput.value);
    const stock = AgroService.nonNegative(stockInput.value);
    const error = document.getElementById('cover-config-error');
    error.textContent = '';

    if (!plot || !insumo || area === null || dose === null || stock === null) {
      error.textContent = 'Revisa el potrero, insumo, superficie, dosis y cantidad disponible. La superficie y dosis deben ser mayores a 0.';
      return false;
    }
    if (area > plot.areaHa) {
      error.textContent = 'La superficie no puede superar las ' + AgroService.fmt(plot.areaHa, 3) + ' ha registradas en este potrero.';
      return false;
    }
    if (!cropSelect.value || (insumo.crop && insumo.crop !== cropSelect.value)) {
      error.textContent = 'El producto del catálogo no corresponde al cultivo seleccionado.';
      return false;
    }
    if (isPesticide(insumo) && (
      insumo.verifiedUse !== true ||
      !insumo.authorizedCrops?.includes(cropSelect.value) ||
      !insumo.controlTargets?.includes(targetSelect.value)
    )) {
      error.textContent = 'Selecciona un objetivo de control autorizado para el producto y cultivo.';
      return false;
    }

    let result;
    try {
      result = await AgroService.calculateOnServer(flow.dataset.calculateUrl, {
        operation: 'coverage',
        calculation_type: 'coverage',
        plot_id: plot.id,
        crop: cropSelect.value,
        product_id: insumo.id,
        target: targetSelect.value,
        area,
        dose,
        unit: insumo.unit || '',
        stock
      });
    } catch (requestError) {
      error.textContent = requestError.message;
      return false;
    }
    const serverDose = result.dose;
    const unit = result.unit || '';
    const displayUnit = unit ? ' ' + AgroService.escape(unit) : '';
    const doseUnit = result.dose_unit?.endsWith('/ha')
      ? result.dose_unit
      : unit ? unit + '/ha' : 'unidad/ha';
    const percent = Math.max(0, Math.min(100, result.percent));
    const filled = Math.round(percent);
    document.getElementById('cover-plot-name').textContent = plot.name + ' · ' + AgroService.fmt(area, 2) + ' ha';
    document.getElementById('cover-label').textContent = AgroService.fmt(percent, 0) + '% cubierto';
    document.getElementById('field-fill').style.width = percent + '%';
    document.getElementById('field-caption').textContent = AgroService.fmt(result.coveredHa, 2) + ' de ' + AgroService.fmt(area, 2) + ' ha';
    document.getElementById('cover-grid').innerHTML = Array.from({ length: 100 }, (_, index) =>
      '<span class="' + (index < filled ? 'ok' : 'miss') + '"></span>'
    ).join('');
    document.getElementById('cover-text').textContent = result.missingHa > 0
      ? 'Con lo disponible cubres ' + AgroService.fmt(result.coveredHa, 2) + ' ha y quedan ' +
        AgroService.fmt(result.missingHa, 2) + ' ha sin cubrir.'
      : 'La cantidad disponible alcanza para cubrir la superficie seleccionada (' + AgroService.fmt(area, 2) + ' ha).';
    document.getElementById('cover-numbers').innerHTML =
      '<div class="metric"><span>Cubierto</span><strong>' + AgroService.fmt(result.coveredHa, 2) + ' ha</strong></div>' +
      '<div class="metric"><span>Sin cubrir</span><strong>' + AgroService.fmt(result.missingHa, 2) + ' ha</strong></div>' +
      '<div class="metric"><span>Necesario en total</span><strong>' + AgroService.fmt(result.needed) + displayUnit + '</strong></div>' +
      '<div class="metric"><span>Disponible</span><strong>' + AgroService.fmt(stock) + displayUnit + '</strong></div>' +
      '<div class="metric"><span>Insumo</span><strong>' + AgroService.escape(insumo.name) + '</strong></div>' +
      '<div class="metric"><span>Dosis utilizada</span><strong>' + AgroService.fmt(serverDose) + ' ' + AgroService.escape(doseUnit) + '</strong></div>' +
      (result.missingQty > 0
        ? '<div class="metric"><span>Faltante</span><strong>' + AgroService.fmt(result.missingQty) + displayUnit + '</strong></div>'
        : '<div class="metric"><span>Disponible después del cálculo</span><strong>' + AgroService.fmt(result.surplus) + displayUnit + '</strong></div>');
    document.getElementById('cover-advice').textContent = result.missingQty > 0
      ? 'El cálculo indica un faltante de ' + AgroService.fmt(result.missingQty) + (unit ? ' ' + unit : '') + '. Verifica la dosis antes de aplicar.'
      : 'El cálculo indica un excedente de ' + AgroService.fmt(result.surplus) + (unit ? ' ' + unit : '') + '.';
    if (!unit) {
      document.getElementById('cover-advice').textContent += ' El catálogo no especifica unidad; confirma la unidad del producto.';
    }
    document.getElementById('cover-advice').textContent += ' Simulación: no modifica inventario ni reserva existencias.';
    if (insumo.verifiedUse) {
      const warnings = [insumo.restrictions, insumo.pollinatorWarning, insumo.environmentalPrecautions,
        insumo.preharvestInterval ? 'Período de carencia: ' + insumo.preharvestInterval : '',
        insumo.reentryInterval ? 'Tiempo de reingreso: ' + insumo.reentryInterval : '']
        .filter(Boolean);
      if (warnings.length) document.getElementById('cover-advice').textContent += ' Advertencias: ' + warnings.join(' ');
    }

    if (save) {
      AgroService.saveResult('cobertura', {
        ...result, plot: plot.name, insumo: insumo.name, crop: cropSelect.value,
        area, dose:serverDose, stock, unit,
        date: new Date().toISOString()
      });
    }
    return true;
  }

  if (params.get('plot')) plotSelect.value = params.get('plot');
  if (params.get('insumo')) insumoSelect.value = params.get('insumo');
  plotSelect.addEventListener('change', () => {
    syncPlot();
    syncInsumo();
  });
  cropSelect.addEventListener('change', () => {
    refreshInsumos();
  });
  insumoSelect.addEventListener('change', () => {
    targetSelect.value = '';
    syncInsumo();
  });
  document.querySelectorAll('[name="surface-scope"]').forEach((radio) => {
    radio.addEventListener('change', () => {
      const fullArea = radio.value === 'total' && radio.checked;
      areaInput.readOnly = fullArea;
      if (fullArea) areaInput.value = selectedPlot()?.areaHa || '';
      else areaInput.focus();
    });
  });
  document.getElementById('cover-form').addEventListener('submit', async (event) => {
    event.preventDefault();
    const submitButton = event.submitter;
    if (submitButton) submitButton.disabled = true;
    try {
      if (await renderResult(true)) {
        flow.dispatchEvent(new CustomEvent('decision:show-step', { detail: { step: 3 } }));
      }
    } finally {
      if (submitButton) submitButton.disabled = false;
    }
  });
  flow.addEventListener('decision:new', () => {
    syncPlot();
    syncInsumo();
    document.getElementById('cover-config-error').textContent = '';
    document.getElementById('cover-label').textContent = '—';
    document.getElementById('field-fill').style.width = '0';
    document.getElementById('field-caption').textContent = '';
    document.getElementById('cover-grid').replaceChildren();
    document.getElementById('cover-numbers').replaceChildren();
    document.getElementById('cover-text').textContent = '';
    document.getElementById('cover-advice').textContent = '';
  });

  if (params.get('plot')) plotSelect.value = params.get('plot');
  if (params.get('insumo')) insumoSelect.value = params.get('insumo');
  const requestedInsumo = availableInsumos.find((item) => AgroService.sameId(item.id, params.get('insumo')));
  if (requestedInsumo?.crop && Array.from(cropSelect.options).some((option) => option.value === requestedInsumo.crop)) {
    cropSelect.value = requestedInsumo.crop;
  }
  syncPlot();
  refreshInsumos();
  if (params.get('insumo')) insumoSelect.value = params.get('insumo');
  syncInsumo();
})();
