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

})();
