(function () {
  document.getElementById('crop').innerHTML += AgroService.getCultivos().map((name) => '<option>' + name + '</option>').join('');
  document.getElementById('problem').innerHTML += AgroService.getProblemas().map((item) => '<option>' + AgroService.escape(item.name) + '</option>').join('');
  document.getElementById('type').innerHTML += [...new Set(AgroService.getInsumos().map((item) => item.type))].map((name) => '<option>' + name + '</option>').join('');

  function normalize(value) {
    return String(value || '').toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '');
  }

  function match(text, term) {
    return normalize(text).includes(term);
  }

  function search() {
    const term = normalize(document.getElementById('term').value.trim());
    const crop = document.getElementById('crop').value;
    const problem = document.getElementById('problem').value;
    const type = document.getElementById('type').value;
    const items = [];
    AgroService.getCultivos().forEach((name) => items.push({ kind: 'cultivo', title: name, text: name, href: '/calendario/' }));
    window.AGRO_MOCK.semillas.forEach((item) => items.push({ kind: 'semilla', title: item.name, text: item.name + ' ' + item.crop, href: '/decisiones/?herramienta=llevar&tipo=semillas' }));
    AgroService.getInsumos(true).forEach((item) => items.push({ kind: 'insumo', title: item.name, text: item.name + ' ' + item.crop + ' ' + item.problem + ' ' + item.type, href: '/productos/' + encodeURIComponent(item.id) + '/', crop: item.crop, problem: item.problem, type: item.type }));
    AgroService.getProblemas().forEach((item) => items.push({ kind: 'problema', title: item.name, text: item.name, href: '/productos/?problema=' + encodeURIComponent(item.id) }));
    AgroService.getPredios().forEach((item) => items.push({ kind: 'predio', title: item.name, text: item.name + ' ' + item.location, href: '/predios/?predio=' + item.id }));
    const results = items.filter((item) => {
      if (term && !match(item.text, term)) return false;
      if (crop && item.crop && item.crop !== crop) return false;
      if (problem && item.problem && item.problem !== problem) return false;
      if (type && item.type && item.type !== type) return false;
      if ((crop || problem || type) && item.kind !== 'insumo' && item.kind !== 'cultivo' && item.kind !== 'problema') {
        if (crop && item.kind === 'cultivo') return item.title === crop;
        if (item.kind !== 'insumo') return !crop && !problem && !type ? true : item.kind === 'problema' && (!problem || item.title === problem);
      }
      return true;
    });
    const labels = { cultivo: 'Cultivo', semilla: 'Semilla', insumo: 'Insumo', problema: 'Problema', predio: 'Predio' };
    document.getElementById('results').innerHTML = results.length
      ? results.map((item) => '<a class="card result kind-' + item.kind + '" href="' + item.href + '"><span class="badge">' + (labels[item.kind] || item.kind) + '</span><h3>' + AgroService.escape(item.title) + '</h3><p class="muted">' + ({ insumo: 'Ver ficha técnica', problema: 'Ver productos relacionados', predio: 'Abrir en el mapa', cultivo: 'Ver calendario agronómico', semilla: 'Calcular semillas' }[item.kind] || 'Abrir') + '</p></a>').join('')
      : '<section class="card"><h2>Sin coincidencias</h2><p class="muted">Prueba “mai”, “gusano” o “santa”. También puedes dejar la búsqueda vacía para ver todo el catálogo demo.</p></section>';
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
