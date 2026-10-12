(function () {
  const params = new URLSearchParams(location.search);
  const noCrop = '__sin_cultivo__';
  let step = 0;
  let crop = '';
  let problem = '';
  let type = '';
  let insumoId = '';

  function activeInsumos() {
    return AgroService.getInsumos(true);
  }

  function cropKey(item) {
    return item.crop || noCrop;
  }

  function cropLabel(value) {
    return value === noCrop ? 'Sin cultivo asociado' : value;
  }

  function cropInsumos() {
    return activeInsumos().filter((item) => cropKey(item) === crop);
  }

  function problemNames(item) {
    if (Array.isArray(item.problems) && item.problems.length) return item.problems;
    return item.problem ? [item.problem] : [];
  }

  function usesProblems() {
    return cropInsumos().some((item) => problemNames(item).length > 0);
  }

  function uniqueValues(items, key) {
    return [...new Set(items.map((item) => item[key]).filter((value) => value !== null && value !== undefined && value !== ''))];
  }

  function options() {
    if (step === 0) {
      return [...new Set(activeInsumos().map(cropKey))]
        .map((value) => ({ value, label: cropLabel(value) }));
    }
    if (step === 1) {
      if (usesProblems()) {
        return [...new Set(cropInsumos().flatMap(problemNames))]
          .map((value) => ({ value, label: value }));
      }
      return uniqueValues(cropInsumos(), 'type').map((value) => ({ value, label: value }));
    }
    if (step === 2 && usesProblems()) {
      return uniqueValues(
        cropInsumos().filter((item) => problemNames(item).includes(problem)),
        'type',
      )
        .map((value) => ({ value, label: value }));
    }
    if (step === 2) {
      return cropInsumos().filter((item) => item.type === type)
        .map((item) => ({ value: String(item.id), label: item.name }));
    }
    return [];
  }

  function match() {
    if (usesProblems()) {
      return cropInsumos().find((item) =>
        problemNames(item).includes(problem) && item.type === type);
    }
    return cropInsumos().find((item) => item.type === type && String(item.id) === insumoId);
  }

  function currentLabels() {
    return [
      'Cultivo',
      usesProblems() ? 'Problema agrícola' : 'Tipo de insumo',
      usesProblems() ? 'Tipo de insumo' : 'Producto',
      'Ficha de insumo'
    ];
  }

  function displayValue(value) {
    if (value === null || value === undefined || value === '') return '';
    if (typeof value === 'boolean') return value ? 'Vigente' : 'No vigente';
    return String(value);
  }

  function safeLink(value) {
    if (!value) return '';
    try {
      const url = new URL(value, location.origin);
      if (!['http:', 'https:'].includes(url.protocol)) return '';
      return url.href;
    } catch {
      return '';
    }
  }

  function listValue(value) {
    return Array.isArray(value) ? value.map(displayValue).filter(Boolean).join(', ') : '';
  }

  function renderFicha(box) {
    const item = match();
    if (!item) {
      box.innerHTML = '<p class="muted">No hay una ficha vigente para esta selección. El catálogo no contiene los datos necesarios.</p>' +
        '<button class="button secondary" type="button" data-step="2">Cambiar selección</button>';
      return;
    }

    AgroService.saveResult('asesor', item);
    function rows(fields) {
      return fields.map(([label, value]) => [label, displayValue(value)])
        .filter(([, value]) => value)
        .map(([label, value]) => '<dt>' + AgroService.escape(label) + '</dt><dd>' + AgroService.escape(value) + '</dd>')
        .join('');
    }
    const composition = rows([
      ['Composición nutricional declarada', item.nutrientComposition],
      ['Nitrógeno (N)', item.nitrogenPct === null || item.nitrogenPct === undefined ? '' : item.nitrogenPct + '%'],
      ['Fósforo (P₂O₅)', item.phosphorusP2o5Pct === null || item.phosphorusP2o5Pct === undefined ? '' : item.phosphorusP2o5Pct + '%'],
      ['Potasio (K₂O)', item.potassiumK2oPct === null || item.potassiumK2oPct === undefined ? '' : item.potassiumK2oPct + '%'],
      ['Variedad de semilla', item.seedVariety],
      ['Tipo de semilla', item.seedType],
      ['Plantas objetivo por m²', item.targetPlantsM2],
      ['Peso de mil semillas (g)', item.thousandSeedWeightG],
      ['Germinación', item.germinationPct === null || item.germinationPct === undefined ? '' : item.germinationPct + '%'],
      ['Pureza', item.purityPct === null || item.purityPct === undefined ? '' : item.purityPct + '%'],
      ['Presentación comercial', item.packageAmount && item.packageUnit ? item.packageAmount + ' ' + item.packageUnit : '']
    ]);
    const useAndDose = rows([
      ['Cultivo asociado', cropLabel(crop)],
      ['Problemas agrícolas relacionados', listValue(item.problems || (item.problem ? [item.problem] : []))],
      ['Cultivos autorizados', listValue(item.authorizedCrops)],
      ['Objetivos de control registrados', listValue(item.controlTargets || (item.problem ? [item.problem] : []))],
      ['Dosis registrada', item.dose === null || item.dose === undefined ? '' :
        item.dose + (item.unit ? ' ' + item.unit : ' (unidad no registrada)')],
      ['Dosis máxima verificada', item.maxDose === null || item.maxDose === undefined ? '' :
        item.maxDose + (item.maxDoseUnit ? ' ' + item.maxDoseUnit : '')],
      ['Vigencia', item.validFrom || item.validUntil
        ? (item.validFrom || 'Sin inicio') + ' – ' + (item.validUntil || 'Sin término')
        : 'Sin rango temporal registrado'],
      ['Zona', item.zone],
      ['Período de carencia', item.preharvestInterval],
      ['Tiempo de reingreso', item.reentryInterval]
    ]);
    const stateLabels = {
      verified: 'Verificado con fuente registrada',
      restricted: 'Restringido',
      cancelled: 'Registro cancelado',
      unverified: 'Información no verificada'
    };
    const statusText = stateLabels[item.verificationStatus] || 'Información no verificada';
    const safetyMessages = [
      item.restrictions,
      item.environmentalPrecautions,
      item.pollinatorWarning,
      item.safety
    ].map(displayValue).filter(Boolean);
    const safetyMessage = safetyMessages.length
      ? safetyMessages.map(AgroService.escape).join('<br>')
      : 'El catálogo no incluye precauciones verificadas para este producto. Revisa la etiqueta oficial.';
    const sourceUrl = safeLink(item.sourceUrl || item.source);
    const labelUrl = safeLink(item.labelUrl);
    const safetyUrl = safeLink(item.safetySheetUrl);
    const documentLinks = [
      sourceUrl ? '<a href="' + AgroService.escape(sourceUrl) + '" target="_blank" rel="noopener noreferrer">Fuente técnica</a>' : '',
      labelUrl ? '<a href="' + AgroService.escape(labelUrl) + '" target="_blank" rel="noopener noreferrer">Etiqueta</a>' : '',
      safetyUrl ? '<a href="' + AgroService.escape(safetyUrl) + '" target="_blank" rel="noopener noreferrer">Hoja de datos de seguridad</a>' : ''
    ].filter(Boolean).join(' · ');
    const canCalculate = item.doseVerified === true &&
      (item.type || '').toLowerCase() !== 'semilla' &&
      (!['herbicida', 'fungicida', 'insecticida', 'acaricida', 'plaguicida'].includes((item.type || '').toLowerCase()) ||
        item.verifiedUse === true);
    const itemId = encodeURIComponent(String(item.id));

    box.innerHTML = '<article class="ficha"><span class="badge">' + AgroService.escape(statusText) + '</span><h2>' +
      AgroService.escape(item.name) + '</h2><p><strong>' + AgroService.escape(item.type) + '</strong>' +
      (item.nutrientComposition ? ' · ' + AgroService.escape(item.nutrientComposition) : '') + '</p>' +
      '<p class="product-verification-note">El estado refleja la información registrada por el administrador del catálogo; no es una consulta en vivo al SAG.</p>' +
      '<details><summary>Descripción</summary><dl><dt>Descripción</dt><dd>' +
      AgroService.escape(item.description || 'Sin información registrada') + '</dd>' +
      '</dl></details><details><summary>Composición y presentación</summary><dl>' +
      (composition || '<dt>Información</dt><dd>No registrada</dd>') +
      '</dl></details><details><summary>Cultivos y usos documentados</summary><dl>' +
      (useAndDose || '<dt>Información</dt><dd>No registrada</dd>') +
      '</dl></details><details><summary>Dosificación</summary><dl>' +
      rows([
        ['Dosis registrada', item.dose === null || item.dose === undefined ? '' :
          item.dose + (item.unit ? ' ' + item.unit : ' (unidad no registrada)')],
        ['Fuente de la dosis', item.doseSource]
      ]) + '</dl></details><div class="alert product-safety"><strong>Precauciones</strong><br>' +
      safetyMessage + '</div><details><summary>Documentación y fuentes</summary><p>' +
      (documentLinks || 'No hay documentación vinculada.') + '</p>' +
      (item.sourceName ? '<p>Fuente declarada: ' + AgroService.escape(item.sourceName) + '</p>' : '') +
      (item.sagRegistration ? '<p>Número SAG registrado: ' + AgroService.escape(item.sagRegistration) + '</p>' : '') +
      (item.formulation ? '<p>Formulación: ' + AgroService.escape(item.formulation) + '</p>' : '') +
      (item.concentration ? '<p>Concentración: ' + AgroService.escape(item.concentration) + '</p>' : '') +
      (item.verifiedAt ? '<p>Fecha de verificación registrada: ' + AgroService.escape(item.verifiedAt) + '</p>' : '') +
      (item.doseSource ? '<p>Fuente de la dosis: ' + AgroService.escape(item.doseSource) + '</p>' : '') +
      '</details><p class="alert">' +
      (canCalculate ? 'La fuente de la dosis está registrada; verifica que corresponda a tu situación.' :
        'Información no verificada para cálculo. No uses la ficha como recomendación de aplicación.') +
      '</p><div class="toolbar">' +
      (canCalculate ? '<a class="button secondary" href="/calculadora/?insumo=' + itemId + '">Usar en cálculo</a>' : '') +
      '</div></article>';
  }

  function render() {
    const stepLabels = currentLabels();
    document.getElementById('steps').innerHTML = stepLabels.map((label, index) =>
      '<li><button type="button" data-step="' + index + '" class="' + (index === step ? 'is-active' : '') + '"' +
      (index >= step ? ' aria-current="step"' : '') + (index > step ? ' disabled' : '') +
      '><span>' + (index + 1) + '</span> ' + AgroService.escape(label) + '</button></li>'
    ).join('');
    const box = document.getElementById('wizard');
    if (step === 3) {
      renderFicha(box);
      return;
    }
    const instructions = [
      'Selecciona el cultivo o grupo disponible en el catálogo.',
      usesProblems() ? 'Elige el problema registrado para este cultivo.' : 'Selecciona el tipo de insumo disponible.',
      usesProblems() ? 'Elige un tipo de producto para consultar.' : 'Elige el producto que quieres consultar.'
    ];
    const choices = options();
    box.innerHTML = '<p class="hint">Paso ' + (step + 1) + ' de 4</p><h2>' +
      AgroService.escape(stepLabels[step]) + '</h2><p class="muted">' + instructions[step] + '</p><div class="choice-grid">' +
      (choices.length ? choices.map((option) =>
        '<button type="button" data-value="' + AgroService.escape(option.value) + '">' +
        AgroService.escape(option.label) + '</button>'
      ).join('') : '<p class="muted">No hay opciones vigentes para esta combinación.</p>') + '</div>';
  }

  document.getElementById('steps').addEventListener('click', (event) => {
    const button = event.target.closest('button[data-step]');
    if (!button || button.disabled) return;
    step = Number(button.dataset.step);
    render();
  });
  document.getElementById('wizard').addEventListener('click', (event) => {
    const previousStep = event.target.closest('button[data-step]');
    if (previousStep && !previousStep.disabled) {
      step = Number(previousStep.dataset.step);
      render();
      return;
    }
    const button = event.target.closest('button[data-value]');
    if (!button) return;
    if (step === 0) {
      crop = button.dataset.value;
      problem = '';
      type = '';
      insumoId = '';
    } else if (step === 1) {
      if (usesProblems()) problem = button.dataset.value;
      else type = button.dataset.value;
    } else if (step === 2) {
      if (usesProblems()) type = button.dataset.value;
      else insumoId = button.dataset.value;
    }
    step = Math.min(3, step + 1);
    render();
  });

  const initialCrop = params.get('crop');
  if (initialCrop && [...new Set(activeInsumos().map(cropKey))].includes(initialCrop)) {
    crop = initialCrop;
    step = 1;
  }
  render();
})();
