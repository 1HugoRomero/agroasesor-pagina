/* Registro de siembra: muestra cuánto falta (o cuánto lleva) cada potrero según sus fechas. */
(function () {
  'use strict';
  var DAY = 86400000;

  function parse(iso) {
    if (!iso) return null;
    var p = iso.split('-');
    if (p.length !== 3) return null;
    return new Date(Number(p[0]), Number(p[1]) - 1, Number(p[2]));
  }

  function plural(n, one, many) {
    return n + ' ' + (n === 1 ? one : many);
  }

  var MONTHS = ['ENE', 'FEB', 'MAR', 'ABR', 'MAY', 'JUN', 'JUL', 'AGO', 'SEP', 'OCT', 'NOV', 'DIC'];

  // Línea de 12 meses con la siembra y la cosecha reales del potrero; no se dibuja nada si faltan las fechas.
  function renderMonths(holder, sow, harvest) {
    if (!holder || (!sow && !harvest)) return;
    var strip = document.createElement('span');
    strip.className = 'month-strip';
    strip.setAttribute('aria-hidden', 'true');
    var sowMonth = sow ? sow.getMonth() : -1;
    var harvestMonth = harvest ? harvest.getMonth() : -1;
    var inSpan = {};
    if (sow && harvest && harvest > sow) {
      var steps = Math.min(12, (harvest.getFullYear() - sow.getFullYear()) * 12 + harvestMonth - sowMonth);
      for (var i = 0; i <= steps; i++) inSpan[(sowMonth + i) % 12] = true;
    }
    MONTHS.forEach(function (name, index) {
      var cell = document.createElement('i');
      cell.title = name;
      if (inSpan[index]) cell.className = 'span';
      if (index === sowMonth) cell.className = 'sow';
      if (index === harvestMonth) cell.className = 'harvest';
      strip.appendChild(cell);
    });
    holder.appendChild(strip);
    var chips = document.createElement('span');
    chips.className = 'month-chips';
    if (sow) {
      var a = document.createElement('span');
      a.className = 'month-chip sow';
      a.textContent = 'Siembra · ' + MONTHS[sowMonth];
      chips.appendChild(a);
    }
    if (harvest) {
      var b = document.createElement('span');
      b.className = 'month-chip harvest';
      b.textContent = 'Cosecha · ' + MONTHS[harvestMonth];
      chips.appendChild(b);
    }
    holder.appendChild(chips);
  }

  var now = new Date();
  var today = new Date(now.getFullYear(), now.getMonth(), now.getDate());

  document.querySelectorAll('.sowing-plot').forEach(function (row) {
    var sow = parse(row.dataset.sowing);
    var harvest = parse(row.dataset.harvest);
    var label = row.querySelector('[data-role="label"]');
    var bar = row.querySelector('[data-role="bar"]');
    if (!label || !bar) return;
    var text = 'Sin fechas registradas';
    var pct = 0;
    var tone = '';
    if (sow && today < sow) {
      var left = Math.round((sow - today) / DAY);
      text = left === 0 ? 'Se siembra hoy' : 'Siembra en ' + plural(left, 'día', 'días');
      tone = 'soon';
    } else if (sow && harvest && harvest > sow) {
      var total = harvest - sow;
      pct = Math.min(100, Math.max(0, ((today - sow) / total) * 100));
      if (today > harvest) {
        text = 'Cosecha vencida hace ' + plural(Math.round((today - harvest) / DAY), 'día', 'días');
        tone = 'late';
      } else {
        text = 'Cosecha en ' + plural(Math.round((harvest - today) / DAY), 'día', 'días');
        tone = 'grow';
      }
    } else if (sow) {
      text = 'Sembrado hace ' + plural(Math.round((today - sow) / DAY), 'día', 'días');
      tone = 'grow';
    } else if (harvest) {
      text = 'Cosecha prevista, falta la siembra';
      tone = 'late';
    }
    label.textContent = text;
    bar.style.width = pct + '%';
    renderMonths(row.querySelector('[data-role="months"]'), sow, harvest);
    row.classList.add('tl-' + (tone || 'none'));
  });
})();
