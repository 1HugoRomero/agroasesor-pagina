(function () {
  const menuBtn = document.querySelector('[data-open-menu]');
  const sidebar = document.querySelector('.sidebar');
  const scrim = document.querySelector('.scrim');
  const profileBtn = document.querySelector('[data-profile]');
  const notesBtn = document.querySelector('[data-notes]');
  const profileMenu = document.querySelector('[data-profile-menu]');
  const notesMenu = document.querySelector('[data-notes-menu]');
  const mobileMenu = window.matchMedia('(max-width: 900px)');

  function setMenuOpen(open) {
    sidebar?.classList.toggle('open', open);
    scrim?.classList.toggle('show', open);
    menuBtn?.setAttribute('aria-expanded', String(open));
  }

  function closePopovers() {
    profileMenu?.classList.remove('open');
    notesMenu?.classList.remove('open');
  }

  menuBtn?.addEventListener('click', () => {
    setMenuOpen(!sidebar?.classList.contains('open'));
  });
  scrim?.addEventListener('click', () => setMenuOpen(false));
  sidebar?.querySelectorAll('a').forEach((link) => {
    link.addEventListener('click', () => {
      if (mobileMenu.matches) setMenuOpen(false);
    });
  });
  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && sidebar?.classList.contains('open')) setMenuOpen(false);
  });
  mobileMenu.addEventListener('change', (event) => {
    if (!event.matches) setMenuOpen(false);
  });
  profileBtn?.addEventListener('click', () => {
    notesMenu?.classList.remove('open');
    profileMenu?.classList.toggle('open');
  });
  notesBtn?.addEventListener('click', () => {
    profileMenu?.classList.remove('open');
    notesMenu?.classList.toggle('open');
  });
  document.addEventListener('click', (event) => {
    if (!event.target.closest('.popover-anchor')) closePopovers();
  });

  if (window.lucide) window.lucide.createIcons();

  // Potrero seleccionado, compartido entre módulos (calculadoras, decisiones, comparador...). Es solo una preferencia
  // de pantalla: el servidor siempre vuelve a comprobar que el potrero pertenezca a la cuenta.
  const userNode = document.getElementById('agro-user-id');
  const selKey = 'agroasesor.potrero.' + (userNode ? userNode.textContent.trim() : '');
  window.AgroSel = {
    get() {
      try {
        return window.localStorage.getItem(selKey) || '';
      } catch (error) {
        return '';
      }
    },
    set(id) {
      try {
        window.localStorage.setItem(selKey, String(id));
      } catch (error) {
        /* sin almacenamiento */
      }
    },
  };

  // Sesión vencida o cookies borradas: si el servidor avisa en una llamada de la página (fetch), se muestra un aviso y se
  // lleva a la persona al login en vez de dejar botones que no hacen nada.
  const fetchOriginal = window.fetch ? window.fetch.bind(window) : null;
  if (fetchOriginal) {
    window.fetch = async function (...args) {
      const respuesta = await fetchOriginal(...args);
      if (
        (respuesta.status === 401 || respuesta.status === 403) &&
        (respuesta.headers.get('content-type') || '').includes('json')
      ) {
        try {
          const datos = await respuesta.clone().json();
          if (datos && datos.codigo === 'sesion_vencida') {
            const aviso = document.createElement('p');
            aviso.className = 'callout session-expired';
            aviso.setAttribute('role', 'alert');
            aviso.textContent = datos.error + ' Te llevamos al inicio de sesión…';
            document.querySelector('.page-container')?.prepend(aviso);
            setTimeout(() => {
              window.location.assign((datos.login_url || '/login/') + '?vencida=1');
            }, 1800);
          }
        } catch (error) {
          /* respuesta sin JSON válido: se deja pasar */
        }
      }
      return respuesta;
    };
  }
})();
