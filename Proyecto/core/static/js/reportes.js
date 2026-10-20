(function () {
  const kindSelect = document.getElementById('kind');
  const historySelect = document.getElementById('history-record');
  const records = JSON.parse(document.getElementById('report-records').textContent);
  const categoriesByKind = {
    'calculo-semillas': ['semillas'],
    'calculo-insumos': ['insumos'],
    'calculo-proteccion': ['proteccion'],
    cobertura: ['coverage'],
    rendimiento: ['rendimiento'],
  };

  function payload() {
    return AgroService.getResult(kindSelect.value);
  }

  function matchingRecords() {
    const categories = categoriesByKind[kindSelect.value] || [];
    return records.filter((record) => categories.includes(record.category));
  }

  function refreshHistoryOptions() {
    const selected = historySelect.value;
    const available = matchingRecords();
    historySelect.replaceChildren(new Option(
      available.length ? 'Último cálculo de este tipo' : 'No hay cálculos guardados de este tipo',
      '',
    ));
    available.forEach((record) => {
      historySelect.add(new Option(
        record.created + ' · ' + record.farm + ' · ' + record.plot + ' · ' + record.operationLabel,
        String(record.id),
      ));
    });
    if (available.some((record) => String(record.id) === selected)) historySelect.value = selected;
  }

  function selectedRecord() {
    const available = matchingRecords();
    return available.find((record) => String(record.id) === historySelect.value) || available[0] || null;
  }

  function lines(data, record) {
    if (record) {
      const rows = [
        'AgroAsesor',
        'Fecha: ' + record.created,
        'Operación: ' + record.operationLabel,
        'Predio: ' + record.farm,
        'Potrero: ' + record.plot,
      ];
      Object.entries(record.input || {}).forEach(([key, value]) => {
        if (value !== null && value !== undefined && value !== '') rows.push(key + ': ' + value);
      });
      Object.entries(record.result || {}).forEach(([key, value]) => {
        if (value !== null && value !== undefined && typeof value !== 'object') rows.push(key + ': ' + value);
      });
      rows.push('Este cálculo fue guardado en la cuenta autenticada.');
      rows.push('Resultado matemático orientativo; verifica unidades y fuentes técnicas antes de utilizarlo.');
      return rows;
    }
    if (!data) return ['No hay un resultado guardado para este tipo. Haz el cálculo o consulta la ficha primero.'];
    const when = data.date ? new Date(data.date).toLocaleDateString('es-CL') : new Date().toLocaleDateString('es-CL');
    const rows = ['AgroAsesor', 'Fecha: ' + when];
    Object.entries(data).forEach(([key, value]) => {
      if (value && typeof value !== 'object') rows.push(key + ': ' + value);
    });
    rows.push('Resultado orientativo. Confirma fuentes y condiciones locales antes de utilizarlo.');
    return rows;
  }

  function preview() {
    const record = selectedRecord();
    const data = record ? null : payload();
    const previewBox = document.getElementById('preview');
    const heading = document.createElement('h2');
    heading.textContent = 'Vista previa';
    previewBox.replaceChildren(heading);
    lines(data, record).forEach((line) => {
      const paragraph = document.createElement('p');
      paragraph.textContent = line;
      previewBox.append(paragraph);
    });
  }

  kindSelect.addEventListener('change', () => {
    refreshHistoryOptions();
    preview();
  });
  historySelect.addEventListener('change', preview);
  refreshHistoryOptions();
  preview();
  document.getElementById('pdf-btn').addEventListener('click', () => {
    const record = selectedRecord();
    const data = record ? null : payload();
    if (!window.jspdf) {
      alert('No se pudo cargar el generador de PDF.');
      return;
    }
    const doc = new window.jspdf.jsPDF();
    doc.setFontSize(16);
    doc.text('AgroAsesor', 14, 20);
    doc.setFontSize(11);
    let y = 32;
    lines(data, record).slice(1).forEach((line) => {
      const wrapped = doc.splitTextToSize(String(line), 180);
      if (y + wrapped.length * 7 > 280) {
        doc.addPage();
        y = 20;
      }
      doc.text(wrapped, 14, y);
      y += wrapped.length * 7;
    });
    doc.save('agroasesor-reporte.pdf');
  });
})();
