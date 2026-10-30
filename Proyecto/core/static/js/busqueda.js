(function () {
  // Datos reales que la página trae en JSON (catálogo de la base y predios del usuario).
  function readJson(id, fallback) {
    const node = document.getElementById(id);
    if (!node) return fallback;
    try {
      return JSON.parse(node.textContent) || fallback;
    } catch (error) {
      return fallback;
    }
  }

  const catalog = readJson('agro-catalog', {});
  const cultivos = (catalog.cultivos || []).filter((item) => item.active !== false).map((item) => item.name || item);
  const problemas = (catalog.problemas || []).filter((item) => item.active !== false);
  const insumos = catalog.insumos || [];
  const insumosActivos = insumos.filter((item) => item.active);
  const semillas = catalog.semillas || [];
  const predios = readJson('agro-farms', {}).predios || [];
  const escape = (value) =>
    String(value ?? '').replace(
      /[&<>"']/g,
      (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c],
    );

  document.getElementById('crop').innerHTML += cultivos.map((name) => '<option>' + name + '</option>').join('');
  document.getElementById('problem').innerHTML += problemas
    .map((item) => '<option>' + escape(item.name) + '</option>')
    .join('');
  document.getElementById('type').innerHTML += [...new Set(insumos.map((item) => item.type))]
    .map((name) => '<option>' + name + '</option>')
    .join('');

  function normalize(value) {
    return String(value || '')
      .toLowerCase()
      .normalize('NFD')
      .replace(/[\u0300-\u036f]/g, '');
  }

  function match(text, term) {
    return normalize(text).includes(term);
  }

  // Ejemplos rápidos con datos reales del catálogo del usuario (nunca términos fijos que podrían no existir).
  (function renderExamples() {
    const host = document.getElementById('search-examples');
    const first = (list) => (list && list.length ? list[0] : null);
    const candidates = [
      first(predios) && first(predios).name,
      first(cultivos),
      first(insumosActivos) && first(insumosActivos).name,
    ].filter(Boolean);
    host.replaceChildren(
      ...[...new Set(candidates)].map((text) => {
        const chip = document.createElement('button');
        chip.className = 'example-chip';
        chip.type = 'button';
        chip.dataset.q = text;
        chip.textContent = text;
        return chip;
      }),
    );
    host.hidden = !host.children.length;
  })();

  function search() {
    const term = normalize(document.getElementById('term').value.trim());
    const crop = document.getElementById('crop').value;
    const problem = document.getElementById('problem').value;
    const type = document.getElementById('type').value;
    const items = [];
    cultivos.forEach((name) => items.push({ kind: 'cultivo', title: name, text: name, href: '/calendario/' }));
    semillas.forEach((item) =>
      items.push({
        kind: 'semilla',
        title: item.name,
        text: item.name + ' ' + item.crop,
        href: '/decisiones/?herramienta=llevar&tipo=semillas',
      }),
    );
    insumosActivos.forEach((item) =>
      items.push({
        kind: 'insumo',
        title: item.name,
        text: item.name + ' ' + item.crop + ' ' + item.problem + ' ' + item.type,
        href: '/productos/' + encodeURIComponent(item.id) + '/',
        crop: item.crop,
        problem: item.problem,
        type: item.type,
      }),
    );
    problemas.forEach((item) =>
      items.push({
        kind: 'problema',
        title: item.name,
        text: item.name,
        href: '/productos/?problema=' + encodeURIComponent(item.id),
      }),
    );
    predios.forEach((item) =>
      items.push({
        kind: 'predio',
        title: item.name,
        text: item.name + ' ' + item.location,
        href: '/predios/?predio=' + item.id,
      }),
    );
    const results = items.filter((item) => {
      if (term && !match(item.text, term)) return false;
      if (crop && item.crop && item.crop !== crop) return false;
      if (problem && item.problem && item.problem !== problem) return false;
      if (type && item.type && item.type !== type) return false;
      if ((crop || problem || type) && item.kind !== 'insumo' && item.kind !== 'cultivo' && item.kind !== 'problema') {
        if (crop && item.kind === 'cultivo') return item.title === crop;
        if (item.kind !== 'insumo')
          return !crop && !problem && !type ? true : item.kind === 'problema' && (!problem || item.title === problem);
      }
      return true;
    });
    const labels = { cultivo: 'Cultivo', semilla: 'Semilla', insumo: 'Insumo', problema: 'Problema', predio: 'Predio' };
    document.getElementById('results').innerHTML = results.length
      ? results
          .map(
            (item) =>
              '<a class="card result kind-' +
              item.kind +
              '" href="' +
              item.href +
              '"><span class="badge">' +
              (labels[item.kind] || item.kind) +
              '</span><h3>' +
              escape(item.title) +
              '</h3><p class="muted">' +
              ({
                insumo: 'Ver ficha técnica',
                problema: 'Ver productos relacionados',
                predio: 'Abrir en el mapa',
                cultivo: 'Ver calendario agronómico',
                semilla: 'Calcular semillas',
              }[item.kind] || 'Abrir') +
              '</p></a>',
          )
          .join('')
      : '<section class="card"><h2>Sin coincidencias</h2><p class="muted">Prueba con parte del nombre o quita los filtros. Si buscas un producto que no está registrado, puedes <a href="/decisiones/?herramienta=llevar&tipo=insumos">calcular a mano en el Centro de decisiones</a> (queda marcado como simulación).</p></section>';
  }

  document.getElementById('search-form').addEventListener('submit', (event) => {
    event.preventDefault();
    search();
  });
  document.querySelectorAll('[data-q]').forEach((chip) => {
    chip.addEventListener('click', () => {
      document.getElementById('term').value = chip.dataset.q;
      search();
    });
  });
  search();
})();
