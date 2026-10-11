(function () {
  function payload() {
    return AgroService.getResult(document.getElementById('kind').value);
  }

  function lines(data) {
    if (!data) return ['No hay un resultado guardado para este tipo. Haz el cálculo o la ficha primero.'];
    const when = new Date().toLocaleDateString('es-CL');
    const rows = ['AgroAsesor', 'Fecha: ' + when];
    Object.entries(data).forEach(([key, value]) => {
      if (value && typeof value !== 'object') rows.push(key + ': ' + value);
    });
    rows.push('Fuente: datos guardados en AgroAsesor; no se consultan fuentes externas.');
    rows.push(window.AGRO_MOCK.disclaimer);
    return rows;
  }

  function preview() {
    const data = payload();
    const previewBox = document.getElementById('preview');
    const heading = document.createElement('h2');
    heading.textContent = 'Vista previa';
    previewBox.replaceChildren(heading);
    lines(data).forEach((line) => {
      const paragraph = document.createElement('p');
      paragraph.textContent = line;
      previewBox.append(paragraph);
    });
  }

  document.getElementById('kind').addEventListener('change', preview);
  preview();
  document.getElementById('pdf-btn').addEventListener('click', () => {
    const data = payload();
    if (!window.jspdf) { alert('No se pudo cargar el generador de PDF.'); return; }
    const doc = new window.jspdf.jsPDF();
    doc.setFontSize(16);
    doc.text('AgroAsesor', 14, 20);
    doc.setFontSize(11);
    lines(data).slice(1).forEach((line, index) => {
      doc.text(String(line).slice(0, 90), 14, 32 + index * 8);
    });
    doc.save('agroasesor-reporte.pdf');
  });
})();
