(function () {
  const sections = [
    { id: 'cultivos', label: 'Cultivos', fields: ['name'] },
    { id: 'variedades', label: 'Variedades', fields: ['name'] },
    { id: 'zonas', label: 'Zonas', fields: ['name'] },
    { id: 'insumos', label: 'Insumos', fields: ['name', 'crop', 'problem', 'type', 'dose', 'unit'] },
    { id: 'problemas', label: 'Problemas agrícolas', fields: ['name'] },
    { id: 'calendario', label: 'Calendario', fields: ['name', 'sow', 'cycle', 'notes'] }
  ];
  let current = 'cultivos';
  const stats = window.AGRO_MOCK.adminStats;

  document.getElementById('admin-stats').innerHTML = [
    ['Agricultores registrados', stats.agricultores],
    ['Cultivos registrados', stats.cultivos],
    ['Insumos registrados', stats.insumos],
    ['Consultas realizadas', stats.consultas]
  ].map(([label, value]) => '<article class="card"><span class="muted">' + label + '</span><strong class="stat-value">' + value + '</strong></article>').join('');

  function items() {
    return AgroService.getState()[current] || [];
  }

  function renderTabs() {
    document.getElementById('tabs').innerHTML = sections.map((item) =>
      '<button class="' + (item.id === current ? 'button' : 'button secondary') + '" type="button" data-sec="' + item.id + '">' + item.label + '</button>'
    ).join('');
  }

  function renderForm() {
    const labels = { name: 'Nombre', crop: 'Cultivo', problem: 'Problema', type: 'Tipo', dose: 'Dosis', unit: 'Unidad', sow: 'Mes de siembra', cycle: 'Ciclo (meses)', notes: 'Notas' };
    const section = sections.find((item) => item.id === current);
    const title = document.getElementById('admin-title');
    if (title) title.textContent = section.label;
    document.getElementById('create-form').innerHTML = section.fields.map((field) =>
      '<label class="field"><span>' + (labels[field] || field) + '</span><input name="' + field + '" required></label>'
    ).join('') + '<button class="button" type="submit">Crear</button>';
  }

  function renderTable() {
    document.getElementById('table').innerHTML = items().map((item) =>
      '<div class="admin-row"><strong>' + (item.name || item.id) + '</strong><span class="badge ' + (item.active === false ? 'amber' : '') + '">' +
      (current === 'insumos' ? (item.active ? 'Vigente' : 'No vigente') : (item.active === false ? 'Inactivo' : 'Activo')) +
      '</span><button class="button secondary" type="button" data-edit="' + item.id + '">Editar</button>' +
      '<button class="button secondary" type="button" data-toggle="' + item.id + '">' + (item.active === false ? 'Activar' : 'Desactivar') + '</button>' +
      '<button class="button secondary" type="button" data-del="' + item.id + '">Eliminar</button></div>'
    ).join('');
  }

  function refresh() {
    renderTabs();
    renderForm();
    renderTable();
  }

  document.getElementById('tabs').addEventListener('click', (event) => {
    if (!event.target.dataset.sec) return;
    current = event.target.dataset.sec;
    refresh();
  });
  document.getElementById('create-form').addEventListener('submit', (event) => {
    event.preventDefault();
    const data = Object.fromEntries(new FormData(event.currentTarget).entries());
    if (data.dose && AgroService.positive(data.dose) === null) { alert('La dosis debe ser mayor a 0.'); return; }
    const list = items();
    list.push({ id: crypto.randomUUID(), active: true, ...data, dose: data.dose ? Number(data.dose) : undefined });
    AgroService.replaceCatalog(current, list);
    event.currentTarget.reset();
    refresh();
  });
  document.getElementById('table').addEventListener('click', (event) => {
    const list = items();
    const edit = event.target.dataset.edit;
    const del = event.target.dataset.del;
    const toggle = event.target.dataset.toggle;
    if (edit) {
      const name = prompt('Nuevo nombre', list.find((item) => item.id === edit)?.name);
      if (!name) return;
      AgroService.replaceCatalog(current, list.map((item) => item.id === edit ? { ...item, name } : item));
    }
    if (toggle) {
      AgroService.replaceCatalog(current, list.map((item) => item.id === toggle ? { ...item, active: item.active === false } : item));
    }
    if (del && confirm('¿Eliminar este registro?')) {
      AgroService.replaceCatalog(current, list.filter((item) => item.id !== del));
    }
    refresh();
  });
  refresh();
})();
