/* Selector de vista de «Mis predios y potreros»: Lista / Tarjetas / Mapa. Solo presentación. */
(function () {
  'use strict';
  var KEY = 'agroasesor.prediosView';
  var list = document.getElementById('farm-picker-list');
  var buttons = document.querySelectorAll('[data-view-mode]');
  if (!list || !buttons.length) return;

  function read() {
    try {
      var value = window.localStorage.getItem(KEY);
      return value === 'list' ? 'list' : 'cards';
    } catch (error) {
      return 'cards';
    }
  }

  function write(mode) {
    try {
      window.localStorage.setItem(KEY, mode);
    } catch (error) {
      /* sin almacenamiento: la vista no se recuerda */
    }
  }

  function apply(mode) {
    list.dataset.view = mode;
    buttons.forEach(function (button) {
      var active = button.dataset.viewMode === mode;
      button.classList.toggle('is-active', active);
      button.setAttribute('aria-pressed', String(active));
    });
  }

  buttons.forEach(function (button) {
    button.addEventListener('click', function () {
      apply(button.dataset.viewMode);
      write(button.dataset.viewMode);
    });
  });

  var focusMap = document.querySelector('[data-view-focus="map"]');
  if (focusMap) {
    focusMap.addEventListener('click', function () {
      var map = document.querySelector('.map-card') || document.getElementById('farm-map');
      if (!map) return;
      map.scrollIntoView({ behavior: 'smooth', block: 'start' });
      map.classList.add('is-focused');
      window.setTimeout(function () {
        map.classList.remove('is-focused');
      }, 1400);
    });
  }

  apply(read());
})();
