/* Generador de PDF compartido por el calendario y la calculadora.
   Mismo formato que AgroAsesor: banda verde con la marca, título y líneas de datos. */
(function () {
  'use strict';

  function slug(text) {
    return String(text || '')
      .toLowerCase()
      .normalize('NFD')
      .replace(/[\u0300-\u036f]/g, '')
      .replace(/[^a-z0-9]+/g, '-')
      .replace(/^-+|-+$/g, '');
  }

  function wrap(doc, text, x, y, maxWidth, lineHeight) {
    doc.splitTextToSize(String(text || ''), maxWidth).forEach(function (line) {
      if (y > 280) {
        doc.addPage();
        y = 20;
      }
      doc.text(line, x, y);
      y += lineHeight;
    });
    return y;
  }

  function plainLines(title, rows, note) {
    const lines = ['AgroAsesor · ' + title, ''];
    (rows || []).forEach(function (row) {
      if (!row) return;
      if (row.heading) lines.push(row.heading);
      else lines.push(row.label ? row.label + ': ' + (row.value == null ? '' : row.value) : String(row.value == null ? row : row.value));
    });
    lines.push('', note);
    return lines;
  }

  /* rows: [{ heading }, { label, value }, ...]. options.badge: texto a la derecha de la banda. */
  function download(filename, title, rows, options) {
    const opts = options || {};
    const note = opts.note
      || (window.AGRO_MOCK && window.AGRO_MOCK.disclaimer)
      || 'Información orientativa; no reemplaza la asesoría de un ingeniero agrónomo.';
    const JsPdf = window.jspdf && window.jspdf.jsPDF;
    if (!JsPdf) {
      // Sin la librería (por ejemplo, sin conexión) se abre una vista imprimible.
      const win = window.open('', '_blank');
      if (!win) {
        window.alert('No se pudo generar el PDF. Revisa tu conexión e inténtalo nuevamente.');
        return false;
      }
      win.document.title = 'AgroAsesor';
      plainLines(title, rows, note).forEach(function (line) {
        const p = win.document.createElement('p');
        p.textContent = line;
        win.document.body.append(p);
      });
      win.print();
      return false;
    }
    const doc = new JsPdf();
    doc.setFillColor(35, 93, 55);
    doc.rect(0, 0, 210, 22, 'F');
    doc.setTextColor(255, 255, 255);
    doc.setFontSize(16);
    doc.text('AgroAsesor', 14, 14);
    if (opts.badge) {
      doc.setFontSize(10);
      doc.text(String(opts.badge), 196, 14, { align: 'right' });
    }
    doc.setTextColor(30, 40, 32);
    doc.setFontSize(14);
    let y = 34;
    y = wrap(doc, title, 14, y, 180, 7);
    doc.setFontSize(10);
    y += 4;
    (rows || []).forEach(function (row) {
      if (!row) return;
      if (row.heading) {
        y += 3;
        doc.setFont(undefined, 'bold');
        y = wrap(doc, row.heading, 14, y, 180, 6);
        doc.setFont(undefined, 'normal');
        return;
      }
      const line = row.label ? row.label + ': ' + (row.value == null ? '' : row.value) : String(row.value == null ? row : row.value);
      y = wrap(doc, line, 14, y, 180, 6);
    });
    y += 8;
    doc.setFontSize(8);
    doc.setTextColor(90, 90, 90);
    wrap(doc, 'Generado: ' + new Date().toLocaleDateString('es-CL') + ' · ' + note, 14, y, 180, 4.5);
    doc.save(filename);
    return true;
  }

  window.AgroPdf = { download: download, slug: slug };
})();
