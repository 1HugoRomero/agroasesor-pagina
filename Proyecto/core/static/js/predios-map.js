(() => {
  'use strict';
  const configNode = document.getElementById('maps-config');
  const mapElement = document.getElementById('farm-map');
  const status = document.getElementById('map-status');
  if (!configNode || !mapElement || !status) return;

  const config = JSON.parse(configNode.textContent);
  const form = document.getElementById('terrain-form');
  const isPlotForm = Boolean(document.getElementById('id_perimetro'));
  const isPredioForm = Boolean(document.getElementById('accept-perimeter'));
  const dataNode = document.getElementById('agro-farms');
  const farmData = dataNode ? JSON.parse(dataNode.textContent) : { predios: [], plots: [] };
  const areaInput = document.getElementById('id_superficie_ha');
  const latitudeInput = document.getElementById('id_latitud');
  const longitudeInput = document.getElementById('id_longitud');
  const legacyPerimeterInput = document.getElementById('id_perimetro');
  const geojsonInput = document.getElementById('id_geojson');
  const mapSummary = document.getElementById('map-form-summary');
  const mapSummaryArea = document.getElementById('map-summary-area');
  const mapSummaryPerimeter = document.getElementById('map-summary-perimeter');
  const mapSummaryLocation = document.getElementById('map-summary-location');
  const perimeterAcceptedInput = document.getElementById('id_perimetro_aceptado');
  const confirmationPanel = document.getElementById('perimeter-confirmation');
  const registrationPrompt = document.getElementById('registration-prompt');
  const confirmArea = document.getElementById('confirm-area');
  const confirmPerimeter = document.getElementById('confirm-perimeter');
  const confirmVertices = document.getElementById('confirm-vertices');
  const confirmLocation = document.getElementById('confirm-location');
  const melipillaCenter = [-33.6866, -71.2167];
  let map;
  let currentLayer = null;
  let marker = null;
  let drawing = false;
  let drawingMode = null;
  let drawPoints = [];
  let previewLine = null;
  let savedMeasurement = null;
  let drawMarkers = [];
  let boundaryMarkers = [];
  let viewBounds;
  let originalFeature = null;
  let parentFarm = null;
  let parentFarmLayer = null;
  const farmLayers = new Map();
  const plotLayers = new Map();
  let selectedFarmId = '';
  let selectedPlotId = '';

  function setStatus(message) {
    status.textContent = message;
  }

  function configureTiles() {
    const normalTiles = L.tileLayer(config.tile_url, {
      attribution: config.attribution,
      maxZoom: 19,
      crossOrigin: true
    });
    const satelliteTiles = L.tileLayer(
      'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
      {
        attribution: '&copy; Esri, Maxar, Earthstar Geographics, and the GIS User Community',
        maxZoom: 19,
        crossOrigin: true
      }
    );
    let activeTiles = normalTiles;

    [normalTiles, satelliteTiles].forEach((tiles) => {
      tiles.on('tileerror', () => {
        if (tiles === activeTiles) {
          setStatus('No se cargaron algunas teselas del mapa. Puedes seguir dibujando; comprueba la conexión si el fondo aparece vacío.');
        }
      });
      tiles.on('tileload', () => {
        if (tiles === activeTiles && status.textContent.startsWith('No se cargaron algunas teselas del mapa.')) {
          setStatus(form
            ? 'Mapa listo. Elige “Dibujar campo” para medir superficie y perímetro, o “Medir línea” para un tramo.'
            : 'Mapa listo.');
        }
      });
    });

    const viewControl = L.control({ position: 'topright' });
    viewControl.onAdd = () => {
      const container = L.DomUtil.create('div', 'leaflet-control map-view-switch');
      container.setAttribute('role', 'group');
      container.setAttribute('aria-label', 'Cambiar vista del mapa');
      const buttons = new Map();

      function selectView(tiles) {
        if (tiles !== activeTiles) {
          map.removeLayer(activeTiles);
          activeTiles = tiles;
          activeTiles.addTo(map);
        }
        buttons.forEach((button, layer) => {
          const isActive = layer === activeTiles;
          button.classList.toggle('is-active', isActive);
          button.setAttribute('aria-pressed', String(isActive));
        });
      }

      [['Normal', normalTiles], ['Satélite', satelliteTiles]].forEach(([label, tiles]) => {
        const button = L.DomUtil.create('button', '', container);
        button.type = 'button';
        button.textContent = label;
        button.setAttribute('aria-pressed', 'false');
        button.addEventListener('click', () => selectView(tiles));
        buttons.set(tiles, button);
      });

      L.DomEvent.disableClickPropagation(container);
      L.DomEvent.disableScrollPropagation(container);
      selectView(normalTiles);
      return container;
    };
    viewControl.addTo(map);
    normalTiles.addTo(map);
  }

  function featureOf(layer) {
    const feature = layer.toGeoJSON();
    feature.properties = {};
    return feature;
  }

  function featureCoordinates(feature) {
    if (!feature) return [];
    const geometry = feature.type === 'Feature' ? feature.geometry : feature;
    if (!geometry || geometry.type !== 'Polygon' || !Array.isArray(geometry.coordinates)) return [];
    const ring = (geometry.coordinates[0] || []).map((point) => point.slice());
    if (ring.length > 1 && JSON.stringify(ring[0]) === JSON.stringify(ring[ring.length - 1])) ring.pop();
    return ring;
  }

  function distanceMetres(first, second) {
    const radians = (degrees) => degrees * Math.PI / 180;
    const [longitude1, latitude1] = first;
    const [longitude2, latitude2] = second;
    const deltaLatitude = radians(latitude2 - latitude1);
    const deltaLongitude = radians(longitude2 - longitude1);
    const latitude1Radians = radians(latitude1);
    const latitude2Radians = radians(latitude2);
    const haversine = Math.sin(deltaLatitude / 2) ** 2 +
      Math.cos(latitude1Radians) * Math.cos(latitude2Radians) * Math.sin(deltaLongitude / 2) ** 2;
    return 2 * 6378137 * Math.atan2(Math.sqrt(haversine), Math.sqrt(Math.max(0, 1 - haversine)));
  }

  function perimeterMetres(points, closeRing) {
    const edgeCount = points.length - 1 + (closeRing && points.length > 2 ? 1 : 0);
    let length = 0;
    for (let index = 0; index < edgeCount; index += 1) {
      length += distanceMetres(points[index], points[(index + 1) % points.length]);
    }
    return length;
  }

  function polygonAreaSquareMetres(points) {
    const vectors = points.map(([longitude, latitude]) => {
      const lng = longitude * Math.PI / 180;
      const lat = latitude * Math.PI / 180;
      return [Math.cos(lat) * Math.cos(lng), Math.cos(lat) * Math.sin(lng), Math.sin(lat)];
    });
    const dot = (a, b) => a.reduce((sum, value, index) => sum + value * b[index], 0);
    const origin = vectors[0];
    let excess = 0;
    for (let index = 1; index < vectors.length - 1; index += 1) {
      const b = vectors[index];
      const c = vectors[index + 1];
      const determinant = origin[0] * (b[1] * c[2] - b[2] * c[1]) +
        origin[1] * (b[2] * c[0] - b[0] * c[2]) +
        origin[2] * (b[0] * c[1] - b[1] * c[0]);
      excess += 2 * Math.atan2(
        determinant,
        1 + dot(origin, b) + dot(b, c) + dot(c, origin)
      );
    }
    return Math.abs(excess) * 6378137 ** 2;
  }

  function orientation(a, b, c) {
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0]);
  }

  function segmentsIntersect(a, b, c, d) {
    const epsilon = 1e-12;
    const onSegment = (first, second, point) =>
      Math.min(first[0], second[0]) - epsilon <= point[0] &&
      point[0] <= Math.max(first[0], second[0]) + epsilon &&
      Math.min(first[1], second[1]) - epsilon <= point[1] &&
      point[1] <= Math.max(first[1], second[1]) + epsilon;
    const values = [orientation(a, b, c), orientation(a, b, d), orientation(c, d, a), orientation(c, d, b)];
    if (values[0] * values[1] < 0 && values[2] * values[3] < 0) return true;
    const points = [c, d, a, b];
    return values.some((value, index) => Math.abs(value) < epsilon &&
      onSegment(index < 2 ? a : c, index < 2 ? b : d, points[index]));
  }

  function hasSelfIntersection(points) {
    const edges = points.map((point, index) => [point, points[(index + 1) % points.length]]);
    for (let first = 0; first < edges.length; first += 1) {
      for (let second = first + 1; second < edges.length; second += 1) {
        if (second === first + 1 || (first === 0 && second === edges.length - 1)) continue;
        if (segmentsIntersect(...edges[first], ...edges[second])) return true;
      }
    }
    return false;
  }

  function pointInRing(point, ring) {
    let inside = false;
    for (let index = 0, previous = ring.length - 1; index < ring.length; previous = index, index += 1) {
      const [x, y] = point;
      const [x1, y1] = ring[index];
      const [x2, y2] = ring[previous];
      const cross = (x - x1) * (y2 - y1) - (y - y1) * (x2 - x1);
      if (Math.abs(cross) < 1e-12 &&
          x >= Math.min(x1, x2) - 1e-12 && x <= Math.max(x1, x2) + 1e-12 &&
          y >= Math.min(y1, y2) - 1e-12 && y <= Math.max(y1, y2) + 1e-12) return true;
      if ((y1 > y) !== (y2 > y) && x < ((x2 - x1) * (y - y1)) / (y2 - y1) + x1) {
        inside = !inside;
      }
    }
    return inside;
  }

  function polygonInsideParent(points) {
    if (!parentFarm?.geojson) return true;
    const boundary = featureCoordinates(parentFarm.geojson);
    if (boundary.length < 3 || points.some((point) => !pointInRing(point, boundary))) return false;
    for (let index = 0; index < points.length; index += 1) {
      const first = points[index];
      const second = points[(index + 1) % points.length];
      for (let edge = 0; edge < boundary.length; edge += 1) {
        const third = boundary[edge];
        const fourth = boundary[(edge + 1) % boundary.length];
        const crossesBoundary = orientation(first, second, third) * orientation(first, second, fourth) < 0 &&
          orientation(third, fourth, first) * orientation(third, fourth, second) < 0;
        if (crossesBoundary) return false;
      }
    }
    return true;
  }

  function formatLength(metres) {
    return metres < 1000
      ? metres.toLocaleString('es-CL', { maximumFractionDigits: 1 }) + ' m'
      : (metres / 1000).toLocaleString('es-CL', { maximumFractionDigits: 3 }) + ' km';
  }

  function updateFormMapSummary(points) {
    if (!mapSummary) return;
    const latitude = latitudeInput?.value;
    const longitude = longitudeInput?.value;
    const hasCoordinates = Boolean(latitude && longitude);
    if (points && points.length >= 3) {
      const area = polygonAreaSquareMetres(points);
      if (areaInput) {
        areaInput.value = (area / 10000).toFixed(4);
        areaInput.readOnly = true;
      }
      if (mapSummaryArea) {
        mapSummaryArea.textContent =
          (area / 10000).toLocaleString('es-CL', { maximumFractionDigits: 4 }) + ' ha · ' +
          area.toLocaleString('es-CL', { maximumFractionDigits: 2 }) + ' m²';
      }
      if (mapSummaryPerimeter) {
        mapSummaryPerimeter.textContent = formatLength(perimeterMetres(points, true));
      }
      if (mapSummaryLocation) {
        mapSummaryLocation.textContent = hasCoordinates
          ? 'Ubicación: ' + Number(latitude).toFixed(6) + ', ' + Number(longitude).toFixed(6) + '.'
          : 'Ubicación: se usó el primer vértice del perímetro.';
      }
      mapSummary.hidden = false;
      return;
    }
    if (hasCoordinates) {
      mapSummary.hidden = false;
      if (mapSummaryArea) {
        mapSummaryArea.textContent = areaInput?.value
          ? Number(areaInput.value).toLocaleString('es-CL', { maximumFractionDigits: 4 }) + ' ha · ingreso manual'
          : 'Pendiente de calcular';
      }
      if (mapSummaryPerimeter) mapSummaryPerimeter.textContent = 'Pendiente de delimitar';
      if (mapSummaryLocation) {
        mapSummaryLocation.textContent = 'Ubicación: ' +
          Number(latitude).toFixed(6) + ', ' + Number(longitude).toFixed(6) + '.';
      }
      return;
    }
    mapSummary.hidden = true;
    if (mapSummaryArea) mapSummaryArea.textContent = '';
    if (mapSummaryPerimeter) mapSummaryPerimeter.textContent = '';
    if (mapSummaryLocation) mapSummaryLocation.textContent = '';
  }

  function fmtHa(value, digits) {
    return Number(value || 0).toLocaleString('es-CL', { maximumFractionDigits: digits ?? 2 });
  }

  function fmtDate(value) {
    if (!value) return 'Sin fecha registrada';
    const [year, month, day] = String(value).split('-');
    return day && month && year ? day + '/' + month + '/' + year : value;
  }

  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined && text !== null) node.textContent = text;
    return node;
  }

  function plotActionUrl(kind, plot, farm) {
    const params = new URLSearchParams();
    if (kind === 'calendar') {
      params.set('potrero', plot.id);
      if (plot.cropId) params.set('crop', plot.cropId);
      if (farm.zoneId) params.set('zone', farm.zoneId);
      return '/calendario/?' + params.toString();
    }
    params.set('plot', plot.id);
    if (kind === 'seeds') { params.set('herramienta', 'llevar'); params.set('tipo', 'semillas'); }
    if (kind === 'inputs') { params.set('herramienta', 'llevar'); params.set('tipo', 'insumos'); }
    if (kind === 'sheet') { params.set('herramienta', 'ficha'); if (plot.cropId) params.set('crop', plot.cropId); }
    return '/decisiones/?' + params.toString();
  }

  function setSelectedTerrain(farm, plot) {
    const details = document.getElementById('selected-terrain-details');
    const emptyState = document.getElementById('selected-terrain-empty');
    if (!details || !emptyState) return;
    details.replaceChildren();
    const list = (parent) => {
      const dl = el('dl', 'terrain-facts');
      parent.appendChild(dl);
      return (label, value) => dl.append(el('dt', '', label), el('dd', '', value));
    };
    const actions = el('div', 'detail-actions');
    const addLink = (label, href, primary) => {
      const link = el('a', primary ? 'button' : 'button secondary', label);
      link.href = href;
      actions.appendChild(link);
      return link;
    };
    const farmPlots = farmData.plots.filter((item) => String(item.predio) === String(farm.id));
    const assignedArea = farmPlots.reduce((sum, item) => sum + Number(item.areaHa || 0), 0);

    if (plot) {
      const head = el('div', 'terrain-panel-head');
      head.append(el('span', 'terrain-eyebrow', 'Potrero seleccionado'), el('h3', '', plot.name));
      details.appendChild(head);
      const add = list(details);
      add('Predio', farm.name);
      add('Superficie', fmtHa(plot.areaHa, 2) + ' ha (' + fmtHa(plot.areaM2, 0) + ' m²)');
      if (plot.perimeterM !== null && plot.perimeterM !== undefined) add('Perímetro', formatLength(plot.perimeterM));
      if (plot.crop) {
        add('Cultivo actual', plot.crop);
        add('Variedad', plot.variety || 'No registrada');
        add('Temporada', plot.season || 'Sin rótulo');
        add('Fecha de siembra', fmtDate(plot.sowing));
        add('Cosecha estimada', fmtDate(plot.harvest));
        add('Estado', plot.status || 'No disponible');
      } else {
        const notice = el('div', 'terrain-no-crop');
        notice.append(el('p', '', 'Este potrero todavía no tiene un cultivo asignado'));
        details.appendChild(notice);
      }
      const assign = el('button', 'button', plot.crop ? 'Cambiar cultivo' : 'Asignar cultivo');
      assign.type = 'button';
      assign.dataset.assignCrop = plot.id;
      actions.appendChild(assign);
      addLink('Planificar siembra', plotActionUrl('calendar', plot, farm), false);
      addLink('Calcular semillas', plotActionUrl('seeds', plot, farm), false);
      addLink('Calcular fertilizantes', plotActionUrl('inputs', plot, farm), false);
      addLink('Consultar ficha', plotActionUrl('sheet', plot, farm), false);
      addLink('Ver historial', plot.detailUrl, false);
      addLink('Editar potrero', plot.editUrl, false);
      details.appendChild(actions);

      const history = el('details', 'terrain-season-history');
      history.open = (plot.seasons || []).length > 0 && (plot.seasons || []).length <= 3;
      history.append(el('summary', '', 'Historial de cultivos (' + (plot.seasons || []).length + ')'));
      if ((plot.seasons || []).length) {
        const ol = el('ol', 'season-list');
        plot.seasons.forEach((season, index) => {
          const item = el('li', index === 0 ? 'is-current' : '');
          item.append(el('strong', '', (season.season ? season.season + ' · ' : '') + season.crop + (season.variety ? ' · ' + season.variety : '')));
          item.append(el('span', '', (index === 0 ? 'Actual · ' : 'Anterior · ') + season.statusLabel +
            ' · siembra ' + fmtDate(season.sowingDate) + ' · cosecha ' + fmtDate(season.harvestDate)));
          if (season.notes) item.append(el('small', '', season.notes));
          ol.appendChild(item);
        });
        history.appendChild(ol);
      } else {
        history.appendChild(el('p', 'muted', 'Aún no hay temporadas registradas para este potrero.'));
      }
      details.appendChild(history);
      details.appendChild(el('hr'));
    }

    const farmHead = el('div', 'terrain-panel-head');
    farmHead.append(el('span', 'terrain-eyebrow', plot ? 'Predio del potrero' : 'Predio seleccionado'), el(plot ? 'h4' : 'h3', '', farm.name));
    details.appendChild(farmHead);
    const addFarm = list(details);
    addFarm('Ubicación', farm.location || 'No registrada');
    addFarm('Superficie total', fmtHa(farm.area, 2) + ' ha');
    if (farm.perimeterM !== null && farm.perimeterM !== undefined) addFarm('Perímetro', formatLength(farm.perimeterM));
    addFarm('Potreros', String(farmPlots.length));
    addFarm('Superficie en potreros', fmtHa(assignedArea, 2) + ' ha · sin asignar ' + fmtHa(Math.max(0, Number(farm.area) - assignedArea), 2) + ' ha');
    const crops = [...new Set(farmPlots.map((item) => item.crop).filter(Boolean))];
    addFarm('Cultivos actuales', crops.length ? crops.join(', ') : 'Sin cultivos asignados');
    addFarm('Última modificación', farm.updated || 'No disponible');
    const farmActions = el('div', 'detail-actions');
    [['Registrar potrero', farm.potreroCreateUrl, !plot], ['Ficha e historial del predio', farm.detailUrl, false], ['Editar predio', farm.editUrl, false]]
      .forEach(([label, href, primary]) => {
        const link = el('a', primary ? 'button' : 'button secondary', label);
        link.href = href;
        farmActions.appendChild(link);
      });
    details.appendChild(farmActions);

    emptyState.hidden = true;
    details.hidden = false;
    document.querySelectorAll('[data-select-farm]').forEach((button) => {
      const selected = String(button.dataset.selectFarm) === String(farm.id);
      button.classList.toggle('is-selected', selected);
      button.setAttribute('aria-pressed', String(selected));
    });
    document.querySelectorAll('[data-farm-plots]').forEach((group) => {
      group.hidden = String(group.dataset.farmPlots) !== String(farm.id);
    });
    const plotsPanel = document.getElementById('farm-plots-picker');
    if (plotsPanel) plotsPanel.hidden = false;
    document.querySelectorAll('[data-plot-card]').forEach((card) => {
      card.classList.toggle('is-selected', Boolean(plot && String(card.dataset.plotCard) === String(plot.id)));
    });
    document.querySelectorAll('[data-select-plot]').forEach((button) => {
      const selected = Boolean(plot && String(button.dataset.selectPlot) === String(plot.id));
      button.classList.toggle('is-selected', selected);
      button.setAttribute('aria-pressed', String(selected));
    });
    const createPlotLink = document.getElementById('register-selected-plot');
    if (createPlotLink) {
      createPlotLink.href = farm.potreroCreateUrl;
      createPlotLink.textContent = farmPlots.length ? 'Registrar potrero' : 'Registrar primer potrero';
    }
    const showPlotsButton = document.getElementById('show-selected-farm-plots');
    if (showPlotsButton) showPlotsButton.disabled = farmPlots.length === 0;
    const params = new URLSearchParams(window.location.search);
    params.set('predio', farm.id);
    if (plot) params.set('potrero', plot.id); else params.delete('potrero');
    window.history.replaceState(null, '', window.location.pathname + '?' + params.toString());
  }

  function updateMeasurements(points, closeRing) {
    const perimeterOutput = document.getElementById('live-perimeter');
    if (perimeterOutput) {
      perimeterOutput.textContent = (closeRing ? 'Perímetro' : 'Longitud trazada') + ': ' +
        formatLength(perimeterMetres(points, closeRing));
    }
    const areaOutput = document.getElementById('live-area');
    if (!areaOutput) return;
    if (!closeRing || points.length < 3) {
      areaOutput.textContent = '';
      areaOutput.classList.remove('is-error');
      return;
    }
    if (hasSelfIntersection(points)) {
      areaOutput.textContent = 'El contorno se cruza; ajusta los vértices antes de calcular el área.';
      areaOutput.classList.add('is-error');
      return;
    }
    const squareMetres = polygonAreaSquareMetres(points);
    const hectares = squareMetres / 10000;
    if (isPlotForm && !polygonInsideParent(points)) {
      areaOutput.textContent = 'El potrero debe quedar completamente dentro del límite verde del predio.';
      areaOutput.classList.add('is-error');
      return;
    }
    const availableHectares = Number(areaInput?.max);
    if (isPlotForm && Number.isFinite(availableHectares) &&
        Number(hectares.toFixed(4)) > availableHectares) {
      areaOutput.textContent = 'El perímetro mide ' +
        hectares.toLocaleString('es-CL', { maximumFractionDigits: 4 }) + ' ha; solo hay ' +
        availableHectares.toLocaleString('es-CL', { maximumFractionDigits: 4 }) + ' ha disponibles.';
      areaOutput.classList.add('is-error');
      return;
    }
    areaOutput.classList.remove('is-error');
    areaOutput.textContent =
      squareMetres.toLocaleString('es-CL', { maximumFractionDigits: 2 }) + ' m² · ' +
      hectares.toLocaleString('es-CL', { maximumFractionDigits: 4 }) +
      ' ha (estimación; el servidor confirma el valor al guardar)';
  }

  function setAreaAndGeometry() {
    const coordinates = featureCoordinates(featureOf(currentLayer));
    if (geojsonInput) geojsonInput.value = JSON.stringify(featureOf(currentLayer));
    if (legacyPerimeterInput) legacyPerimeterInput.value = JSON.stringify(coordinates);

    if (coordinates.length < 3) {
      document.getElementById('live-area').textContent = 'Dibuja un perímetro con al menos tres vértices.';
      return;
    }
    updateMeasurements(coordinates, true);
    const squareMetres = polygonAreaSquareMetres(coordinates);
    const hectares = squareMetres / 10000;
    if (areaInput) {
      areaInput.value = hectares.toFixed(4);
      areaInput.readOnly = true;
    }
    if (coordinates[0]) {
      if (latitudeInput) latitudeInput.value = coordinates[0][1];
      if (longitudeInput) longitudeInput.value = coordinates[0][0];
    }
    updateFormMapSummary(coordinates);
  }

  function renderBoundaryVertices() {
    boundaryMarkers.forEach((item) => map.removeLayer(item));
    boundaryMarkers = [];
    if (!isPredioForm || !currentLayer) return;
    featureCoordinates(featureOf(currentLayer)).forEach(([longitude, latitude]) => {
      boundaryMarkers.push(L.circleMarker([latitude, longitude], {
        radius: 4,
        color: '#1e3d28',
        fillColor: '#fff',
        fillOpacity: 1,
        weight: 2,
        interactive: false
      }).addTo(map));
    });
  }

  function setPerimeterControls(available, accepted) {
    const accept = document.getElementById('accept-perimeter');
    const edit = document.getElementById(isPredioForm ? 'edit-perimeter' : 'toggle-edit');
    const cancel = document.getElementById('cancel-perimeter');
    if (accept) accept.hidden = !available || accepted;
    if (edit) edit.hidden = !available || accepted;
    if (cancel) cancel.hidden = !available || accepted;
  }

  function showPerimeterConfirmation() {
    if (!currentLayer) {
      setStatus('Dibuja primero el perímetro del predio.');
      return;
    }
    const points = featureCoordinates(featureOf(currentLayer));
    if (points.length < 3 || points.length > 200 || hasSelfIntersection(points)) {
      setStatus('El perímetro debe tener entre 3 y 200 vértices y no cruzarse a sí mismo.');
      return;
    }
    const area = polygonAreaSquareMetres(points);
    if (!Number.isFinite(area) || area < 1) {
      setStatus('El perímetro debe delimitar una superficie válida de al menos 1 m².');
      return;
    }
    if (perimeterAcceptedInput) perimeterAcceptedInput.value = 'on';
    if (confirmArea) {
      confirmArea.textContent =
        area.toLocaleString('es-CL', { maximumFractionDigits: 2 }) + ' m² · ' +
        (area / 10000).toLocaleString('es-CL', { maximumFractionDigits: 4 }) + ' ha';
    }
    if (confirmPerimeter) confirmPerimeter.textContent = formatLength(perimeterMetres(points, true));
    if (confirmVertices) confirmVertices.textContent = String(points.length);
    if (confirmLocation) {
      const latitude = latitudeInput?.value || points[0][1];
      const longitude = longitudeInput?.value || points[0][0];
      confirmLocation.textContent =
        'Ubicación aproximada: ' + Number(latitude).toFixed(6) + ', ' + Number(longitude).toFixed(6);
    }
    if (confirmationPanel) confirmationPanel.hidden = false;
    setPerimeterControls(true, true);
    if (currentLayer.pm) currentLayer.pm.disable();
    renderBoundaryVertices();
    setStatus('Revisa la vista previa y confirma el perímetro para continuar.');
  }

  function editConfirmedPerimeter() {
    if (!currentLayer || !currentLayer.pm) return;
    if (confirmationPanel) confirmationPanel.hidden = true;
    if (perimeterAcceptedInput) perimeterAcceptedInput.value = '';
    setPerimeterControls(true, false);
    boundaryMarkers.forEach((item) => map.removeLayer(item));
    boundaryMarkers = [];
    currentLayer.pm.enable({ allowSelfIntersection: false });
    setStatus('Edición activada. Ajusta los vértices y acepta nuevamente el perímetro.');
  }

  function cancelPerimeterChanges() {
    if (drawing) stopDrawing();
    boundaryMarkers.forEach((item) => map.removeLayer(item));
    boundaryMarkers = [];
    if (currentLayer) map.removeLayer(currentLayer);
    currentLayer = null;
    if (originalFeature) {
      addCurrentLayer(originalFeature, false);
    } else {
      if (geojsonInput) geojsonInput.value = '';
      if (legacyPerimeterInput) legacyPerimeterInput.value = '[]';
      if (areaInput) {
        areaInput.value = '';
        areaInput.readOnly = isPredioForm;
      }
      if (latitudeInput) latitudeInput.value = '';
      if (longitudeInput) longitudeInput.value = '';
      if (mapSummary) mapSummary.hidden = true;
      setPerimeterControls(false, false);
      const perimeterOutput = document.getElementById('live-perimeter');
      const areaOutput = document.getElementById('live-area');
      if (perimeterOutput) perimeterOutput.textContent = '';
      if (areaOutput) areaOutput.textContent = '';
    }
    if (perimeterAcceptedInput) perimeterAcceptedInput.value = '';
    if (confirmationPanel) confirmationPanel.hidden = true;
    setStatus(originalFeature
      ? 'Cambios descartados. Se mantiene el perímetro guardado.'
      : 'Dibujo descartado. Los predios existentes no se modificaron.');
  }

  function continueAfterConfirmation() {
    if (form) form.hidden = false;
    if (registrationPrompt) registrationPrompt.hidden = true;
    const editButton = document.getElementById('edit-perimeter');
    if (editButton) editButton.hidden = false;
    const dataStep = document.getElementById('step-data');
    if (dataStep) dataStep.classList.add('is-current');
    if (confirmationPanel) confirmationPanel.hidden = true;
    const nameInput = document.getElementById('id_nombre');
    if (nameInput) nameInput.focus({ preventScroll: true });
    setStatus('Perímetro confirmado. Completa los datos y guarda el predio.');
  }

  function stopDrawing() {
    drawing = false;
    drawingMode = null;
    drawPoints = [];
    if (previewLine) map.removeLayer(previewLine);
    previewLine = null;
    drawMarkers.forEach((item) => map.removeLayer(item));
    drawMarkers = [];
    document.getElementById('undo-point').disabled = true;
    document.getElementById('finish-perimeter').disabled = true;
    document.getElementById('finish-line').hidden = true;
    document.getElementById('finish-line').disabled = true;
    document.getElementById('cancel-drawing').hidden = true;
    document.getElementById('draw-perimeter').classList.remove('is-active');
    document.getElementById('measure-line').classList.remove('is-active');
  }

  function enableEditing() {
    if (currentLayer && currentLayer.pm) {
      if (isPredioForm) {
        editConfirmedPerimeter();
      } else {
        currentLayer.pm.enable({ allowSelfIntersection: false });
        setStatus('Edición activada. Ajusta vértices y vuelve a guardar.');
      }
    }
  }

  function addCurrentLayer(feature, askToReplace) {
    if (currentLayer && askToReplace && !window.confirm('¿Reemplazar el perímetro existente?')) return false;
    boundaryMarkers.forEach((item) => map.removeLayer(item));
    boundaryMarkers = [];
    if (currentLayer) map.removeLayer(currentLayer);
    currentLayer = L.geoJSON(feature, {
      style: { color: '#255b37', weight: 3, fillColor: '#74a567', fillOpacity: 0.24 }
    }).getLayers()[0];
    if (!currentLayer) return false;
    currentLayer.addTo(map);
    if (currentLayer.pm) currentLayer.pm.disable();
    currentLayer.on('pm:edit', () => {
      setAreaAndGeometry();
      if (isPredioForm) {
        if (perimeterAcceptedInput) perimeterAcceptedInput.value = '';
        if (confirmationPanel) confirmationPanel.hidden = true;
        setPerimeterControls(true, false);
      }
    });
    currentLayer.on('pm:dragend', () => {
      setAreaAndGeometry();
      if (isPredioForm) {
        if (perimeterAcceptedInput) perimeterAcceptedInput.value = '';
        if (confirmationPanel) confirmationPanel.hidden = true;
        setPerimeterControls(true, false);
      }
    });
    viewBounds.extend(currentLayer.getBounds());
    setAreaAndGeometry();
    renderBoundaryVertices();
    if (isPredioForm) setPerimeterControls(true, false);
    else document.getElementById('toggle-edit').hidden = false;
    return true;
  }

  function beginDrawing(mode) {
    if (drawing) return;
    if (mode === 'polygon' && currentLayer && !window.confirm('¿Reemplazar el perímetro existente?')) return;
    if (mode === 'line' && savedMeasurement && !window.confirm('¿Reemplazar la línea medida?')) return;
    if (mode === 'line' && savedMeasurement) {
      map.removeLayer(savedMeasurement);
      savedMeasurement = null;
      document.getElementById('clear-measurement').hidden = true;
    }
    drawing = true;
    drawingMode = mode;
    drawPoints = [];
    document.getElementById(mode === 'polygon' ? 'draw-perimeter' : 'measure-line').classList.add('is-active');
    document.getElementById('undo-point').disabled = true;
    document.getElementById('cancel-drawing').hidden = false;
    document.getElementById('finish-perimeter').hidden = mode !== 'polygon';
    document.getElementById('finish-line').hidden = mode !== 'line';
    setStatus(mode === 'polygon'
      ? 'Dibujar campo: marca al menos tres vértices alrededor del terreno.'
      : 'Medir línea: marca los puntos del lindero o tramo; necesitas al menos dos.');
  }

  function addDrawingPoint(event) {
    if (!drawing) {
      if (latitudeInput && longitudeInput && !currentLayer) {
        latitudeInput.value = event.latlng.lat.toFixed(6);
        longitudeInput.value = event.latlng.lng.toFixed(6);
        if (marker) map.removeLayer(marker);
        marker = L.marker(event.latlng, { draggable: true }).addTo(map);
        marker.on('dragend', (dragEvent) => {
          latitudeInput.value = dragEvent.target.getLatLng().lat.toFixed(6);
          longitudeInput.value = dragEvent.target.getLatLng().lng.toFixed(6);
          updateFormMapSummary([]);
        });
        updateFormMapSummary([]);
        setStatus('Ubicación marcada. Puedes arrastrar el marcador o dibujar el perímetro.');
      }
      return;
    }
    drawPoints.push([event.latlng.lng, event.latlng.lat]);
    const latLngs = drawPoints.map((point) => [point[1], point[0]]);
    if (previewLine) map.removeLayer(previewLine);
    previewLine = L.polyline(latLngs, { color: '#255b37', dashArray: '6 5' }).addTo(map);
    const vertex = L.circleMarker(event.latlng, {
      radius: 5, color: '#1e3d28', fillColor: '#fff', fillOpacity: 1, weight: 2
    }).addTo(map);
    drawMarkers.push(vertex);
    document.getElementById('undo-point').disabled = drawPoints.length === 0;
    const polygonMode = drawingMode === 'polygon';
    document.getElementById('finish-perimeter').disabled = polygonMode && drawPoints.length < 3;
    document.getElementById('finish-line').disabled = !polygonMode && drawPoints.length < 2;
    updateMeasurements(drawPoints, polygonMode && drawPoints.length >= 3);
  }

  function finishDrawing() {
    if (!drawing || drawingMode !== 'polygon' || drawPoints.length < 3) {
      setStatus('Agrega al menos tres vértices para finalizar el campo.');
      return;
    }
    if (hasSelfIntersection(drawPoints)) {
      setStatus('El perímetro se cruza a sí mismo. Ajusta los vértices antes de guardar.');
      return;
    }
    if (isPlotForm && !polygonInsideParent(drawPoints)) {
      setStatus('El potrero debe quedar completamente dentro del límite verde del predio. Ajusta el dibujo o enfoca el predio.');
      return;
    }
    const drawnAreaHa = polygonAreaSquareMetres(drawPoints) / 10000;
    const availableHectares = Number(areaInput?.max);
    if (isPlotForm && Number.isFinite(availableHectares) &&
        Number(drawnAreaHa.toFixed(4)) > availableHectares) {
      setStatus('La superficie dibujada supera las ' +
        availableHectares.toLocaleString('es-CL', { maximumFractionDigits: 4 }) +
        ' ha disponibles en este predio. Reduce el perímetro o enfoca el predio para revisar el límite.');
      return;
    }
    const feature = {
      type: 'Feature',
      properties: {},
      geometry: { type: 'Polygon', coordinates: [[...drawPoints.map((point) => point.slice()), drawPoints[0].slice()]] }
    };
    stopDrawing();
    addCurrentLayer(feature, false);
    if (isPredioForm) {
      if (perimeterAcceptedInput) perimeterAcceptedInput.value = '';
      setPerimeterControls(true, false);
      setStatus('Perímetro cerrado. Revisa el terreno y selecciona “Aceptar perímetro”.');
    } else {
      setStatus('Perímetro dibujado. La superficie se volverá a validar en el servidor al guardar.');
    }
  }

  function finishLineMeasurement() {
    if (!drawing || drawingMode !== 'line' || drawPoints.length < 2) {
      setStatus('Marca al menos dos puntos para medir una línea.');
      return;
    }
    if (previewLine) {
      savedMeasurement = previewLine;
      previewLine = null;
      document.getElementById('clear-measurement').hidden = false;
    }
    const length = perimeterMetres(drawPoints, false);
    stopDrawing();
    const areaMessage = document.getElementById('live-area');
    if (areaMessage) areaMessage.textContent = 'Medición lineal terminada. Esta línea no cambia el perímetro guardado.';
    document.getElementById('live-perimeter').textContent = 'Longitud medida: ' + formatLength(length);
    setStatus('Medición lista. La línea es temporal y no modifica el terreno guardado.');
  }

  function clearLineMeasurement() {
    if (savedMeasurement) map.removeLayer(savedMeasurement);
    savedMeasurement = null;
    document.getElementById('clear-measurement').hidden = true;
    if (currentLayer) setAreaAndGeometry();
    else {
      document.getElementById('live-perimeter').textContent = '';
      document.getElementById('live-area').textContent = '';
      updateFormMapSummary([]);
    }
    setStatus('Medición lineal eliminada. El perímetro guardado no cambió.');
  }

  function clearPerimeter() {
    if (currentLayer && !window.confirm('¿Quitar el perímetro guardado? Podrás indicar una superficie manual.')) return;
    if (drawing) stopDrawing();
    if (currentLayer) map.removeLayer(currentLayer);
    currentLayer = null;
    if (geojsonInput) geojsonInput.value = '';
    if (legacyPerimeterInput) legacyPerimeterInput.value = '[]';
    if (areaInput) areaInput.readOnly = false;
    if (latitudeInput) latitudeInput.value = '';
    if (longitudeInput) longitudeInput.value = '';
    if (areaInput) areaInput.value = '';
    if (marker) map.removeLayer(marker);
    marker = null;
    document.getElementById('live-area').textContent = '';
    const perimeterOutput = document.getElementById('live-perimeter');
    if (perimeterOutput) perimeterOutput.textContent = '';
    document.getElementById('toggle-edit').hidden = true;
    setStatus('Perímetro quitado. Puedes indicar una ubicación y superficie manuales.');
  }

  function cancelDrawing() {
    if (!drawing) return;
    stopDrawing();
    setStatus('Dibujo cancelado. El perímetro guardado permanece sin cambios.');
    if (currentLayer) setAreaAndGeometry();
    else {
      document.getElementById('live-area').textContent = '';
      document.getElementById('live-perimeter').textContent = '';
    }
  }

  function addContextLayers() {
    if (!form) return;
    const predioId = document.getElementById('id_predio');
    const activeFarmMatch = window.location.pathname.match(/predios\/(\d+)\//);
    const activeFarmId = activeFarmMatch ? activeFarmMatch[1] : '';
    const editingFarm = /predios\/\d+\/editar/.test(window.location.pathname);
    const activePlotId = window.location.pathname.match(/potreros\/(\d+)\/editar/);
    const activeId = activePlotId ? activePlotId[1] : '';
    const activePredioId = predioId ? predioId.value : (isPlotForm ? activeFarmId : '');
    parentFarm = isPlotForm
      ? farmData.predios.find((farm) => String(farm.id) === activePredioId) || null
      : null;
    farmData.predios.forEach((farm) => {
      if (editingFarm && String(farm.id) === activeFarmId) return;
      if (farm.geojson && (!activePredioId || String(farm.id) === activePredioId)) {
        const layer = L.geoJSON(farm.geojson, {
          style: isPlotForm && String(farm.id) === activePredioId
            ? { color: '#18713c', weight: 5, fillColor: '#64a76d', fillOpacity: 0.1, dashArray: '8 5' }
            : { color: '#496a8a', weight: 2, fillColor: '#8daac4', fillOpacity: 0.08 },
          interactive: !form
        }).addTo(map);
        if (isPlotForm && String(farm.id) === activePredioId) parentFarmLayer = layer;
        if (!form) layer.on('click', () => setSelectedTerrain(farm, null));
        viewBounds.extend(layer.getBounds());
      } else if (isPlotForm && String(farm.id) === activePredioId &&
          farm.lat !== null && farm.lng !== null) {
        parentFarmLayer = L.marker([farm.lat, farm.lng]).addTo(map);
        viewBounds.extend(parentFarmLayer.getLatLng());
      }
    });
    farmData.plots.forEach((plot) => {
      if (activeId && String(plot.id) === activeId) return;
      if (activePredioId && String(plot.predio) !== activePredioId) return;
      if (plot.geojson) {
        const layer = L.geoJSON(plot.geojson, {
          style: { color: '#7d8c78', weight: 2, fillColor: '#aebda5', fillOpacity: 0.08 }
        }).addTo(map);
        viewBounds.extend(layer.getBounds());
      }
    });
  }

  const FARM_STYLE = { color: '#3d6e8c', weight: 2, dashArray: '6 4', fillColor: '#8daac4', fillOpacity: 0.06 };
  function plotStyle(plot) {
    return plot && plot.crop
      ? { color: '#2f6b3f', weight: 2, fillColor: '#7cb07a', fillOpacity: 0.32 }
      : { color: '#6f7d69', weight: 2, fillColor: '#c4cfbd', fillOpacity: 0.22 };
  }

  function resetTerrainStyles() {
    farmLayers.forEach((layer) => {
      if (layer.setStyle) layer.setStyle(FARM_STYLE);
      else if (layer.setOpacity) layer.setOpacity(0.8);
    });
    plotLayers.forEach((layer, id) => {
      const plot = farmData.plots.find((item) => String(item.id) === String(id));
      if (layer.setStyle) layer.setStyle(plotStyle(plot));
      else if (layer.setOpacity) layer.setOpacity(0.8);
    });
  }

  function layerBounds(layer) {
    if (layer.getBounds) return layer.getBounds();
    const bounds = L.latLngBounds([]);
    if (layer.getLatLng) bounds.extend(layer.getLatLng());
    return bounds;
  }

  function selectFarm(farm, includePlots) {
    if (!farm) return;
    selectedFarmId = String(farm.id);
    selectedPlotId = '';
    resetTerrainStyles();
    const farmLayer = farmLayers.get(selectedFarmId);
    if (farmLayer) {
      if (farmLayer.setStyle) {
        farmLayer.setStyle({ color: '#1e3d28', weight: 4, dashArray: null, fillColor: '#74a567', fillOpacity: 0.12 });
      } else if (farmLayer.setOpacity) farmLayer.setOpacity(1);
      map.fitBounds(layerBounds(farmLayer), { padding: [28, 28], maxZoom: 17 });
    } else if (map && farm.lat !== null && farm.lng !== null) {
      map.setView([farm.lat, farm.lng], 16);
    }
    const farmPlots = farmData.plots.filter((plot) => String(plot.predio) === selectedFarmId);
    if (includePlots) {
      const plotBounds = window.L ? L.latLngBounds([]) : null;
      farmPlots.forEach((plot) => {
        const layer = plotLayers.get(String(plot.id));
        if (layer) {
          if (layer.setStyle) {
            layer.setStyle({ color: '#255b37', weight: 3, fillColor: '#74a567', fillOpacity: 0.28 });
          } else if (layer.setOpacity) layer.setOpacity(1);
          if (plotBounds) plotBounds.extend(layerBounds(layer));
        }
      });
      if (map && plotBounds.isValid()) map.fitBounds(plotBounds, { padding: [28, 28], maxZoom: 17 });
      setStatus(farmPlots.length
        ? 'Mostrando los potreros registrados en «' + farm.name + '».'
        : 'Este predio todavía no tiene potreros registrados.');
    } else {
      setStatus(farmPlots.length
        ? 'Predio seleccionado. Elige uno de sus potreros o consulta sus datos.'
        : 'Este predio todavía no tiene potreros registrados. Puedes registrar el primero desde el panel.');
    }
    setSelectedTerrain(farm, null);
  }

  function selectPlot(plot) {
    const farm = farmData.predios.find((item) => String(item.id) === String(plot.predio));
    if (!farm) return;
    selectedFarmId = String(farm.id);
    selectedPlotId = String(plot.id);
    resetTerrainStyles();
    const layer = plotLayers.get(selectedPlotId);
    if (layer) {
      if (layer.setStyle) {
        layer.setStyle({ color: '#c9a227', weight: 5, fillColor: '#55a85c', fillOpacity: 0.5 });
        if (layer.bringToFront) layer.bringToFront();
      } else if (layer.setOpacity) layer.setOpacity(1);
      map.fitBounds(layerBounds(layer), { padding: [32, 32], maxZoom: 18 });
    } else if (map && plot.lat !== null && plot.lng !== null) {
      map.setView([plot.lat, plot.lng], 17);
    } else {
      const farmLayer = farmLayers.get(selectedFarmId);
      if (farmLayer) map.fitBounds(layerBounds(farmLayer), { padding: [28, 28], maxZoom: 17 });
    }
    setStatus('Potrero «' + plot.name + '» seleccionado en «' + farm.name + '».');
    setSelectedTerrain(farm, plot);
  }

  function showAllFarms() {
    selectedFarmId = '';
    selectedPlotId = '';
    resetTerrainStyles();
    document.querySelectorAll('[data-select-farm]').forEach((button) => {
      button.classList.remove('is-selected');
      button.setAttribute('aria-pressed', 'false');
    });
    document.querySelectorAll('[data-farm-plots]').forEach((group) => { group.hidden = true; });
    document.querySelectorAll('[data-plot-card]').forEach((card) => { card.classList.remove('is-selected'); });
    document.querySelectorAll('[data-select-plot]').forEach((button) => {
      button.classList.remove('is-selected');
      button.setAttribute('aria-pressed', 'false');
    });
    const plotsPanel = document.getElementById('farm-plots-picker');
    if (plotsPanel) plotsPanel.hidden = true;
    const details = document.getElementById('selected-terrain-details');
    const empty = document.getElementById('selected-terrain-empty');
    if (details) details.hidden = true;
    if (farmData.predios.length) renderOverview();
    else if (empty) {
      empty.hidden = false;
      empty.textContent = farmData.predios.length
        ? (farmData.plots.length
          ? 'Selecciona un predio o potrero en el listado o en el mapa.'
          : 'Selecciona un predio para registrar y administrar sus potreros.')
        : 'No tienes predios registrados.';
    }
    setStatus(farmData.predios.length
      ? (farmData.plots.length
        ? 'Selecciona un potrero en el listado o directamente en el mapa.'
        : 'Selecciona un predio para registrar y administrar sus potreros.')
      : 'No tienes predios registrados.');
    const showPlotsButton = document.getElementById('show-selected-farm-plots');
    if (showPlotsButton) showPlotsButton.disabled = true;
    if (map && viewBounds.isValid()) map.fitBounds(viewBounds, { padding: [24, 24], maxZoom: 16 });
    else if (map) map.setView(melipillaCenter, 11);
    const params = new URLSearchParams(window.location.search);
    params.delete('predio'); params.delete('potrero');
    window.history.replaceState(null, '', window.location.pathname + (params.toString() ? '?' + params.toString() : ''));
  }

  function loadFormGeometry() {
    if (isPlotForm) {
      try {
        const points = JSON.parse(legacyPerimeterInput.value || '[]');
        if (Array.isArray(points) && points.length >= 3) {
          addCurrentLayer({
            type: 'Feature',
            properties: {},
            geometry: { type: 'Polygon', coordinates: [[...points.map((point) => point.slice()), points[0].slice()]] }
          }, false);
        }
      } catch (error) {
        setStatus('No se pudo cargar el perímetro existente. Puedes corregirlo dibujando uno nuevo.');
        console.error('No se pudo interpretar el perímetro del potrero.', error);
      }
    } else if (geojsonInput && geojsonInput.value) {
      try {
        const geometry = JSON.parse(geojsonInput.value);
        originalFeature = JSON.parse(JSON.stringify(geometry));
        addCurrentLayer(geometry, false);
      } catch (error) {
        setStatus('No se pudo cargar el perímetro GeoJSON existente. Corrige el registro o vuelve a dibujarlo.');
        console.error('No se pudo interpretar el perímetro del predio.', error);
      }
    }
    if (!currentLayer && latitudeInput?.value && longitudeInput?.value) {
      marker = L.marker([Number(latitudeInput.value), Number(longitudeInput.value)], { draggable: true }).addTo(map);
      marker.on('dragend', (event) => {
        latitudeInput.value = event.target.getLatLng().lat.toFixed(6);
        longitudeInput.value = event.target.getLatLng().lng.toFixed(6);
        updateFormMapSummary([]);
      });
      updateFormMapSummary([]);
      viewBounds.extend(marker.getLatLng());
    }
  }

  function showMap() {
    viewBounds = L.latLngBounds([]);
    map = L.map(mapElement, { zoomControl: true }).setView(melipillaCenter, form ? 14 : 11);
    configureTiles();
    addContextLayers();
    if (!form) {
      farmData.predios.forEach((farm) => {
        if (farm.geojson) {
          const layer = L.geoJSON(farm.geojson, { style: FARM_STYLE }).addTo(map);
          layer.on('click', () => selectFarm(farm, false));
          farmLayers.set(String(farm.id), layer);
          viewBounds.extend(layer.getBounds());
        } else if (farm.lat !== null && farm.lng !== null) {
          const pin = L.marker([farm.lat, farm.lng]).addTo(map);
          pin.on('click', () => selectFarm(farm, false));
          farmLayers.set(String(farm.id), pin);
          viewBounds.extend(pin.getLatLng());
        }
      });
      farmData.plots.forEach((plot) => {
        const predio = farmData.predios.find((item) => String(item.id) === String(plot.predio));
        const fallbackFeature = Array.isArray(plot.coordinates) && plot.coordinates.length >= 3
          ? {
            type: 'Feature',
            properties: {},
            geometry: { type: 'Polygon', coordinates: [[...plot.coordinates, plot.coordinates[0]]] }
          }
          : null;
        const feature = plot.geojson || fallbackFeature;
        if (feature) {
          const layer = L.geoJSON(feature, { style: plotStyle(plot) }).addTo(map);
          layer.on('click', (event) => {
            if (event && event.originalEvent) L.DomEvent.stopPropagation(event);
            selectPlot(plot);
          });
          layer.bindTooltip(plotLabel(plot), {
            permanent: true, direction: 'center', className: 'plot-label', opacity: 1
          });
          plotLayers.set(String(plot.id), layer);
          viewBounds.extend(layer.getBounds());
        } else if (plot.lat !== null && plot.lng !== null) {
          const pin = L.marker([plot.lat, plot.lng]).addTo(map);
          pin.bindTooltip(plotLabel(plot), { permanent: true, direction: 'top', className: 'plot-label', offset: [0, -20] });
          pin.on('click', () => selectPlot(plot));
          plotLayers.set(String(plot.id), pin);
          viewBounds.extend(pin.getLatLng());
        }
      });
      if (!farmData.predios.length) setStatus('No tienes predios registrados.');
      else if (!farmData.plots.length) setStatus('Selecciona un predio para registrar y administrar sus potreros.');
      else setStatus('Selecciona un potrero en el listado o directamente en el mapa.');
      const syncLabels = () => mapElement.classList.toggle('hide-plot-labels', map.getZoom() < 15);
      map.on('zoomend', syncLabels);
      syncLabels();
      bindListControls();
    } else {
      loadFormGeometry();
      map.on('click', addDrawingPoint);
      document.getElementById('draw-perimeter').addEventListener('click', () => beginDrawing('polygon'));
      document.getElementById('measure-line').addEventListener('click', () => beginDrawing('line'));
      document.getElementById('cancel-drawing').addEventListener('click', cancelDrawing);
      document.getElementById('finish-line').addEventListener('click', finishLineMeasurement);
      document.getElementById('clear-measurement').addEventListener('click', clearLineMeasurement);
      document.addEventListener('keydown', (event) => {
        if (event.key === 'Escape') cancelDrawing();
      });
      document.getElementById('undo-point').addEventListener('click', () => {
        if (!drawing || !drawPoints.length) return;
        drawPoints.pop();
        const markerToRemove = drawMarkers.pop();
        if (markerToRemove) map.removeLayer(markerToRemove);
        if (previewLine) map.removeLayer(previewLine);
        previewLine = drawPoints.length ? L.polyline(drawPoints.map((point) => [point[1], point[0]]), {
          color: '#255b37', dashArray: '6 5'
        }).addTo(map) : null;
        document.getElementById('undo-point').disabled = drawPoints.length === 0;
        document.getElementById('finish-perimeter').disabled = drawPoints.length < 3;
        document.getElementById('finish-line').disabled = drawPoints.length < 2;
        if (drawPoints.length >= 2) {
          updateMeasurements(drawPoints, drawingMode === 'polygon' && drawPoints.length >= 3);
        } else {
          const perimeterOutput = document.getElementById('live-perimeter');
          if (perimeterOutput) perimeterOutput.textContent = '';
          document.getElementById('live-area').textContent = '';
        }
      });
      document.getElementById('finish-perimeter').addEventListener('click', finishDrawing);
      const clearButton = document.getElementById('clear-perimeter');
      if (clearButton) clearButton.addEventListener('click', clearPerimeter);
      const editButton = document.getElementById(isPredioForm ? 'edit-perimeter' : 'toggle-edit');
      if (editButton) editButton.addEventListener('click', enableEditing);
      const acceptButton = document.getElementById('accept-perimeter');
      if (acceptButton) acceptButton.addEventListener('click', showPerimeterConfirmation);
      const cancelPerimeterButton = document.getElementById('cancel-perimeter');
      if (cancelPerimeterButton) cancelPerimeterButton.addEventListener('click', cancelPerimeterChanges);
      const continueButton = document.getElementById('confirm-and-continue');
      if (continueButton) continueButton.addEventListener('click', continueAfterConfirmation);
      const returnButton = document.getElementById('return-to-edit');
      if (returnButton) returnButton.addEventListener('click', editConfirmedPerimeter);
      document.getElementById('locate-me').addEventListener('click', () => {
        if (!navigator.geolocation) {
          setStatus('Este navegador no permite obtener la ubicación. Marca el punto manualmente en el mapa.');
          return;
        }
        navigator.geolocation.getCurrentPosition((position) => {
          const point = L.latLng(position.coords.latitude, position.coords.longitude);
          if (marker) map.removeLayer(marker);
          marker = L.marker(point, { draggable: true }).addTo(map);
          latitudeInput.value = point.lat.toFixed(6);
          longitudeInput.value = point.lng.toFixed(6);
          marker.on('dragend', (event) => {
            latitudeInput.value = event.target.getLatLng().lat.toFixed(6);
            longitudeInput.value = event.target.getLatLng().lng.toFixed(6);
            updateFormMapSummary([]);
          });
          updateFormMapSummary([]);
          map.setView(point, 16);
          setStatus('Ubicación detectada. Puedes ajustar el marcador y guardar.');
        }, () => {
          setStatus('No fue posible obtener tu ubicación. Marca el punto manualmente en el mapa.');
        }, { timeout: 10000 });
      });
      document.getElementById('center-map').addEventListener('click', () => {
        if (isPlotForm && parentFarmLayer) {
          map.fitBounds(layerBounds(parentFarmLayer), { padding: [42, 42], maxZoom: 18 });
        } else if (viewBounds.isValid()) map.fitBounds(viewBounds, { padding: [24, 24], maxZoom: 17 });
        else map.setView(melipillaCenter, 12);
      });
      form.addEventListener('submit', (event) => {
        if (drawing) {
          event.preventDefault();
          setStatus('Finaliza o cancela el dibujo antes de guardar.');
        }
      });
      if (window.L && L.PM) {
        L.PM.setOptIn(true);
      }
      if (isPlotForm && parentFarm?.geojson) {
        setStatus('Límite verde punteado: predio seleccionado. Dibuja el potrero completamente dentro de ese contorno.');
      } else if (isPlotForm) {
        setStatus('Este predio no tiene un perímetro registrado. La superficie disponible se valida al dibujar y guardar.');
      } else {
        setStatus('Elige “Dibujar campo” para medir área y perímetro o “Medir línea” para un lindero.');
      }
    }

    if (isPlotForm && parentFarmLayer && mapElement.dataset.focusParentOnly !== 'false') {
      map.fitBounds(layerBounds(parentFarmLayer), { padding: [42, 42], maxZoom: 18 });
    } else if (viewBounds.isValid()) map.fitBounds(viewBounds, { padding: [24, 24], maxZoom: 17 });
    window.setTimeout(() => map.invalidateSize(), 0);
    if (!form) selectInitialTerrain();
  }

  function plotLabel(plot) {
    return plot.name + (plot.crop ? ' · ' + plot.crop : '');
  }

  function renderOverview() {
    const details = document.getElementById('selected-terrain-details');
    const emptyState = document.getElementById('selected-terrain-empty');
    if (!details || !emptyState || !farmData.predios.length) return;
    details.replaceChildren();
    const stats = farmData.stats || {};
    const head = el('div', 'terrain-panel-head');
    head.append(el('span', 'terrain-eyebrow', 'Resumen de tu campo'), el('h3', '', 'Todos los predios'));
    details.append(head);
    const kpis = el('div', 'overview-kpis');
    [['Predios', stats.predios], ['Potreros', stats.potreros], ['Superficie', fmtHa(stats.superficie_predios, 2) + ' ha'],
      ['Con cultivo', farmData.plots.filter((plot) => plot.crop).length]].forEach(([label, value]) => {
      const box = el('div', 'overview-kpi');
      box.append(el('span', '', label), el('strong', '', String(value ?? 0)));
      kpis.append(box);
    });
    details.append(kpis);
    if (farmData.plots.length) {
      details.append(el('p', 'overview-hint', 'Selecciona un potrero para ver su ficha y asignar cultivo:'));
      const list = el('ul', 'overview-plots');
      farmData.plots.forEach((plot) => {
        const item = el('li');
        const button = el('button', 'overview-plot');
        button.type = 'button';
        const swatch = el('span', 'overview-swatch' + (plot.crop ? ' has-crop' : ''));
        const text = el('span', 'overview-text');
        text.append(el('strong', '', plot.name), el('small', '', plot.farmName + ' · ' + fmtHa(plot.areaHa, 2) + ' ha · ' + (plot.crop || 'sin cultivo')));
        button.append(swatch, text, el('span', 'overview-status', plot.status || ''));
        button.addEventListener('click', () => selectPlot(plot));
        item.append(button);
        list.append(item);
      });
      details.append(list);
    } else {
      details.append(el('p', 'terrain-no-crop', 'Aún no tienes potreros. Selecciona un predio y registra el primero.'));
    }
    emptyState.hidden = true;
    details.hidden = false;
  }

  function selectInitialTerrain() {
    const initialPlot = farmData.plots.find((item) => String(item.id) === mapElement.dataset.initialPlot);
    if (initialPlot) { selectPlot(initialPlot); return; }
    const initialFarm = farmData.predios.find((item) => String(item.id) === mapElement.dataset.initialFarm);
    if (initialFarm) selectFarm(initialFarm, false);
    else renderOverview();
  }

  function bindListControls() {
    document.querySelectorAll('[data-select-farm]').forEach((button) => {
      button.addEventListener('click', () => {
        const farm = farmData.predios.find((item) => String(item.id) === button.dataset.selectFarm);
        selectFarm(farm, false);
      });
    });
    document.querySelectorAll('[data-select-plot]').forEach((button) => {
      button.addEventListener('click', () => {
        const plot = farmData.plots.find((item) => String(item.id) === button.dataset.selectPlot);
        if (plot) selectPlot(plot);
      });
    });
    document.getElementById('show-all-farms')?.addEventListener('click', showAllFarms);
    document.getElementById('show-selected-farm-plots')?.addEventListener('click', () => {
      const farm = farmData.predios.find((item) => String(item.id) === selectedFarmId);
      if (farm) selectFarm(farm, true);
    });
    document.addEventListener('click', (event) => {
      const trigger = event.target.closest('[data-assign-crop]');
      if (!trigger) return;
      const plot = farmData.plots.find((item) => String(item.id) === trigger.dataset.assignCrop);
      if (plot) openCropDialog(plot);
    });
    setupCropDialog();
  }

  // ---------- Asignar cultivo por temporada ----------
  const cropDialog = document.getElementById('crop-dialog');
  let dialogPlot = null;

  function seasonOptions(selected) {
    const today = new Date();
    const start = today.getMonth() >= 6 ? today.getFullYear() : today.getFullYear() - 1;
    const values = [start - 1, start, start + 1, start + 2].map((year) => year + '-' + (year + 1));
    if (selected && !values.includes(selected)) values.unshift(selected);
    return { values, current: start + '-' + (start + 1) };
  }

  function catalogCrops() {
    const node = document.getElementById('agro-catalog');
    try { return JSON.parse(node.textContent) || {}; } catch (error) { return {}; }
  }

  function setupCropDialog() {
    if (!cropDialog || cropDialog.dataset.ready) return;
    cropDialog.dataset.ready = '1';
    const catalog = catalogCrops();
    const crops = (catalog.cultivos || []).filter((crop) => crop.active !== false);
    const select = document.getElementById('crop-select');
    const datalist = document.getElementById('crop-variety-options');
    select.replaceChildren(new Option(crops.length ? 'Selecciona un cultivo' : 'Sin cultivos en el catálogo', ''));
    crops.forEach((crop) => select.add(new Option(crop.name, String(crop.id))));
    const refreshVarieties = () => {
      datalist.replaceChildren();
      ((catalog.varieties || {})[select.value] || []).forEach((variety) => datalist.append(new Option(variety, variety)));
    };
    select.addEventListener('change', refreshVarieties);
    document.getElementById('crop-empty-catalog').hidden = crops.length > 0;
    document.getElementById('crop-fields').hidden = crops.length === 0;
    document.getElementById('crop-save').disabled = crops.length === 0;
    cropDialog.querySelectorAll('[data-close-dialog]').forEach((button) => {
      button.addEventListener('click', () => cropDialog.close());
    });
    document.getElementById('crop-sowing').addEventListener('change', (event) => {
      const value = event.target.value;
      if (!value) return;
      const [year, month] = value.split('-').map(Number);
      const start = month >= 7 ? year : year - 1;
      const label = start + '-' + (start + 1);
      const seasonSelect = document.getElementById('crop-season');
      if (![...seasonSelect.options].some((option) => option.value === label)) seasonSelect.add(new Option(label, label));
      seasonSelect.value = label;
    });
    document.getElementById('crop-form').addEventListener('submit', saveCropAssignment);
    cropDialog._refreshVarieties = refreshVarieties;
  }

  function openCropDialog(plot) {
    if (!cropDialog) return;
    setupCropDialog();
    dialogPlot = plot;
    const farm = farmData.predios.find((item) => String(item.id) === String(plot.predio));
    document.getElementById('crop-dialog-title').textContent = plot.crop ? 'Cambiar cultivo' : 'Asignar cultivo';
    document.getElementById('crop-farm').textContent = farm ? farm.name : '—';
    document.getElementById('crop-plot').textContent = plot.name;
    document.getElementById('crop-area').textContent = fmtHa(plot.areaHa, 2) + ' ha';
    document.getElementById('crop-current').textContent = plot.crop
      ? plot.crop + (plot.variety ? ' · ' + plot.variety : '') + (plot.season ? ' · ' + plot.season : '')
      : 'Sin cultivo asignado';
    const select = document.getElementById('crop-select');
    select.value = '';
    document.getElementById('crop-variety').value = '';
    document.getElementById('crop-sowing').value = '';
    document.getElementById('crop-harvest').value = '';
    document.getElementById('crop-notes').value = '';
    document.getElementById('crop-status').value = 'planned';
    document.getElementById('crop-error').textContent = '';
    const seasons = seasonOptions();
    const seasonSelect = document.getElementById('crop-season');
    seasonSelect.replaceChildren(...seasons.values.map((value) => new Option(value, value)));
    seasonSelect.value = seasons.current;
    const closePrevious = document.getElementById('crop-close-previous');
    closePrevious.checked = true;
    closePrevious.parentElement.hidden = !(plot.seasons || []).length && !plot.crop;
    cropDialog._refreshVarieties();
    if (typeof cropDialog.showModal === 'function') cropDialog.showModal();
    else cropDialog.setAttribute('open', '');
    select.focus();
  }

  async function saveCropAssignment(event) {
    event.preventDefault();
    const errorBox = document.getElementById('crop-error');
    const cropId = document.getElementById('crop-select').value;
    const sowing = document.getElementById('crop-sowing').value;
    const harvest = document.getElementById('crop-harvest').value;
    const status = document.getElementById('crop-status').value;
    errorBox.textContent = '';
    if (!cropId) { errorBox.textContent = 'Selecciona un cultivo del catálogo.'; return; }
    if (sowing && harvest && harvest < sowing) { errorBox.textContent = 'La fecha de cosecha no puede ser anterior a la siembra.'; return; }
    if (status === 'sown' && !sowing) { errorBox.textContent = 'Indica la fecha de siembra para marcar el cultivo como sembrado.'; return; }
    if (status === 'harvested' && !harvest) { errorBox.textContent = 'Indica la fecha de cosecha para marcarlo como cosechado.'; return; }
    const button = document.getElementById('crop-save');
    button.disabled = true;
    try {
      const token = cropDialog.querySelector('[name=csrfmiddlewaretoken]').value;
      const response = await fetch(dialogPlot.assignUrl, {
        method: 'POST',
        credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': token, Accept: 'application/json' },
        body: JSON.stringify({
          mode: 'new',
          crop_id: cropId,
          variety: document.getElementById('crop-variety').value,
          season: document.getElementById('crop-season').value,
          sowing_date: sowing || null,
          harvest_date: harvest || null,
          status,
          notes: document.getElementById('crop-notes').value,
          close_previous: document.getElementById('crop-close-previous').checked,
        }),
      });
      if (!(response.headers.get('Content-Type') || '').includes('application/json')) {
        throw new Error('Tu sesión expiró. Recarga la página e inicia sesión nuevamente.');
      }
      const data = await response.json();
      if (!response.ok || !data.ok) throw new Error(data.error || 'No se pudo guardar el cultivo.');
      applyPlotUpdate(data.plot);
      cropDialog.close();
      setStatus(data.message);
    } catch (error) {
      errorBox.textContent = error.message;
    } finally {
      button.disabled = false;
    }
  }

  function applyPlotUpdate(updated) {
    const index = farmData.plots.findIndex((item) => String(item.id) === String(updated.id));
    if (index === -1) return;
    farmData.plots[index] = { ...farmData.plots[index], ...updated };
    const plot = farmData.plots[index];
    const layer = plotLayers.get(String(plot.id));
    if (layer && layer.setTooltipContent) layer.setTooltipContent(plotLabel(plot));
    document.querySelectorAll('[data-plot-crop-label="' + plot.id + '"]').forEach((node) => {
      node.textContent = plot.crop + (plot.variety ? ' · ' + plot.variety : '');
    });
    document.querySelectorAll('[data-plot-status="' + plot.id + '"]').forEach((node) => {
      node.textContent = plot.status;
    });
    document.querySelectorAll('[data-assign-crop="' + plot.id + '"]').forEach((node) => {
      if (node.tagName === 'BUTTON') node.textContent = 'Cambiar cultivo';
    });
    selectPlot(plot);
  }

  if (!window.L) {
    if (!form) {
      // Sin cartografía el listado, el panel y la asignación de cultivos siguen funcionando.
      setStatus('No se pudo cargar el mapa (revisa la conexión). Puedes seleccionar predios y potreros desde el listado.');
      bindListControls();
      selectInitialTerrain();
      return;
    }
    setStatus('No se pudo cargar Leaflet. Comprueba la conexión y recarga el mapa; también puedes ingresar la superficie y coordenadas manualmente.');
    ['draw-perimeter', 'undo-point', 'finish-perimeter', 'toggle-edit', 'clear-perimeter', 'locate-me', 'center-map']
      .forEach((id) => {
        const button = document.getElementById(id);
        if (button) button.disabled = true;
      });
    return;
  }
  showMap();
})();
