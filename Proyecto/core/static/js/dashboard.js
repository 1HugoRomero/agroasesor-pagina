(function () {
  const state = AgroService.getState();
  const board = document.getElementById('plot-board');
  if (!board) return;

  function cropClass(name) {
    const key = String(name || '').toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '');
    if (key.includes('maiz')) return 'maiz';
    if (key.includes('trigo')) return 'trigo';
    if (key.includes('alfalfa')) return 'alfalfa';
    if (key.includes('tomate')) return 'tomate';
    if (key.includes('papa')) return 'papa';
    if (key.includes('cebolla')) return 'cebolla';
    return 'otro';
  }

  function cropIcon(name) {
    return ['trigo', 'maiz'].includes(cropClass(name)) ? 'sprout' : 'leaf';
  }

  if (!state.plots.length) {
    board.innerHTML = '<div class="empty-state"><p>Aún no tienes potreros registrados.</p><a class="button secondary" href="/predios/">Registrar predio y potrero</a></div>';
  } else {
    board.innerHTML = state.plots.map((plot) => {
      const farm = state.predios.find((item) => item.id === plot.predio);
      return '<article class="plot-row">' +
        '<div class="plot-identity"><span class="plot-thumb ' + cropClass(plot.crop) + '" aria-hidden="true"></span>' +
        '<div><strong>' + AgroService.escape(plot.name) + '</strong><small class="muted">' +
        AgroService.escape(farm ? farm.name : 'Predio') + '</small></div></div>' +
        '<span class="badge' + (plot.status === 'Planificado' ? ' amber' : '') + '">' +
        AgroService.escape(plot.status || 'Sin estado') + '</span>' +
        '<span class="plot-area">' + AgroService.fmt(plot.areaHa, 2) + ' ha</span>' +
        '<span class="plot-crop">' + AgroService.escape(plot.crop || 'Sin cultivo') + '</span>' +
        '<span class="plot-actions"><a href="/calculadora/?plot=' + encodeURIComponent(plot.id) + '">Cantidad</a>' +
        '<a href="/cobertura/?plot=' + encodeURIComponent(plot.id) + '">Cobertura</a>' +
        '<a href="/predios/?predio=' + encodeURIComponent(plot.predio) + '">Mapa</a></span>' +
        '</article>';
    }).join('');
  }

  const next = state.plots.find((plot) => plot.status === 'Planificado') || state.plots[0];
  if (next) {
    const farm = state.predios.find((item) => item.id === next.predio);
    const nextStep = document.createElement('a');
    nextStep.className = 'next-step';
    nextStep.href = '/calculadora/?plot=' + encodeURIComponent(next.id);
    nextStep.innerHTML = '<span class="next-ico"><i data-lucide="' + cropIcon(next.crop) + '"></i></span>' +
      '<span><span>Siguiente</span><strong>Calcular ' + AgroService.escape(next.crop || 'insumo') +
      ' en ' + AgroService.escape(next.name) + '</strong><small>' +
      AgroService.escape(farm ? farm.name : '') + ' · ' + AgroService.fmt(next.areaHa, 2) +
      ' ha</small></span><i data-lucide="arrow-right"></i>';
    board.before(nextStep);
  }

  const farmMini = document.getElementById('farm-mini');
  if (farmMini) {
    farmMini.innerHTML = state.predios.map((farm) =>
      '<a class="farm-mini" href="/predios/?predio=' + encodeURIComponent(farm.id) + '">' +
      '<strong>' + AgroService.escape(farm.name) + '</strong><span>' +
      AgroService.fmt(farm.area, 2) + ' ha</span></a>'
    ).join('') || '<p class="muted">Aún no tienes predios registrados.</p>';
  }

  if (window.lucide) window.lucide.createIcons();
})();
