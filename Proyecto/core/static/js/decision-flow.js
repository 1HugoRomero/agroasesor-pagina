(function () {
  const root = document.querySelector('[data-decision-flow]');
  if (!root) return;

  const panels = Array.from(root.querySelectorAll('[data-step-panel]'));
  const progress = Array.from(root.querySelectorAll('[data-progress-step]'));
  const form = root.querySelector('form');
  let currentStep = 1;

  if (form) {
    form.addEventListener('submit', (event) => {
      const panel = root.querySelector('[data-step-panel="' + currentStep + '"]');
      const invalid = panel && panel.querySelector(':invalid');
      if (invalid) {
        event.preventDefault();
        event.stopImmediatePropagation();
        invalid.reportValidity();
      }
    });
  }

  function showStep(step, shouldFocus) {
    currentStep = step;
    panels.forEach((panel) => {
      panel.hidden = Number(panel.dataset.stepPanel) !== step;
    });
    progress.forEach((item) => {
      const itemStep = Number(item.dataset.progressStep);
      item.classList.toggle('is-active', itemStep === step);
      item.classList.toggle('is-complete', itemStep < step);
      if (itemStep === step) item.setAttribute('aria-current', 'step');
      else item.removeAttribute('aria-current');
    });
    root.dataset.currentStep = String(step);
    const heading = root.querySelector('[data-step-panel="' + step + '"] h2');
    if (heading && shouldFocus) heading.focus({ preventScroll: true });
  }

  root.addEventListener('click', (event) => {
    const next = event.target.closest('[data-step-target]');
    if (next) {
      const targetStep = Number(next.dataset.stepTarget);
      if (targetStep > currentStep) {
        const panel = root.querySelector('[data-step-panel="' + currentStep + '"]');
        const invalid = panel && panel.querySelector(':invalid');
        if (invalid) {
          invalid.reportValidity();
          return;
        }
        const accepted = root.dispatchEvent(new CustomEvent('decision:before-next', {
          cancelable: true,
          detail: { from: currentStep, to: targetStep }
        }));
        if (!accepted) return;
      }
      showStep(targetStep, true);
      return;
    }

    if (event.target.closest('[data-new-calculation]')) {
      if (form) form.reset();
      root.dispatchEvent(new CustomEvent('decision:new'));
      showStep(1, true);
    }
  });

  root.addEventListener('decision:show-step', (event) => {
    showStep(Number(event.detail.step), true);
  });
  showStep(1);
})();
