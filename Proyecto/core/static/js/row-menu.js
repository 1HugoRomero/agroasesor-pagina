/* Menú contextual «⋯» reutilizable: abre/cierra, teclado, y se posiciona sin quedar recortado por la tarjeta. */
(function () {
  'use strict';
  var openMenu = null;

  function items(menu) {
    return Array.prototype.slice.call(menu.querySelectorAll('.row-menu-item')).filter(function (item) {
      return !item.hidden;
    });
  }

  function place(menu) {
    var trigger = menu.querySelector('.row-menu-trigger');
    var list = menu.querySelector('.row-menu-list');
    if (!trigger || !list) return;
    var rect = trigger.getBoundingClientRect();
    var width = list.offsetWidth;
    var height = list.offsetHeight;
    var left = Math.min(Math.max(8, rect.right - width), window.innerWidth - width - 8);
    var top = rect.bottom + 6;
    if (top + height > window.innerHeight - 8) top = Math.max(8, rect.top - height - 6);
    list.style.left = left + 'px';
    list.style.top = top + 'px';
  }

  function close(returnFocus) {
    if (!openMenu) return;
    var trigger = openMenu.querySelector('.row-menu-trigger');
    openMenu.classList.remove('is-open');
    if (trigger) {
      trigger.setAttribute('aria-expanded', 'false');
      if (returnFocus) trigger.focus();
    }
    openMenu = null;
  }

  function open(menu) {
    close(false);
    menu.classList.add('is-open');
    var trigger = menu.querySelector('.row-menu-trigger');
    if (trigger) trigger.setAttribute('aria-expanded', 'true');
    openMenu = menu;
    place(menu);
  }

  document.addEventListener('click', function (event) {
    var trigger = event.target.closest('.row-menu-trigger');
    if (trigger) {
      event.preventDefault();
      var menu = trigger.closest('.row-menu');
      if (menu === openMenu) close(false);
      else open(menu);
      return;
    }
    if (openMenu && !event.target.closest('.row-menu-list')) {
      close(false);
      return;
    }
    if (openMenu && event.target.closest('.row-menu-item')) close(false);
  });

  document.addEventListener('keydown', function (event) {
    if (!openMenu) return;
    if (event.key === 'Escape') {
      event.preventDefault();
      close(true);
      return;
    }
    if (event.key !== 'ArrowDown' && event.key !== 'ArrowUp') return;
    var list = items(openMenu);
    if (!list.length) return;
    event.preventDefault();
    var index = list.indexOf(document.activeElement);
    if (event.key === 'ArrowDown') index = index < 0 ? 0 : (index + 1) % list.length;
    else index = index <= 0 ? list.length - 1 : index - 1;
    list[index].focus();
  });

  window.addEventListener('resize', function () {
    close(false);
  });
  window.addEventListener(
    'scroll',
    function () {
      close(false);
    },
    true,
  );
})();
