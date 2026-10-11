(function () {
  const params = new URLSearchParams(location.search);
  const state = AgroService.getState();
  const flow = document.querySelector('[data-decision-flow]');
  const plotSelect = document.getElementById('plot');
  const cropSelect = document.getElementById('crop');
  const insumoSelect = document.getElementById('insumo');
  const targetSelect = document.getElementById('target');
  const areaInput = document.getElementById('area');
  const doseInput = document.getElementById('dose');
  const unitInput = document.getElementById('unit');
  const errorBox = document.getElementById('calc-error');
  const phytosanitaryTypes = new Set(['herbicida', 'fungicida', 'insecticida', 'acaricida', 'plaguicida']);
  let mode = 'semillas';

  function typeOf(item) {
    return String(item.type || '').trim().toLocaleLowerCase('es-CL');
  }

  function populate(select, values, label, value, placeholder) {
    select.replaceChildren(new Option(placeholder, ''));
    values.forEach((item) => select.add(new Option(label(item), String(value(item)))));
  }

  populate(plotSelect, state.plots, (plot) => {
    const predio = state.predios.find((item) => item.id === plot.predio);
    return (predio ? predio.name + ' · ' : '') + plot.name;
  }, (plot) => plot.id, 'Selecciona un potrero');
  populate(cropSelect, AgroService.getCultivos(), (name) => name, (name) => name, 'Selecciona un cultivo');

  function selectedPlot() {
    return state.plots.find((item) => item.id === plotSelect.value);
  }

  function selectedInsumo() {
    return AgroService.getInsumos(true).find((item) => AgroService.sameId(item.id, insumoSelect.value));
  }

  function isProtectionProduct(item) {
    return phytosanitaryTypes.has(typeOf(item));
  }

  function validProtectionProduct(item, crop, target) {
    return item.verifiedUse === true &&
      isProtectionProduct(item) &&
      item.crop === crop &&
      Array.isArray(item.authorizedCrops) &&
      item.authorizedCrops.includes(crop) &&
      Array.isArray(item.controlTargets) &&
      item.controlTargets.includes(target) &&
      ['kg/ha', 'g/ha', 'L/ha', 'mL/ha'].includes(item.unit);
  }

  function maxArea() {
    const plot = selectedPlot();
    return plot?.areaHa || state.predios.find((item) => item.id === plot?.predio)?.area || 0;
  }

  function protectionTargets() {
    const crop = cropSelect.value;
    return [...new Set(AgroService.getInsumos(true)
      .filter((item) => item.crop === crop && item.verifiedUse === true && isProtectionProduct(item))
      .flatMap((item) => Array.isArray(item.controlTargets) ? item.controlTargets : []))];
  }

  function refreshTargetOptions() {
    const current = targetSelect.value;
    populate(targetSelect, protectionTargets(), (item) => item, (item) => item, 'Selecciona un objetivo');
    if (protectionTargets().includes(current)) targetSelect.value = current;
  }

  function refreshInsumoOptions(preferredId) {
    if (mode === 'semillas') return;
    const items = AgroService.getInsumos(true);
    let available;
    if (mode === 'proteccion') {
      const target = targetSelect.value;
      available = items.filter((item) => validProtectionProduct(item, cropSelect.value, target));
    } else {
      available = items.filter((item) => typeOf(item) !== 'semilla' && !isProtectionProduct(item) &&
        (!item.crop || item.crop === cropSelect.value));
    }
    populate(insumoSelect, available, (item) => {
        const dose = item.dose === null || item.dose === undefined ? 'sin dosis registrada' :
          AgroService.fmt(item.dose) + ' ' + (item.unit || 'unidad') +
          (mode === 'proteccion' || String(item.unit || '').endsWith('/ha') ? '' : '/ha');
      return item.name + ' · ' + dose;
    }, (item) => item.id, 'Selecciona un producto');
    if (mode === 'insumos') insumoSelect.add(new Option('Otro producto (ingresar manualmente)', 'manual'));
    if (preferredId && Array.from(insumoSelect.options).some((option) => option.value === String(preferredId))) {
      insumoSelect.value = String(preferredId);
    }
  }

  function syncProduct() {
    const product = selectedInsumo();
    const manual = mode === 'insumos' && insumoSelect.value === 'manual';
    document.getElementById('custom-product-field').hidden = !manual;
    const help = document.getElementById('insumo-help');
    if (manual) {
      doseInput.value = '';
      unitInput.value = '';
      help.textContent = 'Ingresa los datos respaldados por tu fuente técnica. No se agregará al inventario.';
    } else if (!product) {
      doseInput.value = '';
      unitInput.value = '';
      help.textContent = mode === 'proteccion'
        ? 'No hay productos verificados para el cultivo y objetivo seleccionados.'
        : 'Elige un insumo registrado o ingreso manual.';
    } else {
      doseInput.value = product.dose ?? '';
      unitInput.value = String(product.unit || '').replace(/\/ha$/i, '');
      help.textContent = product.doseVerified
        ? 'Dosis registrada y verificada: ' + AgroService.fmt(product.dose) + ' ' + product.unit + '. Fuente: ' + (product.doseSource || product.sourceName) + '.'
        : 'Dosis sin verificar en el catálogo. Confirma una fuente técnica antes de usarla.';
    }
    const readonlyProtection = mode === 'proteccion';
    doseInput.readOnly = readonlyProtection;
    unitInput.readOnly = readonlyProtection;
  }

  function syncSeedInfo() {
    const seed = AgroService.getSemilla(cropSelect.value);
    const sourced = Boolean(seed?.densitySource && seed?.densityUrl && seed?.densityVerifiedAt);
    doseInput.value = sourced ? seed.density : '';
    unitInput.value = sourced ? seed.unit || '' : '';
    document.getElementById('dose-help').textContent = sourced
      ? 'Densidad documentada: ' + seed.densitySource + ' · verificada ' + seed.densityVerifiedAt + '.'
      : 'Sin fuente técnica documentada en el catálogo. Confirma la dosis por hectárea antes de usarla.';
    doseInput.readOnly = false;
    unitInput.readOnly = false;
  }

  function syncCropDefaults(preferredId) {
    if (mode === 'semillas') {
      syncSeedInfo();
      return;
    }
    if (mode === 'proteccion') refreshTargetOptions();
    refreshInsumoOptions(preferredId);
    syncProduct();
  }

  function syncPlot() {
    const plot = selectedPlot();
    if (!plot) {
      areaInput.value = '';
      areaInput.max = '';
      document.getElementById('plot-help').textContent = 'La superficie se recupera desde el potrero.';
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
    document.getElementById('plot-help').textContent =
      'Superficie registrada: ' + AgroService.fmt(maxArea(), 3) + ' ha.';
    syncCropDefaults(params.get('insumo'));
  }

  function setMode(next) {
    mode = ['semillas', 'insumos', 'proteccion'].includes(next) ? next : 'semillas';
    const isSeed = mode === 'semillas';
    const isProtection = mode === 'proteccion';
    document.querySelectorAll('#modes button').forEach((button) => {
      const active = button.dataset.mode === mode;
      button.classList.toggle('is-active', active);
      button.setAttribute('aria-pressed', String(active));
    });
    document.getElementById('insumo-field').hidden = isSeed;
    document.getElementById('target-field').hidden = !isProtection;
    document.getElementById('protection-warning').hidden = !isProtection;
    document.getElementById('dose-note').hidden = isProtection;
    insumoSelect.required = !isSeed;
    targetSelect.required = isProtection;
    document.getElementById('dose-label').textContent = isSeed
      ? 'Dosis o densidad por hectárea'
      : isProtection ? 'Dosis verificada por hectárea' : 'Dosis por hectárea';
    document.getElementById('dose-help').textContent = isProtection
      ? 'La dosis de etiqueta verificada no se puede editar en este cálculo.'
      : 'Usa datos documentados o ingresados por tu fuente técnica.';
    if (!isSeed) refreshInsumoOptions(params.get('insumo'));
    syncCropDefaults(params.get('insumo'));
    errorBox.textContent = '';
  }

  async function renderResult(save) {
    const area = AgroService.positive(areaInput.value);
    let dose = AgroService.positive(doseInput.value);
    const unit = unitInput.value.trim();
    const max = maxArea();
    const plot = selectedPlot();
    const crop = cropSelect.value;
    const product = selectedInsumo();
    const manual = mode === 'insumos' && insumoSelect.value === 'manual';
    const productName = manual
      ? document.getElementById('custom-product').value.trim()
      : product?.name || '';
    errorBox.textContent = '';

    if (!plot || !crop || area === null || dose === null || !unit) {
      errorBox.textContent = 'Revisa el potrero, cultivo, superficie, dosis y unidad. La superficie y dosis deben ser mayores a 0.';
      return false;
    }
    if (max && area > max) {
      errorBox.textContent = 'La superficie no puede ser mayor a la disponible (' + AgroService.fmt(max, 3) + ' ha).';
      return false;
    }
    if (mode !== 'semillas' && (!productName || (!manual && !product))) {
      errorBox.textContent = 'Selecciona un producto registrado o indica el nombre del producto manual.';
      return false;
    }
    if (mode === 'proteccion' && (!product || !validProtectionProduct(product, crop, targetSelect.value))) {
      errorBox.textContent = 'No hay un producto con uso, cultivo, objetivo y dosis por hectárea verificados para esta selección.';
      return false;
    }
    let serverResult;
    try {
      serverResult = await AgroService.calculateOnServer(flow.dataset.calculateUrl, {
        operation: 'dose',
        plot_id: plot.id,
        area,
        dose,
        unit,
        crop,
        product_id: product?.id || null,
        target: targetSelect.value
      });
    } catch (error) {
      errorBox.textContent = error.message;
      return false;
    }
    const amountValue = serverResult.amount;
    const outputUnit = AgroService.escape(serverResult.unit || unit);
    dose = serverResult.dose;
    const actualDoseUnit = serverResult.dose_unit || (mode === 'proteccion' ? product.unit : unit + '/ha');
    const safePlot = AgroService.escape(plot.name);
    const safeCrop = AgroService.escape(crop);
    const safeProduct = AgroService.escape(productName);
    const doseUnit = actualDoseUnit;
    const verified = mode === 'proteccion' || (mode !== 'semillas' && product?.doseVerified === true);
    const doseNotice = verified
      ? (product?.doseSource || product?.sourceName || '')
      : 'Dato de entrada sin verificación técnica en el catálogo.';
    const payload = {
      mode: mode === 'proteccion' ? 'insumos' : mode, kind: mode, area, dose, unit: serverResult.unit, amount: amountValue,
      predio: plotSelect.selectedOptions[0]?.text || plot.name,
      plot: plot.name, crop, insumo: productName,
      target: isProtectionMode() ? targetSelect.value : '',
      doseSource: doseNotice, verified,
      date: new Date().toISOString()
    };
    if (save) AgroService.saveResult('calculo-' + (mode === 'proteccion' ? 'proteccion' : mode), payload);
    const amount = AgroService.fmt(amountValue);

    document.getElementById('result').innerHTML =
      '<p class="result-kicker">' + (mode === 'semillas' ? 'Cantidad de semillas' :
        mode === 'proteccion' ? 'Cantidad de producto fitosanitario' : 'Cantidad de insumo') + '</p>' +
      '<p class="decision-result-value">' + amount + ' ' + outputUnit + '</p>' +
      '<p>Para <strong>' + safePlot + '</strong> · ' + safeCrop +
      (productName ? ' · ' + safeProduct : '') + (isProtectionMode() ? ' · ' + AgroService.escape(targetSelect.value) : '') + '</p>' +
      '<div class="formula-box"><p class="formula-line">Superficie × dosis por hectárea</p><p>' +
      AgroService.fmt(area) + ' ha × ' + AgroService.fmt(dose) + ' ' + AgroService.escape(doseUnit) +
      ' = <strong>' + amount + ' ' + outputUnit + '</strong></p></div>' +
      '<div class="decision-result-summary"><div class="metric"><span>Superficie utilizada</span><strong>' +
      AgroService.fmt(area, 3) + ' ha</strong></div><div class="metric"><span>Dosis utilizada</span><strong>' +
      AgroService.fmt(dose) + ' ' + AgroService.escape(doseUnit) + '</strong></div>' +
      (doseNotice ? '<div class="metric"><span>Procedencia de la dosis</span><strong>' + AgroService.escape(doseNotice) + '</strong></div>' : '') +
      '</div>' +
      (isProtectionMode()
        ? '<p class="alert decision-safety">Confirma etiqueta, uso autorizado y precauciones antes de cualquier aplicación. No se recomiendan mezclas ni usos fuera de etiqueta.</p>'
        : '<p class="muted decision-safety">Resultado matemático. Confirma la procedencia y aplicabilidad de los parámetros antes de utilizarlo.</p>');
    return true;
  }

  function isProtectionMode() {
    return mode === 'proteccion';
  }

  document.querySelectorAll('[name="surface-scope"]').forEach((radio) => {
    radio.addEventListener('change', () => {
      const fullArea = radio.value === 'total' && radio.checked;
      areaInput.readOnly = fullArea;
      if (fullArea) areaInput.value = maxArea() || '';
      else areaInput.focus();
    });
  });
  plotSelect.addEventListener('change', syncPlot);
  cropSelect.addEventListener('change', () => {
    if (mode === 'proteccion') targetSelect.value = '';
    syncCropDefaults();
  });
  targetSelect.addEventListener('change', () => {
    refreshInsumoOptions();
    syncProduct();
  });
  insumoSelect.addEventListener('change', syncProduct);
  document.getElementById('modes').addEventListener('click', (event) => {
    const button = event.target.closest('button[data-mode]');
    if (button) setMode(button.dataset.mode);
  });
  document.getElementById('calc-form').addEventListener('submit', async (event) => {
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
    document.getElementById('result').replaceChildren();
    errorBox.textContent = '';
    setMode(params.get('modo') || 'semillas');
    if (params.get('plot')) plotSelect.value = params.get('plot');
    syncPlot();
  });

  if (params.get('plot')) plotSelect.value = params.get('plot');
  const requestedProduct = AgroService.getInsumos(true).find((item) => AgroService.sameId(item.id, params.get('insumo')));
  const startMode = params.get('modo') || (requestedProduct && isProtectionProduct(requestedProduct) ? 'proteccion' :
    params.get('insumo') ? 'insumos' : 'semillas');
  setMode(startMode);
  syncPlot();
  if (requestedProduct) {
    if (requestedProduct.crop && Array.from(cropSelect.options).some((option) => option.value === requestedProduct.crop)) {
      cropSelect.value = requestedProduct.crop;
    }
    syncCropDefaults(requestedProduct.id);
  }
})();
