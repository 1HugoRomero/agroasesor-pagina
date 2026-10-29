(() => {
  'use strict';
  const geometryNode = document.getElementById('predio-detail-geometry');
  const mapElement = document.getElementById('predio-detail-map');
  const configNode = document.getElementById('maps-config');
  if (!geometryNode || !mapElement || !configNode || !window.L) return;

  const geometry = JSON.parse(geometryNode.textContent);
  const config = JSON.parse(configNode.textContent);
  const map = L.map(mapElement, { zoomControl: true });
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
  const status = document.getElementById('predio-map-status');
  function showMapStatus(message) {
    if (status) status.textContent = message;
  }
  [normalTiles, satelliteTiles].forEach((layer) => {
    layer.on('tileerror', () => {
      if (layer === activeTiles) {
        showMapStatus('No se cargaron algunas teselas del mapa. Comprueba la conexión o cambia la vista.');
      }
    });
    layer.on('tileload', () => {
      if (layer === activeTiles) showMapStatus('');
    });
  });
  normalTiles.addTo(map);
  document.querySelectorAll('[data-map-layer]').forEach((button) => {
    button.addEventListener('click', () => {
      const nextTiles = button.dataset.mapLayer === 'satellite' ? satelliteTiles : normalTiles;
      if (nextTiles !== activeTiles) {
        map.removeLayer(activeTiles);
        activeTiles = nextTiles;
        activeTiles.addTo(map);
      }
      document.querySelectorAll('[data-map-layer]').forEach((item) => {
        const selected = item === button;
        item.classList.toggle('is-active', selected);
        item.setAttribute('aria-pressed', String(selected));
      });
    });
  });
  const polygon = L.geoJSON(geometry, {
    style: { color: '#255b37', weight: 3, fillColor: '#74a567', fillOpacity: 0.3 }
  }).addTo(map);
  if (polygon.getBounds().isValid()) map.fitBounds(polygon.getBounds(), { padding: [24, 24] });

  const rawGeometry = geometry.type === 'Feature' ? geometry.geometry : geometry;
  const ring = rawGeometry.coordinates[0] || [];
  const vertices = ring.length > 1 && JSON.stringify(ring[0]) === JSON.stringify(ring[ring.length - 1])
    ? ring.slice(0, -1)
    : ring;
  vertices.forEach(([longitude, latitude]) => {
    L.circleMarker([latitude, longitude], {
      radius: 4,
      color: '#1e3d28',
      fillColor: '#fff',
      fillOpacity: 1,
      weight: 2
    }).addTo(map);
  });
  const vertexList = document.getElementById('predio-vertices');
  if (vertexList) {
    vertices.forEach(([longitude, latitude], index) => {
      const item = document.createElement('li');
      item.textContent = (index + 1) + '. ' + latitude.toFixed(6) + ', ' + longitude.toFixed(6);
      vertexList.appendChild(item);
    });
  }

  const tabs = [
    [document.getElementById('tab-information'), document.getElementById('predio-information')],
    [document.getElementById('tab-history'), document.getElementById('predio-history')]
  ];
  const activateTab = (button) => {
    tabs.forEach(([otherButton, otherPanel]) => {
      if (!otherButton || !otherPanel) return;
      const selected = otherButton === button;
      otherButton.classList.toggle('is-active', selected);
      otherButton.setAttribute('aria-selected', String(selected));
      otherPanel.hidden = !selected;
    });
  };
  tabs.forEach(([button, panel]) => {
    if (!button || !panel) return;
    button.addEventListener('click', () => activateTab(button));
  });
  if (window.location.hash === '#predio-history') {
    activateTab(document.getElementById('tab-history'));
  }
  window.setTimeout(() => map.invalidateSize(), 0);
})();
